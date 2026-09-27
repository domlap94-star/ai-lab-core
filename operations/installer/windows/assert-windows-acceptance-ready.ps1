[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PayloadRoot,

    [ValidateSet('SAC_ON_INSTALLER_TRUSTED', 'SAC_OFF_OWNER_MANAGED_HOST')]
    [string]$AcceptanceMode = 'SAC_ON_INSTALLER_TRUSTED',

    [string]$ExpectedPayloadManifestPath,

    [string[]]$AllowedRuntimeGeneratedFile = @()
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
}

function Assert-ManagedInstallerEvidence {
    param([Parameter(Mandatory = $true)][string]$Path)

    $output = (& fsutil.exe file queryEA $Path 2>&1 | ForEach-Object { $_.ToString() }) -join "`n"
    if ($LASTEXITCODE -ne 0 -or
        -not $output.Contains('$KERNEL.SMARTLOCKER.ORIGINCLAIM') -or
        -not $output.Contains('$KERNEL.PURGE.SMARTLOCKER.VALID')) {
        throw "WINDOWS_NATIVE_PAYLOAD_NOT_INSTALLER_TRUSTED: missing Managed Installer evidence for $Path"
    }
}

function Get-SafeRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$RelativePath
    )

    $normalized = $RelativePath.Replace('/', '\').TrimStart('\')
    if ([string]::IsNullOrWhiteSpace($normalized) -or
        [IO.Path]::IsPathRooted($normalized) -or
        @($normalized.Split('\') | Where-Object { $_ -eq '..' }).Count -ne 0) {
        throw "WINDOWS_PAYLOAD_MANIFEST_PATH_INVALID: $RelativePath"
    }
    $absolute = [IO.Path]::GetFullPath((Join-Path $Root $normalized))
    $prefix = $Root.TrimEnd('\') + '\'
    if (-not $absolute.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "WINDOWS_PAYLOAD_MANIFEST_PATH_ESCAPE: $RelativePath"
    }
    return [ordered]@{
        relative = $normalized.Replace('\', '/')
        absolute = $absolute
    }
}

function Assert-NoBroadWritableAcl {
    param([Parameter(Mandatory = $true)][string]$Path)

    $broadSids = @('S-1-1-0', 'S-1-5-11', 'S-1-5-32-545', 'S-1-5-32-546')
    $writeMask = [Security.AccessControl.FileSystemRights]::Write -bor
        [Security.AccessControl.FileSystemRights]::Modify -bor
        [Security.AccessControl.FileSystemRights]::FullControl -bor
        [Security.AccessControl.FileSystemRights]::WriteData -bor
        [Security.AccessControl.FileSystemRights]::CreateFiles -bor
        [Security.AccessControl.FileSystemRights]::CreateDirectories
    $acl = Get-Acl -LiteralPath $Path
    foreach ($rule in $acl.Access) {
        if ($rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow) {
            continue
        }
        try {
            $sid = $rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
        }
        catch {
            throw "WINDOWS_EXECUTABLE_ACL_IDENTITY_UNRESOLVED: $Path / $($rule.IdentityReference.Value)"
        }
        if ($sid -in $broadSids -and ($rule.FileSystemRights -band $writeMask)) {
            throw "WINDOWS_EXECUTABLE_LOCATION_BROADLY_WRITABLE: $Path / $sid"
        }
    }
}

function Assert-ShortcutTarget {
    param(
        [Parameter(Mandatory = $true)][string]$ShortcutPath,
        [Parameter(Mandatory = $true)][string]$ExpectedTarget
    )

    if (-not (Test-Path -LiteralPath $ShortcutPath -PathType Leaf)) {
        throw "WINDOWS_SHORTCUT_MISSING: $ShortcutPath"
    }
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    if (-not ([IO.Path]::GetFullPath($shortcut.TargetPath)).Equals(
        [IO.Path]::GetFullPath($ExpectedTarget),
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "WINDOWS_SHORTCUT_TARGET_MISMATCH: $ShortcutPath"
    }
}

function Assert-OwnerManagedSecurity {
    $policy = Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy' -ErrorAction Stop
    if ([int]$policy.VerifiedAndReputablePolicyState -ne 0) {
        throw "WINDOWS_SAC_NOT_OFF: state=$($policy.VerifiedAndReputablePolicyState)"
    }

    $bitdefender = @(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct -ErrorAction Stop |
        Where-Object { $_.displayName -match 'Bitdefender' })
    if ($bitdefender.Count -eq 0 -or @($bitdefender | Where-Object { ([int]$_.productState -band 0x1000) -ne 0 }).Count -eq 0) {
        throw 'WINDOWS_BITDEFENDER_NOT_ACTIVE'
    }

    $firewall = @(Get-NetFirewallProfile -ErrorAction Stop)
    if ($firewall.Count -lt 3 -or @($firewall | Where-Object { -not [bool]$_.Enabled }).Count -ne 0) {
        throw 'WINDOWS_FIREWALL_NOT_ACTIVE'
    }

    $uac = (Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' -Name EnableLUA -ErrorAction Stop).EnableLUA
    if ([int]$uac -ne 1) {
        throw 'WINDOWS_UAC_NOT_ACTIVE'
    }
}

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$nativeManifestPath = Join-Path $scriptDirectory 'wdac-accepted-native-payload.json'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $scriptDirectory '..\..\..'))
$rawBuildRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot 'frontend\build\windows'))
$canonicalInstallRoot = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Programs\NEXT Stabil')).TrimEnd('\')

if (-not (Test-Path -LiteralPath $PayloadRoot -PathType Container)) {
    throw "Windows payload root does not exist: $PayloadRoot"
}

$resolvedPayloadRoot = (Resolve-Path -LiteralPath $PayloadRoot).Path.TrimEnd('\')
if ($resolvedPayloadRoot.StartsWith($rawBuildRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'WINDOWS_NATIVE_PAYLOAD_NOT_INSTALLER_TRUSTED: direct Flutter output is never a Windows acceptance artifact on this host.'
}

$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\NEXTStabil'
$uninstall = Get-ItemProperty -LiteralPath $uninstallKey -ErrorAction Stop
$installLocation = [string]$uninstall.InstallLocation
if ([string]::IsNullOrWhiteSpace($installLocation) -or -not (Test-Path -LiteralPath $installLocation -PathType Container)) {
    throw 'WINDOWS_NATIVE_PAYLOAD_NOT_INSTALLER_TRUSTED: registered NEXT Stabil install root is unavailable.'
}
$resolvedInstallRoot = (Resolve-Path -LiteralPath $installLocation).Path.TrimEnd('\')
if (-not $resolvedPayloadRoot.Equals($resolvedInstallRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "WINDOWS_NATIVE_PAYLOAD_NOT_INSTALLER_TRUSTED: payload is not the registered install root: $resolvedPayloadRoot"
}
if (-not $resolvedInstallRoot.Equals($canonicalInstallRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "WINDOWS_INSTALL_ROOT_NOT_CANONICAL: $resolvedInstallRoot"
}

$nativeManifest = Get-Content -LiteralPath $nativeManifestPath -Raw | ConvertFrom-Json
if ($nativeManifest.schema -ne 'NEXT_STABIL_WDAC_ACCEPTED_NATIVE_PAYLOAD_V1') {
    throw 'Unsupported accepted native payload manifest schema.'
}
foreach ($nativeFile in $nativeManifest.files) {
    $nativePath = Join-Path $resolvedPayloadRoot $nativeFile.filename
    if (-not (Test-Path -LiteralPath $nativePath -PathType Leaf) -or
        (Get-Sha256 -Path $nativePath) -ne $nativeFile.sha256.ToUpperInvariant()) {
        throw "WINDOWS_NATIVE_PAYLOAD_NOT_NORMALIZED: $($nativeFile.filename)"
    }
}

$frontendPath = Join-Path $resolvedPayloadRoot 'frontend.exe'
if (-not (Test-Path -LiteralPath $frontendPath -PathType Leaf)) {
    throw 'WINDOWS_NATIVE_PAYLOAD_NOT_INSTALLER_TRUSTED: frontend.exe is missing.'
}

if ($AcceptanceMode -eq 'SAC_ON_INSTALLER_TRUSTED') {
    foreach ($nativeFile in $nativeManifest.files) {
        Assert-ManagedInstallerEvidence -Path (Join-Path $resolvedPayloadRoot $nativeFile.filename)
    }
    Assert-ManagedInstallerEvidence -Path $frontendPath
}
else {
    Assert-OwnerManagedSecurity

    if ([string]::IsNullOrWhiteSpace($ExpectedPayloadManifestPath) -or
        -not (Test-Path -LiteralPath $ExpectedPayloadManifestPath -PathType Leaf)) {
        throw 'WINDOWS_EXPECTED_PAYLOAD_MANIFEST_REQUIRED'
    }
    $expectedManifest = Get-Content -LiteralPath $ExpectedPayloadManifestPath -Raw | ConvertFrom-Json
    if ($expectedManifest.schema -ne 'NEXT_STABIL_WINDOWS_BUILD_MANIFEST_V1') {
        throw 'WINDOWS_EXPECTED_PAYLOAD_MANIFEST_SCHEMA_UNSUPPORTED'
    }
    if ([string]$expectedManifest.version -notmatch '^\d+\.\d+\.\d+$' -or [int]$expectedManifest.build_number -lt 1) {
        throw 'WINDOWS_EXPECTED_PAYLOAD_VERSION_INVALID'
    }

    $expected = @{}
    foreach ($entry in @($expectedManifest.payload_files)) {
        $safe = Get-SafeRelativePath -Root $resolvedInstallRoot -RelativePath ([string]$entry.relative_path)
        $key = $safe.relative.ToLowerInvariant()
        if ($expected.ContainsKey($key)) {
            throw "WINDOWS_EXPECTED_PAYLOAD_DUPLICATE: $($safe.relative)"
        }
        if ([int64]$entry.bytes -lt 0 -or [string]$entry.sha256 -notmatch '^[0-9A-Fa-f]{64}$') {
            throw "WINDOWS_EXPECTED_PAYLOAD_RECORD_INVALID: $($safe.relative)"
        }
        $expected[$key] = [ordered]@{
            relative = $safe.relative
            absolute = $safe.absolute
            bytes = [int64]$entry.bytes
            sha256 = ([string]$entry.sha256).ToUpperInvariant()
        }
    }
    if ($expected.Count -eq 0) {
        throw 'WINDOWS_EXPECTED_PAYLOAD_EMPTY'
    }

    $allowed = @{}
    foreach ($relative in @($AllowedRuntimeGeneratedFile)) {
        $safe = Get-SafeRelativePath -Root $resolvedInstallRoot -RelativePath $relative
        $key = $safe.relative.ToLowerInvariant()
        if ($expected.ContainsKey($key) -or $allowed.ContainsKey($key)) {
            throw "WINDOWS_ALLOWED_RUNTIME_FILE_DUPLICATE: $($safe.relative)"
        }
        $allowed[$key] = $safe
    }

    $actualFiles = @(Get-ChildItem -LiteralPath $resolvedInstallRoot -File -Force -Recurse)
    foreach ($file in $actualFiles) {
        $full = [IO.Path]::GetFullPath($file.FullName)
        $prefix = $resolvedInstallRoot.TrimEnd('\') + '\'
        if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "WINDOWS_INSTALLED_FILE_PATH_ESCAPE: $full"
        }
        $relative = $full.Substring($prefix.Length).Replace('\', '/')
        $key = $relative.ToLowerInvariant()
        if ($expected.ContainsKey($key)) {
            $record = $expected[$key]
            if ([int64]$file.Length -ne $record.bytes) {
                throw "WINDOWS_PAYLOAD_FILE_SIZE_MISMATCH: $relative"
            }
            if ((Get-Sha256 -Path $full) -ne $record.sha256) {
                throw "WINDOWS_PAYLOAD_FILE_HASH_MISMATCH: $relative"
            }
            [void]$expected.Remove($key)
        }
        elseif (-not $allowed.ContainsKey($key)) {
            throw "WINDOWS_UNEXPECTED_INSTALLED_FILE: $relative"
        }
    }
    if ($expected.Count -ne 0) {
        throw "WINDOWS_EXPECTED_INSTALLED_FILE_MISSING: $((@($expected.Values | ForEach-Object { $_.relative }) | Sort-Object) -join ',')"
    }
    foreach ($allowedFile in $allowed.Values) {
        if (-not (Test-Path -LiteralPath $allowedFile.absolute -PathType Leaf)) {
            throw "WINDOWS_ALLOWED_RUNTIME_FILE_MISSING: $($allowedFile.relative)"
        }
    }

    $allItems = @((Get-Item -LiteralPath $resolvedInstallRoot)) + @(Get-ChildItem -LiteralPath $resolvedInstallRoot -Force -Recurse)
    foreach ($item in $allItems) {
        if ([bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "WINDOWS_INSTALLED_ROOT_REPARSE_NOT_ALLOWED: $($item.FullName)"
        }
    }

    $executableDirectories = @($actualFiles |
        Where-Object { $_.Extension -in @('.exe', '.dll') } |
        ForEach-Object { $_.DirectoryName } |
        Sort-Object -Unique)
    foreach ($directory in @($resolvedInstallRoot) + $executableDirectories) {
        Assert-NoBroadWritableAcl -Path $directory
    }

    $expectedDisplayVersion = [string]$expectedManifest.version
    if ([string]$uninstall.DisplayName -ne 'NEXT Stabil' -or
        [string]$uninstall.DisplayVersion -ne $expectedDisplayVersion -or
        [int]$uninstall.NoModify -ne 1 -or
        [int]$uninstall.NoRepair -ne 1) {
        throw 'WINDOWS_UNINSTALL_METADATA_MISMATCH'
    }
    $expectedUninstaller = Join-Path $resolvedInstallRoot 'Uninstall.exe'
    $registeredUninstaller = ([string]$uninstall.UninstallString).Trim().Trim('"')
    if (-not ([IO.Path]::GetFullPath($registeredUninstaller)).Equals(
        [IO.Path]::GetFullPath($expectedUninstaller),
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw 'WINDOWS_UNINSTALL_TARGET_MISMATCH'
    }

    Assert-ShortcutTarget -ShortcutPath (Join-Path ([Environment]::GetFolderPath('Desktop')) 'NEXT Stabil.lnk') -ExpectedTarget $frontendPath
    Assert-ShortcutTarget -ShortcutPath (Join-Path ([Environment]::GetFolderPath('Programs')) 'NEXT Stabil\NEXT Stabil.lnk') -ExpectedTarget $frontendPath

    $frontendVersion = (Get-Item -LiteralPath $frontendPath).VersionInfo
    $expectedVisibleVersion = "$($expectedManifest.version)+$($expectedManifest.build_number)"
    if ($frontendVersion.ProductVersion -ne $expectedVisibleVersion -or
        $frontendVersion.FileVersion -ne $expectedVisibleVersion) {
        throw "WINDOWS_FRONTEND_VERSION_MISMATCH: expected=$expectedVisibleVersion product=$($frontendVersion.ProductVersion) file=$($frontendVersion.FileVersion)"
    }
}

Write-Host 'WINDOWS_ACCEPTANCE_PAYLOAD_GATE=PASS'
Write-Host "WINDOWS_ACCEPTANCE_MODE=$AcceptanceMode"
Write-Host "PAYLOAD_ROOT=$resolvedPayloadRoot"
if ($AcceptanceMode -eq 'SAC_ON_INSTALLER_TRUSTED') {
    Write-Warning 'This pre-launch gate does not replace the required post-launch Code Integrity 3033/3077 audit.'
}
else {
    Write-Host 'WINDOWS_OWNER_MANAGED_SECURITY_GATE=PASS'
    Write-Host 'WINDOWS_EXACT_INSTALLED_ROOT_HASH_GATE=PASS'
}
