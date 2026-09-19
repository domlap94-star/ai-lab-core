# R04 / D-21 / P4-B — native argument transport evidence

> Granica odbioru po review input binding, 2026-09-18: recepta transportowa
> `5F310C64...1FD67` zachowuje własne 17/17 i 120 asercji oraz historyczny
> dozwolony inspect. Nie była jednak wykonawczo kompletna z powodu
> `BASELINE_PATH_BINDING_MISMATCH`. Osobny LOCAL_ONLY pakiet input binding
> `733AA23F...D05B6A` / index `ED05FE26...875C` odtworzył ten fail-before i
> przeszedł 14/14, 119 asercji bez live Docker/Task/HTTP/UAC/mutacji. Nie
> przepisuje to historycznych wyników transportu i nie nadaje zgody P4/B.
> Kontynuacja 2026-09-19 zachowuje oba historyczne pakiety i domyka osobno
> pełną ścieżkę błędu/rollbacku. Recepta `16A35C32...0C4DC8` z indeksem
> `1355EF08...3E3BF` przeszła wykonawcze testy offline; nie była uruchomiona
> przeciwko hostowi.

Status: `RECIPE_NATIVE_ARGUMENT_TRANSPORT_FIXED / TESTED_ON_POWERSHELL_51 /
READY_FOR_REVIEW / NOT_INSTALLED`

Recipe ID: `R04-D21-P4B-RECIPE-TRANSPORT-FIX-20260918T152017Z`

Parent OP_ID: `R04-D21-P4B-WINDOW-20260918T084652Z`

Failed resume: `R04-D21-P4B-RESUME-20260918T112015Z`

## Scope and result

The work was limited to a LOCAL_ONLY replacement recipe, an offline harness and
one non-elevated read-only Docker invocation. No UAC, task/trigger/Startup
change, installation, service action, warm run or rollback occurred.

The failed recipe SHA-256
`D8E2868F51F04D179C3749CA6E0691C307BA8B7ABEB668CC9987E60D4A350F61`
passed a PowerShell array directly to `Start-Process -ArgumentList`. On Windows
PowerShell 5.1 that boundary rebuilt a native command line without preserving
the space-containing Go-template as one token. The harmless preimage probe
received 56 arguments instead of the expected 7. This independently reproduces
the same class of split recorded by the earlier Docker stderr; it does not
rerun the failed installer.

The corrected recipe SHA-256 is
`5F310C64DFB21F55B4403E9A738B80344EB9CEC38536EE4FD2081F6422F1FD67`.
Its new LOCAL_ONLY index is 7,454 B, SHA-256
`43F285C2E82032F6914F5C5F8BA0653C85EC44F2A4F24E13D835A7C02162A2A9`.
The final argv probe received exactly 7/7 arguments and byte-for-byte identical
content, including the complete `--format` value.

## Actual code change

The preimage transport was:

```powershell
$process = Start-Process -FilePath $Executable -ArgumentList $Arguments `
    -WorkingDirectory $installerRoot -RedirectStandardOutput $outPath `
    -RedirectStandardError $errPath -WindowStyle Hidden -PassThru
```

The recipe now reuses the exact normalized definitions from accepted launcher
source `8756314f51a76091a483cfc9b677a05c7f67f315`:

```powershell
$startInfo.FileName = $FilePath
$startInfo.Arguments = Join-WindowsNativeArguments -ArgumentList $ArgumentList
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
```

The recipe wrapper persists bounded output and result metadata before it
interprets status:

```powershell
$result = Invoke-BoundedNativeCommand -FilePath $Executable `
    -ArgumentList $Arguments -WorkingDirectory $installerRoot `
    -TimeoutMilliseconds ($TimeoutSeconds * 1000) `
    -MaximumOutputCharacters 65536

