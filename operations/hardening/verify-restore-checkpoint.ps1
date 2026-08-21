[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$CheckpointPath,
    [string]$ApprovedBackupRoot = "C:\ai-lab-core-backups",
    [ValidateSet("database", "full")]
    [string]$Mode = "full"
)

# Compatibility wrapper. The canonical implementation lives in
# restore-checkpoint.ps1 and is shared with the standalone Recovery App.
$root = [IO.Path]::GetFullPath($ApprovedBackupRoot).TrimEnd('\')
$checkpoint = [IO.Path]::GetFullPath($CheckpointPath).TrimEnd('\')
if (-not $checkpoint.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw "checkpoint_outside_approved_root"
}
$engine = Join-Path $PSScriptRoot "restore-checkpoint.ps1"
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $engine `
    -CheckpointPath $checkpoint -Mode $(if ($Mode -eq "full") { "Full" } else { "Database" }) -ProofOnly
if ($LASTEXITCODE -ne 0) { throw "restore_checkpoint_proof_failed:$LASTEXITCODE" }
return

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

function Invoke-CheckedCommand {
    param([string]$FilePath, [string[]]$Arguments)
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$FilePath failed with exit code $LASTEXITCODE." }
}

function Assert-SafeArchiveEntries {
    param([string]$ArchivePath)
    $entries = @(& tar.exe -tzf $ArchivePath)
    if ($LASTEXITCODE -ne 0) { throw "archive_integrity_failed" }
    foreach ($entry in $entries) {
        $normalized = ([string]$entry).Replace('\', '/')
        if ([string]::IsNullOrWhiteSpace($normalized) -or
            $normalized.StartsWith('/') -or
            $normalized -match '^[A-Za-z]:' -or
            $normalized -match '(^|/)\.\.(/|$)') {
            throw "archive_path_traversal"
        }
    }
    return @($entries)
}

$root = [System.IO.Path]::GetFullPath($ApprovedBackupRoot).TrimEnd('\')
$checkpoint = [System.IO.Path]::GetFullPath($CheckpointPath).TrimEnd('\')
if (-not ($checkpoint.StartsWith($root + '\', [System.StringComparison]::OrdinalIgnoreCase))) {
    throw "checkpoint_outside_approved_root"
}
if (-not (Test-Path -LiteralPath $checkpoint -PathType Container)) { throw "checkpoint_not_found" }
$manifestPath = Join-Path $checkpoint "backup-manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "backup_manifest_missing" }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.schema_version -ne "NEXT_STABIL_BACKUP_V1") { throw "backup_manifest_unsupported" }

$artifactByName = @{}
foreach ($artifact in @($manifest.artifacts)) {
    $relative = [string]$artifact.file
    if ([string]::IsNullOrWhiteSpace($relative) -or
        $relative.StartsWith('/') -or $relative.StartsWith('\') -or
        $relative -match '^[A-Za-z]:' -or $relative -match '(^|[\\/])\.\.([\\/]|$)') {
        throw "backup_artifact_path_invalid"
    }
    $path = [System.IO.Path]::GetFullPath((Join-Path $checkpoint $relative))
    if (-not $path.StartsWith($checkpoint + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "backup_artifact_path_invalid"
    }
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "backup_artifact_missing" }
    $file = Get-Item -LiteralPath $path
    if ([int64]$file.Length -ne [int64]$artifact.bytes) { throw "backup_artifact_size_mismatch" }
    $actualHash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne ([string]$artifact.sha256).ToLowerInvariant()) { throw "backup_artifact_hash_mismatch" }
    $artifactByName[$file.Name] = $path
}

if (-not $artifactByName.ContainsKey("postgres.dump")) { throw "backup_database_missing" }
$fullRequired = @(
    "document-storage.tar.gz", "release-stable.tar.gz", "qdrant.snapshot",
    "n8n-workflows.json", "n8n-credentials.encrypted.json", "configuration.tar.gz"
)
if ($Mode -eq "full") {
    foreach ($name in $fullRequired) {
        if (-not $artifactByName.ContainsKey($name)) { throw "backup_full_component_missing" }
    }
    $validator = Join-Path $PSScriptRoot "..\supervisor\qdrant_snapshot_validator.js"
    $validationJson = (& node.exe $validator $artifactByName["qdrant.snapshot"] 2>$null)
    $validatorExit = $LASTEXITCODE
    if ([string]::IsNullOrWhiteSpace(($validationJson -join ""))) { throw "qdrant_snapshot_invalid" }
    $validation = ($validationJson -join "") | ConvertFrom-Json
    if ($validatorExit -ne 0 -or $validation.valid -ne $true) { throw "qdrant_snapshot_invalid" }
    if ($manifest.qdrant_restore_verified -ne $true) {
        $qdrantError = [string]$manifest.qdrant_restore_error_code
        if ([string]::IsNullOrWhiteSpace($qdrantError)) {
            $qdrantError = "qdrant_restore_verification_required"
        }
        throw $qdrantError
    }
}

$token = [Guid]::NewGuid().ToString("N").Substring(0, 12)
$restoreDb = "ai_lab_restore_test_$token"
$containerDump = "/tmp/$restoreDb.dump"
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) "next-stabil-restore-$token"
$databaseCreated = $false
try {
    New-Item -ItemType Directory -Path $tempRoot | Out-Null
    Invoke-CheckedCommand "docker.exe" @("cp", $artifactByName["postgres.dump"], "postgres`:$containerDump")
    Invoke-CheckedCommand "docker.exe" @("exec", "postgres", "createdb", "-U", "ai_lab", $restoreDb)
    $databaseCreated = $true
    Invoke-CheckedCommand "docker.exe" @(
        "exec", "postgres", "pg_restore", "-U", "ai_lab", "-d", $restoreDb,
        "--no-owner", "--exit-on-error", $containerDump
    )
    $actualDb = (& docker.exe exec postgres psql -U ai_lab -d $restoreDb -At -c "SELECT current_database();").Trim()
    if ($LASTEXITCODE -ne 0 -or $actualDb -ne $restoreDb) { throw "restore_database_guard_failed" }
    if ($actualDb -eq "ai_lab") { throw "restore_production_database_refused" }
    $revision = (& docker.exe exec postgres psql -U ai_lab -d $restoreDb -At -c "SELECT version_num FROM alembic_version;").Trim()
    if ($LASTEXITCODE -ne 0 -or $revision -ne [string]$manifest.db_revision) { throw "restore_database_revision_mismatch" }
    $coreTables = @("clients", "users", "documents", "work_items", "projects", "change_history_events")
    foreach ($table in $coreTables) {
        Invoke-CheckedCommand "docker.exe" @("exec", "postgres", "psql", "-U", "ai_lab", "-d", $restoreDb, "-v", "ON_ERROR_STOP=1", "-At", "-c", "SELECT count(*) FROM $table;")
    }
    $invalidFks = (& docker.exe exec postgres psql -U ai_lab -d $restoreDb -At -c "SELECT count(*) FROM pg_constraint WHERE contype='f' AND NOT convalidated;").Trim()
    if ($LASTEXITCODE -ne 0 -or $invalidFks -ne "0") { throw "restore_database_fk_validation_failed" }

    $documentEntries = 0
    if ($Mode -eq "full") {
        $documentList = @(Assert-SafeArchiveEntries $artifactByName["document-storage.tar.gz"])
        $configList = @(Assert-SafeArchiveEntries $artifactByName["configuration.tar.gz"])
        [void](Assert-SafeArchiveEntries $artifactByName["release-stable.tar.gz"])
        $documentStage = Join-Path $tempRoot "documents"
        $configStage = Join-Path $tempRoot "configuration"
        New-Item -ItemType Directory -Path $documentStage, $configStage | Out-Null
        Invoke-CheckedCommand "tar.exe" @("-xzf", $artifactByName["document-storage.tar.gz"], "-C", $documentStage)
        Invoke-CheckedCommand "tar.exe" @("-xzf", $artifactByName["configuration.tar.gz"], "-C", $configStage)
        $documentEntries = @($documentList | Where-Object { -not ([string]$_).EndsWith('/') }).Count
        if ($documentEntries -lt 1 -or $configList.Count -lt 1) { throw "restore_archive_empty" }
        [void](Get-Content -LiteralPath $artifactByName["n8n-workflows.json"] -Raw | ConvertFrom-Json)
        [void](Get-Content -LiteralPath $artifactByName["n8n-credentials.encrypted.json"] -Raw | ConvertFrom-Json)
        if ((Get-Item -LiteralPath $artifactByName["qdrant.snapshot"]).Length -le 0) { throw "restore_qdrant_snapshot_empty" }
    }

    Write-Output "RESTORE_PROOF=PASS"
    Write-Output "MODE=$Mode"
    Write-Output "ISOLATED_DATABASE=$restoreDb"
    Write-Output "DB_REVISION=$revision"
    Write-Output "DOCUMENT_ARCHIVE_ENTRIES=$documentEntries"
    Write-Output "PRODUCTION_CUTOVER=NO"
}
finally {
    if ($databaseCreated) {
        & docker.exe exec postgres dropdb -U ai_lab --if-exists $restoreDb 2>$null
        if ($LASTEXITCODE -ne 0) { throw "temporary_restore_database_cleanup_failed" }
    }
    & docker.exe exec postgres rm -f $containerDump 2>$null
    if (Test-Path -LiteralPath $tempRoot) {
        $resolvedTemp = [System.IO.Path]::GetFullPath($tempRoot)
        $systemTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
        if (-not $resolvedTemp.StartsWith($systemTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "temporary_restore_path_cleanup_refused"
        }
        Remove-Item -LiteralPath $resolvedTemp -Recurse -Force
    }
}
