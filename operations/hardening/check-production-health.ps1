[CmdletBinding()]
param(
    [string]$RepositoryRoot = "C:\ai-lab-core",
    [string]$BackupRoot = "C:\ai-lab-core-backups",
    [string]$ExpectedRevision = "followup_client_activity_20260819",
    [int]$MaximumBackupAgeHours = 36,
    [int64]$MinimumFreeBytes = 20GB
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0
$checks = New-Object System.Collections.Generic.List[object]

function Add-Check {
    param([string]$Name, [string]$Status, [object]$Details)
    $checks.Add([ordered]@{ name = $Name; status = $Status; details = $Details })
}

function Test-HttpHealth {
    param([string]$Name, [string]$Uri, [scriptblock]$Validator)
    try {
        $response = Invoke-RestMethod -Uri $Uri -TimeoutSec 10
        $valid = & $Validator $response
        Add-Check $Name $(if ($valid) { "ok" } else { "failed" }) $null
    }
    catch { Add-Check $Name "failed" $_.Exception.GetType().Name }
}

Test-HttpHealth "backend" "http://127.0.0.1:8000/health" { param($x) $x.status -eq "ok" }
Test-HttpHealth "qdrant" "http://127.0.0.1:6333/" { param($x) $x.title -like "qdrant*" }
Test-HttpHealth "ollama" "http://127.0.0.1:11434/api/version" { param($x) -not [string]::IsNullOrWhiteSpace($x.version) }
Test-HttpHealth "n8n" "http://127.0.0.1:5678/healthz" { param($x) $true }
Test-HttpHealth "open_webui" "http://127.0.0.1:3000/health" { param($x) $x.status -eq $true }
Test-HttpHealth "supervisor" "http://127.0.0.1:8787/health" { param($x) $x.supervisor_online -eq $true }

try {
    $visionJson = & docker exec ai-lab-backend python -c `
        "import json; from app.services.vision_supervisor_client import VisionSupervisorClient; print(json.dumps(VisionSupervisorClient().health()))"
    if ($LASTEXITCODE -ne 0) { throw "Vision health command failed." }
    $vision = $visionJson | ConvertFrom-Json
    $visionOk = $vision.status -in @("READY", "BUSY", "AUTH_REQUIRED", "UI_CHANGED")
    Add-Check "vision" $(if ($visionOk) { "ok" } else { "failed" }) `
        ([ordered]@{ status = $vision.status; queued = $vision.queued; active = [bool]$vision.active_job_id })
}
catch { Add-Check "vision" "failed" $_.Exception.GetType().Name }

try {
    $revision = (& docker exec postgres psql -U ai_lab -d ai_lab -At -c `
        "SELECT version_num FROM alembic_version;").Trim()
    if ($LASTEXITCODE -ne 0) { throw "Revision query failed." }
    Add-Check "migration" $(if ($revision -eq $ExpectedRevision) { "ok" } else { "failed" }) $revision

    $stateLines = & docker exec postgres psql -U ai_lab -d ai_lab -At -F "=" -c @"
SELECT 'ungranted_locks', count(*) FROM pg_locks WHERE NOT granted;
SELECT 'agent_orphan_started', count(*) FROM agent_executions
 WHERE status='started' AND created_at < now() - interval '4 minutes';
SELECT 'vision_processing_stale', count(*) FROM documents
 WHERE vision_status='processing' AND updated_at < now() - interval '10 minutes';
SELECT 'vision_retry_overdue', count(*) FROM documents
 WHERE vision_status='failed_retryable' AND vision_next_retry_at < now();
SELECT 'vision_pending_auth', count(*) FROM documents WHERE vision_status='pending_auth';
SELECT 'vision_ui_changed', count(*) FROM documents WHERE vision_status='ui_changed';
"@
    if ($LASTEXITCODE -ne 0) { throw "Operational state query failed." }
    $state = [ordered]@{}
    foreach ($line in $stateLines) {
        $parts = $line -split '=', 2
        if ($parts.Count -eq 2) { $state[$parts[0]] = [int]$parts[1] }
    }
    $stateOk = $state.ungranted_locks -eq 0 -and $state.agent_orphan_started -eq 0 -and `
        $state.vision_processing_stale -eq 0 -and $state.vision_retry_overdue -eq 0
    Add-Check "database_operational_state" $(if ($stateOk) { "ok" } else { "warning" }) $state
}
catch { Add-Check "database" "failed" $_.Exception.GetType().Name }

$dataItem = Get-Item -LiteralPath (Join-Path $RepositoryRoot "data")
$dataRoot = if ($dataItem.Target) { [string]$dataItem.Target } else { $dataItem.FullName }
$diskRoots = @($RepositoryRoot, $dataRoot, $BackupRoot) |
    ForEach-Object {
        [System.IO.Path]::GetPathRoot([System.IO.Path]::GetFullPath($_)).TrimEnd('\')
    } | Sort-Object -Unique
foreach ($root in $diskRoots) {
    $drive = Get-PSDrive -Name $root.TrimEnd(':') -PSProvider FileSystem
    $status = if ([int64]$drive.Free -ge $MinimumFreeBytes) { "ok" } else { "warning" }
    Add-Check ("disk_" + $root.TrimEnd(':').ToLowerInvariant()) $status `
        ([ordered]@{ free_bytes = [int64]$drive.Free; used_bytes = [int64]$drive.Used })
}

if (Test-Path -LiteralPath $BackupRoot -PathType Container) {
    $latest = Get-ChildItem -LiteralPath $BackupRoot -Directory |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "backup-manifest.json") } |
        Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    if ($null -ne $latest) {
        $ageHours = ((Get-Date).ToUniversalTime() - $latest.LastWriteTimeUtc).TotalHours
        Add-Check "backup_freshness" $(if ($ageHours -le $MaximumBackupAgeHours) { "ok" } else { "warning" }) `
            ([ordered]@{ age_hours = [math]::Round($ageHours, 2); checkpoint = $latest.Name })
    } else { Add-Check "backup_freshness" "failed" "no_manifest" }
} else { Add-Check "backup_freshness" "failed" "backup_root_missing" }

$overall = if ($checks.status -contains "failed") { "failed" } elseif ($checks.status -contains "warning") { "warning" } else { "ok" }
[ordered]@{
    schema_version = "NEXT_STABIL_HEALTH_V1"
    checked_at = (Get-Date).ToUniversalTime().ToString("o")
    status = $overall
    checks = $checks
} | ConvertTo-Json -Depth 8

if ($overall -eq "failed") { throw "One or more production health checks failed." }
