# R26 krok 2 — D-43 operator PASS, Qdrant snapshot HTTP 500

- Operation ID: `R26-STEP2-D43-20260929T165100Z`
- Source HEAD wejściowy: `0097f74d3162da26d16889478c9d9419a4f01712`
- Product source: `67b867ee279fe0bf7617c05b7d61fff0b337cab3`
- Helper source: `10cb95971dcf288d8c0459355400cb144682db96`
- OutputRoot: `C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-R26-STEP2-D43-20260929T165100Z`
- Status: `R26_STEP2_IN_PROGRESS / FINAL_CONSOLIDATED_K1 / D43_QDRANT_SNAPSHOT_CREATE_HTTP_500_AFTER_ARTIFACT`

## Operator i preflight

LOCAL_ONLY operator zastąpił PowerShell `-join` przez `[string]::Join` i użył
tej samej funkcji read-only production preflight w `ValidateOnly` i `Execute`.
Windows PowerShell 5.1 przeszedł parser, testy `100/24/7`, helper contract,
alias audit `20/60/0` oraz AST audit:

- `command_parameter_join_count=0`;
- `binary_join_operator_count=0`;
- `OPERATOR_JOIN_BINDING_AUDIT_PASS`;
- `D43_EXACT_OPERATOR_VALIDATE_ONLY_PASS`.

Operator ma `51575` B i SHA-256
`4B4DE563CEB7A32B6A791B56DA8019BD4B85F0E2739969D32748EDEC0880E658`.
Jego dokładne bajty zachowano jako `operator.ps1` w OutputRoot. Rzeczywisty
preflight potwierdził Qdrant ID, volume `qdrant_storage`, readiness `200`,
kolekcje `57/157`, DB `r25_external_scope_20260927`, brak `scheduled_date`,
produkt `1.0.2+42`, exact artefakty `+43`, fixture/active backup/Supervisor `0`.

## Jedyny UAC i wynik

Jeden UAC D-43 został zaakceptowany; PID `23032` zakończył się kodem `1`.
Faza toolset zainstalowała wyłącznie helper:

- przed: `60203C42C6971F518B9260A581C40F0A09CECD1C38E089ECEF4E64FB9B37A704`;
- po: `28B84E792C511C7EAC2BEEDAC52E013BD0A1115F239A7E4202BCFA708AAFCD06`;
- runner bez zmiany:
  `6CFFA1EC2CE8242EFD541B931B3E68790FD0FD36F3EC9F4871721356D6A542B6`.

Direct proof zatrzymał się na pierwszej kolekcji:

- stage: `SNAPSHOT_CREATE:ai_lab_document_chunks`;
- exception: `System.Net.WebException`;
- odpowiedź: HTTP `500`;
- komunikat: `Serwer zdalny zwrócił błąd: (500) Wewnętrzny błąd serwera.`;
- pole `code=Serwer` jest błędną klasyfikacją tekstu wyjątku, nie kodem Qdrant;
- staging inventory przed cleanupem zawierał snapshot `348404224` B i plik
  checksum `64` B.

Zgodnie z D-43 nie wykonano retry ani drugiego UAC. Pełny RecoveryPointV2,
migracja, backend/startup, Web/Windows/Android `+43` i live smoke są `NOT_RUN`.

## Rozliczenie skutków

- `pending_mutation=false`;
- `product_mutation_started=false`;
- helper container residue `0`;
- staging residue `0`;
- proof checkpoint absent;
- Qdrant przywrócony: ten sam ID, running, readiness `200`, restart `0`, ten sam
  obraz/referencja/polityka/volume, kolekcje `57/157`, aliasy `0/0`;
- DB `r25_external_scope_20260927`, `scheduled_date` absent;
- backend ID `2e6e9e04aac2728ac84fed38078cb6e5628620525b83c848f850332b6b879e42`;
- startup manifest SHA-256
  `A86582B48A854D963F61327F139A27160057B1004AFB1B394613D0DC28E39AE8`;
- Web/Windows/Android pozostają `1.0.2+42`;
- active backup `0`, fixture `0`, Supervisor `0/0`.

## Materialny K1 i następny krok

Materialny K1 to `D43_QDRANT_SNAPSHOT_CREATE_HTTP_500_AFTER_ARTIFACT`.
Przyczyna odpowiedzi 500 nie została ustalona w tym oknie. Następny krok
wymaga osobnej decyzji na bounded diagnostykę opartą na zachowanym runtime
evidence; nie wolno ponawiać proofu ani UAC w D-43. R04 pozostaje wstrzymane,
D-22 pozostaje `NOT_RUN`.

Canonical footer: R26 krok 1 `ACCEPTED / OWNER_CONFIRMED`; R26 krok 2
`IN_PROGRESS / FINAL_CONSOLIDATED_K1`; R25 `ACCEPTED`; R04 `IN_PROGRESS /
WSTRZYMANE`; D-22 `NOT_RUN`.
