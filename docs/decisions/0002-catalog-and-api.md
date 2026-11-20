# ADR 0002 · Verzije kataloga i HTTP API-ja

Status: prihvaćeno.

Početni katalog uveden je kao jedan JSON dokument sa `schema_version: 1`. Od verzije 2 katalog koristi listu dokaza sa ulogama i graf deklarisanog porekla izvora. Pravila i prelazak opisani su u [README-u kataloga](../../data/catalog/README.md).

Operativni `/health` ostaje izvan verzionisanog javnog API-ja. Javni ugovor počinje od `/api/v1`, a verzija paketa i revizija šeme kataloga imaju zasebne namene.
