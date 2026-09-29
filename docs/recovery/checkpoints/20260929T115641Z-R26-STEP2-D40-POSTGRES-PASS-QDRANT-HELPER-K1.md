# R26 krok 2 — D-40 PostgreSQL PASS, Qdrant helper K1

## Wynik użytkowy

- decision: `D-40`;
- operation ID: `R26-STEP2-D40-20260929T113705Z`;
- OutputRoot:
  `C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-R26-STEP2-D40-20260929T113705Z`;
- jeden UAC: `ACCEPTED / CONSUMED`;
- runner: `PASS / INSTALLED / PRESERVED`;
- PostgreSQL binary transport: `PASS`;
- RecoveryPointV2: `FAILED / NO_FINAL_MANIFEST / INCOMPLETE_CHECKPOINT_CLEANED`;
- produkt R26 krok 2: `NOT_STARTED`;
- `pending_mutation=false`;
- status: `R26_STEP2_IN_PROGRESS / FINAL_CONSOLIDATED_K1 /
  D40_POSTGRES_STREAM_PASS_QDRANT_HELPER_FAILED_NO_DIAGNOSTIC`.

## Source i testy

Stary błąd D-39 wynikał z użycia `Stream.CopyTo` na binarnym stdout procesu:
Windows kończył anonimowy pipe kodem `109`, a wyjątek transportu przerywał
workflow przed rozliczeniem exit/stderr i walidacją archiwum.

Minimalny runner zastąpił `CopyTo` jawną pętlą binarną 1 MiB, dodał bounded
timeout, klasyfikację `109/232` wyłącznie jako EOF candidate, zawsze rozlicza
exit/stderr/bytes oraz używa `postgres.dump.partial`. Finalizacja następuje
dopiero po `pg_restore --list` i pełnym bezprodukcyjnym
`pg_restore --exit-on-error --no-owner --no-privileges --file=/dev/null`.

Testy Windows PowerShell 5.1:

- parser runnera: PASS;
- binary transport: `24` asercje PASS;
- runner selection: `7/7` PASS;
- Qdrant helper contract: PASS;
- `git diff --check`, secret scan i business-content scan: PASS.

Source runnera opublikowano jako:
`c90bef520ee20a93660f211df3c5eb6cbf2c701f`.

## Operator i preflight

- operator LOCAL_ONLY:
  `C:\ai-lab-core-recovery\.r26-d40-20260929T113705Z.ps1`;
- bytes: `48988`;
- SHA-256:
  `739EE916CA95670DE3F682CAE0D5F639EBCE024A1CE83BCAC1E1F29D66B97A27`;
- parser PS5.1: PASS;
- alias audit: `10` funkcji, `46` jawnych poleceń, `0` kolizji,
  `h -> Get-History`, definicje/wywołania `H`: `0/0`;
- ValidateOnly: `D40_EXACT_OPERATOR_VALIDATE_ONLY_PASS`;
- transport w ValidateOnly: `24` asercje;
- produkcyjne/Docker/DB/backup/UAC writes w ValidateOnly: `0`.

Bounded preflight potwierdził:

- local/tracking/remote:
  `c90bef520ee20a93660f211df3c5eb6cbf2c701f`;
- tracked worktree clean; jedynym untracked plikiem był zamrożony operator;
- runner preimage `39671` B / `22B7F64B...6900`;
- helper `6335` B / `39907FB2...644`;
- validator exact, startup manifest valid i approved;
- kontenery `6/6` exact/running;
- DB `r25_external_scope_20260927`, `scheduled_date` absent;
- active backup `0`, Supervisor `0/0`, fixture `0`;
- Web/Windows/Android `1.0.2+42` exact;
- kandydaci `1.0.2+43` exact;
- emulator `emulator-5554`;
- `F:\dump` writable, checkpoint absent, probe usunięty;
- wolne bajty na F: `490183430144`.

## Runner i PostgreSQL PASS

Po UAC zainstalowano wyłącznie runner:

- przed: `39671` B /
  `22B7F64BDEB425F9AF4D8F2481762FEFD3A0D3D73FB02039848684C88CF06900`;
- po: `48074` B /
  `228D0B88F1B9514CAB2C5B7C16E967516B23386CDAA6BB5ECB6133FB14E10AB6`.

