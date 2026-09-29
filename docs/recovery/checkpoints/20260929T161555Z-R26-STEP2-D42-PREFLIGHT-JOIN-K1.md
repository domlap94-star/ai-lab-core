# R26 krok 2 — D-42 source PASS, operator preflight K1

## Wynik użytkowy

- decision: `D-42`;
- source fix: `PASS / PUBLIC / NOT_DEPLOYED`;
- operation ID: `R26-STEP2-D42-20260929T160600Z`;
- OutputRoot:
  `C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-R26-STEP2-D42-20260929T160600Z`;
- pierwsza próba UAC: `CANCELLED_BEFORE_CREATEPROCESS / NO_MUTATION`;
- jedna późniejsza, jawnie ponownie autoryzowana próba: `ACCEPTED / CONSUMED`;
- elevated PID: `25092`, exit `1`;
- runtime mutation: `NOT_STARTED`;
- status: `R26_STEP2_IN_PROGRESS / FINAL_CONSOLIDATED_K1 /
  D42_OPERATOR_PREFLIGHT_JOIN_BINDING_BEFORE_MUTATION`.

## Source i testy

Produkcjny helper nie używa już Go-template. Wszystkie odczyty kontenera
Qdrant korzystają z jednego `docker inspect qdrant`, osobnych stdout/stderr,
`ConvertFrom-Json`, dokładnie jednego obiektu oraz jednoznacznego mountu
`Destination=/qdrant/storage`, `Type=volume`, niepustego `Name`.

Source opublikowano jako:
`10cb95971dcf288d8c0459355400cb144682db96`.

Nowy helper source:

- bytes: `30968`;
- SHA-256:
  `28B84E792C511C7EAC2BEEDAC52E013BD0A1115F239A7E4202BCFA708AAFCD06`.

Niezmieniony runner:
`6CFFA1EC2CE8242EFD541B931B3E68790FD0FD36F3EC9F4871721356D6A542B6`.

Testy:

- helper i runner parser PS5.1: PASS;
- static no-template gate: PASS;
- inspect JSON, mount negatives, inspect negatives i state transitions:
  `100` asercji PASS;
- PostgreSQL transport: `24/24` PASS;
- selection: `7/7` PASS;
- helper contract i nested snapshot path: PASS;
- `git diff --check`, secret scan i business-content scan: PASS;
- publiczny readback helper object: PASS.

## Operator i ValidateOnly

Exact operator został zachowany jako `operator.ps1` w OutputRoot:

- bytes: `46560`;
- SHA-256:
  `4844C7AB57AD94D4F8589C1B797F2784FD847D3DB8A3B48C2589814ED9AF263A`;
- parser PS5.1: PASS;
- alias audit: `18` funkcji, `57` poleceń, `0` kolizji;
- ValidateOnly: `D42_EXACT_OPERATOR_VALIDATE_ONLY_PASS`;
- testy ValidateOnly: `100/24/7` oraz helper contract PASS;
- produkcyjne writes w ValidateOnly: `0`.

Bounded preflight przed UAC potwierdził exact HEAD/toolset/runtime, Qdrant
`ready=200`, restart `0`, kolekcje `57/157`, residue `0`, DB R25 bez
`scheduled_date`, active backup `0`, Supervisor `0/0`, targety `+42`, exact
kandydatów `+43` oraz pojedynczy emulator.

## Pierwsza próba i nowa autoryzacja

Pierwszy monit został anulowany przed `CreateProcess`. Readback potwierdził
brak OutputRoot, checkpointu, proof root i jakiejkolwiek mutacji. Właściciel
następnie jawnie polecił ponowić UAC i kontynuować; ta nowa zgoda nie była
automatycznym retry.

Drugi monit został zaakceptowany. Elevated PID `25092` utworzył wyłącznie
mały journal/result i zatrzymał się w pierwszym etapie `PREFLIGHT`.

## Materialny K1

Operator zawierał wyrażenie łączące wynik wrappera Docker przed parsowaniem
JSON. W Windows PowerShell 5.1 zapis:

`NsR26Docker @('inspect','qdrant') -join "`n"`

został związany tak, jakby `-join` był nazwanym parametrem funkcji
`NsR26Docker`, zamiast operatorem zastosowanym do jej wyniku. Dokładny błąd:

`A parameter cannot be found that matches parameter name 'join'.`

Poprawna granica wymaga najpierw zamknięcia wywołania funkcji, a dopiero potem
operatora `-join`. Nie poprawiono operatora ani nie wykonano kolejnego UAC,
ponieważ zaakceptowana próba D-42 została skonsumowana.

Journal/result:

- phase: `PREFLIGHT -> FAILED`;
- `mutation_started=false`;
- `pending_mutation=false`;
- `product_mutation_started=false`;
- preimage files: `0`;
- direct Qdrant result: absent;
- checkpoint: absent.

## Końcowy readback

- aktywny runner:
  `6CFFA1EC2CE8242EFD541B931B3E68790FD0FD36F3EC9F4871721356D6A542B6`;
- aktywny helper nadal D-41:
  `60203C42C6971F518B9260A581C40F0A09CECD1C38E089ECEF4E64FB9B37A704`;
- Qdrant ID:
  `daa3b0b86b748aa3a52052dac08bfde499cf19ad61600a1325e09061a5451fae`;
- Qdrant running, restart count `0`, readiness `200`;
- kolekcje: `57/157`, indexed `0/0`, aliasy `0/0`;
- helper container residue: `0`;
- staging residue: `0`;
- checkpoint/proof artifact: absent;
- active backup: `0`;
- DB: `r25_external_scope_20260927`, `scheduled_date` absent;
- backend ID nadal
  `2e6e9e04aac2728ac84fed38078cb6e5628620525b83c848f850332b6b879e42`;
- startup manifest nadal
  `A86582B48A854D963F61327F139A27160057B1004AFB1B394613D0DC28E39AE8`;
- Web nadal `44A53C0BF821D31279294D017D4D12673A822AAFFBAAF301B8C90900E4A115EE`;
- Windows nadal
  `C0DE8E94FF2BF4280ACDC2C1FA0B65701CB3A19D3269226F6C2BDB664C134CD5`;
- Android nadal `1.0.2+42`;
- fixture: `0`;
- Supervisor: `0/0`.

Direct Qdrant proof, RecoveryPointV2, migracja, backend/Web/Windows/Android
`+43` i live smoke są `NOT_RUN`.

---
R25: `ACCEPTED` · R26 krok 1: `ACCEPTED / OWNER_CONFIRMED` · R26 krok 2:
`IN_PROGRESS / FINAL_CONSOLIDATED_K1` · R04: `IN_PROGRESS / WSTRZYMANE` ·
D-22: `NOT_RUN`
