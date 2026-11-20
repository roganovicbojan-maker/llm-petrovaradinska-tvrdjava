# Arhitektura

Katalog v2 čuva izvore, tvrdnje, dokaze i njihove uloge, posrednike i uredničke
procene. Python 3.12, Pydantic i FastAPI projektuju jedan katalog u HTML i
javni JSON. Aplikacija validira i učitava katalog pri pokretanju. Izmene
kataloga se vide posle ponovnog pokretanja procesa.

## Implementirano

| Ruta | Namena |
| --- | --- |
| `GET /health` | Liveness procesa i verzija paketa. |
| `GET /ready` | Spremnost kataloga i podatak da li je generator konfigurisan. Provera ne kontaktira Ollama servis. |
| `GET /reviews`, `GET /reviews/{dossier_id}` | Pretraga i prikaz dosijea. |
| `GET /api/v1/review-search` | Do deset rangiranih navoda sa dokazima. |
| `GET /api/v1/reviews/{dossier_id}` | Dosije u JSON-u sa svim dokazima i ocenama iz kataloga. |
| `POST /api/v1/answers` | Opcioni generisani odgovor sa referencama iz pretrage. |
| `GET /docs` | OpenAPI dokumentacija. |

Leksička pretraga normalizuje latinicu, ćirilicu, dijakritike i zabeležene
istorijske i padežne varijante. Testni skup proverava očekivane ID-jeve i upite
bez odgovarajućih dokaza. `python tools/evaluate_retrieval.py` ispisuje
makro Recall@5, MRR@5 i udeo negativnih upita bez rezultata. Skup je regresioni
pilot nad postojećim dosijeima. Za ocenu istorijske relevantnosti na široj
građi potreban je nezavisno označen stručni korpus.

Generator dobija pronađene navode sa ulogama dokaza. Provera odgovora odbija
reference van pronađenog skupa i brojeve kojih nema u citiranim navodima.
Vrednost `verification: structural_only` označava obim automatske provere.
Urednik proverava da li odlomak podržava celu tvrdnju, da li zaključak prenosi
suprotne dokaze u kontekstu i da li su kalendar, izdanje i prevod odgovarajući.
Ocena i datum stručnog pregleda čuvaju se u katalogu. Nove istorijske ocene
nastaju pregledom građe.

## Pokretanje i opterećenje

Aplikaciju pokreni sa `uvicorn llm_petrovaradinska_tvrdjava.api:create_app --factory`.
Promenljive procesa imaju prednost nad `.env` fajlom. Iz razvojnog checkouta
aplikacija čita `.env` iz korena projekta. Instalirani paket koristi promenljive
procesa ili fajl zadat apsolutnom putanjom `FORTRESS_ENV_FILE`. Radni direktorijum
ne određuje koji se fajl čita.

| Podešavanje | Podrazumevano |
| --- | --- |
| `FORTRESS_REQUESTS_PER_MINUTE` | 120 zahteva u kliznom prozoru po procesu. `/health` i `/ready` su izuzeti. Prekoračenje vraća 429. |
| `FORTRESS_MAX_REQUEST_BYTES` | 4096 bajtova za telo zahteva ka generatoru. Veće telo vraća 413. Prijem tela ima rok od 10 sekundi. |
| `FORTRESS_MAX_CONCURRENT_GENERATIONS` | Jedna istovremena generacija po procesu. Zauzet model vraća 503 sa `Retry-After`. |
| `FORTRESS_OLLAMA_TIMEOUT` | 90 sekundi za mrežne operacije prema modelu. Nedostupan model vraća 503. Nevažeći izlaz vraća 502. |

Dnevnik zahteva beleži metod, status i trajanje. Operater prati 429, 502,
503 i kašnjenja, proverava katalog i Ollama servis, a po potrebi isključuje
generisanje uklanjanjem konfiguracije modela i ponovnim pokretanjem. Pre
javnog izlaganja postavi obrnuti proksi sa TLS-om, ograničenjem ukupnih
konekcija i veličine zahteva, te limitom po klijentu i zajedničkim budžetom
za sve procese. Za privatni API dodaj autentifikaciju. Limiti u aplikaciji
važe pojedinačno za svaki proces. Posle konfiguracije uradi probu opterećenja
i podesi nadzor, alarme i pravila za blokiranje zloupotrebe.

Plan za širu građu obuhvata OCR, hibridni indeks i nezavisnu stručnu evaluaciju.
Za prava nad kodom, metapodacima i građom vidi [pravila za podatke](../data/README.md).
