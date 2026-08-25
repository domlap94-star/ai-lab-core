$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildScriptPath = Join-Path $scriptDirectory 'build-windows-release.ps1'
$nsiPath = Join-Path $scriptDirectory 'next-stabil.nsi'
$nativeManifestPath = Join-Path $scriptDirectory 'wdac-accepted-native-payload.json'
$acceptanceGatePath = Join-Path $scriptDirectory 'assert-windows-acceptance-ready.ps1'
$frontendBuildScriptPath = Join-Path $scriptDirectory '..\..\..\frontend\scripts\build-release.ps1'

$parseErrors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile(
    $buildScriptPath,
    [ref]$null,
    [ref]$parseErrors
)
if ($parseErrors.Count -ne 0) {
    throw "PowerShell parser errors: $($parseErrors -join '; ')"
}

foreach ($path in @($acceptanceGatePath, $frontendBuildScriptPath)) {
    $childParseErrors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        $path,
        [ref]$null,
        [ref]$childParseErrors
    )
    if ($childParseErrors.Count -ne 0) {
        throw "PowerShell parser errors in ${path}: $($childParseErrors -join '; ')"
    }
}

$buildScript = Get-Content -LiteralPath $buildScriptPath -Raw
foreach ($requiredToken in @(
    'C:\FlutterSDK-New\flutter\bin\flutter.bat',
    'C:\Users\domai\AppData\Local\NEXT Stabil\Tools\NSIS\3.12\makensis.exe',
    'pubspec version must be exactly',
    'Accepted native payload hash mismatch',
    'Pinned native payload verification failed after copy',
    'NEXT_STABIL_WINDOWS_BUILD_MANIFEST_V1',
    'raw_payload_launch_supported = $false',
    'The staged payload is NSIS installer input'
)) {
    if (-not $buildScript.Contains($requiredToken)) {
        throw "Build script is missing fail-closed token: $requiredToken"
    }
}

$acceptanceGate = Get-Content -LiteralPath $acceptanceGatePath -Raw
foreach ($requiredToken in @(
    'WINDOWS_NATIVE_PAYLOAD_NOT_NORMALIZED',
    'WINDOWS_NATIVE_PAYLOAD_NOT_INSTALLER_TRUSTED',
    '$KERNEL.SMARTLOCKER.ORIGINCLAIM',
    '$KERNEL.PURGE.SMARTLOCKER.VALID',
    'WINDOWS_ACCEPTANCE_PAYLOAD_GATE=PASS'
)) {
    if (-not $acceptanceGate.Contains($requiredToken)) {
        throw "Acceptance gate is missing fail-closed token: $requiredToken"
    }
}

$frontendBuildScript = Get-Content -LiteralPath $frontendBuildScriptPath -Raw
if ($frontendBuildScript -match '(?m)^\s*flutter build windows') {
    throw 'Generic release script still launches a direct Windows Flutter build.'
}
foreach ($requiredToken in @('AcceptedNativeRoot', 'WindowsStagingRoot', 'build-windows-release.ps1')) {
    if (-not $frontendBuildScript.Contains($requiredToken)) {
        throw "Generic release script does not delegate Windows builds safely: $requiredToken"
    }
}
if ($buildScript -match '(?im)^\s*exit\s+\d+') {
    throw 'Shared build script must use throw/LASTEXITCODE rather than exit N.'
}
if ($buildScript -match 'flutter\s+clean') {
    throw 'Canonical build script must never invoke flutter clean.'
}

$nsi = Get-Content -LiteralPath $nsiPath -Raw
foreach ($requiredDefine in @('APP_VERSION', 'APP_BUILD', 'APP_FILE_VERSION', 'BUILD_PAYLOAD_DIR', 'OUTPUT_FILE')) {
    if ($nsi -notmatch "!ifndef\s+$requiredDefine") {
        throw "NSIS script does not fail closed for missing $requiredDefine"
    }
}
if ($nsi -match 'C:\\ai-lab-core') {
    throw 'NSIS script still contains an absolute workstation path.'
}

$manifest = Get-Content -LiteralPath $nativeManifestPath -Raw | ConvertFrom-Json
if ($manifest.schema -ne 'NEXT_STABIL_WDAC_ACCEPTED_NATIVE_PAYLOAD_V1') {
    throw 'Unexpected native payload manifest schema.'
}
if (@($manifest.files).Count -ne 2) {
    throw 'Expected exactly two explicitly pinned native DLLs.'
}
$names = @($manifest.files | ForEach-Object { $_.filename })
if (($names | Select-Object -Unique).Count -ne $names.Count) {
    throw 'Native payload manifest contains duplicate filenames.'
}
foreach ($entry in $manifest.files) {
    if ($entry.sha256 -notmatch '^[0-9A-F]{64}$') {
        throw "Invalid SHA-256 for $($entry.filename)"
    }
    if ($entry.authenticode -ne 'not_signed') {
        throw "Native payload trust must not be overstated for $($entry.filename)"
    }
}

Write-Host 'WINDOWS_RELEASE_TOOLING_TEST=PASS'
