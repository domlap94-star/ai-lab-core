# R04 / D-21 / P4-B — native argument transport evidence

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