[IO.File]::WriteAllText($outPath, [string]$result.stdout, $utf8NoBom)
[IO.File]::WriteAllText($errPath, [string]$result.stderr, $utf8NoBom)
Write-SafeJson -Path $metadataPath -Value ([ordered]@{
    label = $Label
    status = [string]$result.status
    started = [bool]$result.started
    timed_out = [bool]$result.timed_out
    exit_code = $result.exit_code
    pid = $result.pid
    process_left_running = [bool]$result.process_left_running
    duration_ms = [int]$result.duration_ms
    stdout_characters = ([string]$result.stdout).Length
    stderr_characters = ([string]$result.stderr).Length
    stdout_truncated = [bool]$result.stdout_truncated
    stderr_truncated = [bool]$result.stderr_truncated
})
```

`SUCCESS`, empty exit-0 output, nonzero exit, start failure, timeout, unknown
result and truncated/incomplete output remain distinct. The recipe has no
`Start-Process`, `Invoke-Expression`, `cmd /c` or unbounded native fallback.
Only `Get-LiveContainerProjection` calls the bounded native wrapper. The main
installer block after the function replacement is byte-equivalent after
newline normalization to the failed recipe, so accepted guards and mutation
order were not removed.

## Offline tests

Environment: Windows PowerShell `5.1.26100.8894`; .NET Framework compiler
`4.8.9221.0 built by NET481REL1LAST_25H2`.

Final command:

```text
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe
  -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass
  -File <LOCAL_ONLY>\test-native-argument-transport.ps1
```

Result: exit `0`, 17/17 cases and 120 assertions. Covered cases:

- exact failed Go-template and exact guard selectors;
- spaces, Unicode, internal quotes, empty argument and trailing backslashes;
- non-elevated `PowerShell -File` argument shape;
- empty stdout/stderr at exit 0, nonzero exit, start failure, timeout with the
  owned child accounted for, and truncated output without retry;
- pre/post-mutation sequence linked to exact final-recipe statements, with
  complete fake task/file/start actions; index/template/ID/incomplete/formatter
  failures stop before the mutation boundary;
- no repeated wrapper move or disabled Host creation; valid synthetic sequence
  retains two intended warm-run steps without executing them;
- all 29 indexed installation inputs and the four published payload/manifest
  hashes remain unchanged.

The first complete harness run was 15/17. Its two failures were in test-only
formatting (preimage stdout was already captured despite the old runner's empty
exit-code report, and a single-quoted PowerShell probe emitted literal
backtick-t). Earlier parser/compatibility iterations recorded UTF-8-no-BOM and
PowerShell 5.1 harness issues. Those logs are retained LOCAL_ONLY; no Docker,
UAC or host mutation occurred in any offline iteration.

Final evidence:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Offline summary/stdout | 4,446 | `2595FE3808AA338C96820FEC5C4CE6B5F68EAFD90B0CDE916658D3CC86EC03D1` |
| Offline command record | 427 | `DD33BA7344238FD37DEC5C6167E6D33A228934D139AA2D47A629CF495EA1F2D7` |
| Offline stderr | 0 | `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855` |
| argv probe source | 1,385 | `3BE40631205A145A003685F47946D54028AD8765DAE28260FBE262F42C4E262E` |
| argv probe executable | 4,608 | `581FF516F571C87FEC67DDAC9D4C66BA5413A99F8D5B332BEB03B0D7A2D729AB` |

The source, executable, recipe, harness, raw logs and complete index remain
LOCAL_ONLY in the protected P4/B staging root.

## Single exact Docker readback

Only after the offline PASS, the final transport performed exactly one normal-
token call equivalent to:

```text
docker --context desktop-linux container inspect --format <one template token>
  686ac37663ad369f253eb91da4364aa2bd6c16c77b1205cc41d61c68d4d9c854
