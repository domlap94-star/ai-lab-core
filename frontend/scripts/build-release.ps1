param(
    [Parameter(Mandatory = $true)]
    [string]$ApiBaseUrl,

    [Parameter(Mandatory = $true)]
    [string]$SupervisorBaseUrl,

    [ValidateSet(
        "all",
        "windows",
        "android",
        "web"
    )]
    [string]$Platform = "all",

    [string]$Version = "1.0.0",

    [int]$BuildNumber = 1,

    [switch]$AndroidAuthDiagnostics,

    [ValidatePattern('^[a-z0-9][a-z0-9-]{0,63}$')]
    [string]$AndroidCandidateLabel = "candidate",

    [string]$AcceptedNativeRoot = "",

    [string]$WindowsStagingRoot = "",

    [string]$FlutterPath = "C:\FlutterSDK-New\flutter\bin\flutter.bat",

    [string]$MakensisPath = "C:\Users\domai\AppData\Local\NEXT Stabil\Tools\NSIS\3.12\makensis.exe"
)

$ErrorActionPreference = "Stop"

Set-Location (
    Split-Path -Parent $PSScriptRoot
)

$ApiBaseUrl = $ApiBaseUrl.Trim().TrimEnd("/")
$SupervisorBaseUrl = $SupervisorBaseUrl.Trim().TrimEnd("/")

foreach ($url in @($ApiBaseUrl, $SupervisorBaseUrl)) {
    if (
        -not (
            $url.StartsWith("https://") -or
            $url.StartsWith("http://")
        )
    ) {
        throw "Release URLs must start with http:// or https://"
    }
}

$apiUri = [System.Uri]$ApiBaseUrl
$developmentApiHosts = @("127.0.0.1", "localhost", "10.0.2.2")
if ($apiUri.Scheme -ne "https") {
    throw "Release API URL must use HTTPS"
}
if ($apiUri.Host.ToLowerInvariant() -in $developmentApiHosts) {
    throw "Release API URL must not use a development host: $($apiUri.Host)"
}

Write-Host ""
Write-Host "============================================================"
Write-Host "NEXT STABIL RELEASE BUILD"
Write-Host "============================================================"
Write-Host ("API URL        : {0}" -f $ApiBaseUrl)
Write-Host ("SUPERVISOR URL : {0}" -f $SupervisorBaseUrl)
Write-Host ("PLATFORM       : {0}" -f $Platform)
Write-Host ("VERSION        : {0}" -f $Version)
Write-Host ("BUILD NUMBER   : {0}" -f $BuildNumber)
Write-Host ""

flutter pub get

if ($LASTEXITCODE -ne 0) {
    throw "flutter pub get failed"
}

$commonArguments = @(
    "--release",
    "--build-name=$Version",
    "--build-number=$BuildNumber",
    "--dart-define=API_BASE_URL=$ApiBaseUrl",
    "--dart-define=SUPERVISOR_BASE_URL=$SupervisorBaseUrl"
)

if ($AndroidAuthDiagnostics) {
    if ($Platform -ne "android") {
        throw "Android auth diagnostics may only be enabled for an Android-only build"
    }
    $commonArguments += "--dart-define=ANDROID_AUTH_DIAGNOSTICS=true"
    Write-Host "AUTH DIAGNOSTICS: ENABLED (safe metadata only)"
}

if ($Platform -in @("all", "windows")) {
    Write-Host ""
    Write-Host "BUILD WINDOWS"
    Write-Host "------------------------------------------------------------"

    if ([string]::IsNullOrWhiteSpace($AcceptedNativeRoot) -or
        [string]::IsNullOrWhiteSpace($WindowsStagingRoot)) {
        throw "Windows release builds require -AcceptedNativeRoot and -WindowsStagingRoot. Direct Flutter output is not a WDAC acceptance artifact."
    }

    & "$PSScriptRoot\..\..\operations\installer\windows\build-windows-release.ps1" `
        -Version $Version `
        -BuildNumber $BuildNumber `
        -ApiBaseUrl $ApiBaseUrl `
        -SupervisorBaseUrl $SupervisorBaseUrl `
        -AcceptedNativeRoot $AcceptedNativeRoot `
        -StagingRoot $WindowsStagingRoot `
        -FlutterPath $FlutterPath `
        -MakensisPath $MakensisPath
}

if ($Platform -in @("all", "android")) {
    Write-Host ""
    Write-Host "BUILD ANDROID APK"
    Write-Host "------------------------------------------------------------"

    flutter build apk @commonArguments

    if ($LASTEXITCODE -ne 0) {
        throw "Android APK build failed"
    }

    $builtApk = Join-Path (Get-Location) "build\app\outputs\flutter-apk\app-release.apk"
    if (-not (Test-Path -LiteralPath $builtApk -PathType Leaf)) {
        throw "Android build output is missing: $builtApk"
    }
    $ownerStaging = Join-Path (Split-Path -Parent (Get-Location)) "staging\android"
    New-Item -ItemType Directory -Force -Path $ownerStaging | Out-Null
    $ownerApk = Join-Path $ownerStaging (
        "NEXT-Stabil-{0}+{1}-{2}.apk" -f $Version, $BuildNumber, $AndroidCandidateLabel
    )
    Copy-Item -LiteralPath $builtApk -Destination $ownerApk -Force
    $sourceSha = (Get-FileHash -LiteralPath $builtApk -Algorithm SHA256).Hash
    $copiedSha = (Get-FileHash -LiteralPath $ownerApk -Algorithm SHA256).Hash
    if ($sourceSha -ne $copiedSha) {
        throw "Android owner-facing staging copy SHA-256 mismatch"
    }
    Write-Host ("OWNER APK       : {0}" -f $ownerApk)
    Write-Host ("OWNER APK SHA   : {0}" -f $copiedSha)
}

if ($Platform -in @("all", "web")) {
    Write-Host ""
    Write-Host "BUILD WEB"
    Write-Host "------------------------------------------------------------"

    flutter build web @commonArguments

    if ($LASTEXITCODE -ne 0) {
        throw "Web build failed"
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host "BUILD COMPLETE"
Write-Host "============================================================"

if ($Platform -in @("all", "windows")) {
    Write-Host "Windows installer staging:"
    Write-Host $WindowsStagingRoot
    Write-Warning "Do not launch build\windows\x64\runner\Release for acceptance. Install first, then run the Windows acceptance-ready gate against the registered install root."
}

if ($Platform -in @("all", "android")) {
    Write-Host "Android:"
    Write-Host "build\app\outputs\flutter-apk\app-release.apk"
    Write-Host "Owner-facing copy: staging\android"
}

if ($Platform -in @("all", "web")) {
    Write-Host "Web:"
    Write-Host "build\web"
}
