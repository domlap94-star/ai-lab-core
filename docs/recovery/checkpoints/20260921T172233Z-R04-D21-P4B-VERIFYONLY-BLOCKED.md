# R04 / D-21 / P4-B — Host identity VerifyOnly blocked

UTC zapisu: `2026-09-21T17:22:33Z`

Status:

- `P4B_STAGEA_HOST_IDENTITY_CONTINUITY_SOURCE_AND_OFFLINE_ACCEPTED /
  NOT_DEPLOYED`;
- `P4B_VERIFYONLY_BLOCKED_LOCAL_PREREQUISITE_GET_FILE_HASH_UNAVAILABLE /
  NO_TASK_READS / NO_MUTATION`;
- `STAGE_B_BLOCKED / NOT_AUTHORIZED`.

## Jedyna próba

Approval ID:
`R04-D21-P4B-HOST-IDENTITY-VERIFYONLY-20260921T171832Z`.

Przed próbą local/tracking/remote były zgodne na
`7b8eac77b4955345b1e1a5378eadb69033c8245f`, worktree był czysty, `vfy1` i
`out` nie istniały. Top hashe `4/4`, package bindings `8/8` i lokalny I/O
przeszły. Użyto niezmienionej recepty
`FD8DB2C5491E7A8835CC01734A8A902D67F606F29A4436A68A16096A44CBBCFE`,
indeksu `0BC434D97847836CD54C2D847B23795614F684633013DFDCDA1F76AF7C966CDD`
i package operation ID `R04-D21-P4B-HOST22-NUP-20260920T200422Z`.

Jedno niepodniesione Windows PowerShell 5.1 `-NoProfile`, `Mode=VerifyOnly`,
bez `AcknowledgeOneTimeMutation`, zakończyło się:

- UTC `2026-09-21T17:19:57.7792425Z–17:19:58.7371776Z`;
- elapsed `958` ms, timeout `false`, exit `1`;
- stdout `0` B, SHA-256
  `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`;
- stderr `653` B, SHA-256
  `9C578DD42036CC78A9087DAC1E6E635D66ABFB3D331267F15BD2685FA3D3F205`;
- `result.json=ABSENT`, `out=ABSENT`.

`Get-P4BSha256` wywołał nierozpoznany `Get-FileHash` w
`Test-P4BPackageIndex`, linia recepty `241`. Błąd nastąpił w lokalnej
walidacji plików przed `New-RealP4BNarrowUpdateBoundary/ObserveTask`.
Task Scheduler reads/writes/starts, journal, mutation/pending mutation,
changed roles, warm runs, rollback, Docker/HTTP/CIM/TCP/SQL, UAC i install
wynoszą `0`. Własny proces PID `14752` zakończył się; kill nie był potrzebny.
Nie wykonano retry i jednorazowa zgoda jest zużyta.

LOCAL_ONLY pod
`C:\Users\domai\AppData\Local\Temp\P4B-HOST-ID-01\vfy1`:

- summary `1386` B / SHA-256
  `2FF083F60445C012A0BABF030B8781A123D7FA0D611936873E00D20F9D0E7D39`;
- evidence index `1144` B / SHA-256
  `934C384550B5C37383D16C297A8C2CE571347554CD37F313CF8D87BF12CB5957`.

## Jedna rekomendowana decyzja

Zatwierdzić wyłącznie minimalną SOURCE/OFFLINE zgodność recepty z wymaganym
Windows PowerShell 5.1: samowystarczalne obliczanie SHA-256 pliku bez zależności
od dostępności cmdletu `Get-FileHash`, celowany test i review. Dopiero poprawne
bajty mogłyby otrzymać nową, osobną jednorazową zgodę VerifyOnly. Nie jest to
zgoda na retry, live read, Stage B, UAC, instalację ani operacje hosta.

Review D-23 pozostaje `2/2`; nie szukano K2/K3. Installed run01, Host
disabled/no-trigger, warm `0/2`, Private `0` i Supervisor
`INTENTIONALLY_STOPPED` pozostają bez zmian. HTTP i świeży six-container
preflight są `NOT_RUN`.

## ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT

Przed oceną i kolejnym promptem przeczytaj §0, ANTI_EXCESSIVE_WORK, aktywną
kartę i ten checkpoint na pełnym opublikowanym SHA. Zachowaj odbiory. K0/K1:
K1 — exact VerifyOnly nie może przejść obowiązkowej lokalnej integralności w
wymaganym PS 5.1, ponieważ `Get-FileHash` jest niedostępny; dowód stderr
`9C578DD4...F205`, exit `1`, bez Task Scheduler reads. K2/K3 nie ruszać i nie
blokować nimi odbioru. Następny krok: jedna decyzja o minimalnej poprawce
SOURCE/OFFLINE i review; brak zgody na ponowienie lub operacje hosta.
