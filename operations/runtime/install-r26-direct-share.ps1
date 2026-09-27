[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$CandidateWebRoot,
    [Parameter(Mandatory = $true)][string]$CandidateWindowsInstaller,
    [Parameter(Mandatory = $true)][string]$CandidateAndroidApk,
    [Parameter(Mandatory = $true)][string]$OutputRoot,
    [string]$CanonicalRoot = 'C:\ai-lab-core',
    [string]$OperationId = 'R26-DIRECT-SHARE-20260927-B1FF82B824D8',
    [string]$ExpectedStartupManifestSha256 = 'F9C33CB404589309ED3CDE1D8956C96882DBB194654DA21DB0139B350E6BCCCA',
    [string]$ExpectedStableManifestSha256 = 'B45D01BE9DBEB077564A67F5521C0AB98BF3BF6AB19DD5AA3F522AA4F633F781',
    [string]$ExpectedInstalledWebSha256 = 'A6D708B2BF72664676F5232CD1208B3FB656FB275A65BCB927FEBC9AFDDCE80A',
    [string]$ExpectedCandidateWebSha256 = '44A53C0BF821D31279294D017D4D12673A822AAFFBAAF301B8C90900E4A115EE',
    [string]$ExpectedWindowsInstallerSha256 = '1F920C494704F7FA2E91ADC1049DB4002A3B210A4F15948013D5237BC8AB013E',
    [string]$ExpectedAndroidApkSha256 = '10A1193AB6FE50F567549F6F42AA40AE829896B23BA8986EA8E8BE25927BE027'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
}

function Write-Utf8NoBom {
    param([Parameter(Mandatory = $true)][string]$Path, [Parameter(Mandatory = $true)][string]$Text)
    [IO.File]::WriteAllText($Path, $Text, (New-Object Text.UTF8Encoding($false)))
}

function Assert-FileHash {
    param([Parameter(Mandatory = $true)][string]$Path, [Parameter(Mandatory = $true)][string]$Expected)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "FILE_MISSING:$Path" }
    $actual = Get-Sha256 -Path $Path
    if ($actual -ne $Expected.ToUpperInvariant()) { throw "FILE_HASH_MISMATCH:$Path expected=$Expected actual=$actual" }
}

