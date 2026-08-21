[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$CheckpointPath,
    [Parameter(Mandatory = $true)]
    [ValidateSet("Database", "Full")]
    [string]$Mode,
    [string]$DeploymentRoot = "C:\ai-lab-core",
    [string]$OperationId = ([Guid]::NewGuid().ToString("N")),
    [switch]$ProofOnly,
    [switch]$ContinueWithoutSafetyBackup,
    [string]$SafetyOverrideToken = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$schema = "NEXT_STABIL_BACKUP_V1"
$productionApproval = "FOLLOWUP_PRODUCTION_RESTORE_APPROVAL_REQUIRED"
$fullRequired = @("postgres.dump", "document-storage.tar.gz", "release-stable.tar.gz", "qdrant.snapshot", "n8n-workflows.json", "n8n-credentials.encrypted.json", "configuration.tar.gz")
$qdrantImage = "qdrant/qdrant@sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286"
$stateRoot = Join-Path $env:ProgramData "NEXT Stabil Recovery"
$statePath = Join-Path $stateRoot "recovery-state.json"
$reportPath = Join-Path $stateRoot ("NEXT-STABIL-RECOVERY-{0}.json" -f $OperationId)
$stageRoot = Join-Path $stateRoot ("staging-{0}" -f $OperationId)
$mutex = New-Object Threading.Mutex($false, "Global\NEXT_STABIL_RECOVERY_ENGINE_V1")
$mutexHeld = $false
$cutoverStarted = $false
$safetyCheckpoint = $null
$dbProof = $null
$stages = New-Object Collections.Generic.List[object]
$started = (Get-Date).ToUniversalTime()

function Add-Stage {
    param([string]$Name, [string]$Status, [string]$Detail = "")
    $script:stages.Add([ordered]@{ stage = $Name; status = $Status; at = (Get-Date).ToUniversalTime().ToString("o"); detail = $Detail })
    Write-Output ("RECOVERY_STAGE={0}:{1}" -f $Name, $Status)
    Save-State $Name
}

function Save-State {
    param([string]$CurrentStage)
    [ordered]@{
        schema = "NEXT_STABIL_RECOVERY_STATE_V1"; operation_id = $OperationId
        checkpoint = $script:checkpoint; mode = $Mode; current_stage = $CurrentStage
        safety_backup = $script:safetyCheckpoint; staging_path = $stageRoot
        cutover_started = $script:cutoverStarted; updated_at = (Get-Date).ToUniversalTime().ToString("o")
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $statePath -Encoding UTF8
}

function Invoke-Checked {
    param([string]$FilePath, [string[]]$Arguments)
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "command_failed:${FilePath}:$LASTEXITCODE" }
}

function Assert-SafeRelative {
    param([string]$Value)
    $normalized = ([string]$Value).Replace('\', '/')
    $unsafeSegment = @($normalized.Split('/') | Where-Object { $_ -eq '..' } | Select-Object -First 1)
    if ([string]::IsNullOrWhiteSpace($Value) -or [IO.Path]::IsPathRooted($Value) -or
        $unsafeSegment.Count -ne 0 -or $Value -match '^[A-Za-z]:' -or $Value.Contains([char]0) -or $Value.Contains([char]34)) {
        throw "backup_artifact_path_invalid"
    }
}

function Assert-Archive {
    param([string]$Path)
    $entries = @(& tar.exe -tzf $Path)
    if ($LASTEXITCODE -ne 0 -or $entries.Count -eq 0) { throw "archive_integrity_failed" }
    foreach ($entry in $entries) {
        $normalized = ([string]$entry).Replace('\', '/')
        $unsafeSegment = @($normalized.Split('/') | Where-Object { $_ -eq '..' } | Select-Object -First 1)
        if ($normalized.StartsWith('/') -or $normalized -match '^[A-Za-z]:' -or $unsafeSegment.Count -ne 0 -or $normalized.Contains([char]34)) { throw "archive_path_traversal" }
    }
    return $entries
}

function Get-ArtifactMap {
    param([object]$Manifest)
    $map = @{}
    foreach ($artifact in @($Manifest.artifacts)) {
        $relative = [string]$artifact.file; Assert-SafeRelative $relative
        $full = [IO.Path]::GetFullPath((Join-Path $script:checkpoint $relative))
        if (-not $full.StartsWith($script:checkpoint + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "backup_artifact_path_invalid" }
        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { throw "backup_artifact_missing" }
        $item = Get-Item -LiteralPath $full
        if ([int64]$item.Length -ne [int64]$artifact.bytes) { throw "backup_artifact_size_mismatch" }
        if ((Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant() -ne ([string]$artifact.sha256).ToLowerInvariant()) { throw "backup_artifact_hash_mismatch" }
        if ($map.ContainsKey($item.Name)) { throw "backup_artifact_duplicate" }
        $map[$item.Name] = $full
    }
    return $map
}

function Test-DeploymentRoot {
    param([string]$Path)
    $root = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    foreach ($required in @("compose.yaml", "operations\hardening\backup-production.ps1", "compose\postgres\docker-compose.yml", "compose\qdrant\docker-compose.yml")) {
        if (-not (Test-Path -LiteralPath (Join-Path $root $required) -PathType Leaf)) { throw "deployment_root_invalid" }
    }
    return $root
}

function Restore-DatabaseToTemporary {
    param([string]$Dump, [object]$Manifest)
    $token = [Guid]::NewGuid().ToString("N").Substring(0, 12)
    $name = "ai_lab_restore_test_$token"; $containerDump = "/tmp/$name.dump"; $created = $false
    try {
        Invoke-Checked "docker.exe" @("cp", $Dump, "postgres`:$containerDump") | Out-Null
        Invoke-Checked "docker.exe" @("exec", "postgres", "createdb", "-U", "ai_lab", $name) | Out-Null; $created = $true
        Invoke-Checked "docker.exe" @("exec", "postgres", "pg_restore", "-U", "ai_lab", "-d", $name, "--no-owner", "--exit-on-error", $containerDump) | Out-Null
        $actual = (& docker.exe exec postgres psql -U ai_lab -d $name -At -c "SELECT current_database();").Trim()
        if ($LASTEXITCODE -ne 0 -or $actual -ne $name -or $actual -eq "ai_lab") { throw "restore_database_guard_failed" }
        $revision = (& docker.exe exec postgres psql -U ai_lab -d $name -At -c "SELECT version_num FROM alembic_version;").Trim()
        if ($LASTEXITCODE -ne 0 -or $revision -ne [string]$Manifest.db_revision) { throw "restore_database_revision_mismatch" }
        foreach ($table in @("clients", "users", "documents", "work_items", "projects", "change_history_events")) {
            Invoke-Checked "docker.exe" @("exec", "postgres", "psql", "-U", "ai_lab", "-d", $name, "-v", "ON_ERROR_STOP=1", "-At", "-c", "SELECT count(*) FROM $table;") | Out-Null
        }
        $invalid = (& docker.exe exec postgres psql -U ai_lab -d $name -At -c "SELECT count(*) FROM pg_constraint WHERE contype='f' AND NOT convalidated;").Trim()
        if ($LASTEXITCODE -ne 0 -or $invalid -ne "0") { throw "restore_database_fk_validation_failed" }
        return [ordered]@{ name = $name; revision = $revision; container_dump = $containerDump }
    } catch {
        if ($created) { & docker.exe exec postgres dropdb -U ai_lab --if-exists $name 2>$null | Out-Null }
        & docker.exe exec postgres rm -f $containerDump 2>$null | Out-Null
        throw
    }
}

function Remove-TemporaryDatabase {
    param([object]$Proof)
    if ($null -ne $Proof -and [string]$Proof.name -like "ai_lab_restore_test_*") {
        & docker.exe exec postgres dropdb -U ai_lab --if-exists ([string]$Proof.name) 2>$null | Out-Null
        & docker.exe exec postgres rm -f ([string]$Proof.container_dump) 2>$null | Out-Null
    }
}

function Stage-Full {
    param([hashtable]$Artifacts, [object]$Manifest)
    $documents = Join-Path $stageRoot "documents"; $configuration = Join-Path $stageRoot "configuration"; $release = Join-Path $stageRoot "release"
    New-Item -ItemType Directory -Path $documents, $configuration, $release -Force | Out-Null
    [void](Assert-Archive $Artifacts["document-storage.tar.gz"]); [void](Assert-Archive $Artifacts["configuration.tar.gz"]); [void](Assert-Archive $Artifacts["release-stable.tar.gz"])
    Invoke-Checked "tar.exe" @("-xzf", $Artifacts["document-storage.tar.gz"], "-C", $documents)
    Invoke-Checked "tar.exe" @("-xzf", $Artifacts["configuration.tar.gz"], "-C", $configuration)
    Invoke-Checked "tar.exe" @("-xzf", $Artifacts["release-stable.tar.gz"], "-C", $release)
    foreach ($name in @("documents", "document-pages", "document-assets", "archive-extracted")) {
        if (-not (Test-Path -LiteralPath (Join-Path $documents $name) -PathType Container)) { throw "document_stage_component_missing" }
    }
    [void](Get-Content -LiteralPath $Artifacts["n8n-workflows.json"] -Raw | ConvertFrom-Json)
    [void](Get-Content -LiteralPath $Artifacts["n8n-credentials.encrypted.json"] -Raw | ConvertFrom-Json)
    $expected = $Manifest.qdrant_restore_result
    $qdrantVerifier = Join-Path $PSScriptRoot "verify-qdrant-snapshot-offline.ps1"
    $qdrantJson = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $qdrantVerifier `
        -SnapshotPath $Artifacts["qdrant.snapshot"] -QdrantImage $qdrantImage `
        -ExpectedPoints ([int64]$expected.points) -ExpectedDimensions ([int]$expected.dimensions) -ExpectedDistance ([string]$expected.distance)
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($qdrantJson -join ""))) { throw "qdrant_offline_restore_failed" }
    return (($qdrantJson -join "") | ConvertFrom-Json)
}

function Invoke-SafetyBackup {
    param([string]$Root)
    $backup = Join-Path $PSScriptRoot "backup-production.ps1"
    $lines = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $backup -RepositoryRoot $Root -Scope full -Trigger pre_restore
    if ($LASTEXITCODE -ne 0) { throw "pre_restore_backup_failed" }
    $complete = @($lines | Where-Object { $_ -like "BACKUP_COMPLETE=*" } | Select-Object -Last 1)
    if ($complete.Count -ne 1) { throw "pre_restore_backup_failed" }
    return ([string]$complete[0]).Substring("BACKUP_COMPLETE=".Length)
}

function Write-RecoveryReport {
    param([string]$FinalStatus, [string]$ErrorCode = "")
    [ordered]@{
        schema = "NEXT_STABIL_RECOVERY_REPORT_V1"; operation_id = $OperationId
        started_at = $started.ToString("o"); finished_at = (Get-Date).ToUniversalTime().ToString("o")
        checkpoint = $script:checkpoint; mode = $Mode; manifest_sha256 = $script:manifestHash
        safety_backup = $script:safetyCheckpoint; cutover_started = $script:cutoverStarted
        stages = [object[]]$script:stages.ToArray(); final_status = $FinalStatus; error_code = $ErrorCode
        secrets_in_report = $false
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding UTF8
    Write-Output "RECOVERY_FINAL_STATUS=$FinalStatus"; Write-Output "RECOVERY_REPORT=$reportPath"
    if ($ErrorCode) { Write-Output "RECOVERY_ERROR=$ErrorCode" }
}

New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
try {
    try { $mutexHeld = $mutex.WaitOne(0, $false) } catch [Threading.AbandonedMutexException] { $mutexHeld = $true }
    if (-not $mutexHeld) { throw "recovery_operation_already_running" }
    $checkpoint = [IO.Path]::GetFullPath($CheckpointPath).TrimEnd('\')
    if (-not (Test-Path -LiteralPath $checkpoint -PathType Container)) { throw "checkpoint_not_found" }
    $manifestPath = Join-Path $checkpoint "backup-manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "backup_manifest_missing" }
    $manifestHash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.schema_version -ne $schema) { throw "backup_manifest_unsupported" }
    Add-Stage "preflight" "started"
    $artifacts = Get-ArtifactMap $manifest
    if (-not $artifacts.ContainsKey("postgres.dump")) { throw "backup_database_missing" }
    if ($Mode -eq "Full") { foreach ($name in $fullRequired) { if (-not $artifacts.ContainsKey($name)) { throw "backup_full_component_missing" } }; if ($manifest.qdrant_restore_verified -ne $true) { throw "qdrant_restore_verification_required" } }
    Add-Stage "preflight" "completed"

    # The development deliverable proves validation/staging only. The separate
    # destructive operational gate must provide the reviewed host-specific
    # cutover module before any live component is stopped or replaced.
    if (-not $ProofOnly) { throw "production_restore_approval_required" }

    Add-Stage "database_staging" "started"
    $dbProof = Restore-DatabaseToTemporary $artifacts["postgres.dump"] $manifest
    Add-Stage "database_staging" "completed" ([string]$dbProof.revision)
    $qdrantProof = $null
    if ($Mode -eq "Full") { Add-Stage "full_staging" "started"; $qdrantProof = Stage-Full $artifacts $manifest; Add-Stage "full_staging" "completed" }

    if ($ProofOnly) {
        Add-Stage "post_validation" "completed"
        Remove-TemporaryDatabase $dbProof
        Write-RecoveryReport "PASS"
        return
    }

}
catch {
    $code = ([string]$_.Exception.Message -split ':', 2)[0]
    try { Add-Stage "failure" "failed" $code } catch { }
    $final = if ($cutoverStarted) { "ROLLBACK REQUIRED" } else { "FAILED" }
    Write-RecoveryReport $final $code
    throw
}
finally {
    if ($ProofOnly -and $null -ne $dbProof) { try { Remove-TemporaryDatabase $dbProof } catch { } }
    if ($ProofOnly -and (Test-Path -LiteralPath $stageRoot -PathType Container)) {
        $resolvedStage = [IO.Path]::GetFullPath($stageRoot)
        $allowedStagePrefix = [IO.Path]::GetFullPath((Join-Path $stateRoot "staging-"))
        if ($resolvedStage.StartsWith($allowedStagePrefix, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedStage -Recurse -Force
        }
    }
    if ($mutexHeld) { $mutex.ReleaseMutex() }; $mutex.Dispose()
}
