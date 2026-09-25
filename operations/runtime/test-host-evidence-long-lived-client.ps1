[CmdletBinding()]
param(
    [switch]$ExpectLegacyFailure
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$recorderPath = Join-Path $PSScriptRoot 'invoke-host-with-evidence.ps1'
$launcherPath = Join-Path $PSScriptRoot 'start-host-services.ps1'
. $recorderPath -DefinitionOnly

$script:assertions = 0
function Assert-FullCapture {
    param([bool]$Condition, [string]$Message)
    $script:assertions++
    if (-not $Condition) { throw "ASSERTION_FAILED:$Message" }
}

$root = Join-Path $env:TEMP ('next-stabil-recorder-client-' + [Guid]::NewGuid().ToString('N').Substring(0, 8))
[void][System.IO.Directory]::CreateDirectory($root)
$ownedClientIds = New-Object System.Collections.Generic.List[int]
try {
    $shell = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
    Assert-FullCapture (Test-Path -LiteralPath $shell) 'fresh Windows PowerShell 5.1 exists'

    $clientFixture = Join-Path $root 'synthetic-long-lived-client.ps1'
    $launcherFixture = Join-Path $root 'synthetic-real-launcher.ps1'
    $pidPath = Join-Path $root 'client.pid'
    $clientObservationPath = Join-Path $root 'client-observation.json'
    $manifestPath = Join-Path $root 'synthetic-manifest.json'
    $sourceManifestPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\docs\recovery\R04_D21_P4_STARTUP_SET_DRAFT.json')).Path
    [System.IO.File]::WriteAllText($manifestPath, '{}', [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllText($clientFixture, @'
param(
    [Parameter(Mandatory = $true)][string]$PidPath,
    [Parameter(Mandatory = $true)][string]$ObservationPath,
    [Parameter(Mandatory = $true)][string]$ExpectedWorkingDirectory,
    [int]$LifetimeSeconds = 30
)
$observation = [pscustomobject][ordered]@{
    pid = $PID
    arguments_preserved = (-not [string]::IsNullOrWhiteSpace($PidPath) -and -not [string]::IsNullOrWhiteSpace($ObservationPath))
    working_directory = (Get-Location).Path
    expected_working_directory = $ExpectedWorkingDirectory
}
[System.IO.File]::WriteAllText($ObservationPath, (($observation | ConvertTo-Json -Compress) + [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))
[System.IO.File]::WriteAllText($PidPath, [string]$PID, [System.Text.UTF8Encoding]::new($false))
Start-Sleep -Seconds $LifetimeSeconds
'@, [System.Text.UTF8Encoding]::new($false))

    $escapedLauncher = $launcherPath.Replace("'", "''")
    $escapedSourceManifest = $sourceManifestPath.Replace("'", "''")
    $launcherBody = @'
param(
    [string]$ManifestPath,
    [Parameter(Mandatory = $true)][string]$Mode,
    [Parameter(Mandatory = $true)][string]$ClientFixture,
    [Parameter(Mandatory = $true)][string]$PidPath,
    [Parameter(Mandatory = $true)][string]$ObservationPath,
    [Parameter(Mandatory = $true)][string]$FixtureRoot
)
$ErrorActionPreference = 'Stop'
. '__LAUNCHER_PATH__' -DefinitionOnly
if ($Mode -eq 'TIMEOUT') { Start-Sleep -Seconds 30; exit 0 }
$clientStarted = $false
if ($Mode -in @('SUCCESS_CLIENT', 'CLIENT_WITHOUT_RESULT')) {
    $manifest = Get-Content -LiteralPath '__SOURCE_MANIFEST_PATH__' -Raw -Encoding UTF8 | ConvertFrom-Json
    ($manifest.external_tools | Where-Object { $_.name -eq 'windows_client' }).path = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
    $adapters = New-RealStartupAdapters -Manifest $manifest
    $definition = [pscustomobject]@{
        arguments = @('-NoLogo', '-NoProfile', '-NonInteractive', '-File', $ClientFixture, '-PidPath', $PidPath, '-ObservationPath', $ObservationPath, '-ExpectedWorkingDirectory', $FixtureRoot, '-LifetimeSeconds', '30')
        working_directory = $FixtureRoot
    }
    $started = & $adapters.StartClient $definition
    if ([string]$started.status -ne 'ACCEPTED') { throw 'SYNTHETIC_CLIENT_START_FAILED' }
    $clientStarted = $true
    $limit = [DateTime]::UtcNow.AddSeconds(5)
    while (-not (Test-Path -LiteralPath $PidPath) -and [DateTime]::UtcNow -lt $limit) { Start-Sleep -Milliseconds 20 }
    if (-not (Test-Path -LiteralPath $PidPath)) { throw 'SYNTHETIC_CLIENT_PID_NOT_PERSISTED' }
}
$success = '{"schema":"NEXT_STABIL_STARTUP_RESULT_V1","code":"BASE_READY_LIMITED","base_ready":true,"supervisor_status":"INTENTIONALLY_STOPPED","client_status":"RUNNING","user_message":"NEXT Stabil jest gotowy.","events":[{"component":"windows_client","action":"START_ONCE","result":"ACCEPTED"}],"details":[]}'
$refusal = '{"schema":"NEXT_STABIL_STARTUP_RESULT_V1","code":"CONTROLLED_DEPLOY_REQUIRED","base_ready":false,"supervisor_status":"INTENTIONALLY_STOPPED","client_status":"NOT_REQUESTED","user_message":"NEXT Stabil nie jest gotowy.","events":[],"details":["synthetic"]}'
switch ($Mode) {
    'SUCCESS_CLIENT' { [Console]::Out.WriteLine($success); exit 0 }
    'INVALID_JSON' { [Console]::Out.WriteLine('{bad'); exit 0 }
    'STDERR' { [Console]::Error.WriteLine('synthetic real stderr'); [Console]::Out.WriteLine($success); exit 0 }
    'REFUSAL' { [Console]::Out.WriteLine($refusal); exit 22 }
    'CLIENT_WITHOUT_RESULT' { exit 0 }
    default { throw ('UNKNOWN_MODE:' + $Mode) }
}
'@.Replace('__LAUNCHER_PATH__', $escapedLauncher).Replace('__SOURCE_MANIFEST_PATH__', $escapedSourceManifest)
    [System.IO.File]::WriteAllText($launcherFixture, $launcherBody, [System.Text.UTF8Encoding]::new($false))

    function New-FullPathConfiguration {
        param([string]$Name, [int]$TimeoutMilliseconds = 5000)
        [pscustomobject]@{
            powershell_path = $shell
            launcher_path = $launcherFixture
            manifest_path = $manifestPath
            evidence_root = (Join-Path $root ('evidence-' + $Name))
            timeout_ms = $TimeoutMilliseconds
            cleanup_timeout_ms = 1000
            max_stdout_characters = 65536
            max_stderr_characters = 16384
            max_path_characters = 220
            notify_failure = $false
            notification_timeout_seconds = 1
            launcher_arguments = @('-Mode', $Name, '-ClientFixture', $clientFixture, '-PidPath', $pidPath, '-ObservationPath', $clientObservationPath, '-FixtureRoot', $root)
        }
    }

    function Invoke-FullPathCase {
        param([string]$Mode, [int]$TimeoutMilliseconds = 5000)
        Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $clientObservationPath -Force -ErrorAction SilentlyContinue
        $configuration = New-FullPathConfiguration -Name $Mode -TimeoutMilliseconds $TimeoutMilliseconds
        $result = Invoke-HostEvidenceCapture -Configuration $configuration -AttemptIdFactory { 'attempt-' + $Mode.ToLowerInvariant().Replace('_', '-') }
        if (Test-Path -LiteralPath $pidPath) {
            $clientId = [int](Get-Content -LiteralPath $pidPath -Raw -Encoding UTF8)
            if (-not $ownedClientIds.Contains($clientId)) { $ownedClientIds.Add($clientId) }
        }
        return $result
    }

    $successCase = Invoke-FullPathCase -Mode 'SUCCESS_CLIENT'
    Assert-FullCapture $successCase.child_started 'scenario A launcher started'
    if ($ExpectLegacyFailure) {
        Assert-FullCapture ($successCase.recorder_status -eq 'LAUNCHER_PROCESS_UNSETTLED') ('legacy recorder reproduces launcher unsettled; actual=' + [string]$successCase.recorder_status + '; stderr=' + (Get-Content -LiteralPath (Join-Path $successCase.evidence_path 'stderr.txt') -Raw -Encoding UTF8))
        Assert-FullCapture ((Get-Content -LiteralPath (Join-Path $successCase.evidence_path 'stderr.txt') -Raw -Encoding UTF8) -eq 'OUTPUT_STREAMS_UNSETTLED') 'legacy recorder reproduces output streams unsettled'
        Assert-FullCapture (Test-Path -LiteralPath $pidPath) 'legacy failure still started one client'
        $legacyClient = Get-Process -Id ([int](Get-Content -LiteralPath $pidPath -Raw -Encoding UTF8)) -ErrorAction SilentlyContinue
        Assert-FullCapture ($null -ne $legacyClient) 'legacy long-lived client remains running'
        [pscustomobject][ordered]@{
            schema = 'NEXT_STABIL_RECORDER_LONG_LIVED_CLIENT_FAIL_BEFORE_V1'
            status = 'EXPECTED_FAIL_BEFORE_REPRODUCED'
            recorder_status = $successCase.recorder_status
            stderr = [string](Get-Content -LiteralPath (Join-Path $successCase.evidence_path 'stderr.txt') -Raw -Encoding UTF8)
            launcher_process_started = $successCase.child_started
            launcher_process_exited = $true
            launcher_exit_code_known = $false
            client_count = 1
            assertions = $script:assertions
            production_boundaries_called = 0
        } | ConvertTo-Json -Depth 5
        exit 0
    }

    Assert-FullCapture ($successCase.recorder_status -eq 'BASE_READY_LIMITED_CAPTURED') 'scenario A complete result succeeds while client remains running'
    Assert-FullCapture ($successCase.child_exit_code -eq 0) 'scenario A launcher exit code preserved'
    Assert-FullCapture (-not $successCase.stdout.truncated -and -not $successCase.stderr.truncated) 'scenario A streams complete and untruncated'
    Assert-FullCapture ($successCase.stderr.characters -eq 0) 'scenario A stderr empty'
    Assert-FullCapture ($successCase.launcher_result.client_status -eq 'RUNNING') 'scenario A client status captured'
    $clientId = [int](Get-Content -LiteralPath $pidPath -Raw -Encoding UTF8)
    Assert-FullCapture ($null -ne (Get-Process -Id $clientId -ErrorAction SilentlyContinue)) 'scenario A long-lived client remains running'
    $clientObservation = Get-Content -LiteralPath $clientObservationPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-FullCapture $clientObservation.arguments_preserved 'scenario G client arguments preserved'
    Assert-FullCapture ([string]$clientObservation.working_directory -eq $root) 'scenario G client working directory preserved'

    $invalidCase = Invoke-FullPathCase -Mode 'INVALID_JSON'
    Assert-FullCapture ($invalidCase.recorder_status -eq 'LAUNCHER_OUTPUT_INVALID_JSON') 'scenario B invalid JSON refused'

    $stderrCase = Invoke-FullPathCase -Mode 'STDERR'
    Assert-FullCapture ($stderrCase.recorder_status -eq 'LAUNCHER_STDERR_NONEMPTY') 'scenario C real stderr refused'

    $refusalCase = Invoke-FullPathCase -Mode 'REFUSAL'
    Assert-FullCapture ($refusalCase.recorder_status -eq 'LAUNCHER_REFUSED_CAPTURED' -and $refusalCase.child_exit_code -eq 22) 'scenario D refusal exit 22 captured'

    $timeoutCase = Invoke-FullPathCase -Mode 'TIMEOUT' -TimeoutMilliseconds 100
    Assert-FullCapture ($timeoutCase.recorder_status -eq 'LAUNCHER_TIMEOUT_UNKNOWN') 'scenario E launcher timeout fails closed'
    Assert-FullCapture $timeoutCase.child_settled 'scenario E owned launcher settled after cleanup'

    $clientWithoutResultCase = Invoke-FullPathCase -Mode 'CLIENT_WITHOUT_RESULT'
    Assert-FullCapture ($clientWithoutResultCase.recorder_status -eq 'LAUNCHER_OUTPUT_EMPTY') 'scenario F client alone cannot establish success'

    [pscustomobject][ordered]@{
        schema = 'NEXT_STABIL_RECORDER_LONG_LIVED_CLIENT_FULL_PATH_TEST_V1'
        status = 'PASS'
        assertions = $script:assertions
        scenarios = 7
        path = 'recorder -> real launcher process -> real StartClient -> launcher result -> recorder evidence result'
        long_lived_client_preserved_until_fixture_cleanup = $true
        production_boundaries_called = 0
        fixture_root = $root
    } | ConvertTo-Json -Depth 5
}
finally {
    foreach ($clientId in @($ownedClientIds)) {
        $owned = Get-Process -Id $clientId -ErrorAction SilentlyContinue
        if ($null -ne $owned) {
            Stop-Process -Id $clientId -Force -ErrorAction SilentlyContinue
            try { [void]$owned.WaitForExit(5000) } catch {}
        }
    }
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
}