function Assert-PathUnder {
    param([Parameter(Mandatory = $true)][string]$Parent, [Parameter(Mandatory = $true)][string]$Child)
    $parentFull = [IO.Path]::GetFullPath($Parent).TrimEnd('\')
    $childFull = [IO.Path]::GetFullPath($Child).TrimEnd('\')
    if (-not $childFull.StartsWith($parentFull + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "PATH_OUTSIDE_BOUNDARY:$childFull parent=$parentFull"
    }
    return $childFull
}

function Remove-OwnedDirectory {
    param([Parameter(Mandatory = $true)][string]$Parent, [Parameter(Mandatory = $true)][string]$Path)
    $safe = Assert-PathUnder -Parent $Parent -Child $Path
    if (Test-Path -LiteralPath $safe) { Remove-Item -LiteralPath $safe -Recurse -Force }
}

function Copy-DirectoryContents {
    param([Parameter(Mandatory = $true)][string]$Source, [Parameter(Mandatory = $true)][string]$Destination)
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
    }
}

function Save-FilePreimage {
    param([Parameter(Mandatory = $true)][string]$Source, [Parameter(Mandatory = $true)][string]$Destination)
    if (Test-Path -LiteralPath $Source -PathType Leaf) {
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
        return [ordered]@{ state = 'EXACT_BYTES'; sha256 = Get-Sha256 -Path $Source; bytes = (Get-Item -LiteralPath $Source).Length }
    }
    return [ordered]@{ state = 'ABSENT_PREIMAGE'; sha256 = $null; bytes = 0 }
}

if (Test-Path -LiteralPath $OutputRoot) { throw "OUTPUT_ROOT_ALREADY_EXISTS:$OutputRoot" }
$canonical = [IO.Path]::GetFullPath($CanonicalRoot).TrimEnd('\')
$webBuildParent = Join-Path $canonical 'frontend\build'
$installedWebRoot = Join-Path $webBuildParent 'web'
$installedWebMain = Join-Path $installedWebRoot 'main.dart.js'
$runtimeDirectory = Join-Path $canonical 'operations\runtime'
$startupManifest = Join-Path $runtimeDirectory 'startup-set.json'
$stableDirectory = Join-Path $canonical 'release-channel\stable'
$stableManifest = Join-Path $stableDirectory 'manifest.json'
$windowsDirectory = Join-Path $stableDirectory 'windows'
$androidDirectory = Join-Path $stableDirectory 'android'
$windowsTarget = Join-Path $windowsDirectory 'NEXT-Stabil-Setup-1.0.2+42.exe'
$androidTarget = Join-Path $androidDirectory 'NEXT-Stabil-1.0.2+42.apk'
$stageWeb = Join-Path $webBuildParent ("web.r26-stage-" + $OperationId)
$oldWeb = Join-Path $webBuildParent ("web.r26-old-" + $OperationId)
$startupTemp = Join-Path $runtimeDirectory ("startup-set.r26-" + $OperationId + '.tmp')
$stableTemp = Join-Path $stableDirectory ("manifest.r26-" + $OperationId + '.tmp')
$windowsTemp = Join-Path $windowsDirectory ("NEXT-Stabil-Setup-1.0.2+42.r26-" + $OperationId + '.tmp')
$androidTemp = Join-Path $androidDirectory ("NEXT-Stabil-1.0.2+42.r26-" + $OperationId + '.tmp')

foreach ($path in @($stageWeb, $oldWeb)) { [void](Assert-PathUnder -Parent $webBuildParent -Child $path) }
foreach ($path in @($startupTemp, $stableTemp)) { [void](Assert-PathUnder -Parent $canonical -Child $path) }
foreach ($path in @($windowsTemp, $androidTemp, $windowsTarget, $androidTarget)) { [void](Assert-PathUnder -Parent $stableDirectory -Child $path) }

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$preimageRoot = Join-Path $OutputRoot 'preimages'
New-Item -ItemType Directory -Path $preimageRoot -Force | Out-Null
$resultPath = Join-Path $OutputRoot 'result.json'
$pendingPath = Join-Path $OutputRoot 'pending-mutation.json'
$pending = [ordered]@{ schema = 'NEXT_STABIL_R26_PENDING_MUTATION_V1'; operation_id = $OperationId; pending_mutation = $false; mutation_started = $false }
Write-Utf8NoBom -Path $pendingPath -Text (($pending | ConvertTo-Json -Depth 8) + "`n")

$startupPreimage = Join-Path $preimageRoot 'startup-set.json'
$stablePreimage = Join-Path $preimageRoot 'stable-manifest.json'
$windowsPreimage = Join-Path $preimageRoot 'windows-installer.exe'
$androidPreimage = Join-Path $preimageRoot 'android.apk'
$webPreimage = Join-Path $preimageRoot 'web'
$webSwapped = $false
$startupWritten = $false
$stableWritten = $false
$windowsWritten = $false
$androidWritten = $false
$windowsTargetPreimage = [ordered]@{ state = 'UNKNOWN_NOT_CAPTURED'; sha256 = $null; bytes = 0 }
$androidTargetPreimage = [ordered]@{ state = 'UNKNOWN_NOT_CAPTURED'; sha256 = $null; bytes = 0 }

try {
    Assert-FileHash -Path $startupManifest -Expected $ExpectedStartupManifestSha256
    Assert-FileHash -Path $stableManifest -Expected $ExpectedStableManifestSha256
    Assert-FileHash -Path $installedWebMain -Expected $ExpectedInstalledWebSha256
    Assert-FileHash -Path (Join-Path $CandidateWebRoot 'main.dart.js') -Expected $ExpectedCandidateWebSha256
    Assert-FileHash -Path $CandidateWindowsInstaller -Expected $ExpectedWindowsInstallerSha256
    Assert-FileHash -Path $CandidateAndroidApk -Expected $ExpectedAndroidApkSha256

    Copy-Item -LiteralPath $startupManifest -Destination $startupPreimage -Force
    Copy-Item -LiteralPath $stableManifest -Destination $stablePreimage -Force
    Copy-DirectoryContents -Source $installedWebRoot -Destination $webPreimage
    $windowsTargetPreimage = Save-FilePreimage -Source $windowsTarget -Destination $windowsPreimage
    $androidTargetPreimage = Save-FilePreimage -Source $androidTarget -Destination $androidPreimage

    $startupObject = Get-Content -LiteralPath $startupManifest -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($startupObject.approval.status -ne 'APPROVED_FOR_START') { throw 'START_NOT_APPROVED' }
    if ($startupObject.approval.set_id -ne $startupObject.set_id) { throw 'APPROVAL_SET_MISMATCH' }
    $webBindings = @($startupObject.files | Where-Object { $_.path -eq 'frontend/build/web/main.dart.js' })
    if ($webBindings.Count -ne 1) { throw "WEB_BINDING_COUNT_INVALID:$($webBindings.Count)" }
    if ($webBindings[0].sha256 -ne $ExpectedInstalledWebSha256 -or [int64]$webBindings[0].size_bytes -ne 5055021) {
        throw 'WEB_BINDING_PREIMAGE_MISMATCH'
    }
    $startupObject.set_id = $OperationId
    $startupObject.approval.set_id = $OperationId
    $startupObject.approval.decision_id = 'R26-STEP1-OWNER-AUTHORIZED-20260927'
    $webBindings[0].role = 'r26_web_main'
    $webBindings[0].sha256 = $ExpectedCandidateWebSha256
    $webBindings[0].size_bytes = 5067103
    $webBindings[0].evidence = 'R26_STEP1_EXACT_WEB_ARTIFACT_INSTALLED_20260927'
    Write-Utf8NoBom -Path $startupTemp -Text (($startupObject | ConvertTo-Json -Depth 100) + "`n")

    $stableObject = Get-Content -LiteralPath $stableManifest -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($stableObject.version -ne '1.0.2' -or [int]$stableObject.build_number -ne 29 -or $stableObject.minimum_version -ne '1.0.0') {
        throw 'STABLE_MANIFEST_PREIMAGE_SEMANTICS_MISMATCH'
    }
    $stableObject.version = '1.0.2'
    $stableObject.build_number = 42
    $stableObject.published_at = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    $stableObject.platforms.windows.url = '/updates/stable/windows/NEXT-Stabil-Setup-1.0.2+42.exe'
    $stableObject.platforms.windows.sha256 = $ExpectedWindowsInstallerSha256
    $stableObject.platforms.android.url = '/updates/stable/android/NEXT-Stabil-1.0.2+42.apk'
    $stableObject.platforms.android.sha256 = $ExpectedAndroidApkSha256
    Write-Utf8NoBom -Path $stableTemp -Text (($stableObject | ConvertTo-Json -Depth 20) + "`n")

    Remove-OwnedDirectory -Parent $webBuildParent -Path $stageWeb
    Remove-OwnedDirectory -Parent $webBuildParent -Path $oldWeb
    Copy-DirectoryContents -Source $CandidateWebRoot -Destination $stageWeb
    Assert-FileHash -Path (Join-Path $stageWeb 'main.dart.js') -Expected $ExpectedCandidateWebSha256
    New-Item -ItemType Directory -Path $windowsDirectory -Force | Out-Null
    New-Item -ItemType Directory -Path $androidDirectory -Force | Out-Null
    Copy-Item -LiteralPath $CandidateWindowsInstaller -Destination $windowsTemp -Force
    Copy-Item -LiteralPath $CandidateAndroidApk -Destination $androidTemp -Force
    Assert-FileHash -Path $windowsTemp -Expected $ExpectedWindowsInstallerSha256
    Assert-FileHash -Path $androidTemp -Expected $ExpectedAndroidApkSha256

    $pending.pending_mutation = $true
    $pending.mutation_started = $true
    Write-Utf8NoBom -Path $pendingPath -Text (($pending | ConvertTo-Json -Depth 8) + "`n")

    Move-Item -LiteralPath $installedWebRoot -Destination $oldWeb
    Move-Item -LiteralPath $stageWeb -Destination $installedWebRoot
    $webSwapped = $true
    Assert-FileHash -Path $installedWebMain -Expected $ExpectedCandidateWebSha256

    Move-Item -LiteralPath $windowsTemp -Destination $windowsTarget -Force
    $windowsWritten = $true
    Move-Item -LiteralPath $androidTemp -Destination $androidTarget -Force
    $androidWritten = $true
    Move-Item -LiteralPath $stableTemp -Destination $stableManifest -Force
    $stableWritten = $true
    Move-Item -LiteralPath $startupTemp -Destination $startupManifest -Force
    $startupWritten = $true

    . (Join-Path $runtimeDirectory 'startup-runtime.ps1')
    $read = Read-StartupSetManifest -ManifestPath $startupManifest
    if (-not $read.success) { throw "MANIFEST_READ_FAILED:$($read.code)" }
    $validation = Test-StartupSetManifest -Manifest $read.manifest -ManifestPath $startupManifest -ExpectedRoot $canonical
    if (-not $validation.valid) { throw ("MANIFEST_VALIDATION_FAILED:" + (@($validation.errors) -join ',')) }

    Assert-FileHash -Path $installedWebMain -Expected $ExpectedCandidateWebSha256
    Assert-FileHash -Path $windowsTarget -Expected $ExpectedWindowsInstallerSha256
    Assert-FileHash -Path $androidTarget -Expected $ExpectedAndroidApkSha256

    Remove-OwnedDirectory -Parent $webBuildParent -Path $oldWeb
    $pending.pending_mutation = $false
    Write-Utf8NoBom -Path $pendingPath -Text (($pending | ConvertTo-Json -Depth 8) + "`n")
    $result = [ordered]@{
        schema = 'NEXT_STABIL_R26_DEPLOYMENT_RESULT_V1'
        operation_id = $OperationId
        status = 'PASS'
        pending_mutation = $false
        startup_manifest_sha256 = Get-Sha256 -Path $startupManifest
        stable_manifest_sha256 = Get-Sha256 -Path $stableManifest
        web_main_sha256 = Get-Sha256 -Path $installedWebMain
        windows_installer_sha256 = Get-Sha256 -Path $windowsTarget
        android_apk_sha256 = Get-Sha256 -Path $androidTarget
        manifest_validation = 'APPROVED_FOR_START'
        windows_target_preimage = $windowsTargetPreimage
        android_target_preimage = $androidTargetPreimage
        completed_utc = [DateTime]::UtcNow.ToString('o')
    }
    Write-Utf8NoBom -Path $resultPath -Text (($result | ConvertTo-Json -Depth 12) + "`n")
    $result | ConvertTo-Json -Depth 12
    exit 0
}
catch {
    $failure = $_.Exception.Message
    try {
        if ($startupWritten) { Copy-Item -LiteralPath $startupPreimage -Destination $startupManifest -Force }
        if ($stableWritten) { Copy-Item -LiteralPath $stablePreimage -Destination $stableManifest -Force }
        if ($windowsWritten) {
            if ($windowsTargetPreimage.state -eq 'EXACT_BYTES') { Copy-Item -LiteralPath $windowsPreimage -Destination $windowsTarget -Force }
            elseif (Test-Path -LiteralPath $windowsTarget) { Remove-Item -LiteralPath $windowsTarget -Force }
        }
        if ($androidWritten) {
            if ($androidTargetPreimage.state -eq 'EXACT_BYTES') { Copy-Item -LiteralPath $androidPreimage -Destination $androidTarget -Force }
            elseif (Test-Path -LiteralPath $androidTarget) { Remove-Item -LiteralPath $androidTarget -Force }
        }
        if ($webSwapped) {
            Remove-OwnedDirectory -Parent $webBuildParent -Path $installedWebRoot
            if (Test-Path -LiteralPath $oldWeb -PathType Container) { Move-Item -LiteralPath $oldWeb -Destination $installedWebRoot }
            else { Copy-DirectoryContents -Source $webPreimage -Destination $installedWebRoot }
        }
        Remove-OwnedDirectory -Parent $webBuildParent -Path $stageWeb
        Remove-OwnedDirectory -Parent $webBuildParent -Path $oldWeb
        foreach ($temp in @($startupTemp, $stableTemp, $windowsTemp, $androidTemp)) {
            if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force }
        }
        $pending.pending_mutation = $false
        Write-Utf8NoBom -Path $pendingPath -Text (($pending | ConvertTo-Json -Depth 8) + "`n")
        $result = [ordered]@{ schema = 'NEXT_STABIL_R26_DEPLOYMENT_RESULT_V1'; operation_id = $OperationId; status = 'FAILED_ROLLED_BACK'; pending_mutation = $false; error = $failure; completed_utc = [DateTime]::UtcNow.ToString('o') }
        Write-Utf8NoBom -Path $resultPath -Text (($result | ConvertTo-Json -Depth 12) + "`n")
    }
    catch {
        $rollbackError = $_.Exception.Message
        $result = [ordered]@{ schema = 'NEXT_STABIL_R26_DEPLOYMENT_RESULT_V1'; operation_id = $OperationId; status = 'FAILED_ROLLBACK_UNRESOLVED'; pending_mutation = $true; error = $failure; rollback_error = $rollbackError; completed_utc = [DateTime]::UtcNow.ToString('o') }
        Write-Utf8NoBom -Path $resultPath -Text (($result | ConvertTo-Json -Depth 12) + "`n")
    }
    throw
}
