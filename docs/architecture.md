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

Opcioni režim za POST /api/v1/answers gradi vektorski indeks u memoriji
pri pokretanju procesa, sa jednim vektorom po ID-ju navoda. Tekst navoda,
odlomci i kontekst šalju se Ollami putem /api/embed. Pretraga poredi kosinusnu
sličnost sa svim vektorima, odbacuje rezultate ispod praga i spaja dva ranga
metodom Reciprocal Rank Fusion. Linkovi, statusi i uloge dokaza ostaju u
katalogu. Prag FORTRESS_EMBEDDING_MIN_SIMILARITY je početna postavka (0,65)
i treba ga oceniti za konkretan embedding model.

Bez FORTRESS_EMBEDDING_MODEL koristi se leksički režim. Ako izgradnja indeksa
ne uspe, zabeleži se greška i proces koristi leksičku pretragu do ponovnog
pokretanja. Ako ne uspe upit prema modelu, taj zahtev koristi leksičku
pretragu. GET /ready prikazuje spremnost indeksa kada je opcija uključena.
Uspešni odgovori označavaju putanju u X-Fortress-Retrieval. Pregled dosijea
i GET /api/v1/review-search i dalje koriste leksičku pretragu. Leksički
regresioni testovi u CI-ju rade bez Ollame.

Generator dobija pronađene navode sa ulogama dokaza. Svaki iskaz u odgovoru ima
jedan izvor (source_id) i ID-jeve potkrepljujućih navoda (evidence_ids). Provera
odbija reference van pretrage i brojeve (uključujući uobičajene srpske oblike
rečima) kojih nema u citiranim dokazima tog izvora. Odvojeni poziv Ollami
ocenjuje da li dokazi podržavaju ceo iskaz, pripisivanje i ograde, kao i da li je iskaz relevantan za pitanje. Ako provera
ne prođe, odgovor se odbija. API označava rezultat kao model_checked.
Kada se koristi prilagođeni generator bez verifikatora, prihvataju se samo
iskazi koji se poklapaju sa tekstom citiranog kataloga (catalog_excerpt).
Automatske provere mogu pogrešiti. Istorijski status i stručna provera prikazuju
se prema katalogu.

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

Plan za širu građu obuhvata OCR, indeksiranje odlomaka iz primarne građe i nezavisnu stručnu evaluaciju.
Za prava nad kodom, metapodacima i građom vidi [pravila za podatke](../data/README.md).
