# R26 krok 2 — D-39 toolset PASS, backup PostgreSQL stream K1

## Wynik

- decision: `D-39`;
- operation ID: `R26-STEP2-D39-20260928T192821Z`;
- OutputRoot:
  `C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-R26-STEP2-D39-20260928T192821Z`;
- jeden UAC: `ACCEPTED / CONSUMED`;
- faza A toolsetu: `PASS / PRESERVED`;
- backup: `FAILED / INCOMPLETE_CHECKPOINT_CLEANED`;
- produkt: `NOT_STARTED`;
- `pending_mutation=false`;
- status: `R26_STEP2_IN_PROGRESS / FINAL_CONSOLIDATED_K1 /
  D39_TOOLSET_PASS_BACKUP_POSTGRES_STREAM_FAILED`.

## Zamrożony operator

- path przed wykonaniem:
  `C:\ai-lab-core-recovery\.r26-d39-20260928T192821Z.ps1`;
- bytes: `49328`;
- SHA-256:
  `81EE917E5342D5B1D8BFCEEBA2A53BFA1A03645E0B15BB5D8B037F02B2533A91`;
- parser PS5.1: PASS;
- alias collision audit: `OPERATOR_ALIAS_COLLISION_AUDIT_PASS`;
- funkcje: `10`;
- jawne nazwy poleceń: `45`;
- kolizje: `0`;
- `h -> Get-History`: potwierdzone;
- definicje/wywołania `H`: `0/0`;
- nierozwiązane statycznie były wyłącznie dwie funkcje ładowane z
  `startup-runtime.ps1`: `Read-StartupSetManifest` i
  `Test-StartupSetManifest`.

Pełny `-ValidateOnly` zwrócił
`D39_EXACT_OPERATOR_VALIDATE_ONLY_PASS` z produkcyjnymi, Docker, DB, backup i
UAC writes równymi `0`. Przed PASS wykrył lokalnie jeden błąd PS5.1
`Nullable[Int64].Value`; operator został poprawiony, a parser, alias audit i
ValidateOnly wykonano od początku. Po PASS bajty i ścieżka nie były zmieniane;
ten sam SHA sprawdzono ponownie bezpośrednio przed UAC.

## Bounded preflight

- local/tracking/remote:
  `f465cadc2a160ea4a2f29cd4bdd661069bf63563`;
- tracked worktree: clean; jedynym oczekiwanym untracked plikiem był zamrożony
  LOCAL_ONLY operator;
- runner exact preimage, helper absent, validator exact;
- staging residue `0`, pending mutation `false`, active backup `0`, Supervisor
  `0/0`;
- DB `r25_external_scope_20260927`, `scheduled_date` absent;
- sześć kontenerów zgodnych z manifestem i running;
- startup manifest valid;
- `F:\dump` writable, `490183430144` wolnych bajtów, checkpoint absent;
- Web/Windows/Android `+43` exact candidate hashes;
- Android: dokładnie `emulator-5554`, fizyczne urządzenia `0`;
- fixture `0`.

Pierwsza wersja lokalnego formattera preflightu użyła nieistniejącego pola
`name` zamiast `container_name`. Nie wykonała mutacji; read-only bramkę
dokończono z kanonicznym polem.

## Toolset PASS

Zainstalowano dokładnie:

- `backup-production.ps1`: `39671` B,
  `22B7F64BDEB425F9AF4D8F2481762FEFD3A0D3D73FB02039848684C88CF06900`;
- `invoke-qdrant-backup-helper.ps1`: `6335` B,
  `39907FB26283D257F153BCB92E4E6754899FE20895FDBB12850451703AC0F644`.

Post-check wykonał parser in-process bez child PowerShell. Exact hashe,
ACL/owner, reparse, validator i brak staging residue przeszły. Journal zapisał
`TOOLSET PASS / IN_PROCESS_PARSER_NO_CHILD`. Zgodnie z D-39 poprawny toolset
pozostaje zainstalowany po niezależnym K1 backupu.

## Konkretny K1 backupu

RecoveryPointV2 rozpoczął zapis do
`F:\dump\20260928T193121Z`, lecz zatrzymał się w pierwszym artefakcie,
strumieniowanym `postgres.dump`, błędem:

`Exception calling "CopyTo" with "1" argument(s): "Potok został zakończony."`

Stan failu:

- niekompletny `postgres.dump`: `490077104` B;
- `backup-manifest.json`: absent;
- następne artefakty: nieutworzone;
- Qdrant helper container: nieutworzony;
- primary Qdrant ID bez zmian:
  `daa3b0b86b748aa3a52052dac08bfde499cf19ad61600a1325e09061a5451fae`;
- kolekcje bez zmian:
  `ai_lab_document_chunks`, `ai_lab_knowledge_base_chunks`;
- sześć kontenerów running i z niezmienionymi ID;
- active backup `0`, Supervisor `0/0`.

Po potwierdzeniu braku manifestu i aktywnego konsumenta usunięto wyłącznie
operation-owned niekompletny checkpoint. Końcowo
`F:\dump\20260928T193121Z` jest absent. Nie usunięto żadnego historycznego
backupu.

## Produkt i residue

- migracja: `NOT_RUN`;
- DB: `r25_external_scope_20260927`;
- `scheduled_date`: absent;
- backend ID bez zmian:
  `2e6e9e04aac2728ac84fed38078cb6e5628620525b83c848f850332b6b879e42`;
- startup manifest bez zmian:
  `A86582B48A854D963F61327F139A27160057B1004AFB1B394613D0DC28E39AE8`;
- Web/Windows/Android: nadal `1.0.2+42`;
- bulk revoke smoke: `NOT_RUN`;
- inspection date smoke: `NOT_RUN`;
- fixture/residue: `0` przez brak wejścia do fazy produktu;
- active backup `0`, Supervisor `0/0`, pending mutation `false`.

Product source pozostaje
`67b867ee279fe0bf7617c05b7d61fff0b337cab3`, a toolset source
`7dff894b09facc9e8763296a2bf7ea5e03117535`. Jedyny UAC D-39 jest
skonsumowany; nie wykonano retry ani drugiego elevation.

---
R25: `ACCEPTED` · R26 krok 1: `ACCEPTED / OWNER_CONFIRMED` · R26 krok 2:
`IN_PROGRESS / FINAL_CONSOLIDATED_K1` · R04: `IN_PROGRESS / WSTRZYMANE` ·
D-22: `NOT_RUN`
