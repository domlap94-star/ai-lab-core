[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$scriptPath = Join-Path $PSScriptRoot 'invoke-host-with-evidence.ps1'
. $scriptPath -DefinitionOnly

$script:assertions = 0
function Assert-HostEvidence {
    param([bool]$Condition, [string]$Message)
    $script:assertions++
    if (-not $Condition) { throw "ASSERTION_FAILED:$Message" }
}

$root = Join-Path $env:TEMP ('p4b-host-evidence-' + [Guid]::NewGuid().ToString('N').Substring(0, 8))
[void][System.IO.Directory]::CreateDirectory($root)
try {
    $shell = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
    Assert-HostEvidence -Condition (Test-Path -LiteralPath $shell) -Message 'Windows PowerShell 5.1 path exists'

    function New-SyntheticLauncher {
        param([string]$Name, [string]$Body)
        $path = Join-Path $root $Name
        [System.IO.File]::WriteAllText($path, $Body, [System.Text.UTF8Encoding]::new($false))
        return $path
    }
    function New-TestConfiguration {
        param([string]$Launcher, [string]$EvidenceName, [int]$TimeoutMs = 5000, [int]$StdoutCap = 65536)
        $manifest = Join-Path $root 'manifest with spaces.json'
        if (-not (Test-Path -LiteralPath $manifest)) { [System.IO.File]::WriteAllText($manifest, '{}', [System.Text.UTF8Encoding]::new($false)) }
        return [pscustomobject]@{
            powershell_path = $shell
            launcher_path = $Launcher
            manifest_path = $manifest
            evidence_root = (Join-Path $root $EvidenceName)
            timeout_ms = $TimeoutMs
            cleanup_timeout_ms = 2000
            max_stdout_characters = $StdoutCap
            max_stderr_characters = 4096
            max_path_characters = 220
        }
    }
    $successJson = '{"schema":"NEXT_STABIL_STARTUP_RESULT_V1","code":"BASE_READY_LIMITED","base_ready":true,"supervisor_status":"INTENTIONALLY_STOPPED","events":[{"component":"private_gateway","action":"START_ONCE","result":"SUCCESS"}],"details":[]}'
    $refusalJson = '{"schema":"NEXT_STABIL_STARTUP_RESULT_V1","code":"CONTROLLED_DEPLOY_REQUIRED","base_ready":false,"supervisor_status":"INTENTIONALLY_STOPPED","events":[],"details":["synthetic"]}'
    $success = New-SyntheticLauncher -Name 'success launcher.ps1' -Body ("param([string]`$ManifestPath)`nWrite-Output '$successJson'`nexit 0`n")
    $refusal = New-SyntheticLauncher -Name 'refusal.ps1' -Body ("param([string]`$ManifestPath)`nWrite-Output '$refusalJson'`nexit 22`n")
    $malformed = New-SyntheticLauncher -Name 'malformed.ps1' -Body "param([string]`$ManifestPath)`nWrite-Output '{bad'`nexit 0`n"
    $empty = New-SyntheticLauncher -Name 'empty.ps1' -Body "param([string]`$ManifestPath)`nexit 0`n"
    $stderrLauncher = New-SyntheticLauncher -Name 'stderr.ps1' -Body ("param([string]`$ManifestPath)`n[Console]::Error.WriteLine('synthetic warning')`nWrite-Output '$successJson'`nexit 0`n")
    $timeoutLauncher = New-SyntheticLauncher -Name 'timeout.ps1' -Body "param([string]`$ManifestPath)`nStart-Sleep -Milliseconds 1200`nexit 0`n"
    $longLauncher = New-SyntheticLauncher -Name 'long.ps1' -Body ("param([string]`$ManifestPath)`nWrite-Output ('x' * 300)`nexit 0`n")

    $caseSuccess = Invoke-HostEvidenceCapture -Configuration (New-TestConfiguration -Launcher $success -EvidenceName 'success') -AttemptIdFactory { 'attempt-success' }
    Assert-HostEvidence ($caseSuccess.recorder_status -eq 'BASE_READY_LIMITED_CAPTURED') 'success status'
    Assert-HostEvidence ($caseSuccess.recorder_exit_code -eq 0) 'success exit'
    Assert-HostEvidence ($caseSuccess.launcher_result.code -eq 'BASE_READY_LIMITED') 'success JSON captured'
    Assert-HostEvidence ((Get-Content -LiteralPath (Join-Path $caseSuccess.evidence_path 'result.json') -Raw | ConvertFrom-Json).attempt_id -eq 'attempt-success') 'result persisted'

    $caseRefusal = Invoke-HostEvidenceCapture -Configuration (New-TestConfiguration -Launcher $refusal -EvidenceName 'refusal') -AttemptIdFactory { 'attempt-refusal' }
    Assert-HostEvidence ($caseRefusal.recorder_status -eq 'LAUNCHER_REFUSED_CAPTURED') 'refusal status'
    Assert-HostEvidence ($caseRefusal.recorder_exit_code -eq 22) 'refusal exit preserved'
    Assert-HostEvidence ($caseRefusal.launcher_result.code -eq 'CONTROLLED_DEPLOY_REQUIRED') 'refusal JSON captured'

    $caseMalformed = Invoke-HostEvidenceCapture -Configuration (New-TestConfiguration -Launcher $malformed -EvidenceName 'malformed') -AttemptIdFactory { 'attempt-malformed' }
    Assert-HostEvidence ($caseMalformed.recorder_status -eq 'LAUNCHER_OUTPUT_INVALID_JSON') 'malformed refused'
    Assert-HostEvidence ($caseMalformed.recorder_exit_code -eq 24) 'malformed recorder failure'

    $caseEmpty = Invoke-HostEvidenceCapture -Configuration (New-TestConfiguration -Launcher $empty -EvidenceName 'empty') -AttemptIdFactory { 'attempt-empty' }
    Assert-HostEvidence ($caseEmpty.recorder_status -eq 'LAUNCHER_OUTPUT_EMPTY') 'empty refused'

    $caseStderr = Invoke-HostEvidenceCapture -Configuration (New-TestConfiguration -Launcher $stderrLauncher -EvidenceName 'stderr') -AttemptIdFactory { 'attempt-stderr' }
    Assert-HostEvidence ($caseStderr.recorder_status -eq 'LAUNCHER_STDERR_NONEMPTY') 'stderr prevents success'
    Assert-HostEvidence ((Get-Content -LiteralPath (Join-Path $caseStderr.evidence_path 'stderr.txt') -Raw) -match 'synthetic warning') 'stderr persisted'

    $caseTimeout = Invoke-HostEvidenceCapture -Configuration (New-TestConfiguration -Launcher $timeoutLauncher -EvidenceName 'timeout' -TimeoutMs 100) -AttemptIdFactory { 'attempt-timeout' }
    Assert-HostEvidence ($caseTimeout.recorder_status -eq 'LAUNCHER_TIMEOUT_UNKNOWN') 'timeout is unknown'
    Assert-HostEvidence ($caseTimeout.child_settled) 'owned timeout child settled'
    Assert-HostEvidence ($caseTimeout.recorder_exit_code -eq 24) 'timeout recorder failure'

    $caseTruncated = Invoke-HostEvidenceCapture -Configuration (New-TestConfiguration -Launcher $longLauncher -EvidenceName 'truncated' -StdoutCap 64) -AttemptIdFactory { 'attempt-truncated' }
    Assert-HostEvidence ($caseTruncated.recorder_status -eq 'LAUNCHER_OUTPUT_TRUNCATED') 'truncation refused'
    Assert-HostEvidence ($caseTruncated.stdout.characters -eq 64) 'stdout cap applied'
    Assert-HostEvidence ($caseTruncated.stdout.original_characters -gt 64) 'original length retained'

    $collisionConfig = New-TestConfiguration -Launcher $success -EvidenceName 'collision'
    $collisionPath = Join-Path $collisionConfig.evidence_root 'attempt-collision'
    [void][System.IO.Directory]::CreateDirectory($collisionPath)
    $script:collisionStarts = 0
    $collision = Invoke-HostEvidenceCapture -Configuration $collisionConfig -AttemptIdFactory { 'attempt-collision' } -ProcessRunner { param($c, $a) $script:collisionStarts++; throw 'must not run' }
    Assert-HostEvidence ($collision.recorder_status -eq 'EVIDENCE_OUTPUT_COLLISION') 'collision refused'
    Assert-HostEvidence (-not $collision.child_started) 'collision before child'
    Assert-HostEvidence ($script:collisionStarts -eq 0) 'collision runner not called'

    $script:writeCount = 0
    $failingBoundary = New-HostEvidenceFileBoundary
    $realWrite = $failingBoundary.WriteUniqueText
    $failingBoundary.WriteUniqueText = {
        param([string]$Path, [AllowEmptyString()][string]$Text)
        $script:writeCount++
        if ($script:writeCount -eq 2) { throw 'synthetic write refusal' }
        & $realWrite $Path $Text
    }.GetNewClosure()
    $writeFailure = Invoke-HostEvidenceCapture -Configuration (New-TestConfiguration -Launcher $success -EvidenceName 'write-failure') -AttemptIdFactory { 'attempt-write-failure' } -FileBoundary $failingBoundary
    Assert-HostEvidence ($writeFailure.recorder_status -eq 'EVIDENCE_WRITE_FAILED') 'write failure distinguished'
    Assert-HostEvidence ($writeFailure.child_started) 'write failure after child start represented'
    Assert-HostEvidence ($writeFailure.recorder_exit_code -eq 24) 'write failure incomplete'

    $quoted = Join-WindowsCommandLineArguments -Values @('-File', 'C:\path with spaces\tool.ps1', '-ManifestPath', 'C:\x\quote"tail\\')
    Assert-HostEvidence ($quoted -match '"C:\\path with spaces\\tool.ps1"') 'path with spaces quoted'
    Assert-HostEvidence ($quoted -match '\\"') 'embedded quote escaped'
    Assert-HostEvidence ($caseTimeout.child_settled) 'timeout process accounted'

    [pscustomobject][ordered]@{
        schema = 'NEXT_STABIL_HOST_EVIDENCE_CAPTURE_TEST_V1'
        status = 'PASS'
        assertions = $script:assertions
        actual_child_process_cases = 7
        timeout_children_settled = 1
        synthetic_boundary_cases = 2
        production_boundaries_called = 0
        fixture_root = $root
    } | ConvertTo-Json -Depth 6
}
finally {
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
}
