# LLM Petrovaradinska tvrđava

Osnova za javno dostupan sistem znanja o Petrovaradinu i Petrovaradinskoj tvrđavi. Projekat ima validiran katalog, HTTP API i pregled istorijskih navoda po izvorima.

## Portfolio quick start (English)

This Python/FastAPI project lets readers search five historical dossiers and inspect
source references, conflicting figures, and intermediary works such as translations or
later studies. The review UI and its tests run without credentials or a language model.

From the repository root, with Python 3.12 or later:

```bash
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# On Windows Git Bash use: source .venv/Scripts/activate
python -m pip install -e ".[dev]"
python -m pytest -q
python -m uvicorn llm_petrovaradinska_tvrdjava.api:create_app --factory
```

- [Search historical dossiers](http://127.0.0.1:8000/reviews?q=Peterwardein+1694).
- [Compare accounts of the 1716 battle](http://127.0.0.1:8000/reviews/petrovaradin-1716).
- [Open the API documentation](http://127.0.0.1:8000/docs).

Try searching for `topova 1716` and then `Koliko je stanovnika imao Petrovaradin 1716?`.
The second question has no supporting records in the current dossiers.

The optional Ollama adapter generates structured claims from retrieved records. The API
validates each evidence ID and checks that numeric tokens appear in the cited records. Historical
support is reviewed separately. The public dossiers are projected from the versioned catalog. See the [local model setup](#rag-odgovori-uz-lokalni-model).

## Instalacija u PowerShell-u

Iz korena repozitorijuma, uz instaliran **Python 3.12**. Ako ga Windows launcher ne pronalazi, u prvoj komandi zamenite `py -3.12` punom putanjom uz operator `&`, na primer `& "C:\putanja\do\Python312\python.exe" -m venv .venv`. Pozivi preko pune putanje do interpretera rade i kada PowerShell blokira aktivaciju okruženja.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m uvicorn llm_petrovaradinska_tvrdjava.api:create_app --factory --host 127.0.0.1 --port 8000
```

Ako `.env` već postoji, preskočite kopiranje. U drugom PowerShell prozoru pokrenite `Invoke-RestMethod http://127.0.0.1:8000/health`. Očekivani JSON je `{"status":"ok","version":"0.1.0"}`.

## PyCharm

1. Otvorite koren repozitorijuma. Napravite `.venv` prema prethodnom postupku.
2. U **Settings → Project → Python Interpreter** izaberite postojeći interpreter `.venv\Scripts\python.exe`.
3. U **Run → Edit Configurations** dodajte **Python** konfiguraciju. Za **Module name** unesite `uvicorn`, za **Parameters** unesite `llm_petrovaradinska_tvrdjava.api:create_app --factory --host 127.0.0.1 --port 8000`, a za **Working directory** postavite koren repozitorijuma.
4. Pokrenite konfiguraciju i otvorite [health endpoint](http://127.0.0.1:8000/health).

## Demo za portfolio

U PyCharm terminalu koji koristi Git Bash, iz korena repozitorijuma:

```bash
./.venv/Scripts/python.exe -m uvicorn llm_petrovaradinska_tvrdjava.api:create_app --factory --host 127.0.0.1 --port 8000
```

Otvorite [pregled i pretragu dosijea](http://127.0.0.1:8000/reviews).

| Dosije | Šta se može proveriti |
| --- | --- |
| [Paleolitski nalazi](http://127.0.0.1:8000/reviews/petrovaradin-paleolit) | Datovanje slojeva i granice zaključaka o kontinuitetu naseljavanja. |
| [Opsada 1694.](http://127.0.0.1:8000/reviews/petrovaradin-opsada-1694) | Habzburški plan, izdanje osmanske hronike i mađarski dnevnik preko prevoda. |
| [Bitka 1716.](http://127.0.0.1:8000/reviews/petrovaradin-1716) | Datum i mesto bitke i različite procene artiljerije. |
| [Gradnja 1753–1754.](http://127.0.0.1:8000/reviews/petrovaradin-gradnja-1753-1754) | Izvedeni i predloženi radovi i datovanje Beogradske kapije. |
| [Samostan Sv. Franje i vojna bolnica](http://127.0.0.1:8000/reviews/petrovaradin-samostan-sv-franje) | Faze gradnje i prenamena samostana i crkve. |

Leksička pretraga vraća navode sa lokatorima i posrednim izvorima preko
`GET /api/v1/review-search?q=...`. Strukturirani dosije je dostupan preko
`GET /api/v1/reviews/{dossier_id}`.

### RAG odgovori uz lokalni model

Na stranici `/reviews` polje **Pitanje o tvrđavi** koristi isti korpus kao pretraga.
Aplikacija pronalazi relevantne navode, prosleđuje ih lokalnom modelu i proverava
da li se svaki citat odnosi na neki od prosleđenih navoda. Stranica uz svaki iskaz
vezuje izvor i lokator. Provera identifikatora citata je strukturna.
Urednička provera i dalje je potrebna za ocenu istorijske tačnosti iskaza.

Instalirajte [Ollama](https://ollama.com/download), pokrenite ga i u Git Bash-u
preuzmite model sa podrškom za strukturirani izlaz:

```bash
ollama pull qwen3:4b
export FORTRESS_OLLAMA_MODEL=qwen3:4b
./.venv/Scripts/python.exe -m uvicorn llm_petrovaradinska_tvrdjava.api:create_app --factory
```

Umesto `export` možete upisati `FORTRESS_OLLAMA_MODEL=qwen3:4b` u `.env`.
Za drugi Ollama servis podesite FORTRESS_OLLAMA_BASE_URL i FORTRESS_OLLAMA_TIMEOUT.
Podrazumevano Ollama sluša na `127.0.0.1:11434`. JSON API prihvata
`POST /api/v1/answers` sa telom `{"question":"Šta je predloženo za 1754?"}`.

Predložena demo pitanja

- Kako je datovan paleolitski sloj 2b?
- Koji vremenski raspon nosi karta opsade 1694?
- Koje procene broja topova postoje za 1716?
- Šta je predloženo za 1754?
- Kada je vojna bolnica smeštena u samostan?
- Koliko je bilo stanovnika u Vinči 2024?

### Urednička provera

Provera se beleži uz pojedinačni navod. `verified` znači da je urednik proverio
kako je navod prenet i evidentiran. Za nepotpun kontekst ili otvoreno pitanje
koristite `needs_context`. Navod bez uredničke ocene ima oznaku „Čeka proveru“.
Ocena ne menja izvornu vrednost i nema uticaja na ostale navode.

Primer unosa u Git Bash-u:

```bash
./.venv/Scripts/python.exe tools/review_comparison.py artillery-nusretname \
  --verdict needs_context --reviewer "Ime urednika" --date 2026-11-19 \
  --note "Proveriti šta je obuhvaćeno brojem na fol. 315b."
```

Komanda upisuje ocenu u verzionisani JSON dosije. Posle unosa osvežite stranicu
i pregledajte izmenu u Git-u. Web prikaz i API služe za čitanje.

## Provere

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe tools/validate_catalog.py
```

Validator kao argument prima i putanju do drugog JSON kataloga. Testovi rade bez spoljnih API poziva nakon instalacije zavisnosti.

## Dokumentacija

- [Vizija](docs/vision.md)
- [Arhitektura](docs/architecture.md)
- [Istraživačka metodologija](docs/research-methodology.md)
- [Integracija sa Petrovaradin.info](docs/integration-petrovaradin-info.md)
- [Arhitektonske odluke](docs/decisions/)
- [Podaci i katalog](data/README.md)

## Licenca

Kod je pod [MIT licencom](LICENSE), a autorski metapodaci pod [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Prava nad istorijskom građom su opisana u [uputstvu za podatke](data/README.md).
