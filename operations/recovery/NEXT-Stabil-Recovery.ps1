[CmdletBinding()]
param(
    [string]$CheckpointPath,
    [ValidateSet("Database", "Full")]
    [string]$Mode,
    [switch]$ValidateOnly,
    [switch]$ProofOnly,
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$engine = Join-Path $repoRoot "operations\hardening\restore-checkpoint.ps1"
$integrityManifest = Join-Path $PSScriptRoot "recovery-tool-manifest.json"

function Get-Sha256 {
    param([string]$Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $sha.Dispose() }
}

function Assert-HelperIntegrity {
    if (-not (Test-Path -LiteralPath $integrityManifest -PathType Leaf)) { throw "helper_integrity_manifest_missing" }
    $manifest = Get-Content -LiteralPath $integrityManifest -Raw | ConvertFrom-Json
    if ($manifest.schema -ne "NEXT_STABIL_RECOVERY_TOOL_V1") { throw "helper_integrity_manifest_invalid" }
    foreach ($helper in @($manifest.helpers)) {
        $relative = ([string]$helper.file).Replace('/', '\')
        if ([IO.Path]::IsPathRooted($relative) -or $relative.Split('\') -contains '..') { throw "helper_integrity_path_invalid" }
        $path = [IO.Path]::GetFullPath((Join-Path $repoRoot $relative))
        if (-not $path.StartsWith($repoRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "helper_integrity_path_invalid" }
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "helper_integrity_failed" }
        $item = Get-Item -LiteralPath $path
        $hash = Get-Sha256 $path
        if ([int64]$item.Length -ne [int64]$helper.bytes -or $hash -ne ([string]$helper.sha256).ToLowerInvariant()) { throw "helper_integrity_failed" }
    }
}

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Select-CheckpointFolder {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = "Wybierz folder backupu NEXT Stabil"
    $dialog.ShowNewFolderButton = $false
    try {
        if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { return $null }
        return $dialog.SelectedPath
    } finally { $dialog.Dispose() }
}

function Invoke-Engine {
    param([string[]]$Arguments)
    $lines = @(& powershell.exe -NoProfile -NonInteractive -File $engine @Arguments)
    if ($LASTEXITCODE -ne 0) { throw (($lines | Select-Object -Last 1) -join '') }
    return $lines
}

function Get-Validation {
    param([string]$Path)
    $lines = Invoke-Engine @("-CheckpointPath", $Path, "-Mode", "Database", "-ValidateOnly")
    $record = @($lines | Where-Object { $_ -like "RECOVERY_VALIDATION_JSON=*" } | Select-Object -Last 1)
    if ($record.Count -ne 1) { throw "checkpoint_validation_result_missing" }
    return ([string]$record[0]).Substring("RECOVERY_VALIDATION_JSON=".Length) | ConvertFrom-Json
}

function Show-Summary {
    param([object]$Summary)
    Write-Host ""
    Write-Host "========================================"
    Write-Host "NEXT STABIL - RECOVERY"
    Write-Host "========================================"
    Write-Host ("Backup: {0}" -f $Summary.checkpoint)
    Write-Host ("Data backupu: {0}" -f $Summary.created_at)
    Write-Host ("Wersja NEXT Stabil: {0}" -f $Summary.app_version)
    Write-Host ("Rewizja DB: {0}" -f $Summary.db_revision)
    Write-Host ("Zakres: {0}" -f $Summary.scope)
    Write-Host ("Liczba artefaktów: {0}" -f $Summary.artifact_count)
    Write-Host ("Rozmiar: {0:N0} B" -f [int64]$Summary.total_bytes)
    Write-Host "Integralność: PASS"
    Write-Host ("Zgodność: {0}" -f $Summary.compatibility)
    Write-Host ("Database restore: {0}" -f $(if ($Summary.database_eligible) { "DOSTĘPNY" } else { "NIEDOSTĘPNY" }))
    Write-Host ("Full restore: {0}" -f $(if ($Summary.full_eligible) { "DOSTĘPNY" } else { "NIEDOSTĘPNY" }))
    Write-Host ("Qdrant snapshot: {0}" -f $(if ($Summary.qdrant_structurally_valid) { "PASS" } else { "FAIL: $($Summary.qdrant_reason)" }))
    Write-Host ("Qdrant restore evidence: {0}" -f $(if ($Summary.qdrant_restore_verified) { "PASS" } else { "BRAK" }))
    Write-Warning "Sekrety środowiskowe są wymagane z zewnętrznego sejfu/escrow."
}

function Read-Mode {
    param([object]$Summary)
    if (-not $Summary.database_eligible) { throw "database_restore_not_eligible" }
    if ($NonInteractive) { throw "mode_required" }
    Write-Host ""
    Write-Host "[1] Przywróć tylko bazę danych"
    if ($Summary.full_eligible) { Write-Host "[2] Przywróć cały system" }
    Write-Host "[0] Anuluj"
    $choice = Read-Host "Wybierz tryb"
    if ($choice -eq "0") { return $null }
    if ($choice -eq "1") { return "Database" }
    if ($choice -eq "2" -and $Summary.full_eligible) { return "Full" }
    throw "restore_mode_invalid"
}

function Confirm-Restore {
    param([string]$SelectedMode)
    Write-Host ""
    if ($SelectedMode -eq "Full") {
        Write-Warning "TRYB: FULL"
        Write-Host "Zostaną przywrócone: PostgreSQL, dokumenty, Qdrant, n8n/config i wymagane lokalne pliki wdrożeniowe."
        Write-Host "Usługi zostaną czasowo zatrzymane."
        $token = "PRZYWRÓĆ SYSTEM"
    } else {
        Write-Warning "TRYB: DATABASE"
        Write-Host "Zostanie przywrócona produkcyjna baza danych. Obecna baza może zostać zastąpiona."
        Write-Host "Przed zmianą system spróbuje utworzyć backup bezpieczeństwa."
        $token = "PRZYWRÓĆ"
    }
    if ((Read-Host "Czy rozumiesz, że obecne dane mogą zostać zastąpione? [TAK/NIE]") -cne "TAK") { return $false }
    return (Read-Host "Wpisz dokładnie: $token") -ceq $token
}

try {
    Assert-HelperIntegrity
    if ([string]::IsNullOrWhiteSpace($CheckpointPath)) {
        if ($NonInteractive) { throw "checkpoint_path_required" }
        $CheckpointPath = Select-CheckpointFolder
        if ([string]::IsNullOrWhiteSpace($CheckpointPath)) { Write-Output "RECOVERY_FINAL_STATUS=CANCELLED BEFORE CUTOVER"; return }
    }
    $summary = Get-Validation $CheckpointPath
    Show-Summary $summary
    if ($ValidateOnly) { Write-Output "RECOVERY_VALIDATION_STATUS=PASS"; return }
    if ([string]::IsNullOrWhiteSpace($Mode)) { $Mode = Read-Mode $summary }
    if ([string]::IsNullOrWhiteSpace($Mode)) { Write-Output "RECOVERY_FINAL_STATUS=CANCELLED BEFORE CUTOVER"; return }
    if ($Mode -eq "Database" -and -not $summary.database_eligible) { throw "database_restore_not_eligible" }
    if ($Mode -eq "Full" -and -not $summary.full_eligible) { throw "full_restore_not_eligible" }

    if ($ProofOnly) {
        $proofLines = Invoke-Engine @("-CheckpointPath", [string]$summary.checkpoint, "-Mode", $Mode, "-ProofOnly")
        $proofLines | Write-Output
        return
    }

    if (-not (Test-Administrator)) { throw "administrator_required_for_production_restore" }
    if (-not (Confirm-Restore $Mode)) { Write-Output "RECOVERY_FINAL_STATUS=CANCELLED BEFORE CUTOVER"; return }
    # The canonical engine owns the final fail-closed production gate.
    $restoreLines = Invoke-Engine @("-CheckpointPath", [string]$summary.checkpoint, "-Mode", $Mode)
    $restoreLines | Write-Output
}
catch {
    $code = ([string]$_.Exception.Message -split ':', 2)[0]
    Write-Output "RECOVERY_FINAL_STATUS=FAILED"
    Write-Output "RECOVERY_ERROR=$code"
    throw
}
