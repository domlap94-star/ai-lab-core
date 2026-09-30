[CmdletBinding()]
param(
    [string]$RepositoryRoot = "C:\ai-lab-core",
    [Parameter(Mandatory = $true)]
    [string]$BackupRoot,
    [string]$Release = "1.0.2+21",
    [string]$QdrantCollection = "ai_lab_document_chunks",
    [string[]]$QdrantCollections = @(),
    [ValidateSet("LegacyV1", "RecoveryPointV2")]
    [string]$ManifestFormat = "LegacyV1",
    [ValidateSet("LegacyRestoreProof", "CaptureOnly")]
    [string]$QdrantProofMode = "LegacyRestoreProof",
    [string]$CheckpointId = "",
    [string]$RuntimeInventoryPath = "",
    [string]$DiagnosticRoot = $env:NEXT_STABIL_BACKUP_DIAGNOSTIC_ROOT,
    [ValidateSet("full", "database", "documents", "qdrant", "n8n_config")]
    [string]$Scope = "full",
    [Nullable[long]]$RunId = $null,
    [Nullable[long]]$ScheduleId = $null,
    [ValidateSet("manual", "scheduled", "pre_restore")]
    [string]$Trigger = "manual"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

function Invoke-CheckedCommand {
    param([string]$FilePath, [string[]]$Arguments)
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$FilePath failed with exit code $LASTEXITCODE." }
}

function ConvertTo-NativeArgumentString {
    param([string[]]$Arguments)
    return (($Arguments | ForEach-Object {
        if ($_ -notmatch '[\s"]') { $_ }
        else { '"' + $_.Replace('\', '\').Replace('"', '\"') + '"' }
    }) -join ' ')
}

function Get-BoundedQdrantDiagnosticText {
    param([AllowNull()][string]$Text, [int]$MaximumLength = 8192)
    if ($null -eq $Text) { return "" }
    if ($Text.Length -le $MaximumLength) { return $Text }
    return $Text.Substring(0, $MaximumLength)
}

function Invoke-QdrantHelperProcess {
    param(
        [Parameter(Mandatory = $true)][string]$HelperScript,
        [Parameter(Mandatory = $true)][string]$RequestPath,
        [Parameter(Mandatory = $true)][string]$ResultPath,
        [int]$TimeoutSeconds = 3600
    )
    foreach ($pathValue in @($HelperScript, $RequestPath, $ResultPath)) {
        if ($pathValue.Contains('"')) { throw "qdrant_helper_path_quote_rejected" }
    }
    Remove-Item -LiteralPath $ResultPath -Force -ErrorAction SilentlyContinue
    $powershell51 = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
    if (-not (Test-Path -LiteralPath $powershell51 -PathType Leaf)) { throw "qdrant_helper_powershell51_missing" }
    $arguments = @('-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', $HelperScript, '-RequestPath', $RequestPath, '-ResultPath', $ResultPath)
    $startedAt = [DateTime]::UtcNow
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $powershell51
    $start.Arguments = ConvertTo-NativeArgumentString $arguments
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    $started = $process.Start()
    if (-not $started) { throw "qdrant_helper_process_not_started" }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $timedOut = -not $process.WaitForExit(([int64]$TimeoutSeconds * 1000))
    if ($timedOut) {
        try { $process.Kill() } catch { }
        $process.WaitForExit()
    } else { $process.WaitForExit() }
    $stdout = Get-BoundedQdrantDiagnosticText ([string]$stdoutTask.Result)
    $stderr = Get-BoundedQdrantDiagnosticText ([string]$stderrTask.Result)
    $exitCode = $process.ExitCode
    $timer.Stop()
    $resultStatus = "MISSING"
    $resultStage = "RESULT_READ"
    $resultCode = "QDRANT_HELPER_RESULT_MISSING"
    $result = $null
    if (Test-Path -LiteralPath $ResultPath -PathType Leaf) {
        try {
            $result = Get-Content -LiteralPath $ResultPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ([string]$result.schema -ne 'NEXT_STABIL_QDRANT_BACKUP_HELPER_RESULT_V1') { throw "schema_mismatch" }
            $resultStatus = [string]$result.status
            $resultStage = [string]$result.stage
            $resultCode = [string]$result.code
        }
        catch {
            $result = $null
            $resultStatus = "INVALID"
            $resultStage = "RESULT_READ"
            $resultCode = "QDRANT_HELPER_RESULT_INVALID"
        }
    }
    if ($timedOut) {
        $resultStatus = "MISSING"
        $resultStage = "PROCESS_WAIT"
        $resultCode = "HELPER_TIMEOUT"
        $result = $null
    }
    return [pscustomobject][ordered]@{
        schema = 'NEXT_STABIL_QDRANT_HELPER_CAPTURE_V1'
        started = $started
        started_at = $startedAt.ToString('o')
        finished_at = [DateTime]::UtcNow.ToString('o')
        duration_ms = [int64]$timer.ElapsedMilliseconds
        timed_out = $timedOut
        exit_code = $exitCode
        stdout = $stdout
        stderr = $stderr
        result_status = $resultStatus
        stage = $resultStage
        code = $resultCode
        result = $result
    }
}

function Write-QdrantHelperEvidence {
    param([Parameter(Mandatory = $true)]$Capture, [string]$EvidenceRoot = "")
    if ([string]::IsNullOrWhiteSpace($EvidenceRoot)) { return }
    New-Item -ItemType Directory -Path $EvidenceRoot -Force | Out-Null
    [IO.File]::WriteAllText((Join-Path $EvidenceRoot 'qdrant-helper-capture.json'), (($Capture | ConvertTo-Json -Depth 12) + "`n"), (New-Object Text.UTF8Encoding($false)))
    [IO.File]::WriteAllText((Join-Path $EvidenceRoot 'qdrant-helper-stdout.txt'), ([string]$Capture.stdout), (New-Object Text.UTF8Encoding($false)))
    [IO.File]::WriteAllText((Join-Path $EvidenceRoot 'qdrant-helper-stderr.txt'), ([string]$Capture.stderr), (New-Object Text.UTF8Encoding($false)))
    if ($null -ne $Capture.result) {
        [IO.File]::WriteAllText((Join-Path $EvidenceRoot 'qdrant-helper-result.json'), (($Capture.result | ConvertTo-Json -Depth 12) + "`n"), (New-Object Text.UTF8Encoding($false)))
    }
}

function Assert-QdrantHelperProcessPass {
    param([Parameter(Mandatory = $true)]$Capture, [Parameter(Mandatory = $true)][string[]]$RequiredCollections)
    $result = $Capture.result
    $recordCollections = if ($null -eq $result) { @() } else { @($result.records | ForEach-Object { [string]$_.collection }) }
    $missingCollections = @($RequiredCollections | Where-Object { $_ -notin $recordCollections })
    $invalidRecords = @(if ($null -eq $result) { 'missing_result' } else { @($result.records | Where-Object {
        [string]::IsNullOrWhiteSpace([string]$_.snapshot_artifact) -or
        [string]::IsNullOrWhiteSpace([string]$_.checksum_artifact) -or
        [string]$_.snapshot_sha256 -notmatch '^[a-f0-9]{64}$' -or
        [string]$_.qdrant_checksum -notmatch '^[a-f0-9]{64}$' -or
        [string]$_.checksum_file_sha256 -notmatch '^[a-f0-9]{64}$' -or
        $_.structurally_valid -ne $true -or $_.helper_ready_after -ne $true
    }) })
    $passed = $Capture.started -eq $true -and $Capture.timed_out -eq $false -and $Capture.exit_code -eq 0 -and
        $Capture.result_status -eq 'PASS' -and $null -ne $result -and
        $result.helper_removed -eq $true -and $result.primary_restarted -eq $true -and $result.primary_ready -eq $true -and
        [string]$result.staging_volume -eq 'F:' -and [int]$result.helper_container_residue_count -eq 0 -and
        [int]$result.staging_residue_count -eq 0 -and $missingCollections.Count -eq 0 -and $invalidRecords.Count -eq 0
    if (-not $passed) {
        $primaryReady = if ($null -eq $result) { $false } else { $result.primary_ready }
        $helperRemoved = if ($null -eq $result) { $false } else { $result.helper_removed }
        $helperResidue = if ($null -eq $result) { -1 } else { $result.helper_container_residue_count }
        $stagingResidue = if ($null -eq $result) { -1 } else { $result.staging_residue_count }
        throw ("qdrant_backup_helper_failed stage={0} code={1} exit={2} timeout={3} primary_ready={4} helper_removed={5} helper_residue={6} staging_residue={7} missing_collections={8} invalid_records={9} stderr={10}" -f
            $Capture.stage, $Capture.code, $Capture.exit_code, $Capture.timed_out, $primaryReady,
            $helperRemoved, $helperResidue, $stagingResidue, ($missingCollections -join ','), $invalidRecords.Count, $Capture.stderr)
    }
}

function Get-PipeTransportDisposition {
    param([Parameter(Mandatory = $true)][Exception]$Exception)
    if ($Exception -isnot [IO.IOException]) {
        return [ordered]@{ disposition = "FAIL"; hresult_low_word = $null }
    }
    $code = [int]($Exception.HResult -band 0xFFFF)
    return [ordered]@{
        disposition = if ($code -in @(109, 232)) { "PIPE_EOF_CANDIDATE" } else { "FAIL" }
        hresult_low_word = $code
    }
}

function Write-BinaryTransportEvidence {
    param([string]$Path, $Record)
    if ([string]::IsNullOrWhiteSpace($Path)) { return }
    $parent = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    [IO.File]::WriteAllText(
        $Path,
        (($Record | ConvertTo-Json -Depth 8) + "`n"),
        (New-Object Text.UTF8Encoding($false))
    )
}

function Invoke-CheckedBinaryCapture {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$OutputPath,
        [int]$TimeoutSeconds = 7200,
        [string]$EvidencePath = ""
    )
    $startedAt = [DateTime]::UtcNow
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $timeoutMilliseconds = [int64]$TimeoutSeconds * 1000
    $bytesWritten = [int64]0
    $transportException = $null
    $transport = [ordered]@{ disposition = "NONE"; hresult_low_word = $null }
    $timedOut = $false
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $FilePath
    $start.Arguments = ConvertTo-NativeArgumentString $Arguments
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    if (-not $process.Start()) { throw "$FilePath failed to start." }
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $output = [IO.File]::Open($OutputPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $buffer = New-Object byte[] (1MB)
        while ($true) {
            $remaining = [int][Math]::Min([int]::MaxValue, [Math]::Max(1, $timeoutMilliseconds - $timer.ElapsedMilliseconds))
            $readTask = $process.StandardOutput.BaseStream.ReadAsync($buffer, 0, $buffer.Length)
            try {
                if (-not $readTask.Wait($remaining)) {
                    $timedOut = $true
                    break
                }
                $read = $readTask.Result
            }
            catch {
                $transportException = $_.Exception.GetBaseException()
                $transport = Get-PipeTransportDisposition $transportException
                break
            }
            if ($read -le 0) { break }
            $output.Write($buffer, 0, $read)
            $bytesWritten += [int64]$read
        }
    }
    finally {
        $output.Flush()
        $output.Dispose()
    }
    $remainingForExit = [int][Math]::Min([int]::MaxValue, [Math]::Max(1, $timeoutMilliseconds - $timer.ElapsedMilliseconds))
    if ($timedOut -or -not $process.WaitForExit($remainingForExit)) {
        $timedOut = $true
        try { $process.Kill() } catch { }
        $process.WaitForExit()
    } else {
        $process.WaitForExit()
    }
    $stderr = [string]$stderrTask.Result
    $stderrBounded = if ($stderr.Length -gt 8192) { $stderr.Substring(0, 8192) } else { $stderr }
    $exitCode = $process.ExitCode
    $timer.Stop()
    $evidence = [ordered]@{
        executable = $FilePath
        arguments = @($Arguments | ForEach-Object {
            if ($_ -match '(?i)(password|token|secret|credential)\s*=') { '[REDACTED]' } else { $_ }
        })
        started_at = $startedAt.ToString("o")
        finished_at = [DateTime]::UtcNow.ToString("o")
        duration_ms = [int64]$timer.ElapsedMilliseconds
        timed_out = $timedOut
        exit_code = $exitCode
        bytes_written = $bytesWritten
        pipe_disposition = [string]$transport.disposition
        pipe_hresult_low_word = $transport.hresult_low_word
        stderr = $stderrBounded
        output_path = $OutputPath
    }
    Write-BinaryTransportEvidence $EvidencePath $evidence
    $materialStderr = -not [string]::IsNullOrWhiteSpace($stderr) -and $stderr -match '(?i)(error|fatal|failed|panic|exception)'
    if ($timedOut -or $exitCode -ne 0 -or [string]$transport.disposition -eq "FAIL" -or $materialStderr -or
        -not (Test-Path -LiteralPath $OutputPath -PathType Leaf) -or (Get-Item -LiteralPath $OutputPath).Length -le 0) {
        Remove-Item -LiteralPath $OutputPath -Force -ErrorAction SilentlyContinue
        throw ("binary_capture_failed executable={0} exit={1} timeout={2} pipe={3}/{4} bytes={5} stderr={6}" -f
            $FilePath, $exitCode, $timedOut, $transport.disposition, $transport.hresult_low_word,
            $bytesWritten, $stderrBounded)
    }
    return [pscustomobject]$evidence
}

function Invoke-NsR26NativeProcessCapture {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [int]$TimeoutSeconds = 7200
    )
    $startedAt = [DateTime]::UtcNow
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $FilePath
    $start.Arguments = ConvertTo-NativeArgumentString $Arguments
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    $started = $false
    $timedOut = $false
    $exitCode = -1
    $stdout = ''
    $stderr = ''
    try {
        $started = $process.Start()
        if (-not $started) { throw 'N8N_EXPORT_PROCESS_FAILED' }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $timedOut = -not $process.WaitForExit(([int64]$TimeoutSeconds * 1000))
        if ($timedOut) {
            try { $process.Kill() } catch { }
            $process.WaitForExit()
        } else { $process.WaitForExit() }
        $stdout = Get-BoundedQdrantDiagnosticText -Text ([string]$stdoutTask.Result) -MaximumLength 8192
        $stderr = Get-BoundedQdrantDiagnosticText -Text ([string]$stderrTask.Result) -MaximumLength 8192
        $exitCode = $process.ExitCode
    }
    finally { $timer.Stop() }
    return [pscustomobject][ordered]@{
        executable = $FilePath
        arguments = @($Arguments)
        started = $started
        started_at = $startedAt.ToString('o')
        finished_at = [DateTime]::UtcNow.ToString('o')
        duration_ms = [int64]$timer.ElapsedMilliseconds
        timed_out = $timedOut
        exit_code = $exitCode
        stdout = $stdout
        stderr = $stderr
    }
}

function Test-NsR26N8nExportDocument {
    param(
        [Parameter(Mandatory = $true)][ValidateSet('workflow','credentials')][string]$ExportType,
        [Parameter(Mandatory = $true)][string]$Raw
    )
    $withoutBom = $Raw.TrimStart([char]0xFEFF)
    $firstMatch = [regex]::Match($withoutBom, '\S')
    $first = if ($firstMatch.Success) { [string]$firstMatch.Value } else { '' }
    if ($first -ne '[') { throw 'N8N_EXPORT_TOP_LEVEL_NOT_ARRAY' }
    try {
        Add-Type -AssemblyName System.Web.Extensions
        $serializer = New-Object Web.Script.Serialization.JavaScriptSerializer
        $serializer.MaxJsonLength = 134217728
        $document = $serializer.DeserializeObject($withoutBom)
    }
    catch { throw 'N8N_EXPORT_JSON_INVALID' }
    if ($document -isnot [System.Array]) { throw 'N8N_EXPORT_TOP_LEVEL_NOT_ARRAY' }
    $items = @($document)
    if ($items.Count -lt 1) {
        if ($ExportType -eq 'workflow') { throw 'N8N_WORKFLOW_EXPORT_SCHEMA_INVALID' }
        throw 'N8N_CREDENTIAL_EXPORT_SCHEMA_INVALID'
    }
    $ids = New-Object Collections.Generic.List[string]
    $seen = @{}
    foreach ($item in $items) {
        if ($null -eq $item) {
            if ($ExportType -eq 'workflow') { throw 'N8N_WORKFLOW_EXPORT_SCHEMA_INVALID' }
            throw 'N8N_CREDENTIAL_EXPORT_SCHEMA_INVALID'
        }
        if ($item -isnot [Collections.IDictionary]) {
            if ($ExportType -eq 'workflow') { throw 'N8N_WORKFLOW_EXPORT_SCHEMA_INVALID' }
            throw 'N8N_CREDENTIAL_EXPORT_SCHEMA_INVALID'
        }
        if ($ExportType -eq 'workflow') {
            if (-not $item.ContainsKey('id') -or -not $item.ContainsKey('name') -or -not $item.ContainsKey('nodes') -or -not $item.ContainsKey('connections') -or
                [string]::IsNullOrWhiteSpace([string]$item['id']) -or $item['nodes'] -isnot [System.Array]) {
                throw 'N8N_WORKFLOW_EXPORT_SCHEMA_INVALID'
            }
        } else {
            if (-not $item.ContainsKey('id') -or -not $item.ContainsKey('name') -or -not $item.ContainsKey('type') -or -not $item.ContainsKey('data') -or
                [string]::IsNullOrWhiteSpace([string]$item['id'])) { throw 'N8N_CREDENTIAL_EXPORT_SCHEMA_INVALID' }
            if ($item['data'] -isnot [string] -or [string]::IsNullOrWhiteSpace([string]$item['data'])) {
                throw 'N8N_CREDENTIAL_EXPORT_NOT_ENCRYPTED'
            }
        }
        $id = [string]$item['id']
        if ($seen.ContainsKey($id)) {
            if ($ExportType -eq 'workflow') { throw 'N8N_WORKFLOW_EXPORT_SCHEMA_INVALID' }
            throw 'N8N_CREDENTIAL_EXPORT_SCHEMA_INVALID'
        }
        $seen[$id] = $true
        $ids.Add($id)
    }
    $sortedIds = @($ids | Sort-Object)
    return [pscustomobject][ordered]@{
        export_type = $ExportType
        item_count = $items.Count
        id_list_sha256 = Get-TextSha256 ([string]::Join("`n", [string[]]$sortedIds))
        credential_data_encrypted = if ($ExportType -eq 'credentials') { $true } else { $null }
        first_non_whitespace = $first
    }
}

function Invoke-NsR26N8nExportToArtifact {
    param(
        [Parameter(Mandatory = $true)][ValidateSet('workflow','credentials')][string]$ExportType,
        [Parameter(Mandatory = $true)][string]$HostPartialPath,
        [Parameter(Mandatory = $true)][string]$HostFinalPath,
        [Parameter(Mandatory = $true)][string]$ContainerTemporaryPath,
        [Parameter(Mandatory = $true)][string]$DiagnosticPath,
        [int]$TimeoutSeconds = 7200,
        [int64]$MaximumBytes = 128MB,
        [string]$DockerExecutable = 'docker.exe',
        [string[]]$DockerPrefixArguments = @()
    )
    if ($ContainerTemporaryPath -notmatch '^/tmp/next-stabil-[A-Za-z0-9_.-]+\.json$') { throw 'N8N_CONTAINER_TEMP_PATH_INVALID' }
    if ($HostPartialPath -ne ($HostFinalPath + '.partial')) { throw 'N8N_HOST_PARTIAL_PATH_INVALID' }
    if ((Test-Path -LiteralPath $HostPartialPath) -or (Test-Path -LiteralPath $HostFinalPath)) { throw 'N8N_EXPORT_ARTIFACT_COLLISION' }
    $commandCapture = $null
    $copyCapture = $null
    $failureCode = ''
    $parserExceptionType = ''
    $first = ''
    $observedBytes = [int64]0
    $cleanup = [ordered]@{ remove_exit = $null; absence_exit = $null; temp_absent = $false }
    $validated = $null
    $tempOwned = $false
    try {
        $precheck = Invoke-NsR26NativeProcessCapture -FilePath $DockerExecutable -Arguments @($DockerPrefixArguments + @('exec','n8n','test','!','-e',$ContainerTemporaryPath)) -TimeoutSeconds 30
        if ($precheck.timed_out -or $precheck.exit_code -ne 0) { throw 'N8N_CONTAINER_TEMP_COLLISION' }
        $tempOwned = $true
        $exportCommand = "export:$ExportType"
        $exportArguments = @($DockerPrefixArguments + @('exec','n8n','n8n',$exportCommand,'--all',("--output={0}" -f $ContainerTemporaryPath)))
        if (@($exportArguments | Where-Object { [string]$_ -eq '--decrypted' }).Count -ne 0) { throw 'N8N_CREDENTIAL_EXPORT_NOT_ENCRYPTED' }
        $commandCapture = Invoke-NsR26NativeProcessCapture -FilePath $DockerExecutable -Arguments $exportArguments -TimeoutSeconds $TimeoutSeconds
        if ($commandCapture.timed_out) { throw 'N8N_EXPORT_TIMEOUT' }
        if (-not $commandCapture.started -or $commandCapture.exit_code -ne 0 -or
            ([string]$commandCapture.stderr -match '(?i)(fatal|panic|exception|failed|error)')) { throw 'N8N_EXPORT_PROCESS_FAILED' }
        $copyCapture = Invoke-NsR26NativeProcessCapture -FilePath $DockerExecutable -Arguments @($DockerPrefixArguments + @('cp',("n8n:{0}" -f $ContainerTemporaryPath),$HostPartialPath)) -TimeoutSeconds 300
        if ($copyCapture.timed_out -or $copyCapture.exit_code -ne 0 -or -not (Test-Path -LiteralPath $HostPartialPath -PathType Leaf)) {
            throw 'N8N_EXPORT_FILE_MISSING'
        }
        $observedBytes = [int64](Get-Item -LiteralPath $HostPartialPath).Length
        if ($observedBytes -le 0) { throw 'N8N_EXPORT_FILE_EMPTY' }
        if ($observedBytes -gt $MaximumBytes) { throw 'N8N_EXPORT_FILE_TOO_LARGE' }
        $raw = [IO.File]::ReadAllText($HostPartialPath, (New-Object Text.UTF8Encoding($false)))
        $match = [regex]::Match($raw.TrimStart([char]0xFEFF), '\S')
        $first = if ($match.Success) { [string]$match.Value } else { '' }
        try { $validated = Test-NsR26N8nExportDocument -ExportType $ExportType -Raw $raw }
        catch { $parserExceptionType = $_.Exception.GetType().FullName; throw }
        $hash = (Get-FileHash -LiteralPath $HostPartialPath -Algorithm SHA256).Hash.ToLowerInvariant()
        Move-Item -LiteralPath $HostPartialPath -Destination $HostFinalPath
        return [pscustomobject][ordered]@{
            export_type = $ExportType
            command_exit = [int]$commandCapture.exit_code
            count = [int]$validated.item_count
            bytes = $observedBytes
            sha256 = $hash
            id_list_sha256 = [string]$validated.id_list_sha256
            credential_data_encrypted = $validated.credential_data_encrypted
            container_temporary_path = $ContainerTemporaryPath
        }
    }
    catch {
        $failureCode = if ([string]$_.Exception.Message -match '^N8N_[A-Z0-9_]+$') { [string]$_.Exception.Message } else { 'N8N_EXPORT_PROCESS_FAILED' }
        Remove-Item -LiteralPath $HostPartialPath -Force -ErrorAction SilentlyContinue
        throw $failureCode
    }
    finally {
        if ($tempOwned) {
            $removeCapture = Invoke-NsR26NativeProcessCapture -FilePath $DockerExecutable -Arguments @($DockerPrefixArguments + @('exec','n8n','rm','-f','--',$ContainerTemporaryPath)) -TimeoutSeconds 30
            $absenceCapture = Invoke-NsR26NativeProcessCapture -FilePath $DockerExecutable -Arguments @($DockerPrefixArguments + @('exec','n8n','test','!','-e',$ContainerTemporaryPath)) -TimeoutSeconds 30
            $cleanup.remove_exit = [int]$removeCapture.exit_code
            $cleanup.absence_exit = [int]$absenceCapture.exit_code
            $cleanup.temp_absent = -not $absenceCapture.timed_out -and $absenceCapture.exit_code -eq 0
        }
        $diagnostic = [ordered]@{
            schema = 'NEXT_STABIL_N8N_EXPORT_EVIDENCE_V1'
            export_type = $ExportType
            stage = if ([string]::IsNullOrWhiteSpace($failureCode)) { 'COMPLETE' } else { 'FAILED' }
            code = if ([string]::IsNullOrWhiteSpace($failureCode)) { 'OK' } else { $failureCode }
            command = $commandCapture
            copy = $copyCapture
            bytes = $observedBytes
            first_non_whitespace = $first
            json_parser_exception_type = $parserExceptionType
            cleanup = $cleanup
            count = if ($null -eq $validated) { $null } else { [int]$validated.item_count }
            sha256 = if (Test-Path -LiteralPath $HostFinalPath -PathType Leaf) { (Get-FileHash -LiteralPath $HostFinalPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
            id_list_sha256 = if ($null -eq $validated) { $null } else { [string]$validated.id_list_sha256 }
            credential_data_encrypted = if ($null -eq $validated) { $null } else { $validated.credential_data_encrypted }
        }
        Write-BinaryTransportEvidence -Path $DiagnosticPath -Record $diagnostic
        if ($tempOwned -and -not $cleanup.temp_absent) {
            Remove-Item -LiteralPath $HostPartialPath -Force -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath $HostFinalPath -Force -ErrorAction SilentlyContinue
            throw 'N8N_CONTAINER_TEMP_RESIDUE'
        }
    }
}

function Invoke-CheckedFileInput {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$InputPath,
        [int]$TimeoutSeconds = 7200,
        [string]$EvidencePath = ""
    )
    $startedAt = [DateTime]::UtcNow
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $timeoutMilliseconds = [int64]$TimeoutSeconds * 1000
    $bytesRead = [int64]0
    $transportException = $null
    $transport = [ordered]@{ disposition = "NONE"; hresult_low_word = $null }
    $timedOut = $false
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $FilePath
    $start.Arguments = ConvertTo-NativeArgumentString $Arguments
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardInput = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    if (-not $process.Start()) { throw "$FilePath failed to start." }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $input = [IO.File]::OpenRead($InputPath)
    try {
        $buffer = New-Object byte[] (1MB)
        while (($read = $input.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $remaining = [int][Math]::Min([int]::MaxValue, [Math]::Max(1, $timeoutMilliseconds - $timer.ElapsedMilliseconds))
            $writeTask = $process.StandardInput.BaseStream.WriteAsync($buffer, 0, $read)
            try {
                if (-not $writeTask.Wait($remaining)) {
                    $timedOut = $true
                    break
                }
                $bytesRead += [int64]$read
            }
            catch {
                $transportException = $_.Exception.GetBaseException()
                $transport = Get-PipeTransportDisposition $transportException
                break
            }
        }
    }
    finally {
        $input.Dispose()
        try { $process.StandardInput.Close() } catch { }
    }
    $remainingForExit = [int][Math]::Min([int]::MaxValue, [Math]::Max(1, $timeoutMilliseconds - $timer.ElapsedMilliseconds))
    if ($timedOut -or -not $process.WaitForExit($remainingForExit)) {
        $timedOut = $true
        try { $process.Kill() } catch { }
        $process.WaitForExit()
    } else {
        $process.WaitForExit()
    }
    $null = $stdoutTask.Result
    $stderr = [string]$stderrTask.Result
    $stderrBounded = if ($stderr.Length -gt 8192) { $stderr.Substring(0, 8192) } else { $stderr }
    $exitCode = $process.ExitCode
    $timer.Stop()
    $evidence = [ordered]@{
        executable = $FilePath
        arguments = @($Arguments | ForEach-Object {
            if ($_ -match '(?i)(password|token|secret|credential)\s*=') { '[REDACTED]' } else { $_ }
        })
        started_at = $startedAt.ToString("o")
        finished_at = [DateTime]::UtcNow.ToString("o")
        duration_ms = [int64]$timer.ElapsedMilliseconds
        timed_out = $timedOut
        exit_code = $exitCode
        bytes_read = $bytesRead
        pipe_disposition = [string]$transport.disposition
        pipe_hresult_low_word = $transport.hresult_low_word
        stderr = $stderrBounded
        input_path = $InputPath
    }
    Write-BinaryTransportEvidence $EvidencePath $evidence
    $materialStderr = -not [string]::IsNullOrWhiteSpace($stderr) -and $stderr -match '(?i)(error|fatal|failed|panic|exception)'
    if ($timedOut -or $exitCode -ne 0 -or [string]$transport.disposition -eq "FAIL" -or $materialStderr) {
        throw ("binary_input_failed executable={0} exit={1} timeout={2} pipe={3}/{4} bytes={5} stderr={6}" -f
            $FilePath, $exitCode, $timedOut, $transport.disposition, $transport.hresult_low_word,
            $bytesRead, $stderrBounded)
    }
    return [pscustomobject]$evidence
}

function Get-DirectoryBytes {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "Required source directory does not exist: $Path"
    }
    $measurement = Get-ChildItem -LiteralPath $Path -File -Recurse -Force |
        Measure-Object -Property Length -Sum
    return [int64]$measurement.Sum
}

function Get-ArtifactRecord {
    param([string]$BasePath, [string]$Path)
    $item = Get-Item -LiteralPath $Path
    $relative = $item.FullName.Substring($BasePath.Length).TrimStart('\')
    return [ordered]@{
        file = $relative.Replace('\', '/')
        bytes = [int64]$item.Length
        sha256 = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

function Get-TextSha256 {
    param([string]$Value)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Value)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    } finally { $sha.Dispose() }
}

function Get-StorageDomainRecord {
    param([string]$DataRoot, [string]$Name)
    if ($Name -notmatch '^[a-z][a-z0-9-]{0,63}$') { throw "storage_domain_name_invalid" }
    $path = Join-Path $DataRoot $Name
    if (-not (Test-Path -LiteralPath $path -PathType Container)) { throw "storage_domain_missing:$Name" }
    $rootItem = Get-Item -LiteralPath $path
    if (($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "storage_domain_reparse_point_rejected:$Name"
    }
    $root = [IO.Path]::GetFullPath($path).TrimEnd('\')
    $prefix = $root + '\'
    [int64]$bytes = 0
    [int64]$files = 0
    foreach ($item in @(Get-ChildItem -LiteralPath $root -Recurse -Force)) {
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "storage_domain_reparse_point_rejected:$Name"
        }
        $full = [IO.Path]::GetFullPath($item.FullName)
        if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "storage_domain_path_escape:$Name"
        }
        if (-not $item.PSIsContainer) { $files++; $bytes += [int64]$item.Length }
    }
    return [ordered]@{ directory = $Name; file_count = $files; bytes = $bytes }
}

function Get-KnowledgeBaseSourceInventory {
    param([string]$DataRoot)
    $kbRoot = [IO.Path]::GetFullPath((Join-Path $DataRoot "knowledge-base")).TrimEnd('\')
    if (-not (Test-Path -LiteralPath $kbRoot -PathType Container)) { throw "knowledge_base_storage_missing" }
    $kbPrefix = $kbRoot + '\'
    $sql = "BEGIN TRANSACTION READ ONLY; SET LOCAL statement_timeout='5000ms'; SELECT COALESCE(json_agg(json_build_object('storage_path',storage_path,'file_size',file_size,'checksum_sha256',checksum_sha256) ORDER BY id),'[]'::json)::text FROM knowledge_base_items; COMMIT;"
    $lines = @(& docker.exe exec postgres psql -U ai_lab -d ai_lab -X -qAt -v ON_ERROR_STOP=1 -c $sql)
    if ($LASTEXITCODE -ne 0) { throw "knowledge_base_inventory_query_failed" }
    $jsonLines = @($lines | Where-Object { ([string]$_).TrimStart().StartsWith('[') })
    if ($jsonLines.Count -ne 1 -or ([string]$jsonLines[0]).Length -gt 4194304) {
        throw "knowledge_base_inventory_response_invalid"
    }
    try { $parsed = ([string]$jsonLines[0] | ConvertFrom-Json) }
    catch { throw "knowledge_base_inventory_response_invalid" }
    $rows = @()
    if ($null -ne $parsed) { $rows = @($parsed) }
    $referenced = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $referenceLines = New-Object Collections.Generic.List[string]
    [int64]$matched = 0
    foreach ($row in $rows) {
        $rawPath = [string]$row.storage_path
        if ([string]::IsNullOrWhiteSpace($rawPath)) { throw "knowledge_base_reference_path_invalid" }
        if ($rawPath -match '^/data(?:/|$)') {
            $relativeFromData = $rawPath.Substring(5).TrimStart('/').Replace('/', '\')
            $candidate = Join-Path $DataRoot $relativeFromData
        } elseif ([IO.Path]::IsPathRooted($rawPath)) {
            $candidate = $rawPath
        } else {
            $candidate = Join-Path $DataRoot $rawPath.Replace('/', '\')
        }
        try { $full = [IO.Path]::GetFullPath($candidate) }
        catch { throw "knowledge_base_reference_path_invalid" }
        if (-not $full.StartsWith($kbPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "knowledge_base_reference_outside_root"
        }
        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { throw "knowledge_base_reference_missing" }
        $item = Get-Item -LiteralPath $full
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "knowledge_base_reference_reparse_point_rejected"
        }
        [int64]$expectedBytes = 0
        if (-not [int64]::TryParse([string]$row.file_size, [ref]$expectedBytes) -or $expectedBytes -lt 0) {
            throw "knowledge_base_reference_size_invalid"
        }
        if ([int64]$item.Length -ne $expectedBytes) { throw "knowledge_base_reference_size_mismatch" }
        $expectedHash = ([string]$row.checksum_sha256).Trim().ToLowerInvariant()
        if ($expectedHash -notmatch '^[a-f0-9]{64}$') { throw "knowledge_base_reference_checksum_invalid" }
        $actualHash = (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash) { throw "knowledge_base_reference_hash_mismatch" }
        $relative = $full.Substring($kbPrefix.Length).Replace('\', '/')
        if ([string]::IsNullOrWhiteSpace($relative) -or $relative.Split('/') -contains '..') {
            throw "knowledge_base_reference_path_invalid"
        }
        [void]$referenced.Add($full)
        $referenceLines.Add("$relative|$expectedBytes|$expectedHash")
        $matched++
    }
    $storageLines = New-Object Collections.Generic.List[string]
    $storageFiles = @(Get-ChildItem -LiteralPath $kbRoot -File -Recurse -Force | Sort-Object FullName)
    [int64]$storageBytes = 0
    foreach ($item in $storageFiles) {
        $full = [IO.Path]::GetFullPath($item.FullName)
        if (-not $full.StartsWith($kbPrefix, [StringComparison]::OrdinalIgnoreCase) -or
            ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "knowledge_base_storage_path_invalid"
        }
        $relative = $full.Substring($kbPrefix.Length).Replace('\', '/')
        $hash = (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant()
        $storageLines.Add("$relative|$([int64]$item.Length)|$hash")
        $storageBytes += [int64]$item.Length
    }
    $referenceText = (@($referenceLines | Sort-Object) -join "`n")
    $storageText = (@($storageLines | Sort-Object) -join "`n")
    return [ordered]@{
        status = "COMPLETE"
        reference_state = if ($rows.Count -eq 0) { "EMPTY_CONFIRMED" } else { "COMPLETE" }
        reference_count = [int64]$rows.Count
        matched_reference_count = $matched
        unique_referenced_file_count = [int64]$referenced.Count
        storage_file_count = [int64]$storageFiles.Count
        storage_bytes = $storageBytes
        unreferenced_file_count = [int64]($storageFiles.Count - $referenced.Count)
        missing_count = [int64]0
        unreadable_count = [int64]0
        outside_root_count = [int64]0
        size_mismatch_count = [int64]0
        hash_mismatch_count = [int64]0
        reference_inventory_sha256 = Get-TextSha256 $referenceText
        storage_inventory_sha256 = Get-TextSha256 $storageText
    }
}

function Assert-KnowledgeBaseInventoryUnchanged {
    param([object]$Expected, [object]$Actual)
    foreach ($name in @("reference_count", "matched_reference_count", "unique_referenced_file_count", "storage_file_count", "storage_bytes", "unreferenced_file_count", "reference_inventory_sha256", "storage_inventory_sha256")) {
        if ([string]$Expected[$name] -ne [string]$Actual[$name]) { throw "knowledge_base_inventory_changed_during_capture" }
    }
}

function Get-BoundedJsonObject {
    param([string]$Path, [int64]$MaximumBytes = 1048576)
    $item = Get-Item -LiteralPath $Path
    if (-not $item.PSIsContainer -and [int64]$item.Length -gt 0 -and [int64]$item.Length -le $MaximumBytes) {
        return (Get-Content -LiteralPath $item.FullName -Raw | ConvertFrom-Json)
    }
    throw "runtime_inventory_invalid"
}

function Get-SafeQdrantCollectionName {
    param([string]$Name)
    if ([string]::IsNullOrWhiteSpace($Name) -or $Name -notmatch '^[A-Za-z0-9_-]{1,128}$') {
        throw "qdrant_collection_name_invalid"
    }
    return $Name
}

$repo = (Resolve-Path -LiteralPath $RepositoryRoot).Path.TrimEnd('\')
$toolRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..")).TrimEnd('\')
$dataRoot = (Resolve-Path -LiteralPath (Join-Path $repo "data")).Path.TrimEnd('\')
$backupBase = [System.IO.Path]::GetFullPath($BackupRoot).TrimEnd('\')
if ([IO.Path]::GetPathRoot($backupBase).TrimEnd('\').ToUpperInvariant() -in @('C:', 'D:')) {
    throw "backup_destination_system_or_data_volume_forbidden"
}
if ($backupBase.StartsWith($repo + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "BackupRoot must be outside the repository."
}
if ($backupBase.StartsWith($dataRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "BackupRoot must be outside the active data tree."
}
if (-not (Test-Path -LiteralPath $backupBase -PathType Container)) {
    throw "backup_root_missing"
}
$physicalBackupBase = (Resolve-Path -LiteralPath $backupBase).Path.TrimEnd('\')
if ([IO.Path]::GetPathRoot($physicalBackupBase).TrimEnd('\').ToUpperInvariant() -in @('C:', 'D:')) {
    throw "backup_destination_system_or_data_volume_forbidden"
}
$stamp = if ([string]::IsNullOrWhiteSpace($CheckpointId)) {
    (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
} else {
    if ($CheckpointId -notmatch '^\d{8}T\d{6}Z$') { throw "checkpoint_id_invalid" }
    $CheckpointId
}
$checkpoint = Join-Path $backupBase $stamp
$artifacts = Join-Path $checkpoint "artifacts"
$configDir = Join-Path $checkpoint "configuration"
if (Test-Path -LiteralPath $checkpoint) { throw "backup_checkpoint_collision" }

[string[]]$selectedCollections = @(
    if (@($QdrantCollections).Count -gt 0) {
        foreach ($collection in @($QdrantCollections)) {
            Get-SafeQdrantCollectionName ([string]$collection)
        }
    } else {
        Get-SafeQdrantCollectionName ([string]$QdrantCollection)
    }
)
[int]$selectedCollectionCount = @($selectedCollections).Count
if (@($selectedCollections | Select-Object -Unique).Count -ne $selectedCollectionCount) {
    throw "qdrant_collection_duplicate"
}
$requiredRecoveryCollections = @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks")
if ($ManifestFormat -eq "RecoveryPointV2") {
    if ($Scope -ne "full") { throw "recovery_point_v2_requires_full_scope" }
    if ($QdrantProofMode -ne "CaptureOnly") { throw "recovery_point_v2_capture_must_not_restore" }
    if ($selectedCollectionCount -ne $requiredRecoveryCollections.Count -or
        @($requiredRecoveryCollections | Where-Object { $_ -notin $selectedCollections }).Count -ne 0) {
        throw "recovery_point_v2_required_collections_missing"
    }
    if ([string]::IsNullOrWhiteSpace($RuntimeInventoryPath) -or
        -not (Test-Path -LiteralPath $RuntimeInventoryPath -PathType Leaf)) {
        throw "runtime_inventory_required"
    }
    $runtimeInventory = Get-BoundedJsonObject $RuntimeInventoryPath
    if ([string]$runtimeInventory.schema -ne "NEXT_STABIL_RUNTIME_INVENTORY_V1" -or
        $runtimeInventory.contains_secret_values -ne $false) {
        throw "runtime_inventory_contract_invalid"
    }
} else {
    if ($selectedCollectionCount -ne 1) { throw "legacy_manifest_requires_one_qdrant_collection" }
    $runtimeInventory = $null
}

$legacyDocumentSources = @("documents", "document-pages", "document-assets", "archive-extracted")
$documentSources = if ($ManifestFormat -eq "RecoveryPointV2") {
    @($legacyDocumentSources + "knowledge-base")
} else { @($legacyDocumentSources) }
$storageDomainRecords = @()
$knowledgeBaseInventory = $null
$estimatedBytes = [int64]0
if ($Scope -in @("full", "documents")) {
    foreach ($name in $documentSources) {
        $domain = Get-StorageDomainRecord -DataRoot $dataRoot -Name $name
        $storageDomainRecords += $domain
        $estimatedBytes += [int64]$domain.bytes
    }
    if ($ManifestFormat -eq "RecoveryPointV2") { $knowledgeBaseInventory = Get-KnowledgeBaseSourceInventory -DataRoot $dataRoot }
}
if ($Scope -eq "full") {
    $estimatedBytes += Get-DirectoryBytes -Path (Join-Path $repo "release-channel\stable")
}
$requiredFreeBytes = [int64]([math]::Ceiling($estimatedBytes * 1.35) + 2GB)
if ($ManifestFormat -eq "RecoveryPointV2") {
    $requiredFreeBytes = [math]::Max($requiredFreeBytes, [int64]40GB)
}
$driveName = [System.IO.Path]::GetPathRoot($backupBase).TrimEnd('\').TrimEnd(':')
$drive = Get-PSDrive -Name $driveName -PSProvider FileSystem
if ([int64]$drive.Free -lt $requiredFreeBytes) {
    throw "Insufficient backup space. Required at least $requiredFreeBytes bytes; available $($drive.Free)."
}

New-Item -ItemType Directory -Path $checkpoint | Out-Null

$currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
Invoke-CheckedCommand "icacls.exe" @(
    $checkpoint, "/inheritance:r", "/grant:r", "*$currentSid`:(OI)(CI)F",
    "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F", "/C"
)
New-Item -ItemType Directory -Path $artifacts | Out-Null
New-Item -ItemType Directory -Path $configDir | Out-Null

$head = (& git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw "Unable to read source HEAD." }
$toolHead = (& git -C $toolRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw "Unable to read tool source HEAD." }
$dbRevision = (& docker exec postgres psql -U ai_lab -d ai_lab -At -c "SELECT version_num FROM alembic_version;").Trim()
if ($LASTEXITCODE -ne 0) { throw "Unable to read Alembic revision." }

$artifactRecords = @()
$qdrantSnapshotName = $null
$qdrantSnapshotStructurallyValid = $null
$qdrantSnapshotValidationReason = $null
$qdrantRestoreVerified = $null
$qdrantRestoreResult = $null
$qdrantCollectionRecords = @()
$componentWindows = @()
if ($Scope -in @("full", "database")) {
    $componentStarted = (Get-Date).ToUniversalTime()
    Write-Output "BACKUP_STAGE=database"
    $dbDump = Join-Path $artifacts "postgres.dump"
    $dbDumpPartial = $dbDump + ".partial"
    $captureEvidencePath = Join-Path $configDir "postgres-dump-transport.json"
    $listEvidencePath = Join-Path $configDir "postgres-list-validation.json"
    $fullReadEvidencePath = Join-Path $configDir "postgres-full-read-validation.json"
    try {
        $captureResult = Invoke-CheckedBinaryCapture "docker.exe" @(
            "exec", "postgres", "pg_dump", "-U", "ai_lab", "-d", "ai_lab",
            "--format=custom", "--compress=6", "--no-owner"
        ) $dbDumpPartial 7200 $captureEvidencePath
        $listResult = Invoke-CheckedFileInput "docker.exe" @(
            "exec", "-i", "postgres", "pg_restore", "--list"
        ) $dbDumpPartial 7200 $listEvidencePath
        $fullReadResult = Invoke-CheckedFileInput "docker.exe" @(
            "exec", "-i", "postgres", "pg_restore", "--exit-on-error",
            "--no-owner", "--no-privileges", "--file=/dev/null"
        ) $dbDumpPartial 7200 $fullReadEvidencePath
        if ($captureResult.exit_code -ne 0 -or $listResult.exit_code -ne 0 -or $fullReadResult.exit_code -ne 0) {
            throw "postgres_archive_validation_failed"
        }
        $validatedSha256 = (Get-FileHash -LiteralPath $dbDumpPartial -Algorithm SHA256).Hash.ToLowerInvariant()
        $captureEvidence = Get-Content -LiteralPath $captureEvidencePath -Raw | ConvertFrom-Json
        $captureEvidence | Add-Member -MemberType NoteProperty -Name validator_list -Value "PASS"
        $captureEvidence | Add-Member -MemberType NoteProperty -Name validator_full_read -Value "PASS"
        $captureEvidence | Add-Member -MemberType NoteProperty -Name validated_sha256 -Value $validatedSha256
        Write-BinaryTransportEvidence $captureEvidencePath $captureEvidence
        Move-Item -LiteralPath $dbDumpPartial -Destination $dbDump
    }
    catch {
        Remove-Item -LiteralPath $dbDumpPartial -Force -ErrorAction SilentlyContinue
        throw
    }
    $artifactRecords += Get-ArtifactRecord $checkpoint $dbDump
    $componentWindows += [ordered]@{ component = "postgres"; started_at = $componentStarted.ToString("o"); finished_at = (Get-Date).ToUniversalTime().ToString("o") }
}

if ($Scope -in @("full", "documents")) {
    $componentStarted = (Get-Date).ToUniversalTime()
    Write-Output "BACKUP_STAGE=documents"
    if ($ManifestFormat -eq "RecoveryPointV2") {
        $beforeArchiveInventory = Get-KnowledgeBaseSourceInventory -DataRoot $dataRoot
        Assert-KnowledgeBaseInventoryUnchanged -Expected $knowledgeBaseInventory -Actual $beforeArchiveInventory
    }
    $documentsArchive = Join-Path $artifacts "document-storage.tar.gz"
    Invoke-CheckedCommand "tar.exe" (@("-czf", $documentsArchive, "-C", $dataRoot) + $documentSources)
    Invoke-CheckedCommand "tar.exe" @("-tzf", $documentsArchive) | Out-Null
    if ($ManifestFormat -eq "RecoveryPointV2") {
        $afterArchiveInventory = Get-KnowledgeBaseSourceInventory -DataRoot $dataRoot
        Assert-KnowledgeBaseInventoryUnchanged -Expected $knowledgeBaseInventory -Actual $afterArchiveInventory
    }
    $artifactRecords += Get-ArtifactRecord $checkpoint $documentsArchive
    $componentWindows += [ordered]@{ component = "document_storage"; started_at = $componentStarted.ToString("o"); finished_at = (Get-Date).ToUniversalTime().ToString("o") }
}

if ($Scope -eq "full") {
    $componentStarted = (Get-Date).ToUniversalTime()
    Write-Output "BACKUP_STAGE=release"
    $releaseArchive = Join-Path $artifacts "release-stable.tar.gz"
    Invoke-CheckedCommand "tar.exe" @("-czf", $releaseArchive, "-C", $repo, "release-channel/stable")
    Invoke-CheckedCommand "tar.exe" @("-tzf", $releaseArchive) | Out-Null
    $artifactRecords += Get-ArtifactRecord $checkpoint $releaseArchive
    $componentWindows += [ordered]@{ component = "release"; started_at = $componentStarted.ToString("o"); finished_at = (Get-Date).ToUniversalTime().ToString("o") }
}

if ($Scope -in @("full", "qdrant")) {
    Write-Output "BACKUP_STAGE=qdrant"
    $validator = Join-Path $toolRoot "operations\supervisor\qdrant_snapshot_validator.js"
    if (-not (Test-Path -LiteralPath $validator -PathType Leaf)) { throw "qdrant_validator_missing" }
    $helperScript = Join-Path $toolRoot "operations\hardening\invoke-qdrant-backup-helper.ps1"
    if (-not (Test-Path -LiteralPath $helperScript -PathType Leaf)) { throw "qdrant_backup_helper_missing" }
    $useExternalQdrantHelper = $true
    if ($useExternalQdrantHelper) {
        $qdrantArtifactRoot = if ($ManifestFormat -eq "RecoveryPointV2") { Join-Path $artifacts "qdrant" } else { $artifacts }
        if (-not (Test-Path -LiteralPath $qdrantArtifactRoot)) { New-Item -ItemType Directory -Path $qdrantArtifactRoot | Out-Null }
        $helperOperationId = if ($null -ne $RunId) { "schedule-$ScheduleId-run-$RunId" } else { $CheckpointId }
        $helperRequestPath = Join-Path $configDir 'qdrant-helper-request.json'
        $helperResultPath = Join-Path $configDir 'qdrant-helper-result.json'
        $helperRequest = [ordered]@{
            schema = 'NEXT_STABIL_QDRANT_BACKUP_HELPER_REQUEST_V1'
            operation_id = $helperOperationId
            backup_root = $backupBase
            artifact_root = $qdrantArtifactRoot
            collections = @($selectedCollections)
            validator_path = $validator
            helper_port = 16333
            evidence_root = $DiagnosticRoot
        }
        [IO.File]::WriteAllText($helperRequestPath, (($helperRequest | ConvertTo-Json -Depth 8) + "`n"), (New-Object Text.UTF8Encoding($false)))
        $helperCapture = Invoke-QdrantHelperProcess -HelperScript $helperScript -RequestPath $helperRequestPath -ResultPath $helperResultPath
        Write-QdrantHelperEvidence -Capture $helperCapture -EvidenceRoot $DiagnosticRoot
        Assert-QdrantHelperProcessPass -Capture $helperCapture -RequiredCollections $selectedCollections
        $helperResult = $helperCapture.result
        foreach ($record in @($helperResult.records)) {
            $artifactRecord = Get-ArtifactRecord $checkpoint ([string]$record.snapshot_artifact)
            $checksumArtifactRecord = Get-ArtifactRecord $checkpoint ([string]$record.checksum_artifact)
            $artifactRecords += $artifactRecord
            $artifactRecords += $checksumArtifactRecord
            $qdrantSnapshotName = [string]$record.snapshot_name
            $qdrantCollectionRecords += [ordered]@{ collection=[string]$record.collection;artifact_file=[string]$artifactRecord.file;checksum_artifact_file=[string]$checksumArtifactRecord.file;snapshot_name=[string]$record.snapshot_name;snapshot_created_at=$null;creation_http_status=[int]$record.creation_http_status;creation_outcome=[string]$record.creation_outcome;snapshot_sha256=[string]$record.snapshot_sha256;qdrant_checksum=[string]$record.qdrant_checksum;checksum_file_sha256=[string]$record.checksum_file_sha256;points_count=[int64]$record.points_count;indexed_vectors_count=[int64]$record.indexed_vectors_count;segments_count=[int]$record.segments_count;vectors=$record.config.params.vectors;shard_number=$record.config.params.shard_number;replication_factor=$record.config.params.replication_factor;write_consistency_factor=$record.config.params.write_consistency_factor;on_disk_payload=$record.config.params.on_disk_payload;aliases=@($record.aliases);structurally_valid=$true;structural_validation_reason=[string]$record.structural_validation_reason;restore_status='NOT_RUN_BY_POLICY';restore_verified=$false }
            $componentWindows += [ordered]@{component="qdrant:$($record.collection)";started_at=$null;finished_at=(Get-Date).ToUniversalTime().ToString('o')}
        }
        $qdrantSnapshotStructurallyValid = $true
        $qdrantSnapshotValidationReason = 'valid_external_f_staging'
        $qdrantRestoreVerified = $false
        $qdrantRestoreResult = $null
    } else {
    if ($ManifestFormat -eq "RecoveryPointV2") {
        $qdrantArtifactRoot = Join-Path $artifacts "qdrant"
        New-Item -ItemType Directory -Path $qdrantArtifactRoot | Out-Null
    }
    foreach ($collection in $selectedCollections) {
        $componentStarted = (Get-Date).ToUniversalTime()
        $collectionInfo = Invoke-RestMethod -Uri "http://127.0.0.1:6333/collections/$collection" -TimeoutSec 30
        if ($collectionInfo.status -ne "ok" -or $null -eq $collectionInfo.result) { throw "qdrant_collection_unavailable" }
        $aliasesResponse = Invoke-RestMethod -Uri "http://127.0.0.1:6333/collections/$collection/aliases" -TimeoutSec 30
        if ($aliasesResponse.status -ne "ok") { throw "qdrant_alias_inventory_failed" }
        $qdrantResponse = Invoke-RestMethod -Method Post `
            -Uri "http://127.0.0.1:6333/collections/$collection/snapshots" -TimeoutSec 900
        if ($qdrantResponse.status -ne "ok" -or [string]::IsNullOrWhiteSpace($qdrantResponse.result.name)) {
            throw "qdrant_snapshot_create_failed"
        }
        $snapshotName = [string]$qdrantResponse.result.name
        $qdrantSnapshotName = $snapshotName
        $artifactLeaf = if ($ManifestFormat -eq "RecoveryPointV2") { "$collection.snapshot" } else { "qdrant.snapshot" }
        $qdrantSnapshot = if ($ManifestFormat -eq "RecoveryPointV2") {
            Join-Path $qdrantArtifactRoot $artifactLeaf
        } else { Join-Path $artifacts $artifactLeaf }
        try {
            Invoke-CheckedCommand "curl.exe" @(
                "--fail", "--silent", "--show-error", "--location", "--max-time", "900",
                "--output", $qdrantSnapshot,
                "http://127.0.0.1:6333/collections/$collection/snapshots/$snapshotName"
            )
            $validationJson = (& node.exe $validator $qdrantSnapshot 2>$null)
            $validatorExit = $LASTEXITCODE
            if ([string]::IsNullOrWhiteSpace(($validationJson -join ""))) { throw "qdrant_snapshot_validation_failed" }
            $validation = ($validationJson -join "") | ConvertFrom-Json
            $structurallyValid = $validatorExit -eq 0 -and $validation.valid -eq $true
            if (-not $structurallyValid) { throw "qdrant_snapshot_invalid" }
        } finally {
            Invoke-RestMethod -Method Delete -Uri "http://127.0.0.1:6333/collections/$collection/snapshots/$snapshotName" -TimeoutSec 30 | Out-Null
        }
        $artifactRecord = Get-ArtifactRecord $checkpoint $qdrantSnapshot
        $artifactRecords += $artifactRecord
        $vectors = $collectionInfo.result.config.params.vectors
        $qdrantCollectionRecords += [ordered]@{
            collection = $collection
            artifact_file = [string]$artifactRecord.file
            snapshot_name = $snapshotName
            snapshot_created_at = [string]$qdrantResponse.result.creation_time
            points_count = [int64]$collectionInfo.result.points_count
            indexed_vectors_count = [int64]$collectionInfo.result.indexed_vectors_count
            segments_count = [int]$collectionInfo.result.segments_count
            vectors = $vectors
            shard_number = $collectionInfo.result.config.params.shard_number
            replication_factor = $collectionInfo.result.config.params.replication_factor
            write_consistency_factor = $collectionInfo.result.config.params.write_consistency_factor
            on_disk_payload = $collectionInfo.result.config.params.on_disk_payload
            aliases = @($aliasesResponse.result.aliases | ForEach-Object { [string]$_.alias_name })
            structurally_valid = $true
            structural_validation_reason = [string]$validation.reason
            restore_status = if ($QdrantProofMode -eq "CaptureOnly") { "NOT_RUN_WAITING_APPROVAL" } else { "PENDING_LEGACY_PROOF" }
            restore_verified = $false
        }
        $componentWindows += [ordered]@{ component = "qdrant:$collection"; started_at = $componentStarted.ToString("o"); finished_at = (Get-Date).ToUniversalTime().ToString("o") }
    }
    $qdrantSnapshotStructurallyValid = @($qdrantCollectionRecords | Where-Object { $_.structurally_valid -ne $true }).Count -eq 0
    $qdrantSnapshotValidationReason = if ($qdrantSnapshotStructurallyValid) { "valid" } else { "qdrant_snapshot_invalid" }
    if ($QdrantProofMode -eq "LegacyRestoreProof") {
        Write-Output "BACKUP_STAGE=qdrant_restore_drill"
        $qdrantImage = (& docker.exe inspect qdrant --format '{{.Config.Image}}').Trim()
        if ($LASTEXITCODE -ne 0) { throw "qdrant_image_inspection_failed" }
        $restoreVerifier = Join-Path $toolRoot "operations\hardening\verify-qdrant-snapshot-restore.ps1"
        try {
            $restoreJson = (& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass `
                -File $restoreVerifier -SnapshotPath $qdrantSnapshot `
                -SourceCollection $selectedCollections[0] -QdrantImage $qdrantImage 2>$null)
            if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace(($restoreJson -join ""))) {
                $qdrantRestoreResult = ($restoreJson -join "") | ConvertFrom-Json
                $qdrantRestoreVerified = $qdrantRestoreResult.verified -eq $true
            } else { $qdrantRestoreVerified = $false }
        } catch { $qdrantRestoreVerified = $false }
    } else {
        $qdrantRestoreVerified = $false
        $qdrantRestoreResult = $null
    }
    }
}

if ($Scope -in @("full", "n8n_config")) {
    $componentStarted = (Get-Date).ToUniversalTime()
    Write-Output "BACKUP_STAGE=n8n"
    $n8nWorkflows = Join-Path $artifacts "n8n-workflows.json"
    $n8nCredentials = Join-Path $artifacts "n8n-credentials.encrypted.json"
    $safeN8nId = $stamp -replace '[^A-Za-z0-9_.-]', '-'
    $workflowContainerTemp = "/tmp/next-stabil-$safeN8nId-workflows.json"
    $credentialContainerTemp = "/tmp/next-stabil-$safeN8nId-credentials.json"
    $n8nWorkflowEvidence = Invoke-NsR26N8nExportToArtifact -ExportType workflow `
        -HostPartialPath ($n8nWorkflows + '.partial') -HostFinalPath $n8nWorkflows `
        -ContainerTemporaryPath $workflowContainerTemp -DiagnosticPath (Join-Path $configDir 'n8n-workflow-export.json')
    $n8nCredentialEvidence = Invoke-NsR26N8nExportToArtifact -ExportType credentials `
        -HostPartialPath ($n8nCredentials + '.partial') -HostFinalPath $n8nCredentials `
        -ContainerTemporaryPath $credentialContainerTemp -DiagnosticPath (Join-Path $configDir 'n8n-credential-export.json')
    if ($n8nWorkflowEvidence.count -lt 1 -or $n8nCredentialEvidence.count -lt 1 -or
        $n8nCredentialEvidence.credential_data_encrypted -ne $true) { throw 'N8N_EXPORT_POSTCONDITION_FAILED' }
    $artifactRecords += Get-ArtifactRecord $checkpoint $n8nWorkflows
    $artifactRecords += Get-ArtifactRecord $checkpoint $n8nCredentials
    $componentWindows += [ordered]@{ component = "n8n_exports"; started_at = $componentStarted.ToString("o"); finished_at = (Get-Date).ToUniversalTime().ToString("o") }
}

if ($Scope -in @("full", "n8n_config")) {
    $componentStarted = (Get-Date).ToUniversalTime()
    Write-Output "BACKUP_STAGE=configuration"
    $configFiles = @(
        "compose.yaml", "compose/backend/docker-compose.yml", "compose/postgres/docker-compose.yml",
        "compose/qdrant/docker-compose.yml", "compose/ollama/docker-compose.yml",
        "compose/n8n/docker-compose.yml", "compose/open-webui/docker-compose.yml",
        "backend/Dockerfile", "backend/requirements.txt", "release-channel/stable/manifest.json"
    )
    foreach ($relative in $configFiles) {
        $source = Join-Path $repo $relative
        $destination = Join-Path $configDir $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination
    }

    # Inventory setting names from tracked specifications only. Never open the
    # runtime .env while producing a capture: A1 authorizes neither plaintext
    # secret access nor an environment-value inventory.
    $envNamesPath = Join-Path $configDir "required-env-names.txt"
    $requiredEnvNames = @()
    $settingsSpec = Join-Path $repo "backend\app\core\config.py"
    if (Test-Path -LiteralPath $settingsSpec -PathType Leaf) {
        foreach ($line in Get-Content -LiteralPath $settingsSpec) {
            if ($line -match '^\s{4}@computed_field') { break }
            if ($line -match '^\s{4}([a-z][a-z0-9_]*)\s*:') {
                $requiredEnvNames += $Matches[1].ToUpperInvariant()
            }
        }
    }
    foreach ($relative in $configFiles) {
        $source = Join-Path $repo $relative
        foreach ($line in Get-Content -LiteralPath $source) {
            foreach ($match in [regex]::Matches($line, '\$\{([A-Za-z_][A-Za-z0-9_]*)')) {
                $requiredEnvNames += $match.Groups[1].Value.ToUpperInvariant()
            }
            if ($line -match '^\s*-\s*([A-Z_][A-Z0-9_]*)=') {
                $requiredEnvNames += $Matches[1].ToUpperInvariant()
            }
            elseif ($line -match '^\s*([A-Z_][A-Z0-9_]*)\s*:') {
                $requiredEnvNames += $Matches[1].ToUpperInvariant()
            }
        }
    }
    $requiredEnvNames | Sort-Object -Unique |
        Set-Content -LiteralPath $envNamesPath -Encoding UTF8

    $imageInventory = @()
    foreach ($containerName in @("postgres", "qdrant", "ollama", "n8n", "open-webui", "ai-lab-backend")) {
        $configuredImage = (& docker.exe inspect $containerName --format '{{.Config.Image}}').Trim()
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($configuredImage)) {
            throw "Unable to inspect configured image for $containerName."
        }
        $imageId = (& docker.exe inspect $containerName --format '{{.Image}}').Trim()
        if ($LASTEXITCODE -ne 0 -or $imageId -notmatch '^sha256:[a-f0-9]{64}$') {
            throw "Unable to inspect image identity for $containerName."
        }
        $repoDigestsJson = (& docker.exe image inspect $imageId --format '{{json .RepoDigests}}').Trim()
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($repoDigestsJson)) {
            throw "Unable to inspect image digests for $containerName."
        }
        $repoDigests = @($repoDigestsJson | ConvertFrom-Json)
        $imageInventory += [ordered]@{
            container = $containerName; configured_image = $configuredImage
            image_id = $imageId; repo_digests = $repoDigests
        }
    }
    $imageInventory | ConvertTo-Json -Depth 6 |
        Set-Content -LiteralPath (Join-Path $configDir "runtime-images.json") -Encoding UTF8

    $configArchive = Join-Path $artifacts "configuration.tar.gz"
    Invoke-CheckedCommand "tar.exe" @("-czf", $configArchive, "-C", $checkpoint, "configuration")
    Invoke-CheckedCommand "tar.exe" @("-tzf", $configArchive) | Out-Null
    $artifactRecords += Get-ArtifactRecord $checkpoint $configArchive
    $componentWindows += [ordered]@{ component = "configuration"; started_at = $componentStarted.ToString("o"); finished_at = (Get-Date).ToUniversalTime().ToString("o") }
}

if ($ManifestFormat -eq "RecoveryPointV2") {
    $runtimeArtifact = Join-Path $artifacts "runtime-inventory.json"
    Copy-Item -LiteralPath (Resolve-Path -LiteralPath $RuntimeInventoryPath).Path -Destination $runtimeArtifact
    [void](Get-BoundedJsonObject $runtimeArtifact)
    $artifactRecords += Get-ArtifactRecord $checkpoint $runtimeArtifact
}

$manifest = [ordered]@{
    schema_version = if ($ManifestFormat -eq "RecoveryPointV2") { "NEXT_STABIL_BACKUP_V2" } else { "NEXT_STABIL_BACKUP_V1" }
    scope = $Scope
    run_id = $RunId
    schedule_id = $ScheduleId
    trigger = $Trigger
    app_version = $Release
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    source_head = $head; tool_source_head = $toolHead; release = $Release; db_revision = $dbRevision
    qdrant_collection = $QdrantCollection; qdrant_snapshot_name = $qdrantSnapshotName
    qdrant_collections = if ($ManifestFormat -eq "RecoveryPointV2") { $qdrantCollectionRecords } else { @() }
    required_qdrant_collections = if ($ManifestFormat -eq "RecoveryPointV2") { $requiredRecoveryCollections } else { @() }
    artifact_hash_verified = $true
    qdrant_snapshot_structurally_valid = $qdrantSnapshotStructurallyValid
    qdrant_snapshot_validation_reason = $qdrantSnapshotValidationReason
    # Artifact/hash verification is not equivalent to an isolated Qdrant
    # recovery proof. Full restore stays fail-closed until that proof succeeds.
    qdrant_restore_verified = $qdrantRestoreVerified
    qdrant_restore_result = $qdrantRestoreResult
    qdrant_restore_error_code = if ($Scope -in @("full", "qdrant")) {
        if ($qdrantSnapshotStructurallyValid -eq $false) { "qdrant_snapshot_invalid" }
        elseif ($qdrantRestoreVerified -eq $true) { $null }
        elseif ($QdrantProofMode -eq "CaptureOnly") { "qdrant_restore_not_run_waiting_approval" }
        else { "qdrant_restore_drill_failed" }
    } else { $null }
    document_directories = if ($Scope -in @("full", "documents")) { $documentSources } else { @() }
    storage_contract_version = if ($ManifestFormat -eq "RecoveryPointV2") { "NEXT_STABIL_STORAGE_COVERAGE_V1" } else { $null }
    storage_coverage = if ($ManifestFormat -eq "RecoveryPointV2") {
        [ordered]@{
            status = "COMPLETE"
            required_domains = $documentSources
            domains = $storageDomainRecords
            knowledge_base = $knowledgeBaseInventory
        }
    } else { $null }
    estimated_source_bytes = $estimatedBytes
    capture_status = if ($ManifestFormat -eq "RecoveryPointV2") { "COMPLETE" } else { $null }
    scope_status = if ($ManifestFormat -eq "RecoveryPointV2") { "COMPLETE" } else { $null }
    provenance_status = if ($ManifestFormat -eq "RecoveryPointV2") { "RECORDED" } else { $null }
    consistency_status = if ($ManifestFormat -eq "RecoveryPointV2") { "COMPONENT_WINDOWS_RECORDED_NON_TRANSACTIONAL" } else { $null }
    component_windows = $componentWindows
    restore_status = if ($ManifestFormat -eq "RecoveryPointV2") { "NOT_RUN_WAITING_APPROVAL" } else { $null }
    escrow_status = if ($ManifestFormat -eq "RecoveryPointV2") { "NOT_RUN_WAITING_OWNER_DECISION" } else { $null }
    rto_status = if ($ManifestFormat -eq "RecoveryPointV2") { "NOT_MEASURED" } else { $null }
    secrets_in_protected_backup = $false
    secrets_note = "Encrypted n8n credential export is included; the separately protected environment secret escrow is required for credential recovery."
    artifacts = $artifactRecords
}
$manifestPartial = Join-Path $checkpoint "backup-manifest.json.partial"
$manifestPath = Join-Path $checkpoint "backup-manifest.json"
Write-Output "BACKUP_STAGE=verifying"
$requiredArtifacts = if ($ManifestFormat -eq "RecoveryPointV2") {
    @("postgres.dump", "document-storage.tar.gz", "release-stable.tar.gz", "n8n-workflows.json", "n8n-credentials.encrypted.json", "configuration.tar.gz", "runtime-inventory.json") +
        @($requiredRecoveryCollections | ForEach-Object { "$_.snapshot" }) +
        @($requiredRecoveryCollections | ForEach-Object { "$_.snapshot.checksum" })
} else { @() }
if ($ManifestFormat -eq "RecoveryPointV2") {
    $artifactNames = @($artifactRecords | ForEach-Object { Split-Path -Leaf ([string]$_.file) })
    foreach ($requiredArtifact in $requiredArtifacts) {
        if ($requiredArtifact -notin $artifactNames) { throw "recovery_point_v2_artifact_missing" }
    }
    foreach ($record in $artifactRecords) {
        $absolute = [IO.Path]::GetFullPath((Join-Path $checkpoint ([string]$record.file).Replace('/', '\')))
        if (-not $absolute.StartsWith($checkpoint + '\', [StringComparison]::OrdinalIgnoreCase) -or
            (Get-FileHash -LiteralPath $absolute -Algorithm SHA256).Hash.ToLowerInvariant() -ne [string]$record.sha256) {
            throw "backup_final_hash_verification_failed"
        }
    }
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPartial -Encoding UTF8
Move-Item -LiteralPath $manifestPartial -Destination $manifestPath

Write-Output ("BACKUP_COMPLETE={0}" -f $checkpoint)
Write-Output ("MANIFEST={0}" -f $manifestPath)
