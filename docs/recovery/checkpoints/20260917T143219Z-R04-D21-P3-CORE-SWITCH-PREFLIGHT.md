# Checkpoint R04 / D-21 / P3 — core backend switch preflight

- UTC: `2026-09-17T14:32:19Z`
- start local/tracking/remote:
  `ca6a1f51cc378cb032a375c39f0ef1811dcce3bb`
- OP_ID: `R04-D21-P3-CORE-SWITCH-20260917T141404Z`
- selected source: `0ee0ea50943578e6e552aae23ce1688595ddc262`
- selected tree: `4ccbc8922051401da1422be0d08f271476c3bab6`
- inactive override source commit: `f5cc96f70c9689d07cb18d1734cf4cc664f308b0`
- result: `CORE_SWITCH_PREFLIGHT_READY / WAITING_OWNER_WINDOW / NO_CUTOVER`

## Decyzja właściciela i punkt danych

Właściciel przyjął ograniczony dowód punktu
`E:\ai-lab-backup\20260917T082022Z`, manifest SHA-256
`2759D684710FB857DBCD0D985B5C480857122E3B139B9DDC362BFF4903895597`,
jako `ROLLBACK_POINT_DATA_EVIDENCE_ACCEPTED_WITH_RECORDED_LIMITATIONS`.
Odbiór zachowuje `COMPONENT_WINDOWS_RECORDED_NON_TRANSACTIONAL`, brak pełnych
owner/run labels, niezatwierdzony historyczny pull/run `alpine:3.20`, pierwszy
niedostarczony transfer tmpfs oraz brak pełnego host/VHD/model/profile/escrow
recovery. Nie wykonano ponownego backupu ani restore.

## Bieżący preflight

- Recovery jest clean; local, tracking i remote wskazują startowy SHA.
- Oryginalny worktree zachowuje `203/203` wpisy: brak missing/hash/size drift,
  `6 modified + 197 untracked`, staged `0`.
- Cały `C:\ai-lab-core\backend` ma 1,473 pliki / 24,624,213 B oraz aggregate
  SHA-256 `72E30A2810F3B52782463917E7439BA9E090A9D42962EA0D4493505B169316F3`.
  Nie jest bieżącym mountem runtime; nie znaleziono obcego procesu wykonującego
  ten katalog. Jest zwykłym katalogiem, nie reparse pointem.
- Backend pozostaje pełnym ID
  `9d9b46c530412e48562b5427a0586b08c1e919ff293ec2cbd1489faffc98615a`,
  image `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`,
  `/app=C:/ai-lab-core/build/deploy-main-483f9bf8/backend`,
  `/data=C:/ai-lab-core/data`, port `127.0.0.1:8000`, network
  `ai-lab-network`, restart `unless-stopped`.
- Pozostałe pięć kontenerów jest uruchomionych z dotychczasowymi pełnymi ID;
  żaden nie montuje recovery/WIP. Public Gateway i Web odpowiadają `200`,
  publiczne `/control` i `/control/health` odpowiadają `404`.
- Supervisor `8787` i Private Gateway `8788` są nieobecne. Public Gateway
  `8789` pozostaje przy PID `41784`. Niczego nie uruchomiono ani zatrzymano.
- Junction nadal jest dokładnie `C:\ai-lab-core\data -> D:\ai-lab-data`;
  D: ma 917,943,300,096 B wolnego miejsca.
- Zasoby punktowe przeszły bramkę: Windows available 7,860,002,816 B;
  commit reserve 39,148,441,600 B; Docker/WSL available 15,775,703,040 B;
  swap użyty 0 B.
- PostgreSQL READ ONLY potwierdził schema
  `followup_assistant_chat_history_20260829`, Administrator readiness `1/1`,
  brak aktywnego backup/import/restore oraz zastane pending `18/16/1`.
  Wybrana znormalizowana projekcja kolejki jest identyczna z odczytem z
  2026-09-16, ale cała delta treści po component windows pozostaje
  `DELTA_NOT_FULLY_OBSERVED`.

## Nieaktywny payload i konfiguracja

Chroniony root lokalny:
`C:\ai-lab-core-staging\recovery\R04_D21_P2_20260915T212340Z\p3-core-switch-20260917T141404Z`.

- Payload `backend/`: 592 pliki / 5,061,238 B; Git blob mismatches `0`;
  aggregate SHA-256
  `7A65EDFC8E18B4B1B592A5DDEB1EBFA5C2CA85762260299157E7132AEE48B055`.
- Kanoniczne archiwum source: 5,539,840 B; SHA-256
  `3D5A52C6DF18018B446205C8EAD30EB209C04D4A3EE097D1E3DFCF59130612DA`.
- Pierwsza próba z CRLF miała blob mismatches i została zachowana jako
  `rejected-crlf-*`; nie jest kandydatem.
- Dockerfile, requirements, migracje i locki backendu nie różnią się względem
  obrazu/main dla wybranego zakresu. Startup z flagami false używa wyłącznie
  read-only readiness i nie uruchamia reconcilerów/dispatcherów.
- Override SHA-256
  `F99BABA92A72DFA366367470181AB1BF9DEC19D71ADBD2CBF1632F0B74DE4E86`
  przeszedł `docker compose config --no-interpolate` w Compose v5.5.1. Pełny
  render nie został utrwalony. Zanonimizowane podsumowanie ma SHA-256
  `73BF672F4C2167A2DFEE37A121FAD5162074378FB82F86EC7B420CC21496B90D`.
- Wynik: exact image + `pull_policy: never`, `/app` read-only z docelowego
  rootu i `/data` bez zmian, oba bindy z `create_host_path=false`, ten sam
  port/sieć/restart/logging oraz 11 zgodnych niesekretnych flag.
- Plan operacji ma SHA-256
  `8F5691A5504FE01213C97502D20B2517FF172A641092629413FD08F64FE31E78`.

## Rollback i jawne ryzyko

Stary deploy-root pozostaje nietknięty. Aktualny snapshot ma 831 plików /
7,472,004 B, aggregate
`EC77BCEB8A481EA2F869E4747BA60FDAA9E6738969E153490471F5CD776F40EA`:
578 ścieżek main oraz 253 wygenerowane `.pyc`, bez brakujących ścieżek main.
Historyczny override `36355C93...436E8` plus nowy lokalny pin obrazu
`7ECE19FC...CE845` daje zweryfikowany stary `/app`, `/data`, port, sieć i obraz.
Ten rollback przywraca również legacy flags: Vision/KB/KB-vector/Advanced/
Assistant V2 true, document preparation false; stary kod nie daje nowych
gwarancji seed/reconciler. Powrót nie odtwarza danych i nie jest BASE_ONLY.

## Skutki i STOP

Nie zmieniono instalacji, runtime, kontenerów, tasków, danych, junctionu,
harmonogramów, backupu ani produkcyjnego override. Wykonano wyłącznie odczyty,
przygotowanie lokalnego payloadu/planów i bezskutkowe `compose config`.

Faza B wymaga bieżącego potwierdzenia właściciela dokładnie dla powyższego
`OP_ID`, payloadu, override, przerwy i ryzyka rollbacku. Do tego czasu:
`WAITING_OWNER_WINDOW / NO_CUTOVER`. Po potwierdzeniu obowiązuje jeszcze krótki
finalny drift check; materialny drift unieważnia zgodę przed mutacją.
