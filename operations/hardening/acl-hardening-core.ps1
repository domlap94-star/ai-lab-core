$ErrorActionPreference = "Stop"

$script:Chunk20AclBaselineSchema = "NEXT_STABIL_ACL_BASELINE_V3"
$script:Chunk20AclBaselineType = "CURRENT_PRE_FINALIZATION_BASELINE"

if (-not ("Chunk20AclNative" -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class Chunk20AclNative {
    private const uint SE_FILE_OBJECT = 1;
    private const uint DACL_SECURITY_INFORMATION = 0x00000004;
    private const uint PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000;
    private const uint UNPROTECTED_DACL_SECURITY_INFORMATION = 0x20000000;
    private const ushort SE_DACL_PROTECTED = 0x1000;

    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool ConvertStringSecurityDescriptorToSecurityDescriptor(
        string descriptor, uint revision, out IntPtr securityDescriptor, out uint size);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool GetSecurityDescriptorDacl(
        IntPtr securityDescriptor, out bool present, out IntPtr dacl, out bool defaulted);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool GetSecurityDescriptorControl(
        IntPtr securityDescriptor, out ushort control, out uint revision);

    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern uint SetNamedSecurityInfo(
        string objectName, uint objectType, uint securityInfo,
        IntPtr owner, IntPtr group, IntPtr dacl, IntPtr sacl);

    [DllImport("kernel32.dll")]
    private static extern IntPtr LocalFree(IntPtr memory);

    public static void SetDacl(string path, string daclSddl) {
        IntPtr descriptor;
        uint size;
        if (!ConvertStringSecurityDescriptorToSecurityDescriptor(daclSddl, 1, out descriptor, out size))
            throw new Win32Exception(Marshal.GetLastWin32Error());
        try {
            bool present, defaulted;
            IntPtr dacl;
            if (!GetSecurityDescriptorDacl(descriptor, out present, out dacl, out defaulted) || !present)
                throw new Win32Exception(Marshal.GetLastWin32Error(), "DACL is missing");
            ushort control;
            uint revision;
            if (!GetSecurityDescriptorControl(descriptor, out control, out revision))
                throw new Win32Exception(Marshal.GetLastWin32Error());
            uint flags = DACL_SECURITY_INFORMATION |
                ((control & SE_DACL_PROTECTED) != 0
                    ? PROTECTED_DACL_SECURITY_INFORMATION
                    : UNPROTECTED_DACL_SECURITY_INFORMATION);
            uint result = SetNamedSecurityInfo(
                path, SE_FILE_OBJECT, flags, IntPtr.Zero, IntPtr.Zero, dacl, IntPtr.Zero);
            if (result != 0) throw new Win32Exception((int)result);
        } finally {
            LocalFree(descriptor);
        }
    }
}
"@
}

function Get-Chunk20AclRestorableSddl([string]$Path) {
    $sections = [Security.AccessControl.AccessControlSections]::Access
    return (Get-Acl -LiteralPath $Path).GetSecurityDescriptorSddlForm($sections)
}

function Get-Chunk20WritableAcl([string]$Path) {
    $sections = [Security.AccessControl.AccessControlSections]::Access
    $acl = if ((Get-Item -LiteralPath $Path).PSIsContainer) {
        New-Object Security.AccessControl.DirectorySecurity
    } else {
        New-Object Security.AccessControl.FileSecurity
    }
    $acl.SetSecurityDescriptorSddlForm((Get-Chunk20AclRestorableSddl $Path), $sections)
    return $acl
}

function Resolve-Chunk20AclPath([string]$Path) {
    $resolved = [IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $resolved)) {
        throw "acl_path_missing:$resolved"
    }
    return $resolved.TrimEnd('\')
}

function Get-Chunk20AclTargets(
    [string]$RepositoryRoot = "C:\ai-lab-core",
    [string]$BackupRoot = "C:\ai-lab-core-backups"
) {
    $repo = Resolve-Chunk20AclPath $RepositoryRoot
    $definitions = @(
        @($repo, "code"),
        @((Join-Path $repo "backend"), "code"),
        @((Join-Path $repo "compose"), "code"),
        @((Join-Path $repo "operations"), "code"),
        @((Join-Path $repo "operations\hardening"), "code"),
        @((Join-Path $repo "operations\gateway"), "code"),
        @((Join-Path $repo "operations\supervisor"), "code"),
        @((Join-Path $repo "operations\windows"), "code"),
        @((Join-Path $repo "release-channel"), "code"),
        @((Join-Path $repo "operations\hardening\run-trash-purge.ps1"), "code"),
        @((Join-Path $repo "operations\hardening\run-backup-schedule.ps1"), "code"),
        @((Join-Path $repo "operations\hardening\backup-production.ps1"), "code"),
        @((Join-Path $repo "operations\gateway\public_web_server.cjs"), "code"),
        @((Join-Path $repo "operations\gateway\web_server.cjs"), "code"),
        @((Join-Path $repo "operations\supervisor\server.js"), "code"),
        @((Join-Path $repo "operations\windows\start-compose-after-docker.ps1"), "code"),
        @((Join-Path $repo "release-channel\stable\manifest.json"), "code"),
        @((Join-Path $repo "data\vision-spool"), "runtime"),
        @((Join-Path $repo "data\analysis-spool"), "runtime"),
        @((Resolve-Chunk20AclPath $BackupRoot), "runtime"),
        @((Join-Path $repo ".env"), "secret"),
        @((Join-Path $repo "frontend\android\key.properties"), "secret")
    )

    $index = 0
    foreach ($definition in $definitions) {
        $index += 1
        $path = Resolve-Chunk20AclPath $definition[0]
        $item = Get-Item -LiteralPath $path
        $acl = Get-Acl -LiteralPath $path
        [pscustomobject]@{
            index = $index
            path = $path
            path_type = if ($item.PSIsContainer) { "directory" } else { "file" }
            access_class = $definition[1]
            requires_elevation = ($acl.Owner -match 'Administrators|Administratorzy')
        }
    }
}

function Get-Chunk20AclTargetHash([object[]]$Targets) {
    $lines = @($Targets | Sort-Object index | ForEach-Object {
        "{0}|{1}|{2}|{3}" -f $_.index, $_.path.ToLowerInvariant(), $_.path_type, $_.access_class
    })
    $bytes = [Text.Encoding]::UTF8.GetBytes(($lines -join "`n"))
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Assert-Chunk20AclInventory([object[]]$Targets) {
    if ($Targets.Count -ne 22) { throw "acl_target_count_invalid:$($Targets.Count)" }
    $paths = @($Targets | ForEach-Object { $_.path.ToLowerInvariant() })
    if (@($paths | Select-Object -Unique).Count -ne 22) { throw "acl_target_duplicate" }
    if (@($Targets | Where-Object { -not $_.path -or -not $_.path_type -or -not $_.access_class }).Count) {
        throw "acl_target_invalid"
    }
}

function New-Chunk20AclBaseline(
    [object[]]$Targets,
    [string]$BaselineRecord,
    [string]$SourceHead
) {
    Assert-Chunk20AclInventory $Targets
    if (Test-Path -LiteralPath $BaselineRecord) {
        throw "acl_baseline_already_exists"
    }
    $entries = @($Targets | Sort-Object index | ForEach-Object {
        $acl = Get-Acl -LiteralPath $_.path
        [pscustomobject]@{
            index = $_.index
            path = $_.path
            path_type = $_.path_type
            access_class = $_.access_class
            owner = $acl.Owner
            group = $acl.Group
            sddl = Get-Chunk20AclRestorableSddl $_.path
        }
    })
    $record = [ordered]@{
        schema_version = $script:Chunk20AclBaselineSchema
        record_type = $script:Chunk20AclBaselineType
        created_at = [DateTime]::UtcNow.ToString("o")
        target_count = 22
        source_head = $SourceHead
        chunk = 20
        historical_pre_hardening = $false
        target_list_sha256 = Get-Chunk20AclTargetHash $Targets
        entries = $entries
    }
    $parent = Split-Path -Parent ([IO.Path]::GetFullPath($BaselineRecord))
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent | Out-Null
    }
    $record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $BaselineRecord -Encoding UTF8
    return Get-Item -LiteralPath $BaselineRecord
}

function Assert-Chunk20AclBaseline(
    [object[]]$Targets,
    [string]$BaselineRecord
) {
    Assert-Chunk20AclInventory $Targets
    if (-not (Test-Path -LiteralPath $BaselineRecord)) { throw "acl_baseline_missing" }
    $record = Get-Content -LiteralPath $BaselineRecord -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($record.schema_version -ne $script:Chunk20AclBaselineSchema -or
        $record.record_type -ne $script:Chunk20AclBaselineType -or
        $record.historical_pre_hardening -ne $false) {
        throw "acl_baseline_metadata_invalid"
    }
    $entries = @($record.entries)
    if ($record.target_count -ne 22 -or $entries.Count -ne 22) {
        throw "acl_baseline_count_invalid:$($entries.Count)"
    }
    $entryPaths = @($entries | ForEach-Object {
        ([IO.Path]::GetFullPath($_.path)).TrimEnd('\').ToLowerInvariant()
    })
    if (@($entryPaths | Select-Object -Unique).Count -ne 22) { throw "acl_baseline_duplicate" }
    $targetPaths = @($Targets | ForEach-Object { $_.path.ToLowerInvariant() })
    $missing = @($targetPaths | Where-Object { $_ -notin $entryPaths })
    $extra = @($entryPaths | Where-Object { $_ -notin $targetPaths })
    if ($extra.Count) { throw "acl_baseline_extra_entries:$($extra.Count)" }
    if ($missing.Count) { throw "acl_baseline_missing_entries:$($missing.Count)" }
    if ($record.target_list_sha256 -ne (Get-Chunk20AclTargetHash $Targets)) {
        throw "acl_baseline_target_hash_invalid"
    }
    if (@($entries | Where-Object { -not $_.sddl -or -not $_.owner -or -not $_.group }).Count) {
        throw "acl_baseline_entry_invalid"
    }
    return $record
}

function Find-Chunk20AclBaselineEntry([object]$Record, [string]$Path) {
    return @($Record.entries | Where-Object {
        ([IO.Path]::GetFullPath($_.path)).TrimEnd('\') -ieq $Path
    })[0]
}

function Assert-Chunk20AclCurrentMatchesBaseline([object[]]$Targets, [object]$Record) {
    foreach ($target in $Targets) {
        $entry = Find-Chunk20AclBaselineEntry $Record $target.path
        $acl = Get-Acl -LiteralPath $target.path
        if ((Get-Chunk20AclRestorableSddl $target.path) -ne $entry.sddl -or
            $acl.Owner -ne $entry.owner -or $acl.Group -ne $entry.group) {
            throw "acl_current_baseline_drift:$($target.path)"
        }
    }
}

function Restore-Chunk20AclEntries([object[]]$Targets, [object]$Record) {
    foreach ($target in @($Targets | Sort-Object index -Descending)) {
        $entry = Find-Chunk20AclBaselineEntry $Record $target.path
        [Chunk20AclNative]::SetDacl($target.path, [string]$entry.sddl)
    }
    foreach ($target in $Targets) {
        $entry = Find-Chunk20AclBaselineEntry $Record $target.path
        $acl = Get-Acl -LiteralPath $target.path
        if ((Get-Chunk20AclRestorableSddl $target.path) -ne $entry.sddl -or
            $acl.Owner -ne $entry.owner -or $acl.Group -ne $entry.group) {
            throw "acl_rollback_verification_failed:$($target.path)"
        }
    }
}

function Invoke-Chunk20AclTransaction(
    [object[]]$Targets,
    [object]$Record,
    [scriptblock]$ApplyAcl
) {
    $mutated = New-Object System.Collections.ArrayList
    try {
        foreach ($target in $Targets | Sort-Object index) {
            [void]$mutated.Add($target)
            & $ApplyAcl $target
        }
    } catch {
        Restore-Chunk20AclEntries -Targets @($mutated) -Record $Record
        throw
    }
    return @($mutated)
}
