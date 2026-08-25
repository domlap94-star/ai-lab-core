[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PayloadRoot
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

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$manifestPath = Join-Path $scriptDirectory 'wdac-accepted-native-payload.json'
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $scriptDirectory '..\..\..'))
$rawBuildRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot 'frontend\build\windows'))

if (-not (Test-Path -LiteralPath $PayloadRoot -PathType Container)) {
    throw "Windows payload root does not exist: $PayloadRoot"
}

$resolvedPayloadRoot = (Resolve-Path -LiteralPath $PayloadRoot).Path.TrimEnd('\')
if ($resolvedPayloadRoot.StartsWith($rawBuildRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'WINDOWS_NATIVE_PAYLOAD_NOT_INSTALLER_TRUSTED: direct Flutter output is never a Windows acceptance artifact on this WDAC-managed host.'
}

$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\NEXTStabil'
$installLocation = (Get-ItemProperty -LiteralPath $uninstallKey -Name InstallLocation -ErrorAction Stop).InstallLocation
if ([string]::IsNullOrWhiteSpace($installLocation) -or -not (Test-Path -LiteralPath $installLocation -PathType Container)) {
    throw 'WINDOWS_NATIVE_PAYLOAD_NOT_INSTALLER_TRUSTED: registered NEXT Stabil install root is unavailable.'
}
$resolvedInstallRoot = (Resolve-Path -LiteralPath $installLocation).Path.TrimEnd('\')
if (-not $resolvedPayloadRoot.Equals($resolvedInstallRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "WINDOWS_NATIVE_PAYLOAD_NOT_INSTALLER_TRUSTED: payload is not the registered install root: $resolvedPayloadRoot"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.schema -ne 'NEXT_STABIL_WDAC_ACCEPTED_NATIVE_PAYLOAD_V1') {
    throw 'Unsupported accepted native payload manifest schema.'
}

foreach ($nativeFile in $manifest.files) {
    $nativePath = Join-Path $resolvedPayloadRoot $nativeFile.filename
    if (-not (Test-Path -LiteralPath $nativePath -PathType Leaf) -or
        (Get-Sha256 -Path $nativePath) -ne $nativeFile.sha256.ToUpperInvariant()) {
        throw "WINDOWS_NATIVE_PAYLOAD_NOT_NORMALIZED: $($nativeFile.filename)"
    }
    Assert-ManagedInstallerEvidence -Path $nativePath
}

$frontendPath = Join-Path $resolvedPayloadRoot 'frontend.exe'
if (-not (Test-Path -LiteralPath $frontendPath -PathType Leaf)) {
    throw 'WINDOWS_NATIVE_PAYLOAD_NOT_INSTALLER_TRUSTED: frontend.exe is missing.'
}
Assert-ManagedInstallerEvidence -Path $frontendPath

Write-Host "WINDOWS_ACCEPTANCE_PAYLOAD_GATE=PASS"
Write-Host "PAYLOAD_ROOT=$resolvedPayloadRoot"
Write-Warning 'This pre-launch gate does not replace the required post-launch Code Integrity 3033/3077 audit.'