Helper pozostał bez zmiany:
`39907FB26283D257F153BCB92E4E6754899FE20895FDBB12850451703AC0F644`.

Rzeczywisty capture PostgreSQL:

- `pg_dump exit_code=0`;
- stderr pusty;
- timeout `false`;
- pipe disposition `NONE`, HResult `null`;
- zapisane bajty: `490252061`;
- `pg_restore --list`: exit `0`; przy wczesnym zamknięciu stdin odczytano
  `2097152` B i poprawnie sklasyfikowano `109` jako
  `PIPE_EOF_CANDIDATE`, ale sukces pochodzi z exit `0` i pustego stderr;
- pełne `pg_restore --file=/dev/null`: exit `0`, odczytane `490252061` B,
  pipe `NONE`, stderr pusty;
- zwalidowany SHA-256 dumpu:
  `111A4B2D0F74441457BEFD26470F6FCD3EBDF13EB1985F18ADD361FB9130A648`.

Dowody transportu zostały zachowane w OutputRoot pod
`backup-failure-evidence`. Finalny checkpoint został później usunięty zgodnie
z fail-closed kontraktem, więc hash opisuje zwalidowane bajty przed cleanupem,
nie istniejący artefakt końcowy.

## Materialny K1 Qdrant

Po PostgreSQL PASS child
`C:\ai-lab-core\operations\hardening\invoke-qdrant-backup-helper.ps1`
zakończył się błędem. Granica runnera zachowała wyłącznie komunikat:

`BACKUP_FAILED_CLEANED:C:\ai-lab-core\operations\hardening\invoke-qdrant-backup-helper.ps1 : `

Wewnętrzny stage, exit i stderr helpera nie zostały zachowane. Nie ma więc
dowodu pozwalającego przypisać błąd do readiness, snapshotu, walidatora ani
innego konkretnego etapu. To jest bieżący K1:
`QDRANT_HELPER_FAILED_NO_DIAGNOSTIC`.

Nie wykonano retry ani drugiego UAC.

## Cleanup i końcowy readback

- finalny `backup-manifest.json`: absent;
- checkpoint `F:\dump\20260929T114005Z`: absent;
- staging `F:\dump\.next-stabil-qdrant-staging\20260929T114005Z`: absent;
- helper containers: `0`;
- główny Qdrant ID:
  `daa3b0b86b748aa3a52052dac08bfde499cf19ad61600a1325e09061a5451fae`;
- Qdrant: running, restart count `0`;
- `ai_lab_document_chunks`: `57` punktów, aliasy `0`;
- `ai_lab_knowledge_base_chunks`: `157` punktów, aliasy `0`;
- backend ID pozostał
  `2e6e9e04aac2728ac84fed38078cb6e5628620525b83c848f850332b6b879e42`;
- DB nadal `r25_external_scope_20260927`;
- `scheduled_date`: absent;
- startup manifest nadal
  `A86582B48A854D963F61327F139A27160057B1004AFB1B394613D0DC28E39AE8`;
- Web main nadal `44A53C0B...A115EE`;
- Windows executable nadal `C0DE8E94...34CD5`;
- Android nadal `1.0.2+42` na `emulator-5554`;
- migracja/backend replacement/Web/Windows/Android `+43`: `NOT_RUN`;
- bulk revoke i inspection date live smoke: `NOT_RUN`;
- fixture/residue: `0`;
- active backup: `0`;
- Supervisor process/listener: `0/0`;
- `pending_mutation=false`.

## Provenance i bramka

- product source:
  `67b867ee279fe0bf7617c05b7d61fff0b337cab3`;
- Qdrant helper source:
  `7dff894b09facc9e8763296a2bf7ea5e03117535`;
- PostgreSQL stream runner source:
  `c90bef520ee20a93660f211df3c5eb6cbf2c701f`.

Do dalszego wykonania potrzebna jest nowa, jawna operacja dopiero po zmianie,
która zachowa dokładny stage/exit/stderr child helpera i usunie wykazaną
przyczynę. Skonsumowanego D-40 nie wolno ponawiać.

---
R25: `ACCEPTED` · R26 krok 1: `ACCEPTED / OWNER_CONFIRMED` · R26 krok 2:
`IN_PROGRESS / FINAL_CONSOLIDATED_K1` · R04: `IN_PROGRESS / WSTRZYMANE` ·
D-22: `NOT_RUN`
