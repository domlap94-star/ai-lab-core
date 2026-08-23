[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,

    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 2147483647)]
    [int]$BuildNumber,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^https?://')]
    [string]$ApiBaseUrl,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^https?://')]
    [string]$SupervisorBaseUrl,

    [Parameter(Mandatory = $true)]
    [string]$AcceptedNativeRoot,

    [Parameter(Mandatory = $true)]
    [string]$StagingRoot,

    [string]$FlutterPath = 'C:\FlutterSDK-New\flutter\bin\flutter.bat',

    [string]$MakensisPath = 'C:\Users\domai\AppData\Local\NEXT Stabil\Tools\NSIS\3.12\makensis.exe'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Command"
    }
}

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
}

function Get-OptionalCommandOutput {
    param(
        [AllowNull()][string]$Command,
        [string[]]$Arguments = @()
    )
    if ([string]::IsNullOrWhiteSpace($Command) -or -not (Test-Path -LiteralPath $Command -PathType Leaf)) {
        return $null
    }
    $output = & $Command @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    return (($output | ForEach-Object { $_.ToString() }) -join "`n").Trim()
}

function Get-PayloadFileRecords {
    param([Parameter(Mandatory = $true)][string]$PayloadRoot)
    $prefixLength = $PayloadRoot.TrimEnd('\').Length + 1
    return @(Get-ChildItem -LiteralPath $PayloadRoot -File -Recurse |
        Sort-Object FullName |
        ForEach-Object {
            [ordered]@{
                relative_path = $_.FullName.Substring($prefixLength).Replace('\', '/')
                bytes = $_.Length
                sha256 = Get-Sha256 -Path $_.FullName
            }
        })
}

function Get-ToolchainRecord {
    param(
        [Parameter(Mandatory = $true)][string]$FlutterExecutable,
        [Parameter(Mandatory = $true)][string]$MakensisExecutable
    )
    $flutterVersion = (& $FlutterExecutable --version --machine | ConvertFrom-Json)
    $vswherePath = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
    $visualStudioPath = Get-OptionalCommandOutput -Command $vswherePath -Arguments @('-latest', '-products', '*', '-property', 'installationPath')
    $visualStudioVersion = Get-OptionalCommandOutput -Command $vswherePath -Arguments @('-latest', '-products', '*', '-property', 'installationVersion')
    $cmakePath = $null
    $ninjaPath = $null
    $linkerPath = $null
    if ($visualStudioPath) {
        $cmakePath = Join-Path $visualStudioPath 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
        $ninjaPath = Join-Path $visualStudioPath 'Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe'
        $linkerPath = Get-ChildItem -LiteralPath (Join-Path $visualStudioPath 'VC\Tools\MSVC') -Filter link.exe -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\\bin\\Hostx64\\x64\\link\.exe$' } |
            Sort-Object FullName -Descending |
            Select-Object -First 1 -ExpandProperty FullName
    }
    $sdkRoot = 'C:\Program Files (x86)\Windows Kits\10\bin'
    $windowsSdkVersion = $null
    if (Test-Path -LiteralPath $sdkRoot -PathType Container) {
        $windowsSdkVersion = Get-ChildItem -LiteralPath $sdkRoot -Directory |
            Where-Object { $_.Name -match '^\d+\.\d+\.\d+\.\d+$' } |
            Sort-Object { [version]$_.Name } -Descending |
            Select-Object -First 1 -ExpandProperty Name
    }
    $os = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
    return [ordered]@{
        windows_product = $os.ProductName
        windows_display_version = $os.DisplayVersion
        windows_build = "$($os.CurrentBuild).$($os.UBR)"
        powershell = $PSVersionTable.PSVersion.ToString()
        git = ((& git --version) -join ' ').Trim()
        flutter = $flutterVersion.frameworkVersion
        flutter_revision = $flutterVersion.frameworkRevision
        dart = $flutterVersion.dartSdkVersion
        visual_studio = $visualStudioVersion
        msvc_linker_path = $linkerPath
        msvc_linker = if ($linkerPath) { (Get-Item -LiteralPath $linkerPath).VersionInfo.FileVersion } else { $null }
        windows_sdk_latest_discovered = $windowsSdkVersion
        cmake = Get-OptionalCommandOutput -Command $cmakePath -Arguments @('--version')
        ninja = Get-OptionalCommandOutput -Command $ninjaPath -Arguments @('--version')
        makensis_path = (Resolve-Path -LiteralPath $MakensisExecutable).Path
        makensis_version = (& $MakensisExecutable /VERSION | Select-Object -First 1)
    }
}

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $scriptDirectory '..\..\..'))
$frontendRoot = Join-Path $repoRoot 'frontend'
$pubspecPath = Join-Path $frontendRoot 'pubspec.yaml'
$nativeManifestPath = Join-Path $scriptDirectory 'wdac-accepted-native-payload.json'
$nsiPath = Join-Path $scriptDirectory 'next-stabil.nsi'
$releasePayload = Join-Path $frontendRoot 'build\windows\x64\runner\Release'
$expectedVersionLine = "version: $Version+$BuildNumber"

