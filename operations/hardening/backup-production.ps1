[CmdletBinding()]
param(
    [string]$RepositoryRoot = "C:\ai-lab-core",
    [string]$BackupRoot = "C:\ai-lab-core-backups",
    [string]$Release = "1.0.2+21",
    [string]$QdrantCollection = "ai_lab_document_chunks",
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

$repo = (Resolve-Path -LiteralPath $RepositoryRoot).Path.TrimEnd('\')
$dataRoot = (Resolve-Path -LiteralPath (Join-Path $repo "data")).Path.TrimEnd('\')
$backupBase = [System.IO.Path]::GetFullPath($BackupRoot).TrimEnd('\')
if ($backupBase.StartsWith($repo + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "BackupRoot must be outside the repository."
}
if ($backupBase.StartsWith($dataRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "BackupRoot must be outside the active data tree."
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
$driveName = [System.IO.Path]::GetPathRoot($backupBase).TrimEnd('\').TrimEnd(':')
$drive = Get-PSDrive -Name $driveName -PSProvider FileSystem
if ([int64]$drive.Free -lt $requiredFreeBytes) {
    throw "Insufficient backup space. Required at least $requiredFreeBytes bytes; available $($drive.Free)."
}

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$checkpoint = Join-Path $backupBase $stamp
$artifacts = Join-Path $checkpoint "artifacts"
$configDir = Join-Path $checkpoint "configuration"
New-Item -ItemType Directory -Path $artifacts -Force | Out-Null
New-Item -ItemType Directory -Path $configDir -Force | Out-Null

$currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
Invoke-CheckedCommand "icacls.exe" @(
    $checkpoint, "/inheritance:r", "/grant:r", "*$currentSid`:(OI)(CI)F",
    "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F", "/T", "/C"
)

$head = (& git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw "Unable to read source HEAD." }
$dbRevision = (& docker exec postgres psql -U ai_lab -d ai_lab -At -c "SELECT version_num FROM alembic_version;").Trim()
if ($LASTEXITCODE -ne 0) { throw "Unable to read Alembic revision." }

$artifactRecords = @()
$qdrantSnapshotName = $null
$qdrantSnapshotStructurallyValid = $null
$qdrantSnapshotValidationReason = $null
$qdrantRestoreVerified = $null
$qdrantRestoreResult = $null
if ($Scope -in @("full", "database")) {
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
}

if ($Scope -in @("full", "documents")) {
    Write-Output "BACKUP_STAGE=documents"
    $documentsArchive = Join-Path $artifacts "document-storage.tar.gz"
    Invoke-CheckedCommand "tar.exe" (@("-czf", $documentsArchive, "-C", $dataRoot) + $documentSources)
    Invoke-CheckedCommand "tar.exe" @("-tzf", $documentsArchive)
    $artifactRecords += Get-ArtifactRecord $checkpoint $documentsArchive
}

if ($Scope -eq "full") {
    Write-Output "BACKUP_STAGE=release"
    $releaseArchive = Join-Path $artifacts "release-stable.tar.gz"
    Invoke-CheckedCommand "tar.exe" @("-czf", $releaseArchive, "-C", $repo, "release-channel/stable")
    Invoke-CheckedCommand "tar.exe" @("-tzf", $releaseArchive)
    $artifactRecords += Get-ArtifactRecord $checkpoint $releaseArchive
}

if ($Scope -in @("full", "qdrant")) {
    Write-Output "BACKUP_STAGE=qdrant"
    $qdrantResponse = Invoke-RestMethod -Method Post `
        -Uri "http://127.0.0.1:6333/collections/$QdrantCollection/snapshots" -TimeoutSec 900
    if ($qdrantResponse.status -ne "ok" -or [string]::IsNullOrWhiteSpace($qdrantResponse.result.name)) {
        throw "Qdrant did not return a valid snapshot name."
    }
    $qdrantSnapshotName = $qdrantResponse.result.name
    $qdrantSnapshot = Join-Path $artifacts "qdrant.snapshot"
    Invoke-CheckedCommand "curl.exe" @(
        "--fail", "--silent", "--show-error", "--location", "--max-time", "900",
        "--output", $qdrantSnapshot,
        "http://127.0.0.1:6333/collections/$QdrantCollection/snapshots/$qdrantSnapshotName"
    )
    $validator = Join-Path $repo "operations\supervisor\qdrant_snapshot_validator.js"
    $validationJson = (& node.exe $validator $qdrantSnapshot 2>$null)
    $validatorExit = $LASTEXITCODE
    if ([string]::IsNullOrWhiteSpace(($validationJson -join ""))) {
        throw "qdrant_snapshot_validation_failed"
    }
    $validation = ($validationJson -join "") | ConvertFrom-Json
    $qdrantSnapshotStructurallyValid = $validatorExit -eq 0 -and $validation.valid -eq $true
    $qdrantSnapshotValidationReason = [string]$validation.reason
    if ($qdrantSnapshotStructurallyValid) {
        Write-Output "BACKUP_STAGE=qdrant_restore_drill"
        $qdrantImage = (& docker.exe inspect qdrant --format '{{.Config.Image}}').Trim()
        if ($LASTEXITCODE -ne 0) { throw "qdrant_image_inspection_failed" }
        $restoreVerifier = Join-Path $repo "operations\hardening\verify-qdrant-snapshot-restore.ps1"
        try {
            $restoreJson = (& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass `
                -File $restoreVerifier -SnapshotPath $qdrantSnapshot `
                -SourceCollection $QdrantCollection -QdrantImage $qdrantImage 2>$null)
            if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace(($restoreJson -join ""))) {
                $qdrantRestoreResult = ($restoreJson -join "") | ConvertFrom-Json
                $qdrantRestoreVerified = $qdrantRestoreResult.verified -eq $true
            } else { $qdrantRestoreVerified = $false }
        } catch { $qdrantRestoreVerified = $false }
    } else { $qdrantRestoreVerified = $false }
    $artifactRecords += Get-ArtifactRecord $checkpoint $qdrantSnapshot
}

if ($Scope -in @("full", "n8n_config")) {
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
}

if ($Scope -in @("full", "n8n_config")) {
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

    $envNamesPath = Join-Path $configDir "required-env-names.txt"
    if (Test-Path -LiteralPath (Join-Path $repo ".env")) {
        Get-Content -LiteralPath (Join-Path $repo ".env") |
            Where-Object { $_ -match '^\s*[A-Za-z_][A-Za-z0-9_]*\s*=' } |
            ForEach-Object { (($_ -split '=', 2)[0]).Trim() } |
            Sort-Object -Unique | Set-Content -LiteralPath $envNamesPath -Encoding UTF8
    } else { @() | Set-Content -LiteralPath $envNamesPath -Encoding UTF8 }

    $imageInventory = @()
    foreach ($containerName in @("postgres", "qdrant", "ollama", "n8n", "open-webui", "ai-lab-backend")) {
        $container = (& docker inspect $containerName | ConvertFrom-Json | Select-Object -First 1)
        if ($LASTEXITCODE -ne 0) { throw "Unable to inspect $containerName." }
        $image = (& docker image inspect $container.Image | ConvertFrom-Json | Select-Object -First 1)
        if ($LASTEXITCODE -ne 0) { throw "Unable to inspect image for $containerName." }
        $imageInventory += [ordered]@{
            container = $containerName; configured_image = $container.Config.Image
            image_id = $container.Image; repo_digests = @($image.RepoDigests)
        }
    }
    $imageInventory | ConvertTo-Json -Depth 6 |
        Set-Content -LiteralPath (Join-Path $configDir "runtime-images.json") -Encoding UTF8

    $configArchive = Join-Path $artifacts "configuration.tar.gz"
    Invoke-CheckedCommand "tar.exe" @("-czf", $configArchive, "-C", $checkpoint, "configuration")
    Invoke-CheckedCommand "tar.exe" @("-tzf", $configArchive)
    $artifactRecords += Get-ArtifactRecord $checkpoint $configArchive
}

$manifest = [ordered]@{
    schema_version = "NEXT_STABIL_BACKUP_V1"
    scope = $Scope
    run_id = $RunId
    schedule_id = $ScheduleId
    trigger = $Trigger
    app_version = $Release
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    source_head = $head; release = $Release; db_revision = $dbRevision
    qdrant_collection = $QdrantCollection; qdrant_snapshot_name = $qdrantSnapshotName
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
        else { "qdrant_restore_drill_failed" }
    } else { $null }
    document_directories = if ($Scope -in @("full", "documents")) { $documentSources } else { @() }
    estimated_source_bytes = $estimatedBytes
    secrets_in_protected_backup = $false
    secrets_note = "Encrypted n8n credential export is included; the separately protected environment secret escrow is required for credential recovery."
    artifacts = $artifactRecords
}
$manifestPartial = Join-Path $checkpoint "backup-manifest.json.partial"
$manifestPath = Join-Path $checkpoint "backup-manifest.json"
Write-Output "BACKUP_STAGE=verifying"
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPartial -Encoding UTF8
Move-Item -LiteralPath $manifestPartial -Destination $manifestPath

Write-Output ("BACKUP_COMPLETE={0}" -f $checkpoint)
Write-Output ("MANIFEST={0}" -f $manifestPath)
