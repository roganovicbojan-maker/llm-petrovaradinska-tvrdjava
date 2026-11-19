# Katalog izvora i tvrdnji

`catalog.json` je početni katalog verzije 1, trenutno bez bibliografskih zapisa i tvrdnji. Puni ugovor je definisan Pydantic modelima u `src/llm_petrovaradinska_tvrdjava/models.py`.

- Svaki element `sources` ima trajan `source_id`. Za jezik koristite oznaku BCP 47 gde postoji, a za pismo oznaku ISO 15924 kada je primenljiva.
- Svaki element `claims` ima trajan `claim_id` i primarni odlomak `evidence`. Potvrđujuće i protivrečne odlomke vodite preko posebnih veza. Za `locator_kind: unavailable` u `locator` upišite razlog.
- Kod datuma granice su numerički rastuće u deklarisanoj skali. Kod BP opsega manji broj znači manju starost. Konvenciju i metod datovanja opišite u izrazu ili napomenama izvora. Ako istorijski datum ne može verno da se predstavi godinom ili rasponom, sačuvajte originalni izraz i kalendar.
- Kod spornih procena zabeležite posebnu tvrdnju po proceni, uz jedinicu, obuhvaćenu grupu i opis brojanja.
- Uvezena građa može dobiti status `unknown` dok čeka proveru. Stručna ocena zahteva recenzenta, datum, procenu pouzdanosti i pregled korišćenih odlomaka u originalu.
