# Katalog izvora i tvrdnji

[catalog.json](../../src/llm_petrovaradinska_tvrdjava/review_data/catalog.json) koristi verziju 2. Ugovor je definisan Pydantic modelima u
`src/llm_petrovaradinska_tvrdjava/models.py`. Za JSON Schema pokrenite
`validate-catalog --json-schema > catalog.schema.json`.

- `derived_from` sadrži sve poznate neposredne izvore na kojima zapis počiva.
  Svaki ID mora da postoji, a ciklusi se odbijaju.
- Za `confirmed` su potrebna dva potvrđujuća odlomka čiji skupovi korenskih izvora
  nemaju presek i čiji su koreni prihvatljivi kao dokaz. Ova provera koristi
  upisano poreklo. Urednik i dalje proverava da li je poreklo potpuno i da li
  odlomci podržavaju tvrdnju.
- `evidence` je lista sa ulogama `supports`, `contradicts` i `context`.
  Za nedostupan lokator upišite razlog. Odlomci procenjenih tvrdnji moraju biti
  provereni u originalu. Kod protivurečnih procena zabeležite zaseban podatak
  za svaku procenu, uz jedinicu, grupu i definiciju brojanja.
- Za jezik koristite važeće oznake BCP 47, a za pismo registrovanu oznaku ISO 15924.
  Za citate iz izvora sa nepoznatim ili zaštićenim pravima validator dopušta do
  15 reči po odlomku. Urednik proverava pravo objavljivanja i ukupan korišćeni obim.
- Čuvajte izvorni datum i kalendar. Numeričke granice se odnose na deklarisani
  kalendar. Normalizovane gregorijanske granice koriste `YYYY`, `YYYY-MM` ili
  `YYYY-MM-DD` uz jednu deklarisanu preciznost. Za konverzije navedite metod i
  korišćenu konvenciju. Urednik unosi konverziju, a validator proverava oblik,
  postojanje datuma i redosled granica.
- Arheološka starost ide u `dating` uz metod, jedinicu i grešku kada je objavljena.
  `ka` označava hiljade godina, `cal_years_bp` kalibrisane godine pre sadašnjosti.
  Datovan sediment i artefakt imaju različit dokazni domet.
- `Place` podržava istorijske varijante imena, Wikidata QID i par koordinata.

## Prelazak sa verzije 1

Pretvorite jedini `evidence` u listu. Odlomcima iz `supporting_evidence` i
`contradicting_evidence` dodelite odgovarajuću ulogu, a preostalom primarnom odlomku
ulogu prema sadržaju. Isti odlomak evidentirajte jednom. Datum bez numeričke granice
sačuvajte uz potkrepljenu normalizaciju ili kao izvorni izraz uz arheološko datovanje.
Zatim postavite `schema_version` na `2` i pokrenite validator.

## Dosijei

Katalog je jedini zapis izvora i navoda. Elementi `dossiers` povezuju naslove
i sazetke dosijea sa `claim_ids`. Za prikaz pojedinacnog navoda koristi se prvi
dokaz i njegov opcioni `via`; ostali dokazi pripadaju urednickom katalogu.
`editorial_review` belezi urednicku proveru prenosa navoda.
Strucnu potvrdu tvrdnje odvojeno beleze `review` i `status`.
Migrirani navodi bez dokumentovane provere imaju status `unknown`.
