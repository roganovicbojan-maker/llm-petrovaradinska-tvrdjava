# ADR 0001 · RAG zasnovan na citatima

Status: prihvaćeno.

Početni izazov je povezivanje odgovora sa proverljivim odlomcima u višejezičnoj i potencijalno protivrečnoj građi. Usvajamo RAG kao planiranu arhitekturu. Katalog izvora, tvrdnje i pravila provere razvijamo prvi. Ugovor između aplikacije i generatora omogućava kasnije dodavanje lokalnih i komercijalnih adaptera.

Kvalitet odgovora ocenjuje se na osnovu pronalaženja relevantnih izvora, tačnosti citata i predstavljanja neslaganja. Izbor generatora i indeksa sledi nakon formiranja i evaluacije pilot-korpusa.
