# R04 / D-21 / P4-B — USABLE-WARM Stage B configuration prepared

- UTC: `2026-09-24T07:15:56.7002666Z`
- Window decision ID: `R04-D21-P4B-USABLE-WARM-STAGEB-20260924T071556Z`
- Package OperationId: `R04-D21-P4B-USABLE-WARM-20260923T170936Z` (unchanged)
- Scope: `LOCAL_ONLY / OFFLINE VALIDATION`; no host operation

## Prepared exact bytes

| Artifact | Size | SHA-256 | State |
|---|---:|---|---|
| `payload/startup-set.approved-for-start.json` | 31588 B | `38D7C529FD7CE37E25E32A58CC9CF46075FF5E97D7E60F3618D088653C492BDE` | `APPROVED_FOR_START` bytes prepared; not installed |
| `package-index.install-preapproval.json` | 10908 B | `E298F50753BECB023A5A159F010D746046A111DFCEC2B51E89F3E8C2027C93AD` | proposed; all operational authorization false |
| recipe | unchanged | `74E5664F50CCAE9E641BC076390CE17A769C2E6F1D6F109FB6990C80220B7D6D` | no code change |

Original manifest `E139CEC5...357F0` and VerifyOnly index
`4A58DF7D...84DC` remain unchanged. Manifest semantic diff is exactly
`approval.status`, `approval.installation_authorized` and
`approval.startup_authorized`; `set_id` remains the package OperationId and
`decision_id=D-21`. Index semantic diff is exactly manifest package path,
size/hash and `prepared_window.manifest_state`. Its top status remains
`PROPOSED_AWAITING_SEPARATE_OWNER_OPERATIONAL_APPROVAL`.

The future owner-authorized six-field index transition was computed but not
written: `10904` B / SHA-256
`CF1CCA92DFE3E9A0791615F0EA22454E45D600FDA634FC9DF03D507441A7CCE7`.

## Validation

- Windows PowerShell `5.1.26100.8894`;
- unchanged `Test-P4BPackageIndex`: PASS on the complete derivative index and
  real package files;
- unchanged `Test-StartupSetManifest`: PASS on an isolated projection of the
  exact approved manifest;
- negative projection with `NOT_APPROVED`: FAIL with `START_NOT_APPROVED`;
- validation fixture used one owned junction and was removed without traversing
  its target;
- validation summary: `1031` B /
  `CE75DE1DA2A3FB3236F69FC4136C3FF2F7C8380E3CA00892273201C3440D1559`;
- preparation summary: `4279` B /
  `6CE0F8A06BC5FE1E98E52BE84B5829519FA177E55F2507C788283CE2AF16CB18`;
- production Docker/Task/CIM/TCP/HTTP/UAC/start/write boundaries: `0`.

## Exact next gate

No UAC or InstallAndWarm is authorized by this checkpoint. One current owner
confirmation must bind the six authorization-field transitions, one UAC, four
files plus existing `NEXT Stabil - Host`, two recorder-backed warm runs with
Private `START_ONCE 1 -> 0`, logon only after both complete results and Host
idle, one bounded SAFE_INACTIVE, and a short CRM/Web open check through the
unchanged `C:\Users\domai\Desktop\NEXT Stabil.lnk`.

The previous read-only preflight is not repeated. Six containers, five
dependency tasks, helper, backend flags and data junction remain KEEP;
Supervisor remains `INTENTIONALLY_STOPPED`. Docker/WSL available pool and swap
usage remain `UNKNOWN_NOT_MEASURED`. Installed run01 remains unchanged, Host is
historically disabled/no-trigger and warm runs remain `0/2`.

Status: `P4B_USABLE_WARM_STAGE_B_CONFIGURATION_PREPARED /
OFFLINE_GUARDS_PASS / OPERATION_NOT_AUTHORIZED_NOT_RUN`.

## ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT

Przed oceną i kolejnym promptem przeczytaj roadmapę na SHA publikacji: §0,
`ANTI_EXCESSIVE_WORK`, aktywną kartę R04 i ten checkpoint. Zachowaj odbiory;
nie dodawaj K2/K3. K0/K1 blokujące konfigurację: `BRAK`; operację blokuje tylko
bieżąca zgoda właściciela. Efekt: dokładny zestaw jest przygotowany i
zwalidowany offline, ale nie uruchomiony. Cykl review pozostaje `2/2`;
następny krok to jedna decyzja Stage B, nie nowy preflight.

## Aktualizacja po jedynej autoryzowanej próbie Stage B

- owner confirmation: otrzymane dla exact window i SHA tej fazy;
- authorized index: `package-index.install-authorized.json`, `10904` B,
  SHA-256 `CF1CCA92DFE3E9A0791615F0EA22454E45D600FDA634FC9DF03D507441A7CCE7`;
- one UAC / one InstallAndWarm: wykorzystane;
- elevated PID `79776`: `2026-09-24T07:38:21.0096157Z`–
  `2026-09-24T07:39:42.3941321Z`, exit `22`;
- result: `PARTIAL_PENDING_OPERATION_UNKNOWN`, error
  `PENDING_HOST_DISABLED_REGISTER`;
- four exact files: installed and hash-matched;
- task mutation: `TASK_POSTCHECK_NOT_CONFIRMED`, possible effect true,
  settled false, worker cleanup `WORKER_SETTLED`;
- warm runs `0/2`, Host/Private starts `0`, logon `NOT_ENABLED`, shortcut test
  `NOT_RUN`;
- rollback: `FILES_PRESERVED_NO_DESTRUCTIVE_ROLLBACK`;
- result: `3412` B /
  `9598F6CBE756625636D1AF406DD1FAC6A2E8CA55A735FCF3D57E250682506655`;
- journal: `6222` B /
  `A0A3171F4C9D290E3ABA02873CA294F4CE2ED4D604BB56FBBF773A1473D575F2`,
  `CLOSED`;
- zewnętrzny Task/Docker/HTTP post-check: `NOT_RUN`.

Zgoda operacyjna i UAC są zużyte. Stan Host po możliwej mutacji pozostaje
niepotwierdzony; nie wolno retry, competing write, startu ani zewnętrznego
rollbacku. Status checkpointu po aktualizacji:
`P4B_USABLE_WARM_STAGE_B_PARTIAL_PENDING_OPERATION_UNKNOWN /
FOUR_FILES_INSTALLED / WARM_RUNS_0_OF_2 / READY_FOR_OWNER_REVIEW`.
