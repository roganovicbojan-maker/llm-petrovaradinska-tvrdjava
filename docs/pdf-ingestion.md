# Urednički pregled PDF izvora

Sledeće komande su za Git Bash u korenu repozitorijuma.

```bash
./.venv/Scripts/python.exe -m pip install -e ".[pdf]"
./.venv/Scripts/python.exe -m llm_petrovaradinska_tvrdjava.ingest extract tvrdjava/ \
  --output .pdf-review/extraction.json
```

Može se proslediti i jedan PDF. Izveštaj beleži izdanja po SHA-256 kontrolnom
zbiru, strane i odlomke, dokumente sa greškom i strane bez izdvojenog teksta.
Broj strane je redni broj PDF strane od 1. Štampana paginacija može da se
razlikuje. Isti PDF pod drugim imenom obrađuje se jednom u izveštaju.

Za skenirane strane koristi OCRmyPDF sa odgovarajućim jezičkim paketima za
konkretno izdanje. Na primer, sa instaliranim nemačkim paketom:

```bash
ocrmypdf --skip-text -l deu tvrdjava/sken.pdf .pdf-review/sken-ocr.pdf
./.venv/Scripts/python.exe -m llm_petrovaradinska_tvrdjava.ingest extract \
  .pdf-review/sken-ocr.pdf --ocr-input --output .pdf-review/sken.json
```

Proveri OCR prema slici originala. Odlomci su kandidati i pri višestubačnom
prelomu ili lošem OCR-u mogu imati pogrešan redosled reči. Program čuva
kontrolni zbir obrađenog PDF-a. Kod OCR kopije zabeleži vezu ka originalu
u uredničkim beleškama.

1. Izaberi `passage_id`, proveri da je PDF izdanje koje odgovara postojećem
   `source_id` i uporedi odlomak sa originalom.
2. Napiši predlog tvrdnje i sažetu parafrazu na osnovu tog odlomka.

```bash
./.venv/Scripts/python.exe -m llm_petrovaradinska_tvrdjava.ingest draft \
  .pdf-review/extraction.json --output .pdf-review/draft.json \
  --passage-id '<ID iz izveštaja>' --source-id '<ID izvora iz kataloga>' \
  --claim-id '<novi ID tvrdnje>' --topic '<tema>' --location 'Petrovaradin' \
  --statement '<predlog tvrdnje>' --paraphrase '<parafraza izvora>' \
  --locator '<štampana strana>'
```

3. Pregledaj izdanje, lokator, prava, formulaciju i ulogu dokaza. Nacrt nosi
   status `unknown`. Posle pregleda ručno prenesi odobreni zapis iz polja
   `claim` u katalog i, po potrebi, upiši njegov ID u odgovarajući dosije.
4. Pokreni `./.venv/Scripts/python.exe tools/validate_catalog.py` pre commita.

Folderi `tvrdjava/` i `.pdf-review/` su lokalni. Izveštaji o ekstrakciji mogu
sadržati pun tekst publikacija. Za javni katalog pripremi metapodatke i
parafraze koje mogu da se objave.
