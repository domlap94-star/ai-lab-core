[CmdletBinding()]
param(
    [switch]$DefinitionOnly
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Get-HostEvidenceProperty {
    param(
        [AllowNull()]$InputObject,
        [Parameter(Mandatory = $true)][string]$Name
    )
    if ($null -eq $InputObject) { return $null }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function ConvertTo-WindowsCommandLineArgument {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value)

    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') { return $Value }
    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append('"')
    $slashes = 0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq '\') {
            $slashes++
            continue
        }
        if ($character -eq '"') {
            [void]$builder.Append(('\' * (($slashes * 2) + 1)))
            [void]$builder.Append('"')
            $slashes = 0
            continue
        }
        if ($slashes -gt 0) {
            [void]$builder.Append(('\' * $slashes))
            $slashes = 0
        }
        [void]$builder.Append($character)
    }
    if ($slashes -gt 0) { [void]$builder.Append(('\' * ($slashes * 2))) }
    [void]$builder.Append('"')
    return $builder.ToString()
}

function Join-WindowsCommandLineArguments {
    param([Parameter(Mandatory = $true)][string[]]$Values)
    return (($Values | ForEach-Object { ConvertTo-WindowsCommandLineArgument -Value ([string]$_) }) -join ' ')
}

function Limit-HostEvidenceText {
    param(
        [AllowNull()][AllowEmptyString()][string]$Text,
        [Parameter(Mandatory = $true)][ValidateRange(1, 1048576)][int]$MaximumCharacters
    )
    if ($null -eq $Text) { $Text = '' }
    if ($Text.Length -le $MaximumCharacters) {
        return [pscustomobject]@{ text = $Text; truncated = $false; original_characters = $Text.Length }
    }
    return [pscustomobject]@{
        text = $Text.Substring(0, $MaximumCharacters)
        truncated = $true
        original_characters = $Text.Length
    }
}

function Get-HostEvidenceSha256Text {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Text)
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($Text)
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try { return (($hasher.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') }) -join '').ToUpperInvariant() }
    finally { $hasher.Dispose() }
}

function New-HostEvidenceFileBoundary {
    return [pscustomobject]@{
        TestPath = {
            param([string]$Path)
            return (Test-Path -LiteralPath $Path)
        }
        CreateDirectory = {
            param([string]$Path)
            [void][System.IO.Directory]::CreateDirectory($Path)
        }
        WriteUniqueText = {
            param([string]$Path, [AllowEmptyString()][string]$Text)
            $encoding = [System.Text.UTF8Encoding]::new($false)
            $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
            try {
                $writer = New-Object System.IO.StreamWriter($stream, $encoding)
                try { $writer.Write($Text); $writer.Flush() }
                finally { $writer.Dispose() }
            }
            finally { $stream.Dispose() }
        }
    }
}

function Test-HostEvidenceFileBoundary {
    param([Parameter(Mandatory = $true)]$Boundary)
    foreach ($name in @('TestPath', 'CreateDirectory', 'WriteUniqueText')) {
        if (-not ((Get-HostEvidenceProperty -InputObject $Boundary -Name $name) -is [scriptblock])) { return $false }
    }
    return $true
}

function Get-HostEvidenceProductionConfiguration {
    return [pscustomobject][ordered]@{
        powershell_path = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
        launcher_path = 'C:\ai-lab-core\operations\runtime\start-host-services.ps1'
        manifest_path = 'C:\ai-lab-core\operations\runtime\startup-set.json'
        evidence_root = 'C:\ai-lab-core\data\logs\startup'
        timeout_ms = 840000
        cleanup_timeout_ms = 5000
        max_stdout_characters = 65536
        max_stderr_characters = 16384
        max_path_characters = 220
    }
}

function Invoke-BoundedHostEvidenceChildProcess {
    param(
        [Parameter(Mandatory = $true)]$Configuration,
        [Parameter(Mandatory = $true)][string]$AttemptId,
        [scriptblock]$AfterStartHook
    )

    $arguments = @(
        '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
        '-File', [string]$Configuration.launcher_path,
        '-ManifestPath', [string]$Configuration.manifest_path
    )
    $start = [System.Diagnostics.ProcessStartInfo]::new()
    $start.FileName = [string]$Configuration.powershell_path
    $start.Arguments = Join-WindowsCommandLineArguments -Values $arguments
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.WorkingDirectory = [System.IO.Path]::GetDirectoryName([string]$Configuration.launcher_path)

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $start
    $startedUtc = [DateTime]::UtcNow
    $started = $false
    try {
        $started = $process.Start()
        if (-not $started) {
            return [pscustomobject]@{ started = $false; settled = $true; timed_out = $false; exit_code = $null; stdout = ''; stderr = 'PROCESS_START_RETURNED_FALSE'; started_utc = $startedUtc.ToString('o'); finished_utc = [DateTime]::UtcNow.ToString('o'); process_id = $null; arguments = $start.Arguments }
        }
        if ($null -ne $AfterStartHook) { & $AfterStartHook $process }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $completed = $process.WaitForExit([int]$Configuration.timeout_ms)
        $timedOut = -not $completed
        $settled = $completed
        if ($timedOut) {
            try { $process.Kill() } catch {}
            try { $settled = $process.WaitForExit([int]$Configuration.cleanup_timeout_ms) } catch { $settled = $false }
        }
        $stdout = ''
        $stderr = ''
        $streamsSettled = $false
        try {
            $tasks = [System.Threading.Tasks.Task[]]@($stdoutTask, $stderrTask)
            $streamsSettled = [System.Threading.Tasks.Task]::WaitAll($tasks, [int]$Configuration.cleanup_timeout_ms)
        }
        catch { $streamsSettled = $false }
        if ($streamsSettled) {
            try { $stdout = $stdoutTask.GetAwaiter().GetResult() } catch { $stderr = 'STDOUT_READ_FAILED' }
            try {
                $capturedError = $stderrTask.GetAwaiter().GetResult()
                if (-not [string]::IsNullOrEmpty($capturedError)) { $stderr = $capturedError }
            }
            catch { if ([string]::IsNullOrEmpty($stderr)) { $stderr = 'STDERR_READ_FAILED' } }
        }
        else {
            $settled = $false
            $stderr = 'OUTPUT_STREAMS_UNSETTLED'
        }
        $exitCode = $null
        if ($settled) { try { $exitCode = $process.ExitCode } catch {} }
        return [pscustomobject][ordered]@{
            started = $true
            settled = [bool]$settled
            timed_out = [bool]$timedOut
            exit_code = $exitCode
            stdout = [string]$stdout
            stderr = [string]$stderr
            started_utc = $startedUtc.ToString('o')
            finished_utc = [DateTime]::UtcNow.ToString('o')
            process_id = $process.Id
            arguments = $start.Arguments
            attempt_id = $AttemptId
        }
    }
    catch {
        $runnerError = 'PROCESS_RUNNER_ERROR:{0}' -f $_.Exception.GetType().Name
        $settledAfterError = -not $started
        $exitCodeAfterError = $null
        $processIdAfterError = $null
        if ($started) {
            try { $processIdAfterError = $process.Id } catch {}
            try { $settledAfterError = [bool]$process.HasExited } catch { $settledAfterError = $false }
            if (-not $settledAfterError) {
                try { $process.Kill() } catch { $runnerError += ':CHILD_KILL_FAILED' }
                try { $settledAfterError = $process.WaitForExit([int]$Configuration.cleanup_timeout_ms) } catch { $settledAfterError = $false }
            }
            if ($settledAfterError) { try { $exitCodeAfterError = $process.ExitCode } catch {} }
        }
        return [pscustomobject]@{
            started = $started
            settled = [bool]$settledAfterError
            timed_out = $false
            exit_code = $exitCodeAfterError
            stdout = ''
            stderr = $runnerError
            started_utc = $startedUtc.ToString('o')
            finished_utc = [DateTime]::UtcNow.ToString('o')
            process_id = $processIdAfterError
            arguments = $start.Arguments
            attempt_id = $AttemptId
        }
    }
    finally { $process.Dispose() }
}

function ConvertFrom-HostLauncherResult {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Text,
        [Parameter(Mandatory = $true)][int]$ExitCode
    )
    if ([string]::IsNullOrWhiteSpace($Text)) { return [pscustomobject]@{ valid = $false; status = 'LAUNCHER_OUTPUT_EMPTY'; result = $null } }
    try { $value = $Text | ConvertFrom-Json -ErrorAction Stop }
    catch { return [pscustomobject]@{ valid = $false; status = 'LAUNCHER_OUTPUT_INVALID_JSON'; result = $null } }
    foreach ($name in @('schema', 'code', 'base_ready', 'supervisor_status', 'events', 'details')) {
        if ($null -eq $value.PSObject.Properties[$name]) { return [pscustomobject]@{ valid = $false; status = ('LAUNCHER_OUTPUT_FIELD_MISSING:{0}' -f $name); result = $null } }
    }
    if ([string]$value.schema -ne 'NEXT_STABIL_STARTUP_RESULT_V1') { return [pscustomobject]@{ valid = $false; status = 'LAUNCHER_OUTPUT_SCHEMA_INVALID'; result = $null } }
    $safe = [pscustomobject][ordered]@{
        schema = [string]$value.schema
        code = [string]$value.code
        base_ready = [bool]$value.base_ready
        supervisor_status = [string]$value.supervisor_status
        events = @($value.events)
        details = @($value.details)
    }
    if ($ExitCode -eq 0 -and ($safe.code -ne 'BASE_READY_LIMITED' -or -not $safe.base_ready -or $safe.supervisor_status -ne 'INTENTIONALLY_STOPPED')) {
        return [pscustomobject]@{ valid = $false; status = 'LAUNCHER_SUCCESS_CONTRACT_MISMATCH'; result = $safe }
    }
    return [pscustomobject]@{ valid = $true; status = 'VALID'; result = $safe }
}

function New-HostEvidenceAttemptId {
    return ('{0}-{1}' -f [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'), ([Guid]::NewGuid().ToString('N').Substring(0, 8)))
}

function Invoke-HostEvidenceCapture {
    param(
        [Parameter(Mandatory = $true)]$Configuration,
        [scriptblock]$ProcessRunner,
        $FileBoundary,
        [scriptblock]$AttemptIdFactory
    )

    if ($null -eq $ProcessRunner) { $ProcessRunner = { param($config, $attemptId) Invoke-BoundedHostEvidenceChildProcess -Configuration $config -AttemptId $attemptId } }
    if ($null -eq $FileBoundary) { $FileBoundary = New-HostEvidenceFileBoundary }
    if ($null -eq $AttemptIdFactory) { $AttemptIdFactory = { New-HostEvidenceAttemptId } }
    if (-not (Test-HostEvidenceFileBoundary -Boundary $FileBoundary)) { throw 'EVIDENCE_FILE_BOUNDARY_INVALID' }

    $attemptId = [string](& $AttemptIdFactory)
    if ($attemptId -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$') {
        return [pscustomobject]@{ recorder_status = 'ATTEMPT_ID_INVALID'; recorder_exit_code = 23; attempt_id = $attemptId; child_started = $false; evidence_path = $null }
    }
    $attemptPath = Join-Path ([string]$Configuration.evidence_root) $attemptId
    if ($attemptPath.Length -gt [int]$Configuration.max_path_characters) {
        return [pscustomobject]@{ recorder_status = 'EVIDENCE_PATH_TOO_LONG'; recorder_exit_code = 23; attempt_id = $attemptId; child_started = $false; evidence_path = $attemptPath }
    }
    if (& $FileBoundary.TestPath $attemptPath) {
        return [pscustomobject]@{ recorder_status = 'EVIDENCE_OUTPUT_COLLISION'; recorder_exit_code = 23; attempt_id = $attemptId; child_started = $false; evidence_path = $attemptPath }
    }

    $markerPath = Join-Path $attemptPath 'attempt.marker.json'
    try {
        & $FileBoundary.CreateDirectory $attemptPath
        $marker = [pscustomobject][ordered]@{
            schema = 'NEXT_STABIL_HOST_EVIDENCE_MARKER_V1'
            attempt_id = $attemptId
            created_utc = [DateTime]::UtcNow.ToString('o')
            launcher_path = [string]$Configuration.launcher_path
            manifest_path = [string]$Configuration.manifest_path
            child_started = $false
        }
        & $FileBoundary.WriteUniqueText $markerPath (($marker | ConvertTo-Json -Depth 4) + [Environment]::NewLine)
    }
    catch {
        return [pscustomobject]@{ recorder_status = 'EVIDENCE_INITIALIZATION_FAILED'; recorder_exit_code = 23; attempt_id = $attemptId; child_started = $false; evidence_path = $attemptPath }
    }

    $child = & $ProcessRunner $Configuration $attemptId
    $childStarted = [bool](Get-HostEvidenceProperty -InputObject $child -Name 'started')
    $stdout = Limit-HostEvidenceText -Text ([string](Get-HostEvidenceProperty -InputObject $child -Name 'stdout')) -MaximumCharacters ([int]$Configuration.max_stdout_characters)
    $stderr = Limit-HostEvidenceText -Text ([string](Get-HostEvidenceProperty -InputObject $child -Name 'stderr')) -MaximumCharacters ([int]$Configuration.max_stderr_characters)
    $stdoutPath = Join-Path $attemptPath 'stdout.txt'
    $stderrPath = Join-Path $attemptPath 'stderr.txt'
    $resultPath = Join-Path $attemptPath 'result.json'
    $writeFailed = $false
    try {
        & $FileBoundary.WriteUniqueText $stdoutPath $stdout.text
        & $FileBoundary.WriteUniqueText $stderrPath $stderr.text
    }
    catch { $writeFailed = $true }

    $timedOut = [bool](Get-HostEvidenceProperty -InputObject $child -Name 'timed_out')
    $settled = [bool](Get-HostEvidenceProperty -InputObject $child -Name 'settled')
    $exitCodeValue = Get-HostEvidenceProperty -InputObject $child -Name 'exit_code'
    $launcher = $null
    $status = 'LAUNCHER_RESULT_UNKNOWN'
    $recorderExitCode = 24
    if ($writeFailed) { $status = 'EVIDENCE_WRITE_FAILED' }
    elseif (-not $childStarted) { $status = 'LAUNCHER_NOT_STARTED' }
    elseif ($timedOut) { $status = 'LAUNCHER_TIMEOUT_UNKNOWN' }
    elseif (-not $settled -or $null -eq $exitCodeValue) { $status = 'LAUNCHER_PROCESS_UNSETTLED' }
    elseif ($stdout.truncated -or $stderr.truncated) { $status = 'LAUNCHER_OUTPUT_TRUNCATED' }
    elseif (-not [string]::IsNullOrEmpty($stderr.text)) { $status = 'LAUNCHER_STDERR_NONEMPTY' }
    else {
        $launcher = ConvertFrom-HostLauncherResult -Text $stdout.text -ExitCode ([int]$exitCodeValue)
        if (-not $launcher.valid) { $status = $launcher.status }
        elseif ([int]$exitCodeValue -eq 0) { $status = 'BASE_READY_LIMITED_CAPTURED'; $recorderExitCode = 0 }
        elseif ([int]$exitCodeValue -eq 22) { $status = 'LAUNCHER_REFUSED_CAPTURED'; $recorderExitCode = 22 }
        else { $status = 'LAUNCHER_EXIT_UNEXPECTED' }
    }

    $summary = [pscustomobject][ordered]@{
        schema = 'NEXT_STABIL_HOST_EVIDENCE_RESULT_V1'
        attempt_id = $attemptId
        recorder_status = $status
        recorder_exit_code = $recorderExitCode
        child_started = $childStarted
        child_settled = $settled
        child_timed_out = $timedOut
        child_process_id = Get-HostEvidenceProperty -InputObject $child -Name 'process_id'
        child_exit_code = $exitCodeValue
        started_utc = Get-HostEvidenceProperty -InputObject $child -Name 'started_utc'
        finished_utc = Get-HostEvidenceProperty -InputObject $child -Name 'finished_utc'
        stdout = [pscustomobject]@{ path = 'stdout.txt'; characters = $stdout.text.Length; original_characters = $stdout.original_characters; truncated = $stdout.truncated; sha256 = (Get-HostEvidenceSha256Text -Text $stdout.text) }
        stderr = [pscustomobject]@{ path = 'stderr.txt'; characters = $stderr.text.Length; original_characters = $stderr.original_characters; truncated = $stderr.truncated; sha256 = (Get-HostEvidenceSha256Text -Text $stderr.text) }
        launcher_result = if ($null -ne $launcher) { $launcher.result } else { $null }
        evidence_path = $attemptPath
    }
    if (-not $writeFailed) {
        try { & $FileBoundary.WriteUniqueText $resultPath (($summary | ConvertTo-Json -Depth 12) + [Environment]::NewLine) }
        catch { $summary.recorder_status = 'EVIDENCE_RESULT_WRITE_FAILED'; $summary.recorder_exit_code = 24 }
    }
    return $summary
}

if (-not $DefinitionOnly) {
    $configuration = Get-HostEvidenceProductionConfiguration
    $capture = Invoke-HostEvidenceCapture -Configuration $configuration
    $capture | ConvertTo-Json -Depth 12
    exit ([int]$capture.recorder_exit_code)
}
