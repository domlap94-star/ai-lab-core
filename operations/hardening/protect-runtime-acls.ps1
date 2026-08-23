[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$RepositoryRoot = "C:\ai-lab-core",
    [string]$BackupRoot = "C:\ai-lab-core-backups",
    [string]$BaselineRecord = "$env:LOCALAPPDATA\NEXT Stabil\Security\chunk20-acl-current-baseline-v3.json",
    [switch]$CaptureBaseline,
    [switch]$Apply,
    [switch]$Rollback
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "acl-hardening-core.ps1")

if (@($CaptureBaseline, $Apply, $Rollback | Where-Object { $_ }).Count -ne 1) {
    throw "acl_mode_required"
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Assert-SafeBaselineLocation([string]$Path) {
    $safeRoot = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA "NEXT Stabil\Security")).TrimEnd('\') + '\'
    $candidate = [IO.Path]::GetFullPath($Path)
    if (-not $candidate.StartsWith($safeRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "acl_baseline_location_unsafe"
    }
    $parent = Split-Path -Parent $candidate
    if (Test-Path -LiteralPath $parent) {
        $writeMask = [Security.AccessControl.FileSystemRights]::WriteData -bor
            [Security.AccessControl.FileSystemRights]::CreateFiles -bor
            [Security.AccessControl.FileSystemRights]::Modify -bor
            [Security.AccessControl.FileSystemRights]::FullControl
        foreach ($rule in (Get-Acl -LiteralPath $parent).Access) {
            try { $sid = $rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value } catch { continue }
            if ($rule.AccessControlType -eq 'Allow' -and
                $sid -in @('S-1-5-11', 'S-1-5-32-545') -and
                (($rule.FileSystemRights -band $writeMask) -ne 0)) {
                throw "acl_baseline_location_broad_write"
            }
        }
    }
}

function New-Rule(
    [string]$Identity,
    [Security.AccessControl.FileSystemRights]$Rights,
    [Security.AccessControl.InheritanceFlags]$Inheritance,
    [Security.AccessControl.PropagationFlags]$Propagation = [Security.AccessControl.PropagationFlags]::None
) {
    $identityReference = if ($Identity -match '^S-1-') {
        New-Object Security.Principal.SecurityIdentifier($Identity)
    } else {
        New-Object Security.Principal.NTAccount($Identity)
    }
    return New-Object Security.AccessControl.FileSystemAccessRule(
        $identityReference,
        $Rights,
        $Inheritance,
        $Propagation,
        [Security.AccessControl.AccessControlType]::Allow
    )
}

$targets = @(Get-Chunk20AclTargets -RepositoryRoot $RepositoryRoot -BackupRoot $BackupRoot)
Assert-Chunk20AclInventory $targets
$sourceHead = (git -C $RepositoryRoot rev-parse HEAD).Trim()
Assert-SafeBaselineLocation $BaselineRecord

if ($CaptureBaseline) {
    $item = New-Chunk20AclBaseline -Targets $targets -BaselineRecord $BaselineRecord -SourceHead $sourceHead
    Assert-SafeBaselineLocation $item.FullName
    [void](Assert-Chunk20AclBaseline -Targets $targets -BaselineRecord $BaselineRecord)
    Write-Output "CHUNK20_ACL_BASELINE_CAPTURED=$($item.FullName)"
    Write-Output "CHUNK20_ACL_BASELINE_TARGETS=22"
    exit 0
}

if (-not (Test-IsAdministrator)) {
    throw "acl_elevation_required_before_mutation"
}

$record = Assert-Chunk20AclBaseline -Targets $targets -BaselineRecord $BaselineRecord
if ($Rollback) {
    if ($PSCmdlet.ShouldProcess("22 canonical ACL targets", "Restore current-baseline ACLs")) {
        Restore-Chunk20AclEntries -Targets $targets -Record $record
    }
    Write-Output "CHUNK20_ACL_ROLLBACK=PASS"
    exit 0
}

Assert-Chunk20AclCurrentMatchesBaseline -Targets $targets -Record $record
$invocationStamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssfffZ")
$invocationRecordPath = Join-Path (Split-Path -Parent $BaselineRecord) "chunk20-acl-invocation-$invocationStamp.json"
$invocationItem = New-Chunk20AclBaseline -Targets $targets -BaselineRecord $invocationRecordPath -SourceHead $sourceHead
$record = Assert-Chunk20AclBaseline -Targets $targets -BaselineRecord $invocationItem.FullName
Assert-Chunk20AclCurrentMatchesBaseline -Targets $targets -Record $record
Write-Output "CHUNK20_ACL_INVOCATION_BASELINE=$($invocationItem.FullName)"
$operator = "$env:USERDOMAIN\$env:USERNAME"
$administrators = "S-1-5-32-544"
$system = "S-1-5-18"
$users = "S-1-5-32-545"
$applyAcl = {
    param($target)
    if (-not $PSCmdlet.ShouldProcess($target.path, "Protect runtime ACL")) { return }
    $acl = Get-Chunk20WritableAcl $target.path
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($rule in @($acl.Access)) {
        [void]$acl.RemoveAccessRuleSpecific($rule)
    }
    $inheritance = if ($target.path_type -eq "directory") {
        [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
        [Security.AccessControl.InheritanceFlags]::ObjectInherit
    } else {
        [Security.AccessControl.InheritanceFlags]::None
    }
    $acl.AddAccessRule((New-Rule $administrators FullControl $inheritance))
    $acl.AddAccessRule((New-Rule $system FullControl $inheritance))
    if ($target.access_class -eq "secret") {
        $acl.AddAccessRule((New-Rule $operator Read $inheritance))
    } else {
        $acl.AddAccessRule((New-Rule $operator Modify $inheritance))
    }
    if ($target.access_class -eq "code") {
        $acl.AddAccessRule((New-Rule $users ReadAndExecute $inheritance))
    }
    $daclSddl = $acl.GetSecurityDescriptorSddlForm(
        [Security.AccessControl.AccessControlSections]::Access
    )
    [Chunk20AclNative]::SetDacl($target.path, $daclSddl)
}

[void](Invoke-Chunk20AclTransaction -Targets $targets -Record $record -ApplyAcl $applyAcl)
Write-Output "CHUNK20_ACL_APPLY=PASS"
