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
}

if ($Platform -in @("all", "web")) {
    Write-Host "Web:"
    Write-Host "build\web"
}
