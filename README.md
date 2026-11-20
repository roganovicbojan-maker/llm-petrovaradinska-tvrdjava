# LLM Petrovaradinska tvrđava

Osnova za javno dostupan sistem znanja o Petrovaradinu i Petrovaradinskoj tvrđavi. Projekat ima validiran katalog, HTTP API i pregled istorijskih navoda po izvorima.

## Instalacija u PowerShell-u

Iz korena repozitorijuma, uz instaliran **Python 3.12**. Ako ga Windows launcher ne pronalazi, u prvoj komandi zamenite `py -3.12` punom putanjom uz operator `&`, na primer `& "C:\putanja\do\Python312\python.exe" -m venv .venv`. Pozivi preko pune putanje do interpretera rade i kada PowerShell blokira aktivaciju okruženja.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m uvicorn llm_petrovaradinska_tvrdjava.api:app --host 127.0.0.1 --port 8000
```

Ako `.env` već postoji, preskočite kopiranje. U drugom PowerShell prozoru pokrenite `Invoke-RestMethod http://127.0.0.1:8000/health`. Očekivani JSON je `{"status":"ok","version":"0.1.0"}`.

## PyCharm

1. Otvorite koren repozitorijuma. Napravite `.venv` prema prethodnom postupku.
2. U **Settings → Project → Python Interpreter** izaberite postojeći interpreter `.venv\Scripts\python.exe`.
3. U **Run → Edit Configurations** dodajte **Python** konfiguraciju. Za **Module name** unesite `uvicorn`, za **Parameters** unesite `llm_petrovaradinska_tvrdjava.api:app --host 127.0.0.1 --port 8000`, a za **Working directory** postavite koren repozitorijuma.
4. Pokrenite konfiguraciju i otvorite [health endpoint](http://127.0.0.1:8000/health).

## Demo za portfolio

Otvorite **/reviews/petrovaradin-1716** nakon pokretanja aplikacije. Dosije prikazuje
datum i mesto iz srpske, turske i mađarske literature, a procene artiljerije
prikazuje po izvoru, uz lokator, posrednika i stanje uredničke provere.
Strukturirani podaci su dostupni na **/api/v1/reviews/petrovaradin-1716**.

> A source review tool for comparing historical accounts, tracing citations to
> their origins, and preserving conflicting figures with their context.

U PyCharm terminalu koji koristi Git Bash, iz korena repozitorijuma:

```bash
./.venv/Scripts/python.exe -m uvicorn llm_petrovaradinska_tvrdjava.api:app --host 127.0.0.1 --port 8000
```

Otvorite [dosije o bici 1716.](http://127.0.0.1:8000/reviews/petrovaradin-1716).

Otvorite [pregled i pretragu dosijea](http://127.0.0.1:8000/reviews). Pored bitke,
pregled sadrži dosije o [gradnji tvrđave 1753–1754.](http://127.0.0.1:8000/reviews/petrovaradin-gradnja-1753-1754).
Pretraga vraća navode sa lokatorima i posrednim izvorima. Isti rezultati su
dostupni preko `GET /api/v1/review-search?q=...`. Pretraga je leksička i
predstavlja osnovu za kasnije generisanje odgovora iz pronađene građe.

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
./.venv/Scripts/python.exe -m uvicorn llm_petrovaradinska_tvrdjava.api:app
```

Umesto `export` možete upisati `FORTRESS_OLLAMA_MODEL=qwen3:4b` u `.env`.
Ollama mora da sluša na `127.0.0.1:11434`. JSON API prihvata
`POST /api/v1/answers` sa telom `{"question":"Šta je predloženo za 1754?"}`.

Predložena demo pitanja:

- Šta je predloženo za 1754?
- Koje procene broja topova postoje za 1716?
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

Vlasnik projekta treba da odluči o licenci koda i metapodataka. Status prava nad svakim istorijskim izvorom beleži se posebno.
