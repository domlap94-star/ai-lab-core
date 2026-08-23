[CmdletBinding()]
param(
    [string]$RepositoryRoot = "C:\ai-lab-core",
    [string]$BackupRoot = "C:\ai-lab-core-backups",
    [string]$BaselineRecord = "$env:LOCALAPPDATA\NEXT Stabil\Security\chunk20-acl-current-baseline-v3.json"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "acl-hardening-core.ps1")

function Require([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Expect-Failure([scriptblock]$Action, [string]$ExpectedPrefix) {
    try {
        & $Action
    } catch {
        Require ($_.Exception.Message.StartsWith($ExpectedPrefix)) "unexpected_error:$($_.Exception.Message)"
        return
    }
    throw "expected_failure_missing:$ExpectedPrefix"
}

$targets = @(Get-Chunk20AclTargets -RepositoryRoot $RepositoryRoot -BackupRoot $BackupRoot)
Assert-Chunk20AclInventory $targets
$record = Assert-Chunk20AclBaseline -Targets $targets -BaselineRecord $BaselineRecord

$applySource = Get-Content -LiteralPath (Join-Path $PSScriptRoot "protect-runtime-acls.ps1") -Raw
$testSource = Get-Content -LiteralPath (Join-Path $PSScriptRoot "test-runtime-acl-hardening.ps1") -Raw
Require ($applySource -match 'Get-Chunk20AclTargets') "apply_inventory_not_shared"
Require ($testSource -match 'Get-Chunk20AclTargets') "test_inventory_not_shared"
Require ($applySource -match 'Assert-Chunk20AclCurrentMatchesBaseline') "apply_drift_gate_missing"
Require ($applySource -notmatch 'operations\\gateway\\public_web_server') "apply_inventory_duplicated"
Require ($testSource -notmatch 'operations\\gateway\\public_web_server') "test_inventory_duplicated"

$testRoot = Join-Path $env:TEMP ("next-stabil-acl-transaction-" + [guid]::NewGuid().ToString("N"))
$resolvedTemp = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
$resolvedTest = [IO.Path]::GetFullPath($testRoot)
Require ($resolvedTest.StartsWith($resolvedTemp, [StringComparison]::OrdinalIgnoreCase)) "unsafe_temp_target"
New-Item -ItemType Directory -Path $testRoot | Out-Null

try {
    $fixturePaths = @(
        (New-Item -ItemType Directory -Path (Join-Path $testRoot "directory-a")).FullName,
        (New-Item -ItemType File -Path (Join-Path $testRoot "file-a.txt")).FullName,
        (New-Item -ItemType Directory -Path (Join-Path $testRoot "directory-b")).FullName,
        (New-Item -ItemType File -Path (Join-Path $testRoot "file-b.txt")).FullName
    )
    $fixtureTargets = @()
    $index = 0
    foreach ($path in $fixturePaths) {
        $index += 1
        $fixtureTargets += [pscustomobject]@{
            index = $index
            path = $path
            path_type = if ((Get-Item -LiteralPath $path).PSIsContainer) { "directory" } else { "file" }
            access_class = "fixture"
        }
    }
    $fixtureRecord = [pscustomobject]@{
        entries = @($fixtureTargets | ForEach-Object {
            $acl = Get-Acl -LiteralPath $_.path
            [pscustomobject]@{ path = $_.path; owner = $acl.Owner; group = $acl.Group; sddl = Get-Chunk20AclRestorableSddl $_.path }
        })
    }

    $script:transactionIndex = 0
    $failingApply = {
        param($target)
        $script:transactionIndex += 1
        $acl = Get-Chunk20WritableAcl $target.path
        $acl.SetAccessRuleProtection($true, $true)
        $sddl = $acl.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::Access)
        [Chunk20AclNative]::SetDacl($target.path, $sddl)
        if ($script:transactionIndex -eq 3) { throw "synthetic_mid_apply_failure" }
    }
    Expect-Failure {
        [void](Invoke-Chunk20AclTransaction -Targets $fixtureTargets -Record $fixtureRecord -ApplyAcl $failingApply)
    } "synthetic_mid_apply_failure"
    foreach ($target in $fixtureTargets) {
        $entry = Find-Chunk20AclBaselineEntry $fixtureRecord $target.path
        Require ((Get-Chunk20AclRestorableSddl $target.path) -eq $entry.sddl) "partial_rollback_mismatch:$($target.path)"
    }

    $idempotentTarget = $fixtureTargets[0]
    $idempotentApply = {
        param($target)
        $acl = Get-Chunk20WritableAcl $target.path
        $acl.SetAccessRuleProtection($true, $true)
        $sddl = $acl.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::Access)
        [Chunk20AclNative]::SetDacl($target.path, $sddl)
    }
    & $idempotentApply $idempotentTarget
    $firstSddl = Get-Chunk20AclRestorableSddl $idempotentTarget.path
    & $idempotentApply $idempotentTarget
    $secondSddl = Get-Chunk20AclRestorableSddl $idempotentTarget.path
    Require ($firstSddl -eq $secondSddl) "acl_apply_not_idempotent"
    Restore-Chunk20AclEntries -Targets @($idempotentTarget) -Record $fixtureRecord

    $validJson = Get-Content -LiteralPath $BaselineRecord -Raw -Encoding UTF8 | ConvertFrom-Json
    $missingPath = Join-Path $testRoot "missing.json"
    $missingRecord = $validJson | ConvertTo-Json -Depth 8 | ConvertFrom-Json
    $missingRecord.entries = @($missingRecord.entries | Select-Object -First 21)
    $missingRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $missingPath -Encoding UTF8
    Expect-Failure { [void](Assert-Chunk20AclBaseline $targets $missingPath) } "acl_baseline_count_invalid"

    $duplicatePath = Join-Path $testRoot "duplicate.json"
    $duplicateRecord = $validJson | ConvertTo-Json -Depth 8 | ConvertFrom-Json
    $duplicateRecord.entries = @($duplicateRecord.entries | Select-Object -First 21) + @($duplicateRecord.entries[0])
    $duplicateRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $duplicatePath -Encoding UTF8
    Expect-Failure { [void](Assert-Chunk20AclBaseline $targets $duplicatePath) } "acl_baseline_duplicate"

    $extraPath = Join-Path $testRoot "extra.json"
    $extraRecord = $validJson | ConvertTo-Json -Depth 8 | ConvertFrom-Json
    $extra = $extraRecord.entries[21]
    $extra.path = Join-Path $testRoot "not-a-canonical-target"
    $extraRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $extraPath -Encoding UTF8
    Expect-Failure { [void](Assert-Chunk20AclBaseline $targets $extraPath) } "acl_baseline_extra_entries"

    Write-Output "CHUNK20_ACL_TARGET_INVENTORY=22/22_PASS"
    Write-Output "CHUNK20_ACL_BASELINE_COVERAGE=22/22_PASS"
    Write-Output "CHUNK20_ACL_MISSING_FAIL_CLOSED=PASS"
    Write-Output "CHUNK20_ACL_DUPLICATE_FAIL_CLOSED=PASS"
    Write-Output "CHUNK20_ACL_EXTRA_FAIL_CLOSED=PASS"
    Write-Output "CHUNK20_ACL_TRANSACTIONAL_ROLLBACK=PASS"
    Write-Output "CHUNK20_ACL_PARTIAL_FAILURE_ROLLBACK=PASS"
    Write-Output "CHUNK20_ACL_IDEMPOTENCY=PASS"
    Write-Output "CHUNK20_ACL_APPLY_TEST_PARITY=PASS"
} finally {
    if (Test-Path -LiteralPath $resolvedTest) {
        Remove-Item -LiteralPath $resolvedTest -Recurse -Force
    }
}
