import argparse
import re
import sys
from hashlib import file_digest
from importlib import import_module
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from .catalog import load_catalog
from .models import Catalog, Claim, EvidenceLink, Place, Record, Text

MAX_WORDS = 140


class Passage(Record):
    passage_id: Text
    page: Annotated[int, Field(ge=1)]
    text: Text


class ExtractedPdf(Record):
    filename: Text
    sha256: str
    page_count: int
    pages_without_text: list[int]
    transcription: Literal["unverified", "unverified_ocr"]
    passages: list[Passage]


class ExtractionBatch(Record):
    documents: list[ExtractedPdf]
    failures: dict[str, str]


class ClaimDraft(Record):
    review_required: Literal[True] = True
    filename: Text
    pdf_sha256: str
    passage_id: Text
    pdf_page: int
    claim: Claim


def extract_pdf(path: Path, *, ocr_input: bool = False) -> ExtractedPdf:
    pypdf = import_module("pypdf")
    # The file supplied to the CLI is the edition identified by the checksum.
    with path.open("rb") as stream:
        digest = file_digest(stream, "sha256").hexdigest()
        stream.seek(0)
        reader = pypdf.PdfReader(stream)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDF needs a readable local copy")
        passages = []
        pages_without_text = []
        for page_no, page in enumerate(reader.pages, start=1):
            text = page.extract_text(extraction_mode="layout") or ""
            blocks = re.split(r"\n[ \t]*\n", text)
            page_passages = 0
            for block in blocks:
                words = block.split()
                for start in range(0, len(words), MAX_WORDS):
                    page_passages += 1
                    passages.append(
                        Passage(
                            passage_id=f"{digest}:{page_no}:{page_passages}",
                            page=page_no,
                            text=" ".join(words[start : start + MAX_WORDS]),
                        )
                    )
            if not page_passages:
                pages_without_text.append(page_no)
        return ExtractedPdf(
            filename=path.name,
            sha256=digest,
            page_count=len(reader.pages),
            pages_without_text=pages_without_text,
            transcription="unverified_ocr" if ocr_input else "unverified",
            passages=passages,
        )


def extract_batch(input_path: Path, *, ocr_input: bool) -> ExtractionBatch:
    if input_path.is_dir():
        paths = sorted(
            p for p in input_path.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"
        )
    else:
        paths = [input_path] if input_path.is_file() and input_path.suffix.lower() == ".pdf" else []
    if not paths:
        raise ValueError(f"No PDFs found in {input_path}")

    pypdf = import_module("pypdf")
    documents = []
    failures = {}
    seen = set()
    for path in paths:
        try:
            document = extract_pdf(path, ocr_input=ocr_input)
        except (OSError, ValueError, pypdf.errors.PyPdfError) as error:
            failures[path.name] = str(error)
            continue
        if document.sha256 not in seen:
            documents.append(document)
            seen.add(document.sha256)
    return ExtractionBatch(documents=documents, failures=failures)


def draft_claim(
    batch: ExtractionBatch,
    catalog: Catalog,
    *,
    passage_id: str,
    source_id: str,
    claim_id: str,
    topic: str,
    location: str,
    statement: str,
    paraphrase: str,
    locator: str | None,
) -> ClaimDraft:
    # Selection and historical interpretation require editorial input.
    for document in batch.documents:
        for passage in document.passages:
            if passage.passage_id == passage_id:
                claim = Claim(
                    claim_id=claim_id,
                    text=statement,
                    topic=topic,
                    location=Place(modern_name=location),
                    status="unknown",
                    evidence=[
                        EvidenceLink(
                            source_id=source_id,
                            locator_kind="page",
                            locator=locator or f"PDF page {passage.page}",
                            passage_kind="paraphrase",
                            passage=paraphrase,
                            transcription=document.transcription,
                            role="supports",
                        )
                    ],
                )
                Catalog(
                    schema_version=catalog.schema_version,
                    sources=catalog.sources,
                    claims=[*catalog.claims, claim],
                    dossiers=catalog.dossiers,
                )
                return ClaimDraft(
                    filename=document.filename,
                    pdf_sha256=document.sha256,
                    passage_id=passage.passage_id,
                    pdf_page=passage.page,
                    claim=claim,
                )
    raise ValueError("Passage ID is absent from the extraction batch")


def write_new(record: Record, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(record.model_dump_json(indent=2, exclude_none=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare PDFs and claim drafts for local review.")
    commands = parser.add_subparsers(dest="command", required=True)
    extract = commands.add_parser("extract", help="Extract a PDF or a directory of PDFs.")
    extract.add_argument("input", type=Path)
    extract.add_argument("--output", type=Path, required=True)
    extract.add_argument(
        "--ocr-input", action="store_true", help="Input PDF already went through OCR."
    )
    draft = commands.add_parser("draft", help="Prepare one claim from an editor-selected passage.")
    draft.add_argument("batch", type=Path)
    draft.add_argument("--catalog", type=Path)
    draft.add_argument("--output", type=Path, required=True)
    for name in (
        "passage-id",
        "source-id",
        "claim-id",
        "topic",
        "location",
        "statement",
        "paraphrase",
    ):
        draft.add_argument(f"--{name}", required=True)
    draft.add_argument("--locator", help="Printed page reference if it differs from the PDF page.")
    args = parser.parse_args(argv)

    try:
        if args.command == "extract":
            batch = extract_batch(args.input, ocr_input=args.ocr_input)
            write_new(batch, args.output)
            needs_review = sum(len(pdf.pages_without_text) for pdf in batch.documents)
            print(
                f"{len(batch.documents)} PDFs; {needs_review} pages without text; "
                f"{len(batch.failures)} failed. Review {args.output}."
            )
            return int(bool(batch.failures))
        batch = ExtractionBatch.model_validate_json(args.batch.read_bytes())
        claim = draft_claim(
            batch,
            load_catalog(args.catalog),
            passage_id=args.passage_id,
            source_id=args.source_id,
            claim_id=args.claim_id,
            topic=args.topic,
            location=args.location,
            statement=args.statement,
            paraphrase=args.paraphrase,
            locator=args.locator,
        )
        write_new(claim, args.output)
        print(f"Unreviewed draft saved to {args.output}.")
        return 0
    except ModuleNotFoundError as error:
        if error.name != "pypdf":
            raise
        print('PDF extraction requires: python -m pip install -e ".[pdf]"', file=sys.stderr)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
