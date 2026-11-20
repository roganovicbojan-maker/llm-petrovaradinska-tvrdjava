from pathlib import Path

import pytest
from pydantic import ValidationError

from llm_petrovaradinska_tvrdjava.catalog import load_catalog
from llm_petrovaradinska_tvrdjava.ingest import (
    ExtractedPdf,
    ExtractionBatch,
    Passage,
    draft_claim,
    extract_batch,
    write_new,
)


def test_pdf_extraction_preserves_page_and_flags_blank_page(tmp_path: Path) -> None:
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    name = pypdf.generic.NameObject
    dictionary = pypdf.generic.DictionaryObject
    page[name("/Resources")] = dictionary(
        {
            name("/Font"): dictionary(
                {
                    name("/F1"): dictionary(
                        {
                            name("/Type"): name("/Font"),
                            name("/Subtype"): name("/Type1"),
                            name("/BaseFont"): name("/Helvetica"),
                        }
                    ),
                }
            ),
        }
    )
    stream = pypdf.generic.DecodedStreamObject()
    stream.set_data(b"BT /F1 10 Tf 20 100 Td (Synthetic page text.) Tj ET")
    page[name("/Contents")] = stream
    path = tmp_path / "sample.pdf"
    writer.write(path)
    (tmp_path / "invalid.pdf").write_bytes(b"not a PDF")
    (tmp_path / "duplicate.PDF").write_bytes(path.read_bytes())

    batch = extract_batch(tmp_path, ocr_input=True)

    assert set(batch.failures) == {"invalid.pdf"}
    assert len(batch.documents) == 1
    doc = batch.documents[0]
    assert doc.pages_without_text == [2]
    assert doc.transcription == "unverified_ocr"
    assert doc.passages == [
        Passage(passage_id=f"{doc.sha256}:1:1", page=1, text="Synthetic page text.")
    ]


def test_draft_requires_editor_and_preserves_provenance(tmp_path: Path) -> None:
    batch = ExtractionBatch(
        documents=[
            ExtractedPdf(
                filename="digitized.pdf",
                sha256="a" * 64,
                page_count=4,
                pages_without_text=[],
                transcription="unverified_ocr",
                passages=[Passage(passage_id="p1", page=4, text="Extracted text")],
            )
        ],
        failures={},
    )
    catalog = load_catalog()
    options = {
        "passage_id": "p1",
        "source_id": "eugene-report-56",
        "claim_id": "draft-ingest-fixture",
        "topic": "Probe",
        "location": "Petrovaradin",
        "statement": "Draft statement.",
        "paraphrase": "Editor supplied this paraphrase.",
        "locator": None,
    }
    result = draft_claim(batch, catalog, **options)
    assert result.review_required
    assert result.pdf_page == 4
    assert result.claim.status == "unknown"
    assert result.claim.evidence[0].locator == "PDF page 4"
    assert result.claim.evidence[0].transcription == "unverified_ocr"
    assert result.claim.evidence[0].passage != "Extracted text"
    assert all(c.claim_id != "draft-ingest-fixture" for c in catalog.claims)

    file = tmp_path / "draft.json"
    write_new(result, file)
    with pytest.raises(FileExistsError):
        write_new(result, file)
    with pytest.raises(ValidationError, match="unknown source"):
        draft_claim(batch, catalog, **(options | {"source_id": "unknown-source"}))
    with pytest.raises(ValueError, match="Passage ID"):
        draft_claim(batch, catalog, **(options | {"passage_id": "missing"}))


def test_cli_builds_local_review_files_without_mutating_catalog(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace

    from llm_petrovaradinska_tvrdjava import ingest

    inputs = tmp_path / "tvrdjava"
    inputs.mkdir()
    source = inputs / "source.pdf"
    source.write_bytes(b"synthetic backend input")

    text_page = SimpleNamespace(extract_text=lambda **_: "First paragraph.\n\nSecond paragraph.")
    blank_page = SimpleNamespace(extract_text=lambda **_: "")
    backend = SimpleNamespace(
        PdfReader=lambda _: SimpleNamespace(is_encrypted=False, pages=[text_page, blank_page]),
        errors=SimpleNamespace(PyPdfError=RuntimeError),
    )
    monkeypatch.setattr(ingest, "import_module", lambda _: backend)
    report = tmp_path / ".pdf-review" / "extraction.json"
    assert ingest.main(["extract", str(inputs), "--output", str(report)]) == 0
    assert "1 pages without text" in capsys.readouterr().out

    batch = ExtractionBatch.model_validate_json(report.read_bytes())
    assert [item.text for item in batch.documents[0].passages] == [
        "First paragraph.",
        "Second paragraph.",
    ]
    item = batch.documents[0].passages[0]
    output = tmp_path / ".pdf-review" / "draft.json"
    args = [
        "draft",
        str(report),
        "--output",
        str(output),
        "--passage-id",
        item.passage_id,
        "--source-id",
        "eugene-report-56",
        "--claim-id",
        "probe-draft-cli",
        "--topic",
        "Probe",
        "--location",
        "Petrovaradin",
        "--statement",
        "Draft claim.",
        "--paraphrase",
        "Reviewed paraphrase.",
        "--locator",
        "Printed page 56",
    ]
    assert ingest.main(args) == 0
    assert ingest.ClaimDraft.model_validate_json(output.read_bytes()).claim.evidence[0].locator == (
        "Printed page 56"
    )
    assert ingest.main(args) == 1
