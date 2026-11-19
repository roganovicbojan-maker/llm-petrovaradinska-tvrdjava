# ADR 0002 · Verzije kataloga i HTTP API-ja

Status: prihvaćeno.

Početni katalog je jedan JSON dokument sa `schema_version: 1`. Pydantic i komandni validator proveravaju pojedinačne zapise i veze između njih. Ovaj format omogućava pregled promena u Git-u i jednostavan početak rada. Višekorisničko uređivanje bi zahtevalo kasnije skladište i istoriju izmena.

Operativni `/health` ostaje izvan verzionisanog javnog API-ja. Javni ugovor počinje od `/api/v1`, a verzija paketa i revizija šeme kataloga imaju zasebne namene.
