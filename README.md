# LLM Petrovaradinska tvrđava

Osnova za javno dostupan sistem znanja o Petrovaradinu i Petrovaradinskoj tvrđavi. Prva verzija sadrži validiran katalog izvora i tvrdnji i HTTP proveru rada servisa. Katalog je prazan dok bibliografski podaci ne prođu proveru.

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
