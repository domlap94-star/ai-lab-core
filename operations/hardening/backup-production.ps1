[CmdletBinding()]
param(
    [string]$RepositoryRoot = "C:\ai-lab-core",
    [string]$BackupRoot = "C:\ai-lab-core-backups",
    [string]$Release = "1.0.2+21",
    [string]$QdrantCollection = "ai_lab_document_chunks",
    [string[]]$QdrantCollections = @(),
    [ValidateSet("LegacyV1", "RecoveryPointV2")]
    [string]$ManifestFormat = "LegacyV1",
    [ValidateSet("LegacyRestoreProof", "CaptureOnly")]
    [string]$QdrantProofMode = "LegacyRestoreProof",
    [string]$CheckpointId = "",
    [string]$RuntimeInventoryPath = "",
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
if ($backupBase.StartsWith($repo + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "BackupRoot must be outside the repository."
}
if ($backupBase.StartsWith($dataRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "BackupRoot must be outside the active data tree."
}
if (-not (Test-Path -LiteralPath $backupBase -PathType Container)) {
    throw "backup_root_missing"
}

$selectedCollections = if ($QdrantCollections.Count -gt 0) {
    @($QdrantCollections | ForEach-Object { Get-SafeQdrantCollectionName ([string]$_) })
} else {
    @(Get-SafeQdrantCollectionName $QdrantCollection)
}
if (@($selectedCollections | Select-Object -Unique).Count -ne $selectedCollections.Count) {
    throw "qdrant_collection_duplicate"
}
$requiredRecoveryCollections = @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks")
if ($ManifestFormat -eq "RecoveryPointV2") {
    if ($Scope -ne "full") { throw "recovery_point_v2_requires_full_scope" }
    if ($QdrantProofMode -ne "CaptureOnly") { throw "recovery_point_v2_capture_must_not_restore" }
    if ($selectedCollections.Count -ne $requiredRecoveryCollections.Count -or
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
    if ($selectedCollections.Count -ne 1) { throw "legacy_manifest_requires_one_qdrant_collection" }
    $runtimeInventory = $null
}

$documentSources = @("documents", "document-pages", "document-assets", "archive-extracted")
$estimatedBytes = [int64]0
if ($Scope -in @("full", "documents")) {
    foreach ($name in $documentSources) {
        $estimatedBytes += Get-DirectoryBytes -Path (Join-Path $dataRoot $name)
    }
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
    $containerDump = "/tmp/next-stabil-$stamp.dump"
    try {
        Invoke-CheckedCommand "docker.exe" @(
            "exec", "postgres", "pg_dump", "-U", "ai_lab", "-d", "ai_lab",
            "--format=custom", "--compress=6", "--no-owner", "--file=$containerDump"
        )
        Invoke-CheckedCommand "docker.exe" @("exec", "postgres", "pg_restore", "--list", $containerDump)
        Invoke-CheckedCommand "docker.exe" @("cp", "postgres`:$containerDump", $dbDump)
    }
    finally { & docker exec postgres rm -f $containerDump 2>$null }
    $artifactRecords += Get-ArtifactRecord $checkpoint $dbDump
    $componentWindows += [ordered]@{ component = "postgres"; started_at = $componentStarted.ToString("o"); finished_at = (Get-Date).ToUniversalTime().ToString("o") }
}

if ($Scope -in @("full", "documents")) {
    $componentStarted = (Get-Date).ToUniversalTime()
    Write-Output "BACKUP_STAGE=documents"
    $documentsArchive = Join-Path $artifacts "document-storage.tar.gz"
    Invoke-CheckedCommand "tar.exe" (@("-czf", $documentsArchive, "-C", $dataRoot) + $documentSources)
    Invoke-CheckedCommand "tar.exe" @("-tzf", $documentsArchive)
    $artifactRecords += Get-ArtifactRecord $checkpoint $documentsArchive
    $componentWindows += [ordered]@{ component = "document_storage"; started_at = $componentStarted.ToString("o"); finished_at = (Get-Date).ToUniversalTime().ToString("o") }
}

if ($Scope -eq "full") {
    $componentStarted = (Get-Date).ToUniversalTime()
    Write-Output "BACKUP_STAGE=release"
    $releaseArchive = Join-Path $artifacts "release-stable.tar.gz"
    Invoke-CheckedCommand "tar.exe" @("-czf", $releaseArchive, "-C", $repo, "release-channel/stable")
    Invoke-CheckedCommand "tar.exe" @("-tzf", $releaseArchive)
    $artifactRecords += Get-ArtifactRecord $checkpoint $releaseArchive
    $componentWindows += [ordered]@{ component = "release"; started_at = $componentStarted.ToString("o"); finished_at = (Get-Date).ToUniversalTime().ToString("o") }
}

if ($Scope -in @("full", "qdrant")) {
    Write-Output "BACKUP_STAGE=qdrant"
    $validator = Join-Path $toolRoot "operations\supervisor\qdrant_snapshot_validator.js"
    if (-not (Test-Path -LiteralPath $validator -PathType Leaf)) { throw "qdrant_validator_missing" }
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

if ($Scope -in @("full", "n8n_config")) {
    $componentStarted = (Get-Date).ToUniversalTime()
    Write-Output "BACKUP_STAGE=n8n"
    $n8nWorkflows = Join-Path $artifacts "n8n-workflows.json"
    $n8nCredentials = Join-Path $artifacts "n8n-credentials.encrypted.json"
    $n8nWorkflowTemp = "/tmp/next-stabil-$stamp-workflows.json"
    $n8nCredentialsTemp = "/tmp/next-stabil-$stamp-credentials.json"
    try {
        Invoke-CheckedCommand "docker.exe" @("exec", "n8n", "n8n", "export:workflow", "--all", "--output=$n8nWorkflowTemp")
        Invoke-CheckedCommand "docker.exe" @("exec", "n8n", "n8n", "export:credentials", "--all", "--output=$n8nCredentialsTemp")
        Invoke-CheckedCommand "docker.exe" @("cp", "n8n`:$n8nWorkflowTemp", $n8nWorkflows)
        Invoke-CheckedCommand "docker.exe" @("cp", "n8n`:$n8nCredentialsTemp", $n8nCredentials)
    }
    finally { & docker exec n8n rm -f $n8nWorkflowTemp $n8nCredentialsTemp 2>$null }
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
    Invoke-CheckedCommand "tar.exe" @("-tzf", $configArchive)
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
        @($requiredRecoveryCollections | ForEach-Object { "$_.snapshot" })
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
