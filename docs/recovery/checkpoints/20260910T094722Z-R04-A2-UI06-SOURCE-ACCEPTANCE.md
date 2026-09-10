# R04-20260910T094722Z-A2-UI06-SOURCE-ACCEPTANCE

- UTC: `2026-09-10T09:47:22Z`.
- Branch/worktree: `recovery/next-stabil-repair-completion` /
  `C:\\ai-lab-core-recovery`.
- Start local/remote: `bc847af5dc27754bb2f7636fd1cf0c688557b927`.
- Accepted frontend source/test:
  `48fbecae0a76edb25f60e9dd314bb8d65bfbae4b`.
- Saved synthetic backend source:
  `f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99`.
- Previous checkpoint:
  `docs/recovery/checkpoints/20260910T080134Z-R04-A2-UI06-REPAIR-HANDOFF.md`.

## Decyzja właściciela

Właściciel zaakceptował source/test `R04-A2-UI06` wyłącznie dla potwierdzonego
błędu `DocumentsController`. Nie zaakceptował analogicznego ryzyka
`ClientsController`, fizycznego Web, całego A2, R04 ani R16. Stan:
`UI06 SOURCE_ACCEPTED@48fbecae0a76edb25f60e9dd314bb8d65bfbae4b / NOT_DEPLOYED`.
Android pozostaje `DEFERRED_BY_OWNER / NOT_TESTED`.

## Bramka obserwacji przed startem

Sprawdzono bieżące instrukcje dostępnej powierzchni przeglądarkowej oraz
dostępne formalne mechanizmy uprawnień. Instrukcje opisują lokalne testy Web,
ale nie wskazują allowlist/approval override dla wcześniej odrzuconego originu
`http://127.0.0.1:18005`. Nie powtórzono odrzuconego dostępu i nie użyto innego
hosta/portu, alternatywnego browsera, raw CDP, proxy ani Computer Use.
`AUTOMATED_ALLOWED` nie zostało ustanowione.

Właściciel nie potwierdził w tej sesji obecności i gotowości przy komputerze;
samo zlecenie jawnie nie stanowi takiego potwierdzenia. `OWNER_OPERATED` nie
zostało ustanowione. Zgodnie z bramką nie uruchomiono kontenerów A2, serwera
Web, przeglądarki ani monitora. Nie wykonano stop/start backendu, mutacji lub
nowego odczytu syntetycznej DB. Testy aplikacyjne: `NOT_RUN`, ponieważ
zaakceptowany source/test nie był zmieniany.

Ograniczona kontrola tylko do odczytu o `2026-09-10T09:56:11Z` potwierdziła
trzy zachowane exact-name kontenery A2 z pełnymi ID i etykietami
`owner=R04-A2`, `run=20260909T131617Z`; każdy miał stan `exited`. Porty
`18004/18005` nie miały listenerów. Nie zmieniono ich stanu.

## Dokładna procedura jednego przyszłego A/B

Procedurę wolno rozpocząć wyłącznie po spełnieniu jednego warunku:

1. `AUTOMATED_ALLOWED`: formalnie dozwolone narzędzie potwierdza obsługę
   dokładnego originu `http://127.0.0.1:18005`; albo
2. `OWNER_OPERATED`: właściciel jawnie potwierdza bieżącą obecność i gotowość,
   Codex prowadzi komendy/monitoring, a właściciel wykonuje kroki UI i potwierdza
   widoczny rezultat.

Po spełnieniu warunku należy:

1. Ponownie zweryfikować remote recovery ref, pełne ID/owner/run, obrazy,
   mounty, sieci i stan trzech zachowanych kontenerów A2 oraz brak obcych
   listenerów `18004/18005`; przejść istniejącą bramkę zasobów.
2. Uruchomić wyłącznie zachowany PostgreSQL/backend/transport bez migracji i
   seeda; potwierdzić testową DB/head, dwa syntetyczne rekordy, dokument,
   wyłączone dispatchery, `/health` i backend source
   `f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99`.
3. Uruchomić Web wyłącznie z zachowanej kopii source
   `48fbecae0a76edb25f60e9dd314bb8d65bfbae4b`, z testowym API
   `http://127.0.0.1:18004` i osobnym profilem/sesją.
4. Scenariusz A: przy zatrzymanym dokładnym backendzie wejść po UI do listy
   dokumentów; wymagać właściwego komunikatu bez wewnętrznego wyjątku. Uruchomić
   ten sam backend, użyć `Spróbuj ponownie` i wymagać poprawnego załadowania
   listy bez duplikatu i bez żądania mutującego.
5. Scenariusz B: przy załadowanej liście zatrzymać ten sam backend, wywołać
   ponowny odczyt/retry i wymagać właściwego komunikatu bez wewnętrznego
   wyjątku. Uruchomić backend, użyć `Spróbuj ponownie` i wymagać odzyskania
   listy bez duplikatu i bez żądania mutującego.
6. Skorelować każdy krok z ekranem, bounded HTTP i read-only stanem syntetycznej
   DB. Zatrzymać wyłącznie własny Web i trzy zweryfikowane kontenery; zachować
   dowody i potwierdzić wolne porty.

## Status i STOP

- R04-A2 UI06: `SOURCE_ACCEPTED / WEB_NOT_VERIFIED /
  WAITING_ALLOWED_UI_OR_OWNER_SESSION`;
- R04: `IN_PROGRESS`;
- R03: `WAITING_APPROVAL / WAITING_ESCROW_DECISION`;
- W-02: `WAITING_OWNER_VISUAL_EVIDENCE`;
- Android: `DEFERRED_BY_OWNER / NOT_TESTED`;
- deployment/release/produkcja/modele/escrow/R05–R24: `NOT_RUN`.

Jeden następny bezpieczny krok: właściciel potwierdza bieżącą gotowość do
`OWNER_OPERATED` albo zostaje udostępniony formalnie dozwolony mechanizm dla
dokładnego originu; dopiero wtedy osobna sesja wykonuje powyższe A/B. STOP.
