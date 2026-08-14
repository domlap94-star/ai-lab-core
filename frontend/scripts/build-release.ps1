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

    [int]$BuildNumber = 1
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

if ($Platform -in @("all", "windows")) {
    Write-Host ""
    Write-Host "BUILD WINDOWS"
    Write-Host "------------------------------------------------------------"

    flutter build windows @commonArguments

    if ($LASTEXITCODE -ne 0) {
        throw "Windows build failed"
    }
}

if ($Platform -in @("all", "android")) {
    Write-Host ""
    Write-Host "BUILD ANDROID APK"
    Write-Host "------------------------------------------------------------"

    flutter build apk @commonArguments

    if ($LASTEXITCODE -ne 0) {
        throw "Android APK build failed"
    }
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
    Write-Host "Windows:"
    Write-Host "build\windows\x64\runner\Release"
}

if ($Platform -in @("all", "android")) {
    Write-Host "Android:"
    Write-Host "build\app\outputs\flutter-apk\app-release.apk"
}

if ($Platform -in @("all", "web")) {
    Write-Host "Web:"
    Write-Host "build\web"
}