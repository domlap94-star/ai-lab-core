[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$CheckpointPath,
    [Parameter(Mandatory = $true)]
    [ValidateSet("Database", "Full")]
    [string]$Mode,
    [string]$DeploymentRoot = "C:\ai-lab-core",
    [string]$OperationId = ([Guid]::NewGuid().ToString("N")),
    [string]$ProofPostgresContainer = "",
    [string]$ProofPostgresUser = "postgres",
    [string]$ProofTargetOwner = "",
    [string]$ProofQdrantClientImage = "",
    [string]$ProofStateRoot = "",
    [switch]$ValidateOnly,
    [switch]$ProofOnly,
    [switch]$ContinueWithoutSafetyBackup,
    [string]$SafetyOverrideToken = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$legacySchema = "NEXT_STABIL_BACKUP_V1"
$recoveryPointSchema = "NEXT_STABIL_BACKUP_V2"
$productionApproval = "FOLLOWUP_PRODUCTION_RESTORE_APPROVAL_REQUIRED"
$legacyFullRequired = @("postgres.dump", "document-storage.tar.gz", "release-stable.tar.gz", "qdrant.snapshot", "n8n-workflows.json", "n8n-credentials.encrypted.json", "configuration.tar.gz")
$v2BaseRequired = @("postgres.dump", "document-storage.tar.gz", "release-stable.tar.gz", "n8n-workflows.json", "n8n-credentials.encrypted.json", "configuration.tar.gz", "runtime-inventory.json")
$v2RequiredCollections = @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks")
$qdrantImage = "qdrant/qdrant@sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286"
$stateRoot = if ($ProofOnly) {
    if ([string]::IsNullOrWhiteSpace($ProofStateRoot)) { throw "proof_state_root_required" }
    $candidate = [IO.Path]::GetFullPath($ProofStateRoot).TrimEnd('\')
    if ((Split-Path -Leaf $candidate) -notmatch '^next-stabil-r03-a1-(test|drill)-[a-z0-9-]{8,96}-state$') {
        throw "proof_state_root_rejected"
    }
    $candidate
} else { Join-Path $env:ProgramData "NEXT Stabil Recovery" }
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
    if (-not $ValidateOnly) { Save-State $Name }
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

function Get-Sha256 {
    param([string]$Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $sha.Dispose() }
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
        if ((Get-Sha256 $full) -ne ([string]$artifact.sha256).ToLowerInvariant()) { throw "backup_artifact_hash_mismatch" }
        if ($map.ContainsKey($item.Name)) { throw "backup_artifact_duplicate" }
        $map[$item.Name] = $full
    }
    return $map
}

function Test-PostgresArchive {
    param([string]$Path)
    $stream = [IO.File]::OpenRead($Path)
    try {
        $header = New-Object byte[] 5
        if ($stream.Read($header, 0, 5) -ne 5) { return $false }
        return [Text.Encoding]::ASCII.GetString($header) -eq "PGDMP"
    } finally { $stream.Dispose() }
}

function Get-Compatibility {
    param([object]$Manifest)
    $currentVersion = [Version]"1.0.2"
    $rawVersion = [string]$Manifest.app_version
    if ([string]::IsNullOrWhiteSpace($rawVersion)) { $rawVersion = [string]$Manifest.release }
    $baseVersion = ($rawVersion -split '\+', 2)[0]
    $parsed = $null
    if (-not [Version]::TryParse($baseVersion, [ref]$parsed)) { return "invalid" }
    if ($parsed -gt $currentVersion) { return "newer_unsupported_checkpoint" }
    if ([string]$Manifest.db_revision -eq "followup_admin_backup_restore_ui_20260821") { return "compatible" }
    if ([string]::IsNullOrWhiteSpace([string]$Manifest.db_revision)) { return "invalid" }
    if ($parsed -lt $currentVersion) { return "older_supported_checkpoint" }
    return "requires_migration_after_restore"
}

function Test-QdrantStructure {
    param([string]$Snapshot)
    $validator = Join-Path $PSScriptRoot "..\supervisor\qdrant_snapshot_validator.js"
    $validator = [IO.Path]::GetFullPath($validator)
    if (-not (Test-Path -LiteralPath $validator -PathType Leaf)) { throw "qdrant_validator_missing" }
    $json = & node.exe $validator $Snapshot
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($json -join ""))) { throw "qdrant_validator_failed" }
    return (($json -join "") | ConvertFrom-Json)
}

function Test-DeploymentRoot {
    param([string]$Path)
    $root = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    foreach ($required in @("compose.yaml", "operations\hardening\backup-production.ps1", "compose\postgres\docker-compose.yml", "compose\qdrant\docker-compose.yml")) {
        if (-not (Test-Path -LiteralPath (Join-Path $root $required) -PathType Leaf)) { throw "deployment_root_invalid" }
    }
    return $root
}

function Get-ManifestStatus {
    param([object]$Manifest, [string]$Name, [bool]$Required)
    $property = $Manifest.PSObject.Properties[$Name]
    if ($null -eq $property -or $null -eq $property.Value -or
        [string]::IsNullOrWhiteSpace([string]$property.Value)) {
        if ($Required) { throw "backup_manifest_v2_status_missing:$Name" }
        return $null
    }
    return [string]$property.Value
}

function Assert-IsolatedPostgresTarget {
    param([string]$Container, [string]$Owner)
    if ([string]::IsNullOrWhiteSpace($Container) -or [string]::IsNullOrWhiteSpace($Owner)) {
        throw "proof_target_required"
    }
    if ($Container -in @("postgres", "ai-lab-backend", "qdrant", "n8n") -or
        $Container -notmatch '^next-stabil-r03-a1-(test|drill)-[a-z0-9-]{8,80}-postgres$') {
        throw "proof_target_name_rejected"
    }
    if ($Owner -notmatch '^next-stabil-r03-a1-(test|drill)-[a-z0-9-]{8,80}$') {
        throw "proof_target_owner_invalid"
    }
    $name = (& docker.exe inspect $Container --format '{{.Name}}').Trim().TrimStart('/')
    if ($LASTEXITCODE -ne 0 -or $name -ne $Container) { throw "proof_postgres_target_missing" }
    $labels = ((& docker.exe inspect $Container --format '{{json .Config.Labels}}') -join "") | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or [string]$labels.'next.stabil.owner' -ne $Owner -or
        [string]$labels.'next.stabil.purpose' -ne "r03-isolated-proof") {
        throw "proof_target_ownership_invalid"
    }
    $privileged = (& docker.exe inspect $Container --format '{{.HostConfig.Privileged}}').Trim()
    if ($LASTEXITCODE -ne 0 -or $privileged -ne "false") { throw "proof_target_privileged_rejected" }
    $portsText = ((& docker.exe inspect $Container --format '{{json .HostConfig.PortBindings}}') -join "").Trim()
    if ($LASTEXITCODE -ne 0 -or $portsText -notin @("null", "{}")) { throw "proof_target_host_ports_rejected" }
    $networkMode = (& docker.exe inspect $Container --format '{{.HostConfig.NetworkMode}}').Trim()
    if ($LASTEXITCODE -ne 0 -or $networkMode -in @("", "default", "bridge", "host", "none") -or
        $networkMode -notmatch '^next-stabil-r03-a1-(test|drill)-[a-z0-9-]{8,80}-network$') {
        throw "proof_target_network_rejected"
    }
    $networkInternal = (& docker.exe network inspect $networkMode --format '{{.Internal}}').Trim()
    $networkLabels = ((& docker.exe network inspect $networkMode --format '{{json .Labels}}') -join "") | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $networkInternal -ne "true" -or
        [string]$networkLabels.'next.stabil.owner' -ne $Owner) {
        throw "proof_target_network_not_isolated"
    }
    $networks = ((& docker.exe inspect $Container --format '{{json .NetworkSettings.Networks}}') -join "") | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or @($networks.PSObject.Properties).Count -ne 1 -or
        @($networks.PSObject.Properties)[0].Name -ne $networkMode) {
        throw "proof_target_network_membership_invalid"
    }
    $mountJson = ((& docker.exe inspect $Container --format '{{json .Mounts}}') -join "")
    $mountValue = $mountJson | ConvertFrom-Json
    $mounts = @()
    if ($null -ne $mountValue) { $mounts = @($mountValue) }
    if ($LASTEXITCODE -ne 0 -or $mounts.Count -ne 1) { throw "proof_target_mount_invalid" }
    $mount = $mounts[0]
    if ([string]$mount.Type -ne "volume" -or [string]$mount.Destination -ne "/var/lib/postgresql/data" -or
        [string]$mount.Name -notmatch '^next-stabil-r03-a1-(test|drill)-[a-z0-9-]{8,80}-postgres-data$') {
        throw "proof_target_mount_invalid"
    }
    $volumeLabels = ((& docker.exe volume inspect ([string]$mount.Name) --format '{{json .Labels}}') -join "") | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or [string]$volumeLabels.'next.stabil.owner' -ne $Owner) {
        throw "proof_target_volume_ownership_invalid"
    }
}

function Get-V2QdrantRecords {
    param([object]$Manifest, [hashtable]$Artifacts)
    $records = @($Manifest.qdrant_collections)
    if ($records.Count -ne $v2RequiredCollections.Count) { throw "backup_qdrant_collection_coverage_invalid" }
    $names = @($records | ForEach-Object { [string]$_.collection })
    if (@($names | Select-Object -Unique).Count -ne $names.Count -or
        @($v2RequiredCollections | Where-Object { $_ -notin $names }).Count -ne 0) {
        throw "backup_qdrant_collection_coverage_invalid"
    }
    foreach ($record in $records) {
        $file = [string]$record.artifact_file
        Assert-SafeRelative $file
        $leaf = Split-Path -Leaf $file
        if ([string]::IsNullOrWhiteSpace($leaf) -or -not $Artifacts.ContainsKey($leaf)) {
            throw "backup_qdrant_artifact_binding_invalid"
        }
        $expectedRelative = [IO.Path]::GetFullPath((Join-Path $script:checkpoint $file))
        if ($Artifacts[$leaf] -ne $expectedRelative) { throw "backup_qdrant_artifact_binding_invalid" }
        if ($record.structurally_valid -ne $true) { throw "backup_qdrant_structure_status_invalid" }
    }
    return $records
}

function Restore-DatabaseToTemporary {
    param([string]$Dump, [object]$Manifest, [string]$Container, [string]$DatabaseUser)
    $token = [Guid]::NewGuid().ToString("N").Substring(0, 12)
    $name = "ai_lab_restore_test_$token"; $containerDump = "/tmp/$name.dump"; $created = $false
    try {
        Invoke-Checked "docker.exe" @("cp", $Dump, "${Container}:$containerDump") | Out-Null
        Invoke-Checked "docker.exe" @("exec", $Container, "createdb", "-U", $DatabaseUser, $name) | Out-Null; $created = $true
        Invoke-Checked "docker.exe" @("exec", $Container, "pg_restore", "-U", $DatabaseUser, "-d", $name, "--no-owner", "--exit-on-error", $containerDump) | Out-Null
        $actual = (& docker.exe exec $Container psql -U $DatabaseUser -d $name -At -c "SELECT current_database();").Trim()
        if ($LASTEXITCODE -ne 0 -or $actual -ne $name -or $actual -eq "ai_lab") { throw "restore_database_guard_failed" }
        $revision = (& docker.exe exec $Container psql -U $DatabaseUser -d $name -At -c "SELECT version_num FROM alembic_version;").Trim()
        if ($LASTEXITCODE -ne 0 -or $revision -ne [string]$Manifest.db_revision) { throw "restore_database_revision_mismatch" }
        foreach ($table in @("clients", "users", "documents", "work_items", "projects", "change_history_events")) {
            Invoke-Checked "docker.exe" @("exec", $Container, "psql", "-U", $DatabaseUser, "-d", $name, "-v", "ON_ERROR_STOP=1", "-At", "-c", "SELECT count(*) FROM $table;") | Out-Null
        }
        $invalid = (& docker.exe exec $Container psql -U $DatabaseUser -d $name -At -c "SELECT count(*) FROM pg_constraint WHERE contype='f' AND NOT convalidated;").Trim()
        if ($LASTEXITCODE -ne 0 -or $invalid -ne "0") { throw "restore_database_fk_validation_failed" }
        return [ordered]@{ name = $name; revision = $revision; container_dump = $containerDump }
    } catch {
        if ($created) { & docker.exe exec $Container dropdb -U $DatabaseUser --if-exists $name 2>$null | Out-Null }
        & docker.exe exec $Container rm -f $containerDump 2>$null | Out-Null
        throw
    }
}

function Remove-TemporaryDatabase {
    param([object]$Proof, [string]$Container, [string]$DatabaseUser)
    if ($null -ne $Proof -and [string]$Proof.name -like "ai_lab_restore_test_*") {
        & docker.exe exec $Container dropdb -U $DatabaseUser --if-exists ([string]$Proof.name) 2>$null | Out-Null
        & docker.exe exec $Container rm -f ([string]$Proof.container_dump) 2>$null | Out-Null
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
    $qdrantVerifier = Join-Path $PSScriptRoot "verify-qdrant-snapshot-offline.ps1"
    $proofs = @()
    if ($Manifest.schema_version -eq $legacySchema) {
        $records = @([ordered]@{ collection = "ai_lab_document_chunks"; artifact_file = "qdrant.snapshot"; points_count = $Manifest.qdrant_restore_result.points; vectors = [ordered]@{ size = $Manifest.qdrant_restore_result.dimensions; distance = $Manifest.qdrant_restore_result.distance } })
    } else {
        $records = @(Get-V2QdrantRecords $Manifest $Artifacts)
    }
    $index = 0
    foreach ($record in $records) {
        $index++
        if ($null -eq $record.vectors.size -or [string]::IsNullOrWhiteSpace([string]$record.vectors.distance)) {
            throw "qdrant_named_vector_proof_not_supported"
        }
        $leaf = Split-Path -Leaf ([string]$record.artifact_file)
        $proofOperation = "${ProofTargetOwner}-qdrant-$index"
        $qdrantJson = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $qdrantVerifier `
            -SnapshotPath $Artifacts[$leaf] -QdrantImage $qdrantImage -TargetCollection ([string]$record.collection) `
            -ExpectedPoints ([int64]$record.points_count) -ExpectedDimensions ([int]$record.vectors.size) `
            -ExpectedDistance ([string]$record.vectors.distance) -OperationId $proofOperation `
            -ClientImage $ProofQdrantClientImage
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($qdrantJson -join ""))) { throw "qdrant_offline_restore_failed" }
        $proofs += (($qdrantJson -join "") | ConvertFrom-Json)
    }
    return $proofs
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

if ($ProofOnly) {
    if ($ProofPostgresUser -notmatch '^[A-Za-z_][A-Za-z0-9_]{0,62}$') { throw "proof_postgres_user_invalid" }
    Assert-IsolatedPostgresTarget -Container $ProofPostgresContainer -Owner $ProofTargetOwner
    if ([string]::IsNullOrWhiteSpace($ProofQdrantClientImage) -or $ProofQdrantClientImage -notmatch '^sha256:[a-f0-9]{64}$') {
        throw "proof_qdrant_client_image_not_pinned"
    }
}
if (-not $ValidateOnly) { New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null }
try {
    try { $mutexHeld = $mutex.WaitOne(0, $false) } catch [Threading.AbandonedMutexException] { $mutexHeld = $true }
    if (-not $mutexHeld) { throw "recovery_operation_already_running" }
    $checkpoint = [IO.Path]::GetFullPath($CheckpointPath).TrimEnd('\')
    if (-not (Test-Path -LiteralPath $checkpoint -PathType Container)) { throw "checkpoint_not_found" }
    $manifestPath = Join-Path $checkpoint "backup-manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "backup_manifest_missing" }
    $manifestHash = Get-Sha256 $manifestPath
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.schema_version -notin @($legacySchema, $recoveryPointSchema)) { throw "backup_manifest_unsupported" }
    $manifestStatuses = @{}
    $requireManifestStatuses = $manifest.schema_version -eq $recoveryPointSchema
    foreach ($name in @("capture_status", "scope_status", "provenance_status", "consistency_status", "restore_status")) {
        $manifestStatuses[$name] = Get-ManifestStatus $manifest $name $requireManifestStatuses
    }
    Add-Stage "preflight" "started"
    $artifacts = Get-ArtifactMap $manifest
    if (-not $artifacts.ContainsKey("postgres.dump")) { throw "backup_database_missing" }
    $databaseArchiveReadable = Test-PostgresArchive $artifacts["postgres.dump"]
    if (-not $databaseArchiveReadable) { throw "backup_database_format_invalid" }
    $compatibility = Get-Compatibility $manifest
    $compatible = @("compatible", "older_supported_checkpoint", "requires_migration_after_restore") -contains $compatibility
    $fullRequired = if ($manifest.schema_version -eq $legacySchema) { $legacyFullRequired } else {
        $v2BaseRequired + @($v2RequiredCollections | ForEach-Object { "$_.snapshot" })
    }
    $fullComponentsPresent = $true
    foreach ($name in $fullRequired) { if (-not $artifacts.ContainsKey($name)) { $fullComponentsPresent = $false } }
    $qdrantStructural = $false
    $qdrantReason = "snapshot_missing"
    $qdrantRecords = @()
    if ($manifest.schema_version -eq $legacySchema -and $artifacts.ContainsKey("qdrant.snapshot")) {
        $qdrantResult = Test-QdrantStructure $artifacts["qdrant.snapshot"]
        $qdrantStructural = $qdrantResult.valid -eq $true
        $qdrantReason = if ($qdrantStructural) { "valid" } else { [string]$qdrantResult.reason }
    } elseif ($manifest.schema_version -eq $recoveryPointSchema) {
        $qdrantRecords = @(Get-V2QdrantRecords $manifest $artifacts)
        $qdrantStructural = $true
        foreach ($record in $qdrantRecords) {
            $leaf = Split-Path -Leaf ([string]$record.artifact_file)
            $qdrantResult = Test-QdrantStructure $artifacts[$leaf]
            if ($qdrantResult.valid -ne $true) { $qdrantStructural = $false; $qdrantReason = [string]$qdrantResult.reason; break }
        }
        if ($qdrantStructural) { $qdrantReason = "valid" }
    }
    $databaseEligible = $compatible -and $databaseArchiveReadable
    $captureComplete = $databaseEligible -and $fullComponentsPresent -and $qdrantStructural
    if ($manifest.schema_version -eq $recoveryPointSchema) {
        $captureComplete = $captureComplete -and [string]$manifestStatuses["capture_status"] -eq "COMPLETE" -and
            [string]$manifestStatuses["scope_status"] -eq "COMPLETE" -and
            [string]$manifestStatuses["provenance_status"] -eq "RECORDED"
    }
    $fullEligible = $captureComplete -and ($manifest.qdrant_restore_verified -eq $true)
    if ($Mode -eq "Full" -and -not $fullComponentsPresent) { throw "backup_full_component_missing" }
    if ($Mode -eq "Full" -and $manifest.schema_version -eq $legacySchema -and $manifest.qdrant_restore_verified -ne $true) { throw "qdrant_restore_verification_required" }
    if ($Mode -eq "Full" -and -not $ValidateOnly -and -not $ProofOnly -and $manifest.qdrant_restore_verified -ne $true) { throw "qdrant_restore_verification_required" }
    if ($Mode -eq "Full" -and -not $qdrantStructural) { throw "qdrant_snapshot_invalid" }
    Add-Stage "preflight" "completed"

    if ($ValidateOnly) {
        $totalBytes = [int64]0
        foreach ($artifact in @($manifest.artifacts)) { $totalBytes += [int64]$artifact.bytes }
        $summary = [ordered]@{
            valid = $true; checkpoint = $checkpoint; manifest_sha256 = $manifestHash
            created_at = [string]$manifest.created_at; scope = [string]$manifest.scope
            app_version = $(if ([string]::IsNullOrWhiteSpace([string]$manifest.app_version)) { [string]$manifest.release } else { [string]$manifest.app_version })
            source_head = [string]$manifest.source_head; db_revision = [string]$manifest.db_revision
            artifact_count = @($manifest.artifacts).Count; total_bytes = $totalBytes
            compatibility = $compatibility; database_eligible = $databaseEligible; full_eligible = $fullEligible
            qdrant_structurally_valid = $qdrantStructural; qdrant_reason = $qdrantReason
            qdrant_restore_verified = ($manifest.qdrant_restore_verified -eq $true)
            capture_complete = $captureComplete; capture_status = $manifestStatuses["capture_status"]
            scope_status = $manifestStatuses["scope_status"]; provenance_status = $manifestStatuses["provenance_status"]
            consistency_status = $manifestStatuses["consistency_status"]; restore_status = $manifestStatuses["restore_status"]
            qdrant_collections = @($qdrantRecords | ForEach-Object { [string]$_.collection })
        }
        Write-Output ("RECOVERY_VALIDATION_JSON=" + ($summary | ConvertTo-Json -Compress -Depth 5))
        return
    }

    # The development deliverable proves validation/staging only. The separate
    # destructive operational gate must provide the reviewed host-specific
    # cutover module before any live component is stopped or replaced.
    if (-not $ProofOnly) { throw "production_restore_approval_required" }

    Add-Stage "database_staging" "started"
    $dbProof = Restore-DatabaseToTemporary $artifacts["postgres.dump"] $manifest $ProofPostgresContainer $ProofPostgresUser
    Add-Stage "database_staging" "completed" ([string]$dbProof.revision)
    $qdrantProof = $null
    if ($Mode -eq "Full") { Add-Stage "full_staging" "started"; $qdrantProof = Stage-Full $artifacts $manifest; Add-Stage "full_staging" "completed" }

    if ($ProofOnly) {
        Add-Stage "post_validation" "completed"
        Remove-TemporaryDatabase $dbProof $ProofPostgresContainer $ProofPostgresUser
        Write-RecoveryReport "PASS"
        return
    }

}
catch {
    $code = ([string]$_.Exception.Message -split ':', 2)[0]
    if ($ValidateOnly) {
        Write-Output "RECOVERY_VALIDATION_VALID=false"
        Write-Output "RECOVERY_VALIDATION_ERROR=$code"
        throw
    }
    try { Add-Stage "failure" "failed" $code } catch { }
    $final = if ($cutoverStarted) { "ROLLBACK REQUIRED" } else { "FAILED" }
    Write-RecoveryReport $final $code
    throw
}
finally {
    if ($ProofOnly -and $null -ne $dbProof) { try { Remove-TemporaryDatabase $dbProof $ProofPostgresContainer $ProofPostgresUser } catch { } }
    if ($ProofOnly -and (Test-Path -LiteralPath $stageRoot -PathType Container)) {
        $resolvedStage = [IO.Path]::GetFullPath($stageRoot)
        $allowedStagePrefix = [IO.Path]::GetFullPath((Join-Path $stateRoot "staging-"))
        if ($resolvedStage.StartsWith($allowedStagePrefix, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedStage -Recurse -Force
        }
    }
    if ($mutexHeld) { $mutex.ReleaseMutex() }; $mutex.Dispose()
}
