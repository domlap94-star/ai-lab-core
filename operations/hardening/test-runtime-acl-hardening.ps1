[CmdletBinding()]
param(
    [string]$RepositoryRoot = "C:\ai-lab-core",
    [string]$BackupRoot = "C:\ai-lab-core-backups",
    [switch]$AllowIncomplete
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "acl-hardening-core.ps1")

$operator = "$env:USERDOMAIN\$env:USERNAME"
$broadPrincipalPattern = 'Authenticated Users|Użytkownicy uwierzytelnieni'
$writeMask = [Security.AccessControl.FileSystemRights]::WriteData -bor
    [Security.AccessControl.FileSystemRights]::CreateFiles -bor
    [Security.AccessControl.FileSystemRights]::AppendData -bor
    [Security.AccessControl.FileSystemRights]::Delete -bor
    [Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles -bor
    [Security.AccessControl.FileSystemRights]::ChangePermissions -bor
    [Security.AccessControl.FileSystemRights]::TakeOwnership

$targets = @(Get-Chunk20AclTargets -RepositoryRoot $RepositoryRoot -BackupRoot $BackupRoot)
Assert-Chunk20AclInventory $targets
$failures = @()
foreach ($target in $targets) {
    $acl = Get-Acl -LiteralPath $target.path
    if (-not $acl.AreAccessRulesProtected) {
        $failures += "inheritance_enabled:$($target.path)"
    }
    foreach ($rule in $acl.Access) {
        if (
            $rule.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
            $rule.IdentityReference.Value -match $broadPrincipalPattern -and
            (($rule.FileSystemRights -band $writeMask) -ne 0)
        ) {
            $failures += "broad_write:$($target.path)"
        }
    }
    $operatorRule = @($acl.Access | Where-Object {
        $_.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
        $_.IdentityReference.Value -eq $operator
    })
    if ($operatorRule.Count -eq 0) {
        $failures += "operator_missing:$($target.path)"
    }
}

Write-Output "CHUNK20_ACL_CANONICAL_TARGETS=$($targets.Count)"
Write-Output "CHUNK20_ACL_TARGET_HASH=$(Get-Chunk20AclTargetHash $targets)"
if ($failures.Count -ne 0) {
    Write-Output "CHUNK20_ACL_INCOMPLETE=$($failures -join ';')"
    if (-not $AllowIncomplete) {
        throw "runtime_acl_hardening_incomplete"
    }
} else {
    Write-Output "CHUNK20_ACL_NEGATIVE_WRITE_SEMANTICS=PASS"
    Write-Output "CHUNK20_RUNTIME_ACL_HARDENING=PASS"
}