```

Result: exit `0`; stderr empty; no retry. The safe projection confirmed the
same backend ID, `/ai-lab-backend`, image
`sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`,
running state, `RestartCount=0`, `/app=C:/ai-lab-core/backend:ro`,
`/data=C:/ai-lab-core/data:rw`, loopback port `8000`, project/service labels and
network `ai-lab-network`.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Safe verdict | 3,388 | `FBFFA2C853565C539480B8C8F94355FD6E08C06D515653B3C201D9F9A7CF1A43` |
| Command record | 397 | `9D9E6B86AEDFB3F301196E9F297819FF0B3857ACB98297A88DF453B7EBE66045` |
| Bounded native result | 364 | `B57DDA0C873E739BB73244DE21F6A145028E4E9F093F0452A789F9A148EE1A67` |
| Native stdout | 860 | `EC7EED9EA543C65D3FF77B98CC4F9840E9B32DE0C7A71A525501D43E57C1BC1E` |
| Native stderr | 0 | `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855` |

This proves the corrected argument boundary for one exact read. It is not a
fresh six-container drift check, installation preflight or runtime acceptance.

## Unchanged installation inputs and next gate

The launcher/runtime/helper/manifest hashes remain respectively:

- `7BB24450C0B0EFDD8321935B129A25CEDD788BA3B8951965EF8E4A09BBF33871`;
- `349404C3B8DE7B2502437E023BEC09464428856A6D8F120EAFBD68E1ABCF4FA7`;
- `91C763F5D0FF6CC7184E0B238EA6A6047CBB3FB13F88917777F4E0696E9667EC`;
- `E66F22A7EC433183940FC3014E1B9F8C1DBE535375EC2D6580B958B55586010C`.

The repository/global manifest remains `NOT_APPROVED_FOR_START`; launcher,
runtime and manifest remain uninstalled; warm runs remain `0/2`. The next step
is owner review of the exact recipe and index. A future installation requires a
new single-use decision, fresh bounded drift check and separately approved UAC.
This evidence does not authorize that operation.

## Full error and SAFE_INACTIVE rollback path — 2026-09-19

Zakres `RV-P4B-FULL-01–04` wykonano na zachowanym preimage. Nie wykonano
Docker, Task Scheduler, CIM, TCP, HTTP, UAC ani mutacji produktu. Preimage
potwierdził cztery niezależne braki:

- kolizję niezmiennej zmiennej `$Host` oraz błędne `-Status (if (...))`;
- predykat rollbacku, dla którego `$null -ne 'Running'` pozwalał na usuwanie;
- synchroniczną granicę hosta niewłączoną do budżetu całego adaptera;
- harness sprawdzający tekst źródła zamiast rzeczywistego catch/finalization.

Nowa recepta ma 77,031 B i SHA-256
`16A35C328A091801A4713A7F282A72C7E143BE489BF847A1AEE15599F70C4DC8`.
Package index ma 3,775 B i SHA-256
`1355EF0878C31202145E4E324C40A5D07E343FB78B0C6C7D029E2E932C43E3BF`.
Review ZIP ma 37,305 B, osiem wpisów i SHA-256
`DE8483568A17E27E80F3EE1C222C9E4BAC8EC6D78BA4C4CDC6DC48E2A86CFAEC`;
roundtrip listy wpisów przeszedł. ZIP nie zawiera raw logów, danych firmy ani
payloadu runtime.

Końcowy harness wejściowy przeszedł 14 przypadków/110 asercji. Harness
orkiestracji przeszedł 10 przypadków/67 asercji i wykonał rzeczywiste funkcje
recepty dla: sukcesu dwóch warm runów, błędu przed mutacją, błędu po mutacji z
SAFE_INACTIVE, zatrzymania po pierwszym warm runie, odmów rollbacku dla
Running/Queued/Unknown/denied/timeout, awarii logowania bez maskowania błędu
pierwotnego, obcej tożsamości i zawieszonej granicy dolnej. Własne workery
zakończyły się 9/9. Zarezerwowany output
`execution-output\exact-full-path-attempt-1` nie powstał.

Pliki testowe pozostają LOCAL_ONLY w chronionym katalogu P4/B. Recepta nie
przyjmuje arbitralnego kodu z JSON; zamknięte operacje hosta korzystają ze
wspólnego pozostałego deadline, a timeout po możliwym żądaniu startu daje
UNKNOWN bez retry. Destrukcyjny rollback wymaga pozytywnie potwierdzonego
disabled/no-trigger/exact identity i braku instancji; stan nieznany, obcy helper
lub obcy plik blokują usuwanie.

Wynik to `FULL_ERROR_AND_SAFE_INACTIVE_ROLLBACK_PATH_READY_FOR_REVIEW /
OFFLINE_ONLY / NOT_INSTALLED`. Stan hosta pozostaje historyczny:
`PARTIAL_SAFE_INACTIVE`, payload/manifest nieobecne i warm runs `0/2`. Każda
przyszła operacja wymaga osobnego review exact recipe/index/ZIP, świeżego
bounded drift check i nowej jednorazowej decyzji właściciela.

## Zależności rollbacku i nierozliczone mutacje — 2026-09-19

Kontynuacja była wyłącznie `SOURCE / LOCAL FILE READ / OFFLINE TEST ONLY`.
Zachowany preimage `16A35C32...0C4DC8` odtworzył trzy dalsze uwagi:

- `RV-P4B-FULL-03B — REPRODUCED`: po timeout po handoffie stary kod uruchamiał
  konkurujący rollback i usuwał zależne pliki, zanim kontrolowany późny writer
  zakończył operację;
- `RV-P4B-FULL-02B — REPRODUCED`: znany bezczynny Host pozwalał przywrócić
  legacy helper pomimo nierozliczonego Compose/automatycznego triggera;
- `RV-P4B-FULL-02C — REPRODUCED`: realna ścieżka rollbacku rejestrowała task
  przez `-Force` bez świeżej kontroli przypiętego lub operation-owned stanu.

Preimage harness przeszedł `4/4` przypadki i `16` asercji, wykazując rzeczywistą
kolejność oraz zakończenie jednego kontrolowanego późnego writera. Poprawiona
recepta przechowuje ustrukturyzowany ledger operacji mutujących. Stan
`PENDING_OPERATION_UNKNOWN` blokuje automatyczny retry, rollback i cleanup
zależnych plików. Przywrócenie legacy helpera wymaga pozytywnego potwierdzenia
bezczynności i bezpiecznej konfiguracji Host oraz Compose, a każdy zapis taska
w rollbacku przechodzi wspólną kontrolę tożsamości bezpośrednio przed zapisem.
UNKNOWN, brak odczytu lub obcy drift oznaczają zero zapisu do danego taska i
zachowanie plików.

| Artefakt | Bajty | SHA-256 |
|---|---:|---|
| `invoke-p4b-resume-installer.rollback-safe.ps1` | 91,889 | `F6D3A8CC7AA57ED50244D773076700BCBE5771609762947B230E344C5C883F0E` |
| `test-input-bindings-rollback-safe.ps1` | 22,568 | `4753C26B1FB85CDA351A30B5E1FF1750398954D99CCA185399978894ADBC3C00` |
| `test-rollback-safe-orchestration.ps1` | 27,098 | `61C9C6FF8E083AFFAB3F2A84550ED0CC41558C800250285751F953994FEDFBEC` |
| `repro-preimage-rollback-dependencies.ps1` | 24,302 | `85D0A96DBA5A77EA8E6F9F2083EC0AC87557A044FE40EA1C9EF9E2C215B28E01` |
| `rollback-safe-package-index.json` | 2,970 | `FDF9FE7AF55A8285FB51506E3CBFA5368F366353748DC68BBCCBBC37164A977F` |
| `REVIEW_INDEX.md` | 2,620 | `731BE887CCEF81AF701ABA5DA8210027C3CE7A7CA71CEF9B19AB128EECBE600C` |
| review ZIP, 7 wpisów | 47,891 | `D2B3263BE6ECB20E139CF63E7559C0E53605CE8827183989E37979247965DA1C` |

Końcowe Windows PowerShell `5.1.26100.8894`: input/index `14/14`, `110`
asercji; orkiestracja `15/15`, `96` asercji; workery `437/437`; parser czterech
skryptów `PASS`; ZIP roundtrip i hashe wszystkich siedmiu wpisów `PASS`.
Rzeczywiste Docker/Task Scheduler/CIM/TCP/HTTP/UAC i mutacje produktu: `0`.
Stan hosta nie był ponownie odczytywany i pozostaje wyłącznie historyczny:
wrapper w rollbacku, Host disabled/no-trigger, pięć tasków na preimage,
payload/manifest nieobecne, warm runs `0/2`.

Wynik: `P4B ROLLBACK_DEPENDENCIES_AND_PENDING_MUTATIONS_READY_FOR_REVIEW /
OFFLINE_ONLY / NOT_INSTALLED`. Nie jest to odbiór P4/B ani zgoda na live
preflight, UAC, instalację lub rollback hosta.

## TaskInfo i dokładna pochodna short-output — 2026-09-19

Odebrana recepta F6D3 pozostała byte-for-byte bez zmian. Przygotowana obok
niej pochodna `invoke-p4b-resume-installer.short-output.ps1` ma 91,912 B i
SHA-256
`F65DF7232ADC3DBFE6B35FC08D255D385748ED17CC3078CACB93501FB9BF8C9A`.
Allowlisted diff zmienia wyłącznie identyfikację/entry HEAD, kanoniczną nazwę i
bazę wyników na
`C:\ai-lab-core-staging\recovery\P4B-FIN-01\out\run01`. Wszystkie ciała
funkcji, wejścia, sześć baseline'ów, mutacje i rollback pozostają zgodne z
preimage.

Poprawiony exact TaskInfo worker przeszedł PowerShell 5.1 `16/126`, a jedna
kampania live utrwaliła `6/6` odczytów bez uruchomienia tasków. Pochodna
przeszła input `14/110`, orchestration `15/96`, `437/437` workerów,
path/I/O `206<=220` i VerifyInputsOnly `29/29 + 6`; `out\run01` nie powstał.
Bieżący drift ma wynik
`PASS_WITH_DOCKER_WSL_POOL_AND_SWAP_UNKNOWN` — wymagane tożsamości i health są
zgodne, Windows/disk gates przeszły, lecz pula Docker/WSL i swap-used pozostają
`UNKNOWN`.

Package index:
`36623A0384F400D10D9FF0714FE7ED67B0090FC872C19751ED195D2E52C8D49E`.
Review ZIP: 75,385 B, SHA-256
`407A872A9B0504F35F2141992E3F84132198175A0146B5B0D1925B0F878D7272`,
roundtrip `17/17`. Status:
`SHORT_OUTPUT_DERIVATIVE_READY_FOR_REVIEW / TASKINFO_6_OF_6 / NO_UAC /
NOT_INSTALLED`. Dalszy RunAs/UAC, Install, warm runs lub rollback wymagają
nowej bieżącej decyzji właściciela.

## Wynik exact resume short-output — 2026-09-19

Właściciel zaakceptował pochodną tylko dla jednorazowego resume
`R04-D21-P4B-RESUME-SHORT-OUTPUT-20260919T202300Z`. Jeden RunAs/UAC został
wykonany. Instalator zakończył `PARTIAL_AFTER_FAILURE` z
`HOST_TASK_FAILED:22`; pierwszy Host run był jedyną próbą, warm `0/2`, Private
starts `0`. Recepta wykonała jeden SAFE_INACTIVE, który zakończył
`PARTIAL_UNKNOWN`, ponieważ Public Gateway pozostał `Running`; nie wykonano
destrukcyjnego rollbacku plików ani helper restore. Wszystkie workery
instalatora są rozliczone `50/50`, pending mutator `false`.

Zainstalowane hashe odpowiadają czterem przypiętym wejściom. Pooperacyjny
readback wykazał Host disabled/no-trigger z `LastTaskResult=22`, brak logon
triggera, Private i Supervisor bez listenerów, backend/Public Gateway `200`,
publiczne `/control*` `404` oraz sześć niezmienionych działających kontenerów,
`RestartCount=0`, PostgreSQL healthy. Nie wykonano container start/stop/restart.

Bezpieczne dowody LOCAL_ONLY:

| Dowód | Bajty | SHA-256 |
|---|---:|---|
| installer result | 10,760 | `3EA0038DDE23C63D69E13E038B329274357C3AC6FFFE89B398098C4243E764C6` |
| installer events | 9,098 | `F915A12C457589BAD3F7BD30144C66D5A66B4D0D7C5FFB25C2E507C789111CC2` |
| post task | 5,544 | `B3D1EDB09910B5A4E67027469E8335DE0ECDB1DAD3000C497B6DD2AF8488A005` |
| post task definitions | 8,616 | `97352F8F1C027C7E8B2C4A0F392B90A3DEBB4B71EB95AFCA0C38EC580C31C825` |
| post surface | 4,845 | `AE93C524C82125C3A1C512E52F2A29C35F9581042B9CEB9497228D784D9649FE` |
| post containers | 8,299 | `8865AC7C224CCA04A4FD851238DC6C3EACC691FD92D4FB7CF3453E53C08969E9` |

Nie utrwalono bezpiecznej projekcji stdout launchera, więc kod `22` pozostaje
`LAUNCHER_RESULT_DETAIL_NOT_CAPTURED`. Nie wolno przypisać go konkretnemu
adapterowi bez nowego dowodu. Status: `P4B PARTIAL_AFTER_FAILURE /
HOST_TASK_FAILED_22 / SAFE_INACTIVE_PARTIAL_UNKNOWN /
PAYLOAD_AND_MANIFEST_INSTALLED / HOST_DISABLED_NO_TRIGGER /
WARM_RUNS_0_OF_2 / PRIVATE_NOT_STARTED / LOGON_TRIGGER_NOT_INSTALLED /
READY_FOR_OWNER_REVIEW`. Zgoda/UAC/rollback są skonsumowane; bez retry.
