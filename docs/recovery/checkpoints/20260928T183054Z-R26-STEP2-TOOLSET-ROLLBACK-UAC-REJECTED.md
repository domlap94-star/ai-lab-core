# R26 krok 2 — toolset exact rollback, drugi UAC formalnie odrzucony

## Wynik

- operation ID: `R26-STEP2-TOOLSET-DEPLOY-20260928T182203Z`;
- pierwszy UAC: `ACCEPTED`;
- faza A: `MUTATION_STARTED`;
- wynik fazy A: `PHASE_A_FAILED_ROLLED_BACK`;
- planowane resume: `R26-STEP2-TOOLSET-DEPLOY-RESUME-20260928T182916Z`;
- drugi UAC: `FORMALLY_REJECTED_BEFORE_CREATEPROCESS`;
- backup/migracja/deployment/live smoke: `NOT_RUN`;
- status: `R26_STEP2_IN_PROGRESS / CONSOLIDATED_K1 /
  PHASE_A_FAILED_ROLLED_BACK / SECOND_UAC_FORMALLY_REJECTED`.

## Preflight

- local/tracking/remote: `96328f72867dd36bf77fc1e0f7cebc65ca6f9f2f`;
- worktree przed operatorem: clean;
- runner source hotfix, helper source, parser PS5.1, 7/7 i helper contract: PASS;
- validator aktywny:
  `4CDC0D2043AEDA6B3722834878BE2FA27BA8BABA92D686C35FBF5D5392BA495D`;
- validator odpowiada dokładnie kanonicznemu blobowi publicznego repo; checkout
  `DE0F2FCD...01E4FB` różni się wyłącznie CRLF od aktywnego LF;
- Web/Windows/Android `+43`: exact hashes PASS;
- F:\dump: exists, writable, wystarczające miejsce;
- manifest valid, sześć kontenerów bez driftu, PostgreSQL healthy, `/health=200`;
- DB R25, `scheduled_date` absent, active backup `0`, Supervisor `0/0`, fixture `0`.

## Pierwsza próba i rollback

Faza A wystawiła do sibling staging dokładnie runner i helper, zachowała exact
runner preimage oraz `ABSENT_PREIMAGE` helpera, a następnie rozpoczęła mutację.
Post-check wykonywany przez zagnieżdżony child PS5.1 zgłosił:

`PS51_PARSE_FAILED:C:\ai-lab-core\operations\hardening\backup-production.ps1`

Transakcja wykonała rollback:

- runner po: `36724` B,
  `25BD1F12B237A603D2C19323C175E3220ECFA2E8B97FAB48B05D3DE3CCEB4DDE`;
- helper po: `ABSENT`;
- staging/replace residue: `0`;
- `pending_mutation=false`;
- checkpoint `F:\dump\20260928T182503Z`: absent.

## Poprawiona ścieżka i formalna blokada

Zagnieżdżony proces zastąpiono parserem oraz testem 7/7 wykonywanym w tym samym
PS5.1. Lokalny test zwrócił `PASS_IN_PROCESS_PS51_POSTCHECK`, a operator miał
parser PASS. Exact rollback przed resume został potwierdzony.

Mechanizm wykonawczy odrzucił drugi UAC przed `CreateProcess`, uznając, że
defekt lokalnego operatora nie spełnia warunku dodatkowego UAC. Nie wykonano
retry, obejścia ani alternatywnego elevation.

## Końcowy readback

- runner exact preimage, helper absent, staging `0`;
- oba planowane checkpointy absent;
- DB `r25_external_scope_20260927`;
- `scheduled_date` absent;
- backend ID
  `2e6e9e04aac2728ac84fed38078cb6e5628620525b83c848f850332b6b879e42`;
- startup manifest
  `A86582B48A854D963F61327F139A27160057B1004AFB1B394613D0DC28E39AE8`;
- active backup `0`;
- resume OutputRoot absent;
- Web/Windows/Android nadal `+42`.

---
R25: `ACCEPTED` · R26 krok 1: `ACCEPTED / OWNER_CONFIRMED` · R26 krok 2:
`IN_PROGRESS / CONSOLIDATED_K1` · R04: `IN_PROGRESS / WSTRZYMANE` · D-22:
`NOT_RUN`
