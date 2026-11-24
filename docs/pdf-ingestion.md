# PDF ingestion and editorial review

Run the following commands from the repository root in Git Bash.

```bash
./.venv/Scripts/python.exe -m pip install -e ".[pdf]"
./.venv/Scripts/python.exe -m llm_petrovaradinska_tvrdjava.ingest extract tvrdjava/ \
  --output .pdf-review/extraction.json
```

The input can also be a single PDF. The report records filenames, SHA-256 checksums, pages, passages, failed documents, and pages without extracted text. PDF page numbering starts at 1 and may differ from printed page labels. Files with identical content appear once.

For scans, use OCRmyPDF with language packs appropriate to the edition. This example assumes the German language pack is installed.

```bash
ocrmypdf --skip-text -l deu tvrdjava/scan.pdf .pdf-review/scan-ocr.pdf
./.venv/Scripts/python.exe -m llm_petrovaradinska_tvrdjava.ingest extract \
  .pdf-review/scan-ocr.pdf --ocr-input --output .pdf-review/scan.json
```

Check OCR against page images. Multi-column layout and low-quality OCR can scramble reading order. The checksum identifies the processed input. For an OCR derivative, record its relationship to the original in the editorial notes.

1. Select a `passage_id` and verify that the edition matches the existing `source_id`.
2. Draft a claim and a short paraphrase supported by the selected passage.

```bash
./.venv/Scripts/python.exe -m llm_petrovaradinska_tvrdjava.ingest draft \
  .pdf-review/extraction.json --output .pdf-review/draft.json \
  --passage-id '<ID from extraction report>' --source-id '<catalog source ID>' \
  --claim-id '<new claim ID>' --topic '<topic>' --location 'Petrovaradin' \
  --statement '<draft claim>' --paraphrase '<source paraphrase>' \
  --locator '<printed page number>'
```

3. Review the edition, locator, rights, wording, and evidence role. Drafts are marked `unknown`. After editorial review, copy the approved `claim` field into the catalog and add its ID to the relevant dossier as needed.
4. Run `./.venv/Scripts/python.exe tools/validate_catalog.py` before committing.

The `tvrdjava/` and `.pdf-review/` directories are local. Extraction reports may contain complete publications. Prepare publishable metadata and paraphrases for the public catalog.