foreach ($requiredFile in @($FlutterPath, $MakensisPath, $pubspecPath, $nativeManifestPath, $nsiPath)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Required build input is missing: $requiredFile"
    }
}
if (-not (Test-Path -LiteralPath $AcceptedNativeRoot -PathType Container)) {
    throw "Accepted native payload root is missing: $AcceptedNativeRoot"
}
if (-not (Test-Path -LiteralPath $StagingRoot -PathType Container)) {
    throw "Staging root must already exist: $StagingRoot"
}

$resolvedStagingRoot = (Resolve-Path -LiteralPath $StagingRoot).Path
$resolvedRepoRoot = (Resolve-Path -LiteralPath $repoRoot).Path
if ($resolvedStagingRoot -eq $resolvedRepoRoot) {
    throw 'The repository root cannot be used as the Windows staging root.'
}

$pubspecVersion = Select-String -LiteralPath $pubspecPath -Pattern '^version:\s*(\S+)\s*$' | Select-Object -First 1
if ($null -eq $pubspecVersion -or $pubspecVersion.Line.Trim() -ne $expectedVersionLine) {
    throw "pubspec version must be exactly '$expectedVersionLine'"
}

$apiUri = [System.Uri]$ApiBaseUrl.Trim().TrimEnd('/')
if ($apiUri.Host.ToLowerInvariant() -in @('127.0.0.1', 'localhost', '10.0.2.2')) {
    throw "Release API URL must not use a development host: $($apiUri.Host)"
}

$sourceHead = (& git -C $repoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sourceHead -notmatch '^[0-9a-f]{40}$') {
    throw 'Unable to resolve the source Git HEAD.'
}

$nativeManifest = Get-Content -LiteralPath $nativeManifestPath -Raw | ConvertFrom-Json
if ($nativeManifest.schema -ne 'NEXT_STABIL_WDAC_ACCEPTED_NATIVE_PAYLOAD_V1') {
    throw 'Unsupported accepted native payload manifest schema.'
}
$nativeNames = @($nativeManifest.files | ForEach-Object { $_.filename })
if (($nativeNames | Select-Object -Unique).Count -ne $nativeNames.Count) {
    throw 'Accepted native payload manifest contains duplicate filenames.'
}
foreach ($nativeFile in $nativeManifest.files) {
    $acceptedPath = Join-Path $AcceptedNativeRoot $nativeFile.filename
    if (-not (Test-Path -LiteralPath $acceptedPath -PathType Leaf)) {
        throw "Accepted native payload is missing: $acceptedPath"
    }
    if ((Get-Sha256 -Path $acceptedPath) -ne $nativeFile.sha256.ToUpperInvariant()) {
        throw "Accepted native payload hash mismatch: $($nativeFile.filename)"
    }
}

$buildId = "$Version+$BuildNumber-$($sourceHead.Substring(0, 12))"
$buildRoot = Join-Path $resolvedStagingRoot $buildId
if (Test-Path -LiteralPath $buildRoot) {
    throw "Staging build already exists; choose a fresh staging root: $buildRoot"
}
$payloadRoot = Join-Path $buildRoot 'payload'
$artifactRoot = Join-Path $buildRoot 'artifacts'
New-Item -ItemType Directory -Path $payloadRoot -Force | Out-Null
New-Item -ItemType Directory -Path $artifactRoot -Force | Out-Null

