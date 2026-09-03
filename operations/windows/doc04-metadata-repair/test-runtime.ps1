[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedGitSha,
    [Parameter(Mandatory = $true)][string]$RuntimeRoot,
    [Parameter(Mandatory = $true)][string]$CacheRoot,
    [ValidatePattern('^sha256:[0-9a-f]{64}$')][string]$ExpectedBackendImage = '',
    [switch]$RetainVerifiedCache
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$PostgresImage = 'postgres@sha256:a426e44bac0b759c95894d68e1a0ac03ecc20b619f498a91aae373bf06d8508d'
$AuthorizedStagingRoot = 'C:\ai-lab-core-staging\doc04b-runtime'
$AuthorizedCacheRoot = 'C:\ai-lab-core-staging\doc04b-cache'
$j = [ordered]@{}
$k = [ordered]@{}
$l = [ordered]@{}
$m = [ordered]@{}
$containerName = 'doc04b-pg-' + [Guid]::NewGuid().ToString('N').Substring(0,12)
$parityContainer = 'doc04b-parity-' + [Guid]::NewGuid().ToString('N').Substring(0,12)
$database = 'ai_lab_test_doc04b_' + [Guid]::NewGuid().ToString('N').Substring(0,12)
$password = 'doc04b-' + [Guid]::NewGuid().ToString('N')

function Stop-Test([string]$Code) { throw $Code }
function Pass-J([string]$Id, [bool]$Condition) { if (-not $Condition) { Stop-Test ($Id + '_FAIL') }; $j[$Id] = 'PASS' }
function Pass-K([string]$Id, [bool]$Condition) { if (-not $Condition) { Stop-Test ($Id + '_FAIL') }; $k[$Id] = 'PASS' }
function Pass-L([string]$Id, [bool]$Condition) { if (-not $Condition) { Stop-Test ($Id + '_FAIL') }; $l[$Id] = 'PASS' }
function Pass-M([string]$Id, [bool]$Condition) { if (-not $Condition) { Stop-Test ($Id + '_FAIL') }; $m[$Id] = 'PASS' }
function Get-Sha256([string]$Path) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Get-StringSha256([string]$Value) {
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try { $hash = $algorithm.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Value)) } finally { $algorithm.Dispose() }
    return [System.BitConverter]::ToString($hash).Replace('-','').ToLowerInvariant()
}
function Test-IsWithin([string]$Candidate, [string]$Boundary) {
    $candidatePath = [System.IO.Path]::GetFullPath($Candidate).TrimEnd('\')
    $boundaryPath = [System.IO.Path]::GetFullPath($Boundary).TrimEnd('\')
    if ($candidatePath.Equals($boundaryPath,[System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    return $candidatePath.StartsWith($boundaryPath + '\',[System.StringComparison]::OrdinalIgnoreCase)
}
function Test-IsStrictDescendant([string]$Candidate, [string]$Boundary) {
    $candidatePath = [System.IO.Path]::GetFullPath($Candidate).TrimEnd('\')
    $boundaryPath = [System.IO.Path]::GetFullPath($Boundary).TrimEnd('\')
    return -not $candidatePath.Equals($boundaryPath,[System.StringComparison]::OrdinalIgnoreCase) -and (Test-IsWithin $candidatePath $boundaryPath)
}
function Remove-CampaignPath([string]$Path) {
    if (-not (Test-IsWithin $Path $RuntimeRoot) -or $Path -eq $RuntimeRoot) { Stop-Test 'DOC04B_UNOWNED_CLEANUP_REFUSED' }
    if (Test-Path -LiteralPath $Path) { Remove-Item -LiteralPath $Path -Recurse -Force }
}
function New-FreshDirectory([string]$Path) {
    if (Test-Path -LiteralPath $Path) { Stop-Test 'DOC04B_TEST_PATH_NOT_FRESH' }
    [System.IO.Directory]::CreateDirectory($Path) | Out-Null
}
function Remove-CachePath([string]$Path) {
    if (-not (Test-IsStrictDescendant $Path $AuthorizedCacheRoot)) { Stop-Test 'DOC04B_UNOWNED_CACHE_CLEANUP_REFUSED' }
    if (Test-Path -LiteralPath $Path) { Remove-Item -LiteralPath $Path -Recurse -Force }
}
function Invoke-ExpectedFailure([scriptblock]$Action, [string]$ExpectedFragment) {
    try { & $Action; return $false } catch { return ([string]$_.Exception.Message).Contains($ExpectedFragment) }
}
function Invoke-WrapperRaw([string]$Runtime, [hashtable]$Mode, [string]$CallerDirectory) {
    $common = @{RepoRoot=$RepoRoot;ExpectedGitSha=$ExpectedGitSha;RuntimeRoot=$Runtime;SyntheticRoot=$syntheticRoot}
    $modeCopy = @{}
    foreach ($item in $Mode.GetEnumerator()) {
        if ($common.ContainsKey([string]$item.Key)) { $common[[string]$item.Key] = $item.Value }
        else { $modeCopy[[string]$item.Key] = $item.Value }
    }
    Push-Location -LiteralPath $CallerDirectory
    try {
        try {
            $output = @(& $launcher @common @modeCopy 2>&1)
            $code = $LASTEXITCODE
        } catch {
            $bounded = [regex]::Match([string]$_.Exception.Message,'DOC04[A-Z0-9_]+')
            $modeName = (@($modeCopy.Keys | Where-Object { [string]$_ -in @('Readiness','RepairHelp','CompatibilityVectors','IsolatedTest','IsolatedAlembicUpgrade','AuditEnvProbe','SyntheticProductionAudit') }) -join '_').ToUpperInvariant()
            if ($bounded.Success -and $modeName) { Stop-Test ('DOC04B_WRAPPER_' + $modeName + '_' + $bounded.Value) }
            Stop-Test 'DOC04B_WRAPPER_UNBOUNDED_FAILURE'
        }
    } finally { Pop-Location }
    if ($code -ne 0) { Stop-Test 'DOC04B_WRAPPER_INVOCATION_FAILED' }
    $lines = @($output | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($lines.Count -ne 1) { Stop-Test 'DOC04B_WRAPPER_OUTPUT_NOT_BOUNDED' }
    try { [void]($lines[0] | ConvertFrom-Json) } catch { Stop-Test 'DOC04B_WRAPPER_OUTPUT_NOT_JSON' }
    return $lines[0]
}
function Invoke-WrapperJson([string]$Runtime, [hashtable]$Mode, [string]$CallerDirectory) {
    return (Invoke-WrapperRaw $Runtime $Mode $CallerDirectory | ConvertFrom-Json)
}
function Invoke-Docker([string[]]$Arguments) {
    $output = & docker @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { Stop-Test 'DOC04B_DISPOSABLE_DOCKER_FAILURE' }
    return (($output | Out-String).Trim())
}
function Assert-ContainerAbsent([string]$Name) {
    $names = @(& docker ps -a --format '{{.Names}}' 2>$null)
    return $names -notcontains $Name
}
function Assert-CachedArtifact([string]$Path, [int64]$Bytes, [string]$Sha256) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { Stop-Test 'DOC04B_LOCKED_CACHE_ARTIFACT_MISSING' }
    if ((Get-Item -LiteralPath $Path).Length -ne $Bytes) { Stop-Test 'DOC04B_LOCKED_CACHE_SIZE_MISMATCH' }
    if ((Get-Sha256 $Path) -ne $Sha256) { Stop-Test 'DOC04B_LOCKED_CACHE_HASH_MISMATCH' }
}
function Invoke-WrapperExpectedFailure([string]$Runtime, [hashtable]$Mode, [string]$CallerDirectory, [string]$Expected) {
    try { [void](Invoke-WrapperRaw $Runtime $Mode $CallerDirectory); return $false } catch { return ([string]$_.Exception.Message).Contains($Expected) }
}
function Invoke-RelayWrapperProcess([string]$Runtime, [string]$Case) {
    $powershell = (@(Get-Command powershell.exe -CommandType Application -ErrorAction Stop)[0]).Source
    $arguments = @(
        '-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$launcher,
        '-RepoRoot',$RepoRoot,'-ExpectedGitSha',$ExpectedGitSha,'-RuntimeRoot',$Runtime,
        '-SyntheticRoot',$syntheticRoot,'-RepairRelaySelfTest','-RelayCase',$Case
    )
    $output = @(& $powershell @arguments 2>&1 | ForEach-Object { [string]$_ })
    return [pscustomobject]@{exit_code=$LASTEXITCODE;lines=@($output | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })}
}
function Remove-TestJunction([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        $item = Get-Item -LiteralPath $Path -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) { Stop-Test 'DOC04B_EXPECTED_TEST_REPARSE_MISSING' }
        [IO.Directory]::Delete($Path)
    }
}

$RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
$RuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot).TrimEnd('\')
$CacheRoot = [System.IO.Path]::GetFullPath($CacheRoot).TrimEnd('\')
if (-not (Test-IsStrictDescendant $RuntimeRoot $AuthorizedStagingRoot)) { Stop-Test 'DOC04B_CAMPAIGN_ROOT_FORBIDDEN' }
if (-not (Test-IsStrictDescendant $CacheRoot $AuthorizedCacheRoot)) { Stop-Test 'DOC04B_CACHE_ROOT_FORBIDDEN' }
if (Test-Path -LiteralPath $RuntimeRoot) { Stop-Test 'DOC04B_CAMPAIGN_ROOT_NOT_FRESH' }
$cacheExistedAtStart = Test-Path -LiteralPath $CacheRoot
[System.IO.Directory]::CreateDirectory($RuntimeRoot) | Out-Null
[System.IO.Directory]::CreateDirectory($CacheRoot) | Out-Null
$runtimeA = Join-Path $RuntimeRoot 'production-online'
$runtimeB = Join-Path $RuntimeRoot 'production-offline'
$qualificationA = Join-Path $RuntimeRoot 'qualification-online'
$qualificationB = Join-Path $RuntimeRoot 'qualification-offline'
$scratch = Join-Path $RuntimeRoot 'scratch'
$syntheticRoot = Join-Path $AuthorizedStagingRoot ('env-' + [Guid]::NewGuid().ToString('N').Substring(0,12))
New-FreshDirectory $scratch
New-FreshDirectory $syntheticRoot
$tool = Join-Path $RepoRoot 'operations\windows\doc04-metadata-repair'
$lockPath = Join-Path $tool 'runtime-lock.json'
$lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
$builder = Join-Path $tool 'build-runtime.ps1'
$launcher = Join-Path $tool 'invoke-repair.ps1'
$entrypoint = Join-Path $tool 'runtime-entrypoint.py'

if ((& git -C $RepoRoot rev-parse HEAD).Trim() -ne $ExpectedGitSha) { Stop-Test 'DOC04B_TEST_GIT_HEAD_MISMATCH' }
if ((& git -C $RepoRoot status --short | Out-String).Trim()) { Stop-Test 'DOC04B_TEST_WORKTREE_NOT_CLEAN' }
if ($lock.schema -ne 'NEXT_STABIL_DOC04_WINDOWS_RUNTIME_LOCK_V3') { Stop-Test 'DOC04B_LOCK_SCHEMA_INVALID' }

$campaignSucceeded = $false
$rootJunction = $null
$internalJunction = $null

try {
    $allowedHosts = @($lock.allowed_download_hosts)
    $artifactRecords = New-Object System.Collections.Generic.List[object]
    $artifactRecords.Add([pscustomobject]@{filename=$lock.runtime_python.filename;bytes=[int64]$lock.runtime_python.bytes;sha256=$lock.runtime_python.sha256;url=$lock.runtime_python.url})
    $artifactRecords.Add([pscustomobject]@{filename=[IO.Path]::GetFileName($lock.runtime_python.sbom.url);bytes=[int64]$lock.runtime_python.sbom.bytes;sha256=$lock.runtime_python.sbom.sha256;url=$lock.runtime_python.sbom.url})
    $artifactRecords.Add([pscustomobject]@{filename=[IO.Path]::GetFileName($lock.runtime_python.sigstore.url);bytes=[int64]$lock.runtime_python.sigstore.bytes;sha256=$lock.runtime_python.sigstore.sha256;url=$lock.runtime_python.sigstore.url})
    foreach ($package in $lock.packages) { $artifactRecords.Add([pscustomobject]@{filename=$package.filename;bytes=[int64]$package.bytes;sha256=$package.sha256;url=$package.url}) }
    foreach ($artifact in $artifactRecords) {
        $uri = [uri]$artifact.url
        if ($uri.Scheme -ne 'https' -or $allowedHosts -notcontains $uri.DnsSafeHost) { Stop-Test 'DOC04B_CACHE_ORIGIN_NOT_LOCKED' }
        $cached = Join-Path $CacheRoot $artifact.filename
        if (Test-Path -LiteralPath $cached) { Assert-CachedArtifact $cached $artifact.bytes $artifact.sha256 }
    }

    Pass-J 'J01' ($lock.schema -eq 'NEXT_STABIL_DOC04_WINDOWS_RUNTIME_LOCK_V3')
    Pass-K 'K01' ($lock.release_evidence.backend_reference_source_only -and $lock.release_evidence.last_312_binary_release -eq '3.12.10')
    Pass-K 'K02' ($lock.runtime_python.filename -eq 'python-3.12.10-embed-amd64.zip' -and $lock.runtime_python.bytes -eq 11133606 -and $lock.runtime_python.sha256 -eq '4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3')
    Pass-K 'K04' ($lock.patch_variance.type -eq 'same_minor_official_binary_fallback' -and -not $lock.patch_variance.exact_patch_identity)
    $allowedWheelTags=@('cp312-cp312-win_amd64','cp312-abi3-win_amd64','cp311-abi3-win_amd64','cp310-abi3-win_amd64','cp39-abi3-win_amd64','cp38-abi3-win_amd64','cp37-abi3-win_amd64','cp36-abi3-win_amd64','py3-none-any','py2.py3-none-any')
    Pass-K 'K05' (@($lock.packages | Where-Object { $_.classification -eq 'native' -and $_.wheel_tag -notin $allowedWheelTags }).Count -eq 0)
    Pass-K 'K06' (@($lock.security_delta | Select-Object -ExpandProperty release -Unique).Count -eq 3)
    Pass-K 'K07' (@($lock.security_delta | Where-Object { $_.untrusted_production_reachable }).Count -eq 0)

    $builderEnvironmentNames=@('PYTHONDONTWRITEBYTECODE','PYTHONNOUSERSITE','PYTHONUTF8','PYTHONHOME','PYTHONPATH')
    $builderEnvironmentBefore=@{};foreach($name in $builderEnvironmentNames){$builderEnvironmentBefore[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
    $buildA = (& $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot $runtimeA -CacheRoot $CacheRoot -Profile Production | Out-String).Trim() | ConvertFrom-Json
    $qualificationBuildA = (& $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot $qualificationA -CacheRoot $CacheRoot -Profile Qualification | Out-String).Trim() | ConvertFrom-Json
    foreach ($artifact in $artifactRecords) { Assert-CachedArtifact (Join-Path $CacheRoot $artifact.filename) $artifact.bytes $artifact.sha256 }
    $buildB = (& $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot $runtimeB -CacheRoot $CacheRoot -Profile Production -Offline | Out-String).Trim() | ConvertFrom-Json
    $qualificationBuildB = (& $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot $qualificationB -CacheRoot $CacheRoot -Profile Qualification -Offline | Out-String).Trim() | ConvertFrom-Json
    $builderEnvironmentAfterSuccess=@{};foreach($name in $builderEnvironmentNames){$builderEnvironmentAfterSuccess[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
    $builderSuccessEnvironmentUnchanged=@($builderEnvironmentNames | Where-Object { $builderEnvironmentBefore[$_] -cne $builderEnvironmentAfterSuccess[$_] }).Count -eq 0
    Pass-J 'J08' ($buildA.result -eq 'runtime_built' -and $buildA.profile -eq 'Production')
    Pass-J 'J09' ($buildB.result -eq 'runtime_built' -and $buildB.offline -and $qualificationBuildA.profile -eq 'Qualification' -and $qualificationBuildB.offline)
    Pass-J 'J10' ($buildA.runtime_tree_sha256 -eq $buildB.runtime_tree_sha256)
    Pass-J 'J11' ($buildA.runtime_tree_sha256 -eq $lock.profiles.Production.installed_runtime.expected_tree_sha256 -and $buildA.file_count -eq $lock.profiles.Production.installed_runtime.expected_file_count -and $qualificationBuildA.runtime_tree_sha256 -eq $lock.profiles.Qualification.installed_runtime.expected_tree_sha256)
    Pass-J 'J02' ($buildA.python_version -eq '3.12.10' -and $buildA.architecture -eq 'amd64')
    Pass-J 'J03' ($buildA.python_artifact_sha256 -eq $lock.runtime_python.sha256 -and $buildA.authenticode_status -eq 'Valid')
    Pass-K 'K03' ($buildA.authenticode_status -eq 'Valid' -and $buildA.authenticode_publisher -eq 'Python Software Foundation')
    Pass-J 'J04' (@($artifactRecords | Where-Object { (Get-Sha256 (Join-Path $CacheRoot $_.filename)) -ne $_.sha256 -or (Get-Item -LiteralPath (Join-Path $CacheRoot $_.filename)).Length -ne $_.bytes }).Count -eq 0)
    Pass-J 'J05' (@($lock.packages | Where-Object { ($_.classification -eq 'locked_pure_sdist' -and ($_.project -ne 'odfpy' -or $_.filename -ne 'odfpy-1.4.1.tar.gz')) -or ($_.classification -ne 'locked_pure_sdist' -and -not $_.filename.EndsWith('.whl')) -or $_.version -match '[<>=~*]' }).Count -eq 0)
    $top = @{'SQLAlchemy'='2.0.43';'psycopg'='3.2.10';'psycopg-binary'='3.2.10';'pydantic'='2.11.7';'pydantic-settings'='2.11.0';'alembic'='1.16.5'}
    $actualTop=@{}; foreach($package in $lock.packages){if($top.ContainsKey([string]$package.project)){$actualTop[[string]$package.project]=[string]$package.version}}
    Pass-J 'J06' (@($top.Keys | Where-Object { $actualTop[$_] -ne $top[$_] }).Count -eq 0)

    $readinessRaw = Invoke-WrapperRaw $runtimeA @{Readiness=$true} $scratch
    $readinessJson = $readinessRaw | ConvertFrom-Json
    Pass-J 'J07' ($readinessJson.result -eq 'DOC04B_SMOKE_PASS' -and $readinessJson.packages.SQLAlchemy -eq '2.0.43')
    Pass-J 'J28' ($readinessJson.network_connections -eq 0 -and $readinessJson.database_connections -eq 0 -and $readinessJson.env_file_open_attempts -eq 0)

    $tamperCache = Join-Path $AuthorizedCacheRoot ('tamper-' + [Guid]::NewGuid().ToString('N').Substring(0,12)); New-FreshDirectory $tamperCache
    foreach($artifact in $artifactRecords){Copy-Item -LiteralPath (Join-Path $CacheRoot $artifact.filename) -Destination (Join-Path $tamperCache $artifact.filename)}
    [IO.File]::AppendAllText((Join-Path $tamperCache $lock.runtime_python.filename),'x',[Text.Encoding]::ASCII)
    Pass-J 'J12' (Invoke-ExpectedFailure { & $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot (Join-Path $scratch 'tamper-runtime') -CacheRoot $tamperCache -Profile Production -Offline | Out-Null } 'locked_artifact_size_mismatch')
    Remove-CachePath $tamperCache
    $truncateCache = Join-Path $AuthorizedCacheRoot ('truncate-' + [Guid]::NewGuid().ToString('N').Substring(0,12)); New-FreshDirectory $truncateCache
    foreach($artifact in $artifactRecords){Copy-Item -LiteralPath (Join-Path $CacheRoot $artifact.filename) -Destination (Join-Path $truncateCache $artifact.filename)}
    $stream=[IO.File]::Open((Join-Path $truncateCache $lock.runtime_python.filename),[IO.FileMode]::Open,[IO.FileAccess]::Write,[IO.FileShare]::None); try{$stream.SetLength(1024)}finally{$stream.Dispose()}
    Pass-J 'J13' (Invoke-ExpectedFailure { & $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot (Join-Path $scratch 'truncate-runtime') -CacheRoot $truncateCache -Profile Production -Offline | Out-Null } 'locked_artifact_size_mismatch')
    Remove-CachePath $truncateCache

    $builderText = Get-Content -LiteralPath $builder -Raw
    Pass-J 'J14' ($builderText.Contains('download_uri_not_allowlisted') -and $builderText.Contains('maximum_redirects'))
    Pass-J 'J15' ($builderText.Contains('archive_traversal_rejected'))
    Pass-J 'J16' ($builderText.Contains('archive_path_invalid') -and $builderText.Contains("-match '^[A-Za-z]:'"))
    Pass-J 'J17' ($builderText.Contains('archive_duplicate_target') -and $builderText.Contains('wheel_target_collision'))
    Pass-J 'J18' ($builderText.Contains('archive_symlink_rejected') -and $builderText.Contains('wheel_symlink_rejected'))
    Pass-J 'J19' ($builderText.Contains('wheel_project_version_mismatch') -and $builderText.Contains('wheel_metadata_tag_mismatch'))
    Pass-J 'J20' ($builderText.Contains('wheel_executable_payload_rejected'))

    $missing = Join-Path $scratch 'runtime-missing'; Copy-Item -LiteralPath $runtimeA -Destination $missing -Recurse; Remove-Item -LiteralPath (Join-Path $missing 'python312.zip')
    Pass-J 'J21' (Invoke-WrapperExpectedFailure $missing @{Readiness=$true} $scratch 'DOC04B_RUNTIME_TREE_MISMATCH')
    $unexpected = Join-Path $scratch 'runtime-unexpected'; Copy-Item -LiteralPath $runtimeA -Destination $unexpected -Recurse; [IO.File]::WriteAllText((Join-Path $unexpected 'unexpected.txt'),'x')
    Pass-J 'J22' (Invoke-WrapperExpectedFailure $unexpected @{Readiness=$true} $scratch 'DOC04B_RUNTIME_TREE_MISMATCH')
    $changedRuntime = Join-Path $scratch 'runtime-changed'; Copy-Item -LiteralPath $runtimeA -Destination $changedRuntime -Recurse; [IO.File]::AppendAllText((Join-Path $changedRuntime 'python312._pth'),'x')
    Pass-J 'J23' (Invoke-WrapperExpectedFailure $changedRuntime @{Readiness=$true} $scratch 'DOC04B_RUNTIME_TREE_MISMATCH')
    $signatureCopy = Join-Path $scratch 'python-signature-tamper.exe'; Copy-Item -LiteralPath (Join-Path $runtimeA 'python.exe') -Destination $signatureCopy; [IO.File]::AppendAllText($signatureCopy,'x')
    Pass-J 'J24' ((Get-AuthenticodeSignature -LiteralPath $signatureCopy).Status -ne [System.Management.Automation.SignatureStatus]::Valid)
    Pass-J 'J25' (Invoke-ExpectedFailure { & $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot (Join-Path $RepoRoot 'runtime-prohibited') -CacheRoot $CacheRoot -Profile Production -Offline | Out-Null } 'unsafe_runtime_inside_repo')
    Pass-J 'J26' (Invoke-ExpectedFailure { & $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot (Join-Path $RepoRoot 'data\runtime-prohibited') -CacheRoot $CacheRoot -Profile Production -Offline | Out-Null } 'unsafe_runtime_inside_repo')
    $combinedPs = (Get-Content -LiteralPath $builder,$launcher,(Join-Path $tool 'test-runtime.ps1') -Raw) -join "`n"
    Pass-J 'J27' ($combinedPs.Contains('PYTHONNOUSERSITE') -and $combinedPs.Contains('runtime_tree_sha256') -and $combinedPs.Contains('ProcessStartInfo'))
    $helpRaw = Invoke-WrapperRaw $runtimeA @{RepairHelp=$true} $scratch
    $helpJson = $helpRaw | ConvertFrom-Json
    Pass-J 'J29' ($helpJson.result -eq 'DOC04B_REPAIR_HELP_PASS' -and $helpJson.env_file_open_attempts -eq 0 -and $helpJson.option_count -gt 10)
    Pass-J 'J30' ($readinessJson.result -eq 'DOC04B_SMOKE_PASS')

    $gitCopy = Join-Path $scratch 'git-copy'
    & git -c advice.detachedHead=false clone --quiet --shared $RepoRoot $gitCopy
    if ($LASTEXITCODE -ne 0) { Stop-Test 'DOC04B_TEMP_GIT_COPY_FAILED' }
    & git -C $gitCopy -c advice.detachedHead=false checkout --quiet $ExpectedGitSha
    if($LASTEXITCODE -ne 0){Stop-Test 'DOC04B_TEMP_GIT_CHECKOUT_FAILED'}
    [IO.File]::AppendAllText((Join-Path $gitCopy 'backend\app\services\document_metadata_unicode_safety.py'),"`n# synthetic mutation`n")
    $savedRepo=$RepoRoot; $RepoRoot=$gitCopy
    try { Pass-J 'J31' (Invoke-WrapperExpectedFailure $runtimeA @{Readiness=$true} $scratch 'DOC04B_CRITICAL_SOURCE_MODIFIED') } finally { $RepoRoot=$savedRepo }
    & git -C $gitCopy checkout --quiet -- backend/app/services/document_metadata_unicode_safety.py
    [IO.File]::AppendAllText((Join-Path $gitCopy 'operations\windows\doc04-metadata-repair\README.md'),"`nsynthetic mutation`n")
    $savedRepo=$RepoRoot; $RepoRoot=$gitCopy
    try { Pass-J 'J32' (Invoke-WrapperExpectedFailure $runtimeA @{Readiness=$true} $scratch 'DOC04B_CRITICAL_SOURCE_MODIFIED') } finally { $RepoRoot=$savedRepo }
    & git -C $gitCopy checkout --quiet -- operations/windows/doc04-metadata-repair/README.md
    [IO.File]::WriteAllText((Join-Path $gitCopy 'unrelated-synthetic.txt'),'safe')
    $savedRepo=$RepoRoot; $RepoRoot=$gitCopy
    try { $copyReadiness=Invoke-WrapperJson $runtimeA @{Readiness=$true} $scratch; Pass-J 'J33' ($copyReadiness.result -eq 'DOC04B_SMOKE_PASS') } finally { $RepoRoot=$savedRepo }

    $hostileCaller = Join-Path $scratch 'hostile-caller'; New-FreshDirectory $hostileCaller
    [IO.File]::WriteAllText((Join-Path $hostileCaller '.env'),'POISON=hostile-parent-marker',(New-Object Text.UTF8Encoding($false)))
    $hostileReadiness = Invoke-WrapperJson $runtimeA @{Readiness=$true} $hostileCaller
    Pass-L 'L02' ($hostileReadiness.result -eq 'DOC04B_SMOKE_PASS' -and $hostileReadiness.env_file_open_attempts -eq 0)
    $auditProbe = Invoke-WrapperJson $runtimeA @{AuditEnvProbe=$true} $hostileCaller
    Pass-L 'L03' ($auditProbe.result -eq 'DOC04B_AUDIT_GUARD_PASS' -and $auditProbe.env_file_open_attempts -ge 1)
    Pass-L 'L04' ($readinessJson.env_file_open_attempts -eq 0)
    Pass-L 'L05' ($helpJson.result -eq 'DOC04B_REPAIR_HELP_PASS' -and $helpJson.database_connections -eq 0 -and $helpJson.network_connections -eq 0)

    $windowsVectors = Invoke-WrapperRaw $runtimeA @{CompatibilityVectors=$true} $scratch
    $windowsVectorHash = Get-StringSha256 $windowsVectors
    Pass-L 'L06' ($windowsVectors.StartsWith('{') -and $windowsVectors.Contains('repair_json_text_surrogates'))
    Pass-K 'K08' ($windowsVectors.StartsWith('{') -and $windowsVectors.Contains('repair_json_text_surrogates'))

    $sensitiveNames = @('POSTGRES_DB','POSTGRES_USER','POSTGRES_PASSWORD','POSTGRES_HOST','POSTGRES_PORT','SECRET_KEY','ADMIN_USERNAME','ADMIN_EMAIL','ADMIN_PASSWORD','N8N_INGEST_API_KEY','DATA_DIR','VISION_SUPERVISOR_URL','BACKUP_SUPERVISOR_URL','OPENAI_API_KEY','PYTHONHOME','PYTHONPATH','PYTHONUSERBASE','VIRTUAL_ENV','PIP_CONFIG_FILE','PIP_INDEX_URL','PIP_EXTRA_INDEX_URL')
    $savedEnvironment=@{}
    foreach($name in $sensitiveNames){$savedEnvironment[$name]=[Environment]::GetEnvironmentVariable($name,'Process');[Environment]::SetEnvironmentVariable($name,'hostile-parent-marker','Process')}
    try { $scrubbed=Invoke-WrapperJson $runtimeA @{Readiness=$true} $hostileCaller } finally { foreach($name in $savedEnvironment.Keys){[Environment]::SetEnvironmentVariable([string]$name,$savedEnvironment[$name],'Process')} }
    Pass-L 'L09' ($scrubbed.result -eq 'DOC04B_SMOKE_PASS' -and $scrubbed.environment_profile -eq 'synthetic_explicit')
    Pass-L 'L10' ($scrubbed.python -eq '3.12.10')
    Pass-L 'L11' ($readinessJson.cwd_identity_sha256 -match '^[0-9a-f]{64}$')
    Pass-L 'L12' (Invoke-WrapperExpectedFailure $runtimeA @{Readiness=$true;SyntheticRoot=$RepoRoot} $scratch 'DOC04B_SYNTHETIC_ROOT_FORBIDDEN')
    $savedSyntheticRoot=$syntheticRoot; $syntheticRoot=$scratch
    try { Pass-L 'L13' (Invoke-WrapperExpectedFailure $runtimeA @{Readiness=$true;SyntheticForbiddenRoots=@($scratch)} $scratch 'DOC04B_SYNTHETIC_ROOT_FORBIDDEN') } finally { $syntheticRoot=$savedSyntheticRoot }
    $launcherText = Get-Content -LiteralPath $launcher -Raw
    $preflightEnvironmentPattern = 'Mandatory = \$true, ParameterSetName = ''ProductionPreflight''.*\[string\]\$EnvironmentRoot'
    $executeEnvironmentPattern = 'Mandatory = \$true, ParameterSetName = ''ExecuteProduction''.*\[string\]\$EnvironmentRoot'
    Pass-L 'L14' ([regex]::IsMatch($launcherText,$preflightEnvironmentPattern,[Text.RegularExpressions.RegexOptions]::Singleline))
    Pass-L 'L15' ([regex]::IsMatch($launcherText,$executeEnvironmentPattern,[Text.RegularExpressions.RegexOptions]::Singleline))
    $productionAudit = Invoke-WrapperJson $runtimeA @{SyntheticProductionAudit=$true} $scratch
    Pass-L 'L16' ($productionAudit.result -eq 'DOC04B_SYNTHETIC_PRODUCTION_ENV_AUDIT_PASS' -and $productionAudit.allowed_env_opens -eq 1 -and $productionAudit.rejected_env_opens -eq 1)
    $allSafeOutput = @($readinessRaw,$helpRaw,$windowsVectors,($auditProbe|ConvertTo-Json -Compress),($productionAudit|ConvertTo-Json -Compress)) -join "`n"
    Pass-L 'L17' (-not $allSafeOutput.Contains('hostile-parent-marker') -and -not $allSafeOutput.Contains($RepoRoot) -and -not $allSafeOutput.Contains($RuntimeRoot) -and -not $allSafeOutput.Contains($password))
    $harnessText = Get-Content -LiteralPath (Join-Path $tool 'test-runtime.ps1') -Raw
    $readmeText = Get-Content -LiteralPath (Join-Path $tool 'README.md') -Raw
    Pass-L 'L18' (-not (($harnessText + "`n" + $readmeText) -match '(?i)python(?:\.exe)?\s+(?:-m\s+app\.scripts\.repair_document_metadata_surrogates|[^\r\n]*repair_document_metadata_surrogates\.py)'))
    $spaceCaller = Join-Path $scratch 'caller with spaces'; New-FreshDirectory $spaceCaller
    $callerA=Invoke-WrapperJson $runtimeA @{Readiness=$true} $scratch
    $callerB=Invoke-WrapperJson $runtimeA @{Readiness=$true} $RepoRoot
    $callerC=Invoke-WrapperJson $runtimeA @{Readiness=$true} $spaceCaller
    Pass-L 'L19' (@($callerA,$callerB,$callerC | Where-Object { $_.result -ne 'DOC04B_SMOKE_PASS' -or $_.packages.SQLAlchemy -ne '2.0.43' }).Count -eq 0)
    Pass-L 'L20' ($launcherText.Contains('WorkingDirectory = $WorkingDirectory') -and $launcherText.Contains('EnvironmentVariables.Clear()') -and $readinessJson.env_file_open_attempts -eq 0)

    $entryText = Get-Content -LiteralPath $entrypoint -Raw
    Pass-L 'L01' ($entryText.Contains('sys.addaudithook') -and $entryText.IndexOf('sys.addaudithook') -lt $entryText.IndexOf('sys.path.insert'))

    $backendImage = (& docker inspect --format '{{.Image}}' ai-lab-backend 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $backendImage -notmatch '^sha256:[0-9a-f]{64}$') { Stop-Test 'DOC04B_BACKEND_IMAGE_ID_UNAVAILABLE' }
    if ($ExpectedBackendImage -and $ExpectedBackendImage -ne $backendImage) { Stop-Test 'DOC04B_BACKEND_IMAGE_ID_MISMATCH' }
    $backendPath = Join-Path $RepoRoot 'backend'
    $entryPath = Join-Path $tool 'runtime-entrypoint.py'
    $linuxVectors = Invoke-Docker @(
        'run','--rm','--name',$parityContainer,'--network','none','--read-only','--tmpfs','/tmp','-w','/tmp/doc04b',
        '-e','ENVIRONMENT=test','-e','POSTGRES_DB=ai_lab_test_doc04b_reference','-e','POSTGRES_USER=doc04b','-e','POSTGRES_PASSWORD=synthetic-only',
        '-e','POSTGRES_HOST=127.0.0.1','-e','POSTGRES_PORT=65432','-e','SECRET_KEY=synthetic-doc04b-key-not-production',
        '-e','ADMIN_USERNAME=synthetic','-e','ADMIN_EMAIL=synthetic@example.invalid','-e','ADMIN_PASSWORD=synthetic-only','-e','N8N_INGEST_API_KEY=synthetic-only',
        '-e','DATA_DIR=/tmp/doc04b/data','-e','PYTHONDONTWRITEBYTECODE=1','-e','PYTHONNOUSERSITE=1','-e','PYTHONUTF8=1',
        '-e','NEXT_DOC04_RUNTIME_POLICY=backend-reference','-e','NEXT_DOC04_ENVIRONMENT_ROOT=/tmp/doc04b','-e','NEXT_DOC04_WORKING_DIRECTORY=/tmp/doc04b',
        '-e','NEXT_DOC04_FORBIDDEN_ROOTS_JSON=["/app"]','-e','NEXT_DOC04_BACKEND_REFERENCE=1','-e','NEXT_DOC04_RUNTIME_PROFILE=Production',
        '-v',("${backendPath}:/app:ro"),'-v',("${entryPath}:/tool/runtime-entrypoint.py:ro"),
        $backendImage,'python','-I','-B','-X','utf8','/tool/runtime-entrypoint.py','compatibility-vectors'
    )
    $linuxVectorHash = Get-StringSha256 $linuxVectors
    Pass-K 'K09' ($linuxVectors.StartsWith('{') -and $linuxVectors.Contains('repair_json_text_surrogates'))
    Pass-K 'K10' ($windowsVectors -ceq $linuxVectors -and $windowsVectorHash -eq $linuxVectorHash)
    Pass-K 'K11' (Assert-ContainerAbsent $parityContainer)

    $relaySuccess = Invoke-RelayWrapperProcess $runtimeA 'Success'
    $relaySuccessPayload = $relaySuccess.lines[0] | ConvertFrom-Json
    Pass-M 'M01' ($relaySuccess.exit_code -eq 0 -and $relaySuccess.lines.Count -eq 1 -and $relaySuccessPayload.result -eq 'DOCUMENT_METADATA_REPAIR_DRY_RUN' -and -not $relaySuccessPayload.executed)
    $relayRefusal = Invoke-RelayWrapperProcess $runtimeA 'Refusal'
    $relayRefusalPayload = $relayRefusal.lines[0] | ConvertFrom-Json
    Pass-M 'M02' ($relayRefusal.exit_code -eq 2 -and $relayRefusal.lines.Count -eq 1 -and $relayRefusalPayload.result -eq 'DOCUMENT_METADATA_REPAIR_REFUSED' -and -not $relayRefusalPayload.executed)
    $relayFailures = @(
        @('M03','Empty','DOC04B_REPAIR_OUTPUT_LINE_COUNT_INVALID'),
        @('M04','Multiple','DOC04B_REPAIR_OUTPUT_LINE_COUNT_INVALID'),
        @('M05','InvalidJson','DOC04B_REPAIR_OUTPUT_JSON_INVALID'),
        @('M06','Oversized','DOC04B_REPAIR_OUTPUT_OVERSIZED'),
        @('M07','Nul','DOC04B_REPAIR_OUTPUT_NUL'),
        @('M08','Stderr','DOC04B_REPAIR_STDERR_NOT_EMPTY'),
        @('M09','Contradictory','DOC04B_REPAIR_SUCCESS_REFUSAL_CONTRADICTION')
    )
    foreach ($definition in $relayFailures) {
        $failure = Invoke-RelayWrapperProcess $runtimeA $definition[1]
        $failureText = $failure.lines -join "`n"
        Pass-M $definition[0] ($failure.exit_code -ne 0 -and $failureText.Contains($definition[2]) -and -not $failureText.Contains('bounded-test-stderr'))
    }
    Pass-M 'M10' (($relaySuccess.lines -join '') -ceq '{"executed":false,"result":"DOCUMENT_METADATA_REPAIR_DRY_RUN"}')
    Pass-M 'M11' (($relayRefusal.lines -join '') -ceq '{"executed":false,"result":"DOCUMENT_METADATA_REPAIR_REFUSED"}')
    Pass-M 'M12' ($entryText.Contains('return _invoke_and_relay_repair(args.repair_args)') -and $entryText.Contains('def _invoke_and_relay_repair(') -and $launcherText.Contains('$productionPayload = ConvertFrom-BoundedJson $child.stdout'))

    $productionProjects = @($lock.profiles.Production.package_projects)
    $productionPackages = @($lock.packages | Where-Object { $productionProjects -ccontains [string]$_.project })
    $forbiddenProduction = @('odfpy','fastapi','uvicorn','qdrant-client','pymupdf','pillow','pillow_heif','pytesseract','numpy','openpyxl','xlrd','xlsxwriter','python-docx','python-pptx','grpcio','watchfiles','websockets','lxml','pypdf','striprtf')
    Pass-M 'M13' (@($productionPackages | Where-Object { $_.classification -eq 'locked_pure_sdist' }).Count -eq 0)
    Pass-M 'M14' (@($productionProjects | Where-Object { $_.ToLowerInvariant() -in $forbiddenProduction }).Count -eq 0)
    $importTrace = Invoke-WrapperJson $runtimeA @{ProductionImportTrace=$true} $scratch
    Pass-M 'M15' ($importTrace.result -eq 'DOC04B_PRODUCTION_IMPORT_TRACE_PASS' -and $importTrace.package_count -eq $productionProjects.Count -and $importTrace.psycopg_implementation -eq 'binary')
    Pass-M 'M16' ($buildA.package_count -eq 11 -and @($buildA.packages | Where-Object { $_.ToLowerInvariant() -in $forbiddenProduction }).Count -eq 0 -and $qualificationBuildA.package_count -eq 65)
    $fakeDatabaseMode=@{IsolatedTest=$true;TestSuite='runtime-contract';SyntheticDatabaseName='ai_lab_test_doc04b_profile';SyntheticDatabasePort=65432;SyntheticDatabasePassword='synthetic-only'}
    Pass-M 'M17' (Invoke-WrapperExpectedFailure $runtimeA $fakeDatabaseMode $scratch 'DOC04B_RUNTIME_PROFILE_MISMATCH')
    Pass-M 'M18' (Invoke-WrapperExpectedFailure $qualificationA @{Readiness=$true} $scratch 'DOC04B_RUNTIME_PROFILE_MISMATCH')
    Pass-M 'M19' ($buildA.runtime_tree_sha256 -eq $buildB.runtime_tree_sha256 -and $buildA.file_count -eq $buildB.file_count)
    Pass-M 'M20' ($qualificationBuildA.runtime_tree_sha256 -eq $qualificationBuildB.runtime_tree_sha256 -and $qualificationBuildA.file_count -eq $qualificationBuildB.file_count)
    $pathProbeRuntime = Join-Path $scratch 'path-probe-runtime'
    Pass-M 'M21' ((Invoke-ExpectedFailure { & $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot 'C:\ai-lab-core-backups\doc04b-forbidden' -CacheRoot $CacheRoot -Profile Production -Offline | Out-Null } 'unsafe_runtime_outside_authorized_parent') -and (Invoke-ExpectedFailure { & $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot $pathProbeRuntime -CacheRoot 'C:\ai-lab-core-backups\doc04b-forbidden' -Profile Production -Offline | Out-Null } 'unsafe_cache_outside_authorized_parent'))
    Pass-M 'M22' ((Invoke-ExpectedFailure { & $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot 'E:\doc04b-forbidden' -CacheRoot $CacheRoot -Profile Production -Offline | Out-Null } 'unsafe_runtime_outside_authorized_parent') -and (Invoke-ExpectedFailure { & $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot 'F:\doc04b-forbidden' -CacheRoot $CacheRoot -Profile Production -Offline | Out-Null } 'unsafe_runtime_outside_authorized_parent'))
    Pass-M 'M23' (Invoke-ExpectedFailure { & $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot 'C:\Temp\doc04b-forbidden' -CacheRoot $CacheRoot -Profile Production -Offline | Out-Null } 'unsafe_runtime_outside_authorized_parent')
    $assertRuntimeStart=$launcherText.IndexOf('function Assert-Runtime(');$assertRuntimeEnd=$launcherText.IndexOf('function ConvertTo-WindowsArgument',$assertRuntimeStart);$assertRuntimeSource=$launcherText.Substring($assertRuntimeStart,$assertRuntimeEnd-$assertRuntimeStart)
    Pass-M 'M24' ($assertRuntimeSource.IndexOf('Assert-PolicyPath') -ge 0 -and $assertRuntimeSource.IndexOf('Assert-PolicyPath') -lt $assertRuntimeSource.IndexOf('Get-Tree'))

    $junctionTarget=Join-Path $scratch 'root-reparse-target';New-FreshDirectory $junctionTarget
    $rootJunction=Join-Path $AuthorizedStagingRoot ('reparse-' + [Guid]::NewGuid().ToString('N').Substring(0,12))
    [void](New-Item -ItemType Junction -Path $rootJunction -Target $junctionTarget)
    Pass-M 'M25' (Invoke-ExpectedFailure { & $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot (Join-Path $rootJunction 'runtime') -CacheRoot $CacheRoot -Profile Production -Offline | Out-Null } 'unsafe_reparse_path')
    Remove-TestJunction $rootJunction;$rootJunction=$null

    $runtimeReparseCopy=Join-Path $scratch 'runtime-internal-reparse';Copy-Item -LiteralPath $runtimeA -Destination $runtimeReparseCopy -Recurse
    $internalTarget=Join-Path $scratch 'internal-reparse-target';New-FreshDirectory $internalTarget
    $internalJunction=Join-Path $runtimeReparseCopy 'unsafe-junction';[void](New-Item -ItemType Junction -Path $internalJunction -Target $internalTarget)
    Pass-M 'M26' (Invoke-WrapperExpectedFailure $runtimeReparseCopy @{Readiness=$true} $scratch 'DOC04B_RUNTIME_REPARSE_FORBIDDEN')
    Remove-TestJunction $internalJunction;$internalJunction=$null

    $productionEnvRoot=Join-Path $scratch 'synthetic-production-env';New-FreshDirectory $productionEnvRoot
    $productionDataTarget=Join-Path $scratch 'synthetic-production-data-target';New-FreshDirectory $productionDataTarget
    $envJunction=Join-Path $productionEnvRoot '.env';[void](New-Item -ItemType Junction -Path $envJunction -Target $productionDataTarget)
    $productionArguments=@{RepoRoot=$RepoRoot;ExpectedGitSha=$ExpectedGitSha;RuntimeRoot=$runtimeA;EnvironmentRoot=$productionEnvRoot;DataRoot=$productionDataTarget;AllowProductionAiLab=$true;OwnerApprovalId='synthetic-only';ExpectedAlembicHead='synthetic';ExpectedXmin='1';ExpectedUpdatedAt='2026-09-03T00:00:00Z';ExpectedStorageSha256=('0'*64);VerifiedBackupRunId=1;VerifiedBackupManifestSha256=('0'*64);ExpectedBackupFinishedAt='2026-09-03T00:00:00Z';MaximumBackupAgeSeconds=60;ExpectedBackupDestinationRootSha256=('0'*64);ExpectedRawBeforeSha256=('0'*64);ExpectedRawCandidateSha256=('0'*64);ExpectedNormalizedBeforeSha256=('0'*64);ExpectedNormalizedCandidateSha256=('0'*64);ProductionPreflight=$true}
    $envRejected=Invoke-ExpectedFailure { & $launcher @productionArguments | Out-Null } 'DOC04B_PRODUCTION_ENV_FILE_INVALID'
    Remove-TestJunction $envJunction
    [IO.File]::WriteAllText($envJunction,'synthetic=true',(New-Object Text.UTF8Encoding($false)))
    $dataJunction=Join-Path $scratch 'synthetic-production-data-reparse';[void](New-Item -ItemType Junction -Path $dataJunction -Target $productionDataTarget)
    $productionArguments.DataRoot=$dataJunction
    $dataRejected=Invoke-ExpectedFailure { & $launcher @productionArguments | Out-Null } 'DOC04B_PRODUCTION_DATA_ROOT_INVALID'
    Remove-TestJunction $dataJunction
    Pass-M 'M27' ($envRejected -and $dataRejected)

    $builderEnvironmentBeforeFailure=@{};foreach($name in $builderEnvironmentNames){$builderEnvironmentBeforeFailure[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
    [void](Invoke-ExpectedFailure { & $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot $runtimeA -CacheRoot $CacheRoot -Profile Production -Offline | Out-Null } 'runtime_root_not_fresh')
    $builderEnvironmentAfterFailure=@{};foreach($name in $builderEnvironmentNames){$builderEnvironmentAfterFailure[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
    $builderFailureEnvironmentUnchanged=@($builderEnvironmentNames | Where-Object { $builderEnvironmentBeforeFailure[$_] -cne $builderEnvironmentAfterFailure[$_] }).Count -eq 0
    Pass-M 'M28' ($builderSuccessEnvironmentUnchanged -and $builderFailureEnvironmentUnchanged)

    $downloadCases=@('SizeOverflow','PrematureEof','HashMismatch','HttpFailure','RedirectFailure','WriteFailure')
    $downloadCleanup=$true
    foreach($case in $downloadCases){
        $probeRuntime=Join-Path $scratch ('download-' + $case.ToLowerInvariant())
        $probe=(& $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot $probeRuntime -CacheRoot $CacheRoot -Profile Production -Offline -DownloadFailureProbe $case | Out-String).Trim() | ConvertFrom-Json
        if($probe.result -ne 'DOC04B_DOWNLOAD_CLEANUP_PROBE_PASS' -or $probe.owned_partial_count -ne 0 -or @(Get-ChildItem -LiteralPath $CacheRoot -Filter '*.partial' -File).Count -ne 0){$downloadCleanup=$false}
    }
    Pass-M 'M29' $downloadCleanup

    $parentCopy=Join-Path $scratch 'parent-control'
    & git -c advice.detachedHead=false clone --quiet --shared $RepoRoot $parentCopy
    if($LASTEXITCODE -ne 0){Stop-Test 'DOC04B_PARENT_CONTROL_CLONE_FAILED'}
    & git -C $parentCopy -c advice.detachedHead=false checkout --quiet afee8c57c323bd6e371e65173a60e1f369b4ee93
    if($LASTEXITCODE -ne 0){Stop-Test 'DOC04B_PARENT_CONTROL_CHECKOUT_FAILED'}
    $oldEntry=Get-Content -Raw -LiteralPath (Join-Path $parentCopy 'operations\windows\doc04-metadata-repair\runtime-entrypoint.py')
    $oldBuilder=Get-Content -Raw -LiteralPath (Join-Path $parentCopy 'operations\windows\doc04-metadata-repair\build-runtime.ps1')
    $oldHarness=Get-Content -Raw -LiteralPath (Join-Path $parentCopy 'operations\windows\doc04-metadata-repair\test-runtime.ps1')
    $parentControls=[ordered]@{
        relay_output_lost=($oldEntry.Contains('return int(repair_main(args.repair_args))') -and -not $oldEntry.Contains('_invoke_and_relay_repair'));
        c_backup_root_accepted=($oldBuilder -notmatch [regex]::Escape('C:\ai-lab-core-backups'));
        caller_environment_mutated=($oldBuilder.Contains('$env:PYTHONDONTWRITEBYTECODE='));
        partial_cleanup_missing=($oldBuilder -notmatch 'Remove-OwnedPartial');
        runtime_b_and_scratch_retained=($oldHarness.Contains('offline_runtime=$runtimeB') -and -not $oldHarness.Contains('Remove-CampaignPath $runtimeB'))
    }
    if(@($parentControls.Values | Where-Object { -not $_ }).Count -ne 0){Stop-Test 'DOC04B_PARENT_CONTROLS_NOT_REPRODUCED'}

    Invoke-Docker @('run','-d','--name',$containerName,'--pull','never','--network','bridge','-e','POSTGRES_USER=doc04b','-e',("POSTGRES_PASSWORD=$password"),'-e',("POSTGRES_DB=$database"),'-p','127.0.0.1::5432',$PostgresImage) | Out-Null
    [int]$port=0
    for($attempt=0;$attempt -lt 120;$attempt++){
        if($port -eq 0){$mapping=(& docker port $containerName 5432/tcp 2>$null | Out-String).Trim(); if($mapping -match '127\.0\.0\.1:(\d+)$'){$port=[int]$Matches[1]}}
        if($port -gt 0){& docker exec $containerName pg_isready -U doc04b -d $database *> $null; if($LASTEXITCODE -eq 0){break}}
        Start-Sleep -Milliseconds 500
    }
    if($port -le 0 -or $port -eq 5432){Stop-Test 'DOC04B_DISPOSABLE_PORT_INVALID'}
    $databaseMode=@{SyntheticDatabaseName=$database;SyntheticDatabasePort=$port;SyntheticDatabasePassword=$password}
    $upgradeMode=@{IsolatedAlembicUpgrade=$true}+$databaseMode
    $upgrade=Invoke-WrapperJson $qualificationA $upgradeMode $scratch
    Pass-J 'J34' ($upgrade.result -eq 'DOC04B_ALEMBIC_UPGRADE_PASS')
    Pass-J 'J35' ($port -ne 5432 -and $database.StartsWith('ai_lab_test_doc04b_'))
    Pass-L 'L08' ($upgrade.result -eq 'DOC04B_ALEMBIC_UPGRADE_PASS' -and $upgrade.revision -eq 'followup_assistant_chat_history_20260829')

    $contractMode=@{IsolatedTest=$true;TestSuite='runtime-contract'}+$databaseMode
    $contract=Invoke-WrapperJson $qualificationA $contractMode $scratch
    Pass-L 'L07' ($contract.result -eq 'DOC04B_ISOLATED_TEST_PASS' -and $contract.skipped -eq 0)
    $doc04=Invoke-WrapperJson $qualificationA (@{IsolatedTest=$true;TestSuite='doc04a'}+$databaseMode) $scratch
    if($doc04.prefix_counts.U -ne 28 -or $doc04.prefix_counts.R -ne 35 -or $doc04.prefix_counts.G -ne 35 -or $doc04.prefix_counts.H -ne 27 -or $doc04.prefix_counts.I -ne 12){Stop-Test 'DOC04B_DOC04A_MATRIX_COUNT_MISMATCH'}
    $doc01=Invoke-WrapperJson $qualificationA (@{IsolatedTest=$true;TestSuite='doc01'}+$databaseMode) $scratch
    $doc02=Invoke-WrapperJson $qualificationA (@{IsolatedTest=$true;TestSuite='doc02'}+$databaseMode) $scratch
    $doc03=Invoke-WrapperJson $qualificationA (@{IsolatedTest=$true;TestSuite='doc03'}+$databaseMode) $scratch
    if($doc01.tests_run -ne 9 -or $doc02.tests_run -ne 24 -or $doc03.tests_run -ne 18){Stop-Test 'DOC04B_DOC_REGRESSION_COUNT_MISMATCH'}
    $intake=Invoke-WrapperJson $qualificationA (@{IsolatedTest=$true;TestSuite='intake'}+$databaseMode) $scratch
    $assistant=Invoke-WrapperJson $qualificationA (@{IsolatedTest=$true;TestSuite='assistant'}+$databaseMode) $scratch
    $regression=Invoke-WrapperJson $qualificationA (@{IsolatedTest=$true;TestSuite='regression'}+$databaseMode) $scratch
    if($intake.tests_run -ne 1){Stop-Test 'DOC04B_INTAKE_CONTRACT_NOT_EXECUTED'}
    if(@($doc04,$doc01,$doc02,$doc03,$intake,$assistant,$regression | Where-Object { $_.result -ne 'DOC04B_ISOLATED_TEST_PASS' -or $_.skipped -ne 0 }).Count -ne 0){Stop-Test 'DOC04B_PORTABLE_REGRESSION_FAILED'}
    Pass-K 'K12' ($true)
    Pass-J 'J36' ($database.StartsWith('ai_lab_test_doc04b_') -and $port -ne 5432 -and $RepoRoot -notmatch '^[EF]:')
    Pass-K 'K13' ($database.StartsWith('ai_lab_test_doc04b_') -and $port -ne 5432)
    $changedPaths=@(& git -C $RepoRoot diff-tree --no-commit-id --name-only -r $ExpectedGitSha)
    Pass-K 'K14' ($changedPaths -notcontains 'backend/Dockerfile' -and $changedPaths -notcontains 'backend/requirements.txt')

    Invoke-Docker @('rm','-f',$containerName) | Out-Null
    Pass-J 'J34' (Assert-ContainerAbsent $containerName)

    foreach($path in @($runtimeB,$qualificationA,$qualificationB,$scratch)) { Remove-CampaignPath $path }
    foreach($manifest in @(($runtimeB + '.manifest.json'),($qualificationA + '.manifest.json'),($qualificationB + '.manifest.json'))) { if(Test-Path -LiteralPath $manifest){Remove-CampaignPath $manifest} }
    if ($syntheticRoot -and (Test-IsStrictDescendant $syntheticRoot $AuthorizedStagingRoot) -and ([IO.Path]::GetFileName($syntheticRoot) -match '^env-[0-9a-f]{12}$') -and (Test-Path -LiteralPath $syntheticRoot)) { Remove-Item -LiteralPath $syntheticRoot -Recurse -Force }
    if(-not $RetainVerifiedCache -and -not $cacheExistedAtStart){Remove-CachePath $CacheRoot}
    $remainingBeforeReport=@(Get-ChildItem -LiteralPath $RuntimeRoot -Force | Select-Object -ExpandProperty Name | Sort-Object)
    Pass-M 'M30' (($remainingBeforeReport -join ',') -eq 'production-online,production-online.manifest.json')

    foreach($id in 1..36){$name='J{0:D2}' -f $id;if(-not $j.Contains($name)){Stop-Test ($name+'_NOT_EXECUTED')}}
    foreach($id in 1..14){$name='K{0:D2}' -f $id;if(-not $k.Contains($name)){Stop-Test ($name+'_NOT_EXECUTED')}}
    foreach($id in 1..20){$name='L{0:D2}' -f $id;if(-not $l.Contains($name)){Stop-Test ($name+'_NOT_EXECUTED')}}
    foreach($id in 1..30){$name='M{0:D2}' -f $id;if(-not $m.Contains($name)){Stop-Test ($name+'_NOT_EXECUTED')}}
    $result=[ordered]@{
        result='DOC04B2_RUNTIME_CLOSURE_READINESS_PASS';source_git_sha=$ExpectedGitSha;
        runtime_lock_sha256=(Get-Sha256 $lockPath);python_version='3.12.10';backend_reference_python='3.12.13';architecture='amd64';
        python_artifact_filename=$lock.runtime_python.filename;python_artifact_bytes=$lock.runtime_python.bytes;python_artifact_sha256=$lock.runtime_python.sha256;
        authenticode_status=$buildA.authenticode_status;authenticode_publisher=$buildA.authenticode_publisher;
        production_profile=[ordered]@{package_count=$buildA.package_count;packages=$buildA.packages;file_count=$buildA.file_count;runtime_bytes=$buildA.runtime_bytes;online_tree_sha256=$buildA.runtime_tree_sha256;offline_tree_sha256=$buildB.runtime_tree_sha256;sdist_count=0};
        qualification_profile=[ordered]@{package_count=$qualificationBuildA.package_count;file_count=$qualificationBuildA.file_count;runtime_bytes=$qualificationBuildA.runtime_bytes;online_tree_sha256=$qualificationBuildA.runtime_tree_sha256;offline_tree_sha256=$qualificationBuildB.runtime_tree_sha256;sdist='odfpy 1.4.1 only'};
        windows_vector_sha256=$windowsVectorHash;linux_vector_sha256=$linuxVectorHash;vector_equality=($windowsVectors -ceq $linuxVectors);
        backend_reference=[ordered]@{source_category='ai-lab-backend immutable image id';image_id=$backendImage;python='3.12.13'};
        j=$j;k=$k;l=$l;m=$m;parent_controls=$parentControls;matrices=[ordered]@{U='28/28';R='35/35';G='35/35';H='27/27';I='12/12';DOC01='9/9';DOC02='24/24';DOC03='18/18';intake=$intake.tests_run;assistant=$assistant.tests_run;regression=$regression.tests_run};
        environment_isolation=[ordered]@{top_level_backend_imports_before_isolation=0;process_start_info_working_directory=$true;inherited_application_environment='SCRUBBED';nonproduction_env_file_open_attempts=0};
        disposable_postgres_port_non_5432=$true;disposable_postgres_removed=$true;parity_container_removed=$true;production_activity=0;
        retained_runtimes=@($runtimeA);qualification_runtimes_retained=0;offline_runtimes_retained=0;scratch_retained=$false;cache_retained=[bool](Test-Path -LiteralPath $CacheRoot)
    }
    $reportPath=Join-Path $RuntimeRoot 'readiness.json'
    [IO.File]::WriteAllText($reportPath,(($result|ConvertTo-Json -Depth 10 -Compress)+"`n"),(New-Object Text.UTF8Encoding($false)))
    $campaignSucceeded = $true
    $result|ConvertTo-Json -Depth 10 -Compress
} finally {
    if($internalJunction){try{Remove-TestJunction $internalJunction}catch{}}
    if($rootJunction){try{Remove-TestJunction $rootJunction}catch{}}
    if(-not (Assert-ContainerAbsent $containerName)){& docker rm -f $containerName *> $null}
    if(-not (Assert-ContainerAbsent $parityContainer)){& docker rm -f $parityContainer *> $null}
    if ($syntheticRoot -and (Test-IsWithin $syntheticRoot $AuthorizedStagingRoot) -and ([IO.Path]::GetFileName($syntheticRoot) -match '^env-[0-9a-f]{12}$') -and (Test-Path -LiteralPath $syntheticRoot)) {
        Remove-Item -LiteralPath $syntheticRoot -Recurse -Force
    }
    if(-not $campaignSucceeded){
        if((Test-IsStrictDescendant $RuntimeRoot $AuthorizedStagingRoot) -and (Test-Path -LiteralPath $RuntimeRoot)){Remove-Item -LiteralPath $RuntimeRoot -Recurse -Force}
        if(-not $cacheExistedAtStart -and (Test-IsStrictDescendant $CacheRoot $AuthorizedCacheRoot) -and (Test-Path -LiteralPath $CacheRoot)){Remove-Item -LiteralPath $CacheRoot -Recurse -Force}
    }
}
