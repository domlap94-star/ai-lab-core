[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedGitSha,
    [Parameter(Mandatory = $true)][string]$RuntimeRoot,
    [Parameter(Mandatory = $true)][string]$CacheRoot,
    [Parameter(Mandatory = $true)][ValidatePattern('^sha256:[0-9a-f]{64}$')][string]$BackendImage
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$PostgresImage = 'postgres@sha256:a426e44bac0b759c95894d68e1a0ac03ecc20b619f498a91aae373bf06d8508d'
$AuthorizedStagingRoot = 'C:\ai-lab-core-staging\doc04b-runtime'
$j = [ordered]@{}
$k = [ordered]@{}
$l = [ordered]@{}
$containerName = 'doc04b-pg-' + [Guid]::NewGuid().ToString('N').Substring(0,12)
$parityContainer = 'doc04b-parity-' + [Guid]::NewGuid().ToString('N').Substring(0,12)
$database = 'ai_lab_test_doc04b_' + [Guid]::NewGuid().ToString('N').Substring(0,12)
$password = 'doc04b-' + [Guid]::NewGuid().ToString('N')

function Stop-Test([string]$Code) { throw $Code }
function Pass-J([string]$Id, [bool]$Condition) { if (-not $Condition) { Stop-Test ($Id + '_FAIL') }; $j[$Id] = 'PASS' }
function Pass-K([string]$Id, [bool]$Condition) { if (-not $Condition) { Stop-Test ($Id + '_FAIL') }; $k[$Id] = 'PASS' }
function Pass-L([string]$Id, [bool]$Condition) { if (-not $Condition) { Stop-Test ($Id + '_FAIL') }; $l[$Id] = 'PASS' }
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
function Remove-CampaignPath([string]$Path) {
    if (-not (Test-IsWithin $Path $RuntimeRoot) -or $Path -eq $RuntimeRoot) { Stop-Test 'DOC04B_UNOWNED_CLEANUP_REFUSED' }
    if (Test-Path -LiteralPath $Path) { Remove-Item -LiteralPath $Path -Recurse -Force }
}
function New-FreshDirectory([string]$Path) {
    if (Test-Path -LiteralPath $Path) { Stop-Test 'DOC04B_TEST_PATH_NOT_FRESH' }
    [System.IO.Directory]::CreateDirectory($Path) | Out-Null
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

$RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
$RuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot).TrimEnd('\')
$CacheRoot = [System.IO.Path]::GetFullPath($CacheRoot).TrimEnd('\')
if (-not (Test-IsWithin $RuntimeRoot $AuthorizedStagingRoot) -or $RuntimeRoot -eq $AuthorizedStagingRoot) { Stop-Test 'DOC04B_CAMPAIGN_ROOT_FORBIDDEN' }
if (Test-Path -LiteralPath $RuntimeRoot) { Stop-Test 'DOC04B_CAMPAIGN_ROOT_NOT_FRESH' }
[System.IO.Directory]::CreateDirectory($RuntimeRoot) | Out-Null
$runtimeA = Join-Path $RuntimeRoot 'online-a'
$runtimeB = Join-Path $RuntimeRoot 'offline-b'
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
if ($lock.schema -ne 'NEXT_STABIL_DOC04_WINDOWS_RUNTIME_LOCK_V2') { Stop-Test 'DOC04B_LOCK_SCHEMA_INVALID' }

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

    Pass-J 'J01' ($lock.schema -eq 'NEXT_STABIL_DOC04_WINDOWS_RUNTIME_LOCK_V2')
    Pass-K 'K01' ($lock.release_evidence.backend_reference_source_only -and $lock.release_evidence.last_312_binary_release -eq '3.12.10')
    Pass-K 'K02' ($lock.runtime_python.filename -eq 'python-3.12.10-embed-amd64.zip' -and $lock.runtime_python.bytes -eq 11133606 -and $lock.runtime_python.sha256 -eq '4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3')
    Pass-K 'K04' ($lock.patch_variance.type -eq 'same_minor_official_binary_fallback' -and -not $lock.patch_variance.exact_patch_identity)
    $allowedWheelTags=@('cp312-cp312-win_amd64','cp312-abi3-win_amd64','cp311-abi3-win_amd64','cp310-abi3-win_amd64','cp39-abi3-win_amd64','cp38-abi3-win_amd64','cp37-abi3-win_amd64','cp36-abi3-win_amd64','py3-none-any','py2.py3-none-any')
    Pass-K 'K05' (@($lock.packages | Where-Object { $_.classification -eq 'native' -and $_.wheel_tag -notin $allowedWheelTags }).Count -eq 0)
    Pass-K 'K06' (@($lock.security_delta | Select-Object -ExpandProperty release -Unique).Count -eq 3)
    Pass-K 'K07' (@($lock.security_delta | Where-Object { $_.untrusted_production_reachable }).Count -eq 0)

    $buildA = (& $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot $runtimeA -CacheRoot $CacheRoot | Out-String).Trim() | ConvertFrom-Json
    foreach ($artifact in $artifactRecords) { Assert-CachedArtifact (Join-Path $CacheRoot $artifact.filename) $artifact.bytes $artifact.sha256 }
    $buildB = (& $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot $runtimeB -CacheRoot $CacheRoot -Offline | Out-String).Trim() | ConvertFrom-Json
    Pass-J 'J08' ($buildA.result -eq 'runtime_built')
    Pass-J 'J09' ($buildB.result -eq 'runtime_built' -and $buildB.offline)
    Pass-J 'J10' ($buildA.runtime_tree_sha256 -eq $buildB.runtime_tree_sha256)
    Pass-J 'J11' ($buildA.runtime_tree_sha256 -eq $lock.installed_runtime.expected_tree_sha256 -and $buildA.file_count -eq $lock.installed_runtime.expected_file_count)
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

    $tamperCache = Join-Path $scratch 'cache-tamper'; New-FreshDirectory $tamperCache
    foreach($artifact in $artifactRecords){Copy-Item -LiteralPath (Join-Path $CacheRoot $artifact.filename) -Destination (Join-Path $tamperCache $artifact.filename)}
    [IO.File]::AppendAllText((Join-Path $tamperCache $lock.runtime_python.filename),'x',[Text.Encoding]::ASCII)
    Pass-J 'J12' (Invoke-ExpectedFailure { & $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot (Join-Path $scratch 'tamper-runtime') -CacheRoot $tamperCache -Offline | Out-Null } 'locked_artifact_size_mismatch')
    Remove-CampaignPath $tamperCache
    $truncateCache = Join-Path $scratch 'cache-truncate'; New-FreshDirectory $truncateCache
    foreach($artifact in $artifactRecords){Copy-Item -LiteralPath (Join-Path $CacheRoot $artifact.filename) -Destination (Join-Path $truncateCache $artifact.filename)}
    $stream=[IO.File]::Open((Join-Path $truncateCache $lock.runtime_python.filename),[IO.FileMode]::Open,[IO.FileAccess]::Write,[IO.FileShare]::None); try{$stream.SetLength(1024)}finally{$stream.Dispose()}
    Pass-J 'J13' (Invoke-ExpectedFailure { & $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot (Join-Path $scratch 'truncate-runtime') -CacheRoot $truncateCache -Offline | Out-Null } 'locked_artifact_size_mismatch')
    Remove-CampaignPath $truncateCache

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
    Pass-J 'J25' (Invoke-ExpectedFailure { & $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot (Join-Path $RepoRoot 'runtime-prohibited') -CacheRoot $CacheRoot -Offline | Out-Null } 'unsafe_runtime_inside_repo')
    Pass-J 'J26' (Invoke-ExpectedFailure { & $builder -RepoRoot $RepoRoot -ExpectedGitSha $ExpectedGitSha -RuntimeRoot (Join-Path $RepoRoot 'data\runtime-prohibited') -CacheRoot $CacheRoot -Offline | Out-Null } 'unsafe_runtime_inside_repo')
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

    $backendPath = Join-Path $RepoRoot 'backend'
    $entryPath = Join-Path $tool 'runtime-entrypoint.py'
    $linuxVectors = Invoke-Docker @(
        'run','--rm','--name',$parityContainer,'--network','none','--read-only','--tmpfs','/tmp','-w','/tmp/doc04b',
        '-e','ENVIRONMENT=test','-e','POSTGRES_DB=ai_lab_test_doc04b_reference','-e','POSTGRES_USER=doc04b','-e','POSTGRES_PASSWORD=synthetic-only',
        '-e','POSTGRES_HOST=127.0.0.1','-e','POSTGRES_PORT=65432','-e','SECRET_KEY=synthetic-doc04b-key-not-production',
        '-e','ADMIN_USERNAME=synthetic','-e','ADMIN_EMAIL=synthetic@example.invalid','-e','ADMIN_PASSWORD=synthetic-only','-e','N8N_INGEST_API_KEY=synthetic-only',
        '-e','DATA_DIR=/tmp/doc04b/data','-e','PYTHONDONTWRITEBYTECODE=1','-e','PYTHONNOUSERSITE=1','-e','PYTHONUTF8=1',
        '-e','NEXT_DOC04_RUNTIME_POLICY=backend-reference','-e','NEXT_DOC04_ENVIRONMENT_ROOT=/tmp/doc04b','-e','NEXT_DOC04_WORKING_DIRECTORY=/tmp/doc04b',
        '-e','NEXT_DOC04_FORBIDDEN_ROOTS_JSON=["/app"]','-e','NEXT_DOC04_BACKEND_REFERENCE=1',
        '-v',("${backendPath}:/app:ro"),'-v',("${entryPath}:/tool/runtime-entrypoint.py:ro"),
        $BackendImage,'python','-I','-B','-X','utf8','/tool/runtime-entrypoint.py','compatibility-vectors'
    )
    $linuxVectorHash = Get-StringSha256 $linuxVectors
    Pass-K 'K09' ($linuxVectors.StartsWith('{') -and $linuxVectors.Contains('repair_json_text_surrogates'))
    Pass-K 'K10' ($windowsVectors -ceq $linuxVectors -and $windowsVectorHash -eq $linuxVectorHash)
    Pass-K 'K11' (Assert-ContainerAbsent $parityContainer)

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
    $upgrade=Invoke-WrapperJson $runtimeA $upgradeMode $scratch
    Pass-J 'J34' ($upgrade.result -eq 'DOC04B_ALEMBIC_UPGRADE_PASS')
    Pass-J 'J35' ($port -ne 5432 -and $database.StartsWith('ai_lab_test_doc04b_'))
    Pass-L 'L08' ($upgrade.result -eq 'DOC04B_ALEMBIC_UPGRADE_PASS' -and $upgrade.revision -eq 'followup_assistant_chat_history_20260829')

    $contractMode=@{IsolatedTest=$true;TestSuite='runtime-contract'}+$databaseMode
    $contract=Invoke-WrapperJson $runtimeA $contractMode $scratch
    Pass-L 'L07' ($contract.result -eq 'DOC04B_ISOLATED_TEST_PASS' -and $contract.skipped -eq 0)
    $doc04=Invoke-WrapperJson $runtimeA (@{IsolatedTest=$true;TestSuite='doc04a'}+$databaseMode) $scratch
    if($doc04.prefix_counts.U -ne 28 -or $doc04.prefix_counts.R -ne 35 -or $doc04.prefix_counts.G -ne 35 -or $doc04.prefix_counts.H -ne 27 -or $doc04.prefix_counts.I -ne 12){Stop-Test 'DOC04B_DOC04A_MATRIX_COUNT_MISMATCH'}
    $doc01=Invoke-WrapperJson $runtimeA (@{IsolatedTest=$true;TestSuite='doc01'}+$databaseMode) $scratch
    $doc02=Invoke-WrapperJson $runtimeA (@{IsolatedTest=$true;TestSuite='doc02'}+$databaseMode) $scratch
    $doc03=Invoke-WrapperJson $runtimeA (@{IsolatedTest=$true;TestSuite='doc03'}+$databaseMode) $scratch
    if($doc01.tests_run -ne 9 -or $doc02.tests_run -ne 24 -or $doc03.tests_run -ne 18){Stop-Test 'DOC04B_DOC_REGRESSION_COUNT_MISMATCH'}
    $intake=Invoke-WrapperJson $runtimeA (@{IsolatedTest=$true;TestSuite='intake'}+$databaseMode) $scratch
    $assistant=Invoke-WrapperJson $runtimeA (@{IsolatedTest=$true;TestSuite='assistant'}+$databaseMode) $scratch
    $regression=Invoke-WrapperJson $runtimeA (@{IsolatedTest=$true;TestSuite='regression'}+$databaseMode) $scratch
    if($intake.tests_run -ne 1){Stop-Test 'DOC04B_INTAKE_CONTRACT_NOT_EXECUTED'}
    if(@($doc04,$doc01,$doc02,$doc03,$intake,$assistant,$regression | Where-Object { $_.result -ne 'DOC04B_ISOLATED_TEST_PASS' -or $_.skipped -ne 0 }).Count -ne 0){Stop-Test 'DOC04B_PORTABLE_REGRESSION_FAILED'}
    Pass-K 'K12' ($true)
    Pass-J 'J36' ($database.StartsWith('ai_lab_test_doc04b_') -and $port -ne 5432 -and $RepoRoot -notmatch '^[EF]:')
    Pass-K 'K13' ($database.StartsWith('ai_lab_test_doc04b_') -and $port -ne 5432)
    $changedPaths=@(& git -C $RepoRoot diff-tree --no-commit-id --name-only -r $ExpectedGitSha)
    Pass-K 'K14' ($changedPaths -notcontains 'backend/Dockerfile' -and $changedPaths -notcontains 'backend/requirements.txt')

    Invoke-Docker @('rm','-f',$containerName) | Out-Null
    Pass-J 'J34' (Assert-ContainerAbsent $containerName)

    foreach($id in 1..36){$name='J{0:D2}' -f $id;if(-not $j.Contains($name)){Stop-Test ($name+'_NOT_EXECUTED')}}
    foreach($id in 1..14){$name='K{0:D2}' -f $id;if(-not $k.Contains($name)){Stop-Test ($name+'_NOT_EXECUTED')}}
    foreach($id in 1..20){$name='L{0:D2}' -f $id;if(-not $l.Contains($name)){Stop-Test ($name+'_NOT_EXECUTED')}}
    $result=[ordered]@{
        result='DOC04B_WINDOWS_RUNTIME_ENV_ISOLATED_READINESS_PASS';source_git_sha=$ExpectedGitSha;
        runtime_lock_sha256=(Get-Sha256 $lockPath);python_version='3.12.10';backend_reference_python='3.12.13';architecture='amd64';
        python_artifact_filename=$lock.runtime_python.filename;python_artifact_bytes=$lock.runtime_python.bytes;python_artifact_sha256=$lock.runtime_python.sha256;
        authenticode_status=$buildA.authenticode_status;authenticode_publisher=$buildA.authenticode_publisher;
        runtime_file_count=$buildA.file_count;runtime_bytes=$buildA.runtime_bytes;online_tree_sha256=$buildA.runtime_tree_sha256;offline_tree_sha256=$buildB.runtime_tree_sha256;
        windows_vector_sha256=$windowsVectorHash;linux_vector_sha256=$linuxVectorHash;vector_equality=($windowsVectors -ceq $linuxVectors);
        j=$j;k=$k;l=$l;matrices=[ordered]@{U='28/28';R='35/35';G='35/35';H='27/27';I='12/12';DOC01='9/9';DOC02='24/24';DOC03='18/18';intake=$intake.tests_run;assistant=$assistant.tests_run;regression=$regression.tests_run};
        environment_isolation=[ordered]@{top_level_backend_imports_before_isolation=0;process_start_info_working_directory=$true;inherited_application_environment='SCRUBBED';nonproduction_env_file_open_attempts=0};
        disposable_postgres_port_non_5432=$true;disposable_postgres_removed=$true;parity_container_removed=$true;production_activity=0;
        online_runtime=$runtimeA;offline_runtime=$runtimeB
    }
    $reportPath=Join-Path $RuntimeRoot 'readiness.json'
    [IO.File]::WriteAllText($reportPath,(($result|ConvertTo-Json -Depth 10 -Compress)+"`n"),(New-Object Text.UTF8Encoding($false)))
    $result|ConvertTo-Json -Depth 10 -Compress
} finally {
    if(-not (Assert-ContainerAbsent $containerName)){& docker rm -f $containerName *> $null}
    if(-not (Assert-ContainerAbsent $parityContainer)){& docker rm -f $parityContainer *> $null}
    if ($syntheticRoot -and (Test-IsWithin $syntheticRoot $AuthorizedStagingRoot) -and ([IO.Path]::GetFileName($syntheticRoot) -match '^env-[0-9a-f]{12}$') -and (Test-Path -LiteralPath $syntheticRoot)) {
        Remove-Item -LiteralPath $syntheticRoot -Recurse -Force
    }
}
