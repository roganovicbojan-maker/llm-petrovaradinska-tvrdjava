# Arhitektura

Početna osnova koristi Python 3.12, FastAPI i Pydantic. Uređeni JSON katalog ima verziju šeme i povezuje dokaze sa stabilnim identifikatorima izvora. Validator proverava strukturu, jedinstvenost identifikatora, reference, uslove stručne provere i upotrebu izvora. Stručnu tačnost ocenjuje urednik pregledom originalne građe.

## Planirani tok RAG sistema

1. Urednik evidentira izvor, izdanje, poreklo, prava i dostupnost. Građa se čuva izvan Git-a.
2. Unos priprema odlomke sa stabilnim identifikatorom izvora, preciznim lokatorom, jezikom i oznakama OCR-a i prevoda.
3. Pretraga vraća relevantne odlomke, tvrdnje i veze ka suprotnim iskazima. Pilot-dosijei služe za procenu pretrage po jeziku, terminima i istorijskim nazivima.
4. Aplikacija prosleđuje odlomke ugovorenom interfejsu za generisanje. Adapteri za lokalne i komercijalne modele mogu da koriste isti ugovor.
5. Aplikacija proverava da li citati odgovaraju stvarno pronađenim odlomcima. Pravila prikaza čuvaju neslaganje i naglašavaju nedovoljan dokaz.

Katalog i pravila citiranja treba da ostanu nezavisni od modela, adaptera za pretragu i skladišta. Izbor indeksa i modela sledi nakon rada sa građom iz pilot-dosijea.

## HTTP

`GET /health` je operativna provera procesa i vraća status i verziju paketa, koja se vidi i u OpenAPI metapodacima. Budući javni API koristiće prefiks `/api/v1`. Verzija kataloga je odvojena od verzije paketa i ugovora HTTP API-ja.
