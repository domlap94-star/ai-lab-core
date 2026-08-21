[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$root = $PSScriptRoot
$repo = [IO.Path]::GetFullPath((Join-Path $root "..\.."))
$tool = Join-Path $root "NEXT-Stabil-Recovery.ps1"
$engine = Join-Path $repo "operations\hardening\restore-checkpoint.ps1"
$tests = 0

function Assert-True { param([bool]$Value, [string]$Name) if (-not $Value) { throw "test_failed:$Name" }; $script:tests++ }

$errors = $null
[void][Management.Automation.Language.Parser]::ParseFile($tool, [ref]$null, [ref]$errors)
Assert-True ($errors.Count -eq 0) "tool_parse"
$errors = $null
[void][Management.Automation.Language.Parser]::ParseFile($engine, [ref]$null, [ref]$errors)
Assert-True ($errors.Count -eq 0) "engine_parse"

$text = Get-Content -LiteralPath $tool -Raw -Encoding UTF8
Assert-True ($text -match 'FolderBrowserDialog') "folder_picker"
Assert-True ($text -match 'Assert-HelperIntegrity') "helper_integrity"
Assert-True ($text -match '\$token = "[^\"]+ SYSTEM"') "full_confirmation"
Assert-True ($text -match '\$token = "[^\"]+"') "database_confirmation"
Assert-True ($text -match 'administrator_required_for_production_restore') "admin_gate"
Assert-True ($text -match '\-ProofOnly') "proof_mode"
Assert-True ($text -notmatch 'backup_runs|restore_runs|backup_schedules|JWT|/api/') "offline_contract"

$engineText = Get-Content -LiteralPath $engine -Raw
Assert-True ($engineText -match 'production_restore_approval_required') "production_gate"
Assert-True ($engineText -match 'RECOVERY_VALIDATION_JSON') "validate_only"

function Invoke-FailingValidation {
    param([string]$Checkpoint)
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = @(& powershell.exe -NoProfile -NonInteractive -File $engine -CheckpointPath $Checkpoint -Mode Database -ValidateOnly 2>&1)
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousPreference
    return [ordered]@{ exit_code = $exitCode; text = ($output -join "`n") }
}

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("next-stabil-recovery-test-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempRoot | Out-Null
try {
    $missing = Join-Path $tempRoot "missing"
    New-Item -ItemType Directory -Path $missing | Out-Null
    $result = Invoke-FailingValidation $missing
    Assert-True ($result.exit_code -ne 0 -and $result.text -match 'backup_manifest_missing') "missing_manifest_rejected"

    $badHash = Join-Path $tempRoot "bad-hash"
    New-Item -ItemType Directory -Path $badHash | Out-Null
    [IO.File]::WriteAllBytes((Join-Path $badHash "postgres.dump"), [Text.Encoding]::ASCII.GetBytes("PGDMPfixture"))
    [ordered]@{
        schema_version = "NEXT_STABIL_BACKUP_V1"; scope = "database"; app_version = "1.0.2+25"
        db_revision = "followup_admin_backup_restore_ui_20260821"
        artifacts = @([ordered]@{ file = "postgres.dump"; bytes = 12; sha256 = ("0" * 64) })
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $badHash "backup-manifest.json") -Encoding UTF8
    $result = Invoke-FailingValidation $badHash
    Assert-True ($result.exit_code -ne 0 -and $result.text -match 'backup_artifact_hash_mismatch') "bad_hash_rejected"

    $badPath = Join-Path $tempRoot "bad-path"
    New-Item -ItemType Directory -Path $badPath | Out-Null
    [ordered]@{
        schema_version = "NEXT_STABIL_BACKUP_V1"; scope = "database"; app_version = "1.0.2+25"
        db_revision = "followup_admin_backup_restore_ui_20260821"
        artifacts = @([ordered]@{ file = "../postgres.dump"; bytes = 1; sha256 = ("0" * 64) })
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $badPath "backup-manifest.json") -Encoding UTF8
    $result = Invoke-FailingValidation $badPath
    Assert-True ($result.exit_code -ne 0 -and $result.text -match 'backup_artifact_path_invalid') "path_traversal_rejected"

    $copyRoot = Join-Path $tempRoot "tampered-tool"
    foreach ($directory in @("operations\recovery", "operations\hardening", "operations\supervisor")) {
        New-Item -ItemType Directory -Path (Join-Path $copyRoot $directory) -Force | Out-Null
    }
    Copy-Item -LiteralPath $tool,(Join-Path $root "recovery-tool-manifest.json") -Destination (Join-Path $copyRoot "operations\recovery")
    foreach ($relative in @("operations\hardening\restore-checkpoint.ps1", "operations\hardening\backup-production.ps1", "operations\hardening\verify-qdrant-snapshot-offline.ps1", "operations\supervisor\qdrant_snapshot_validator.js")) {
        Copy-Item -LiteralPath (Join-Path $repo $relative) -Destination (Join-Path $copyRoot $relative)
    }
    Add-Content -LiteralPath (Join-Path $copyRoot "operations\hardening\backup-production.ps1") -Value "# tamper"
    $tamperedTool = Join-Path $copyRoot "operations\recovery\NEXT-Stabil-Recovery.ps1"
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $tamperOutput = @(& powershell.exe -NoProfile -NonInteractive -File $tamperedTool -CheckpointPath $missing -Mode Database -ValidateOnly 2>&1)
    $tamperExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousPreference
    Assert-True ($tamperExitCode -ne 0 -and ($tamperOutput -join "`n") -match 'helper_integrity_failed') "helper_tamper_rejected"
}
finally {
    $resolvedTemp = [IO.Path]::GetFullPath($tempRoot)
    if ($resolvedTemp.StartsWith([IO.Path]::GetFullPath([IO.Path]::GetTempPath()), [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolvedTemp -Recurse -Force
    }
}

Write-Output "RECOVERY_POWERSHELL_TESTS=$tests/$tests PASS"
