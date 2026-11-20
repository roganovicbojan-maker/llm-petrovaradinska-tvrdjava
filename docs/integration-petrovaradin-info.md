# Buduća integracija sa Petrovaradin.info

- **Zaseban backend API.** Servis bi izlagao ugovor pod `/api/v1`, sa jasnim odgovorima o dostupnosti dokaza i strukturiranim citatima. Integracija može ići preko proxy-ja sajta ili direktno uz ograničen CORS.
- **Ugrađeni chat.** Interfejs na sajtu prikazivao bi odgovor, bitna neslaganja i citate. Korisnik bi birao srpsku latinicu ili ćirilicu, uz čuvanje originalnog pisma u označenim citatima.
- **Otvaranje izvora.** Svaki citat imao bi identifikator izvora i lokator poput stranice ili folija. Koristio bi direktnu legalnu vezu do zapisa ili odlomka kad je dostupna. Kod ograničene građe prikazao bi bibliografiju i signaturu.
- **Stručna provera.** Administrativni interfejs bi omogućio urednicima pregled odlomaka, ocenu tvrdnji i beleženje potpisa, datuma i istorije izmena. Uredničke operacije zahtevaju autentifikaciju i odgovarajuću ulogu.
- **Keširanje i zaštita.** Keš treba vezati za jezik, pismo, verziju korpusa i ugovora odgovora. Ograničiti učestalost zahteva, dužinu ulaza i trošak generisanja. Čuvati ključeve na serveru i tretirati tekst iz izvora kao podatke i kada sadrži uputstva. Ograničiti pristup sadržaju i logovima prema pravima i nameni.

Ovo su smernice za buduću integraciju. Implementirane rute i uslovi za javno pokretanje navedeni su u [arhitekturi](architecture.md).