Push-Location $frontendRoot
try {
    Invoke-CheckedCommand -Command $FlutterPath -Arguments @('pub', 'get')
    Invoke-CheckedCommand -Command $FlutterPath -Arguments @(
        'build', 'windows', '--release',
        "--build-name=$Version",
        "--build-number=$BuildNumber",
        "--dart-define=API_BASE_URL=$($ApiBaseUrl.Trim().TrimEnd('/'))",
        "--dart-define=SUPERVISOR_BASE_URL=$($SupervisorBaseUrl.Trim().TrimEnd('/'))"
    )
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath (Join-Path $releasePayload 'frontend.exe') -PathType Leaf)) {
    throw 'Flutter Windows release payload was not produced.'
}
Copy-Item -Path (Join-Path $releasePayload '*') -Destination $payloadRoot -Recurse

$toolchain = Get-ToolchainRecord -FlutterExecutable $FlutterPath -MakensisExecutable $MakensisPath
$freshManifestPath = Join-Path $artifactRoot 'windows-payload-fresh-manifest.json'
$freshManifest = [ordered]@{
    schema = 'NEXT_STABIL_WINDOWS_PAYLOAD_MANIFEST_V1'
    normalization = 'fresh_flutter_output'
    source_head = $sourceHead
    version = $Version
    build_number = $BuildNumber
    generated_utc = [DateTime]::UtcNow.ToString('o')
    dart_define_names = @('API_BASE_URL', 'SUPERVISOR_BASE_URL')
    toolchain = $toolchain
    payload_files = @(Get-PayloadFileRecords -PayloadRoot $payloadRoot)
}
[System.IO.File]::WriteAllText(
    $freshManifestPath,
    ($freshManifest | ConvertTo-Json -Depth 8),
    (New-Object System.Text.UTF8Encoding($false))
)

foreach ($nativeFile in $nativeManifest.files) {
    $acceptedPath = Join-Path $AcceptedNativeRoot $nativeFile.filename
    $destinationPath = Join-Path $payloadRoot $nativeFile.filename
    if (-not (Test-Path -LiteralPath $destinationPath -PathType Leaf)) {
        throw "Flutter payload did not contain expected native plug-in: $($nativeFile.filename)"
    }
    Copy-Item -LiteralPath $acceptedPath -Destination $destinationPath -Force
    if ((Get-Sha256 -Path $destinationPath) -ne $nativeFile.sha256.ToUpperInvariant()) {
        throw "Pinned native payload verification failed after copy: $($nativeFile.filename)"
    }
}

$installerPath = Join-Path $artifactRoot "NEXT-Stabil-Setup-$Version+$BuildNumber.exe"
$fileVersion = "$Version.$BuildNumber"
Invoke-CheckedCommand -Command $MakensisPath -Arguments @(
    "/DAPP_VERSION=$Version",
    "/DAPP_BUILD=$BuildNumber",
    "/DAPP_FILE_VERSION=$fileVersion",
    "/DBUILD_PAYLOAD_DIR=$payloadRoot",
    "/DOUTPUT_FILE=$installerPath",
    $nsiPath
)
if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
    throw 'NSIS did not produce the expected installer.'
}

$payloadFiles = Get-PayloadFileRecords -PayloadRoot $payloadRoot
$buildManifest = [ordered]@{
    schema = 'NEXT_STABIL_WINDOWS_BUILD_MANIFEST_V1'
    source_head = $sourceHead
    version = $Version
    build_number = $BuildNumber
    build_utc = [DateTime]::UtcNow.ToString('o')
    dart_define_names = @('API_BASE_URL', 'SUPERVISOR_BASE_URL')
    accepted_native_manifest_sha256 = Get-Sha256 -Path $nativeManifestPath
    accepted_native_files = @($nativeManifest.files)
    toolchain = $toolchain
    payload_files = @($payloadFiles)
    installer = [ordered]@{
        filename = Split-Path -Leaf $installerPath
        bytes = (Get-Item -LiteralPath $installerPath).Length
        sha256 = Get-Sha256 -Path $installerPath
    }
}
$manifestPath = Join-Path $artifactRoot 'windows-build-manifest.json'
$manifestJson = $buildManifest | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText($manifestPath, $manifestJson, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Windows staging build complete: $buildRoot"
Write-Host "Build manifest: $manifestPath"
