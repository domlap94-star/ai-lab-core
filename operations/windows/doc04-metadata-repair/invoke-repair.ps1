[CmdletBinding(DefaultParameterSetName = 'Readiness')]
param(
    [Parameter(Mandatory = $true, ParameterSetName = 'Readiness')][switch]$Readiness,
    [Parameter(Mandatory = $true, ParameterSetName = 'RepairHelp')][switch]$RepairHelp,
    [Parameter(Mandatory = $true, ParameterSetName = 'CompatibilityVectors')][switch]$CompatibilityVectors,
    [Parameter(Mandatory = $true, ParameterSetName = 'IsolatedTest')][switch]$IsolatedTest,
    [Parameter(Mandatory = $true, ParameterSetName = 'IsolatedAlembicUpgrade')][switch]$IsolatedAlembicUpgrade,
    [Parameter(Mandatory = $true, ParameterSetName = 'AuditEnvProbe')][switch]$AuditEnvProbe,
    [Parameter(Mandatory = $true, ParameterSetName = 'SyntheticProductionAudit')][switch]$SyntheticProductionAudit,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionImportTrace')][switch]$ProductionImportTrace,
    [Parameter(Mandatory = $true, ParameterSetName = 'NetworkForbiddenProbe')][switch]$NetworkForbiddenProbe,
    [Parameter(ParameterSetName = 'NetworkForbiddenProbe')]
    [ValidateSet('socket_new','bind','sendto','sendmsg','gethostbyaddr','getnameinfo','getservbyname','getservbyport','wrong_connect')]
    [string]$NetworkProbeCase = 'socket_new',
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionProfilePreflightIntegration')][switch]$ProductionProfilePreflightIntegration,
    [Parameter(Mandatory = $true, ParameterSetName = 'RepairRelaySelfTest')][switch]$RepairRelaySelfTest,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')][switch]$ProductionPreflight,
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][switch]$ExecuteProduction,
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedGitSha,
    [Parameter(Mandatory = $true)][string]$RuntimeRoot,
    [Parameter(Mandatory = $true, ParameterSetName = 'Readiness')]
    [Parameter(Mandatory = $true, ParameterSetName = 'RepairHelp')]
    [Parameter(Mandatory = $true, ParameterSetName = 'CompatibilityVectors')]
    [Parameter(Mandatory = $true, ParameterSetName = 'IsolatedTest')]
    [Parameter(Mandatory = $true, ParameterSetName = 'IsolatedAlembicUpgrade')]
    [Parameter(Mandatory = $true, ParameterSetName = 'AuditEnvProbe')]
    [Parameter(Mandatory = $true, ParameterSetName = 'SyntheticProductionAudit')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionImportTrace')]
    [Parameter(Mandatory = $true, ParameterSetName = 'NetworkForbiddenProbe')]
    [Parameter(Mandatory = $true, ParameterSetName = 'RepairRelaySelfTest')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionProfilePreflightIntegration')][string]$SyntheticRoot,
    [Parameter(ParameterSetName = 'Readiness')]
    [Parameter(ParameterSetName = 'RepairHelp')]
    [Parameter(ParameterSetName = 'CompatibilityVectors')]
    [Parameter(ParameterSetName = 'IsolatedTest')]
    [Parameter(ParameterSetName = 'IsolatedAlembicUpgrade')]
    [Parameter(ParameterSetName = 'AuditEnvProbe')]
    [Parameter(ParameterSetName = 'SyntheticProductionAudit')]
    [Parameter(ParameterSetName = 'ProductionImportTrace')]
    [Parameter(ParameterSetName = 'RepairRelaySelfTest')][string[]]$SyntheticForbiddenRoots = @(),
    [Parameter(Mandatory = $true, ParameterSetName = 'RepairRelaySelfTest')]
    [ValidateSet('Success','Refusal','Empty','Multiple','InvalidJson','Oversized','Nul','Stderr','Contradictory')]
    [string]$RelayCase,
    [Parameter(Mandatory = $true, ParameterSetName = 'IsolatedTest')]
    [Parameter(Mandatory = $true, ParameterSetName = 'IsolatedAlembicUpgrade')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionProfilePreflightIntegration')][ValidatePattern('^ai_lab_test_doc04b_[a-z0-9_]+$')][string]$SyntheticDatabaseName,
    [Parameter(Mandatory = $true, ParameterSetName = 'IsolatedTest')]
    [Parameter(Mandatory = $true, ParameterSetName = 'IsolatedAlembicUpgrade')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionProfilePreflightIntegration')][ValidateRange(1, 65535)][int]$SyntheticDatabasePort,
    [Parameter(Mandatory = $true, ParameterSetName = 'IsolatedTest')]
    [Parameter(Mandatory = $true, ParameterSetName = 'IsolatedAlembicUpgrade')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionProfilePreflightIntegration')][string]$SyntheticDatabasePassword,
    [Parameter(Mandatory = $true, ParameterSetName = 'IsolatedTest')][ValidateSet('runtime-contract','doc04a','doc01','doc02','doc03','intake','assistant','regression')][string]$TestSuite,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionProfilePreflightIntegration')][string]$EnvironmentRoot,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionProfilePreflightIntegration')][string]$QualificationRuntimeRoot,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionProfilePreflightIntegration')]
    [ValidateSet('Success','WrongBeforeHash')][string]$IntegrationCase,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionProfilePreflightIntegration')]
    [ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedEnvironmentFileSha256,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][string]$DataRoot,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][switch]$AllowProductionAiLab,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][string]$OwnerApprovalId,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][string]$ExpectedAlembicHead,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][string]$ExpectedXmin,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][string]$ExpectedUpdatedAt,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedStorageSha256,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][int]$VerifiedBackupRunId,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][ValidatePattern('^[0-9a-f]{64}$')][string]$VerifiedBackupManifestSha256,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][string]$ExpectedBackupFinishedAt,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][ValidateRange(1, 86400)][int]$MaximumBackupAgeSeconds,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedBackupDestinationRootSha256,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedRawBeforeSha256,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedRawCandidateSha256,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedNormalizedBeforeSha256,
    [Parameter(Mandatory = $true, ParameterSetName = 'ProductionPreflight')]
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedNormalizedCandidateSha256,
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][switch]$IUnderstandThisWritesProduction,
    [Parameter(Mandatory = $true, ParameterSetName = 'ExecuteProduction')][string]$ConfirmationPhrase
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Stop-Launch([string]$Code) { throw $Code }
function Get-Sha256([string]$Path) {
    $stream = [System.IO.File]::OpenRead($Path)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try { return ([System.BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
    finally { $algorithm.Dispose(); $stream.Dispose() }
}
function Get-StringSha256([string]$Value) {
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try { $hash = $algorithm.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Value)) } finally { $algorithm.Dispose() }
    return [System.BitConverter]::ToString($hash).Replace('-','').ToLowerInvariant()
}
function Get-Tree([string]$Root) {
    $records = New-Object System.Collections.Generic.List[string]
    [int64]$bytes = 0
    [string[]]$relativePaths = @(Get-ChildItem -LiteralPath $Root -File -Recurse -Force | ForEach-Object { $_.FullName.Substring($Root.Length).TrimStart('\').Replace('\','/') })
    [System.Array]::Sort($relativePaths, [System.StringComparer]::Ordinal)
    foreach ($relative in $relativePaths) {
        $file = Get-Item -LiteralPath (Join-Path $Root $relative.Replace('/','\'))
        $bytes += [int64]$file.Length
        $records.Add($relative + [char]0 + [string]$file.Length + [char]0 + (Get-Sha256 $file.FullName) + "`n")
    }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $joined = [string]::Join('', $records.ToArray())
    try { $hash = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($joined)) } finally { $sha.Dispose() }
    return [pscustomobject]@{sha256=[System.BitConverter]::ToString($hash).Replace('-','').ToLowerInvariant();file_count=$relativePaths.Count;bytes=$bytes}
}
function Get-TrustedGitExecutable {
    $shim=(@(Get-Command git.exe -CommandType Application -ErrorAction Stop)[0]).Source
    $gitRoot=Split-Path -Parent (Split-Path -Parent $shim)
    $direct=Join-Path $gitRoot 'mingw64\bin\git.exe'
    if(Test-Path -LiteralPath $direct -PathType Leaf){return $direct}
    return $shim
}
function Invoke-Git([string[]]$Arguments, [string]$InputText = '') {
    $gitExecutable = Get-TrustedGitExecutable
    $boundary = Join-Path ([IO.Path]::GetTempPath()) ('doc04b-git-' + [Guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($boundary) | Out-Null
    $globalConfig=Join-Path $boundary 'global.gitconfig';$attributes=Join-Path $boundary 'global.attributes';$gitHomeRoot=Join-Path $boundary 'home';$xdg=Join-Path $boundary 'xdg'
    [IO.Directory]::CreateDirectory($gitHomeRoot)|Out-Null;[IO.Directory]::CreateDirectory($xdg)|Out-Null
    [IO.File]::WriteAllText($globalConfig,'',[Text.UTF8Encoding]::new($false));[IO.File]::WriteAllText($attributes,'',[Text.UTF8Encoding]::new($false))
    $allArguments=@('-c',"core.attributesFile=$attributes",'-c','core.autocrlf=false')+$Arguments
    $info=New-Object Diagnostics.ProcessStartInfo;$info.FileName=$gitExecutable;$info.Arguments=(@($allArguments|ForEach-Object{ConvertTo-WindowsArgument ([string]$_)})-join ' ')
    $hasInput=-not [string]::IsNullOrEmpty($InputText)
    $info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.RedirectStandardInput=$hasInput;$info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true;$info.EnvironmentVariables.Clear()
    foreach($name in @('SystemRoot','WINDIR','ComSpec','PATH')){$value=[Environment]::GetEnvironmentVariable($name,'Process');if($value){$info.EnvironmentVariables[$name]=$value}}
    $info.EnvironmentVariables['GIT_CONFIG_NOSYSTEM']='1';$info.EnvironmentVariables['GIT_ATTR_NOSYSTEM']='1';$info.EnvironmentVariables['GIT_TERMINAL_PROMPT']='0';$info.EnvironmentVariables['GIT_NO_REPLACE_OBJECTS']='1';$info.EnvironmentVariables['GIT_OPTIONAL_LOCKS']='0';$info.EnvironmentVariables['TEMP']=$boundary;$info.EnvironmentVariables['TMP']=$boundary;$info.EnvironmentVariables['GIT_CONFIG_GLOBAL']=$globalConfig;$info.EnvironmentVariables['HOME']=$gitHomeRoot;$info.EnvironmentVariables['USERPROFILE']=$gitHomeRoot;$info.EnvironmentVariables['XDG_CONFIG_HOME']=$xdg
    $process=New-Object Diagnostics.Process;$process.StartInfo=$info
    try{if(-not $process.Start()){Stop-Launch 'DOC04B_GIT_IDENTITY_FAILED'};$stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync();if($hasInput){$process.StandardInput.Write($InputText);$process.StandardInput.Close()};if(-not $process.WaitForExit(30000)){try{$process.Kill()}catch{};Stop-Launch 'DOC04B_GIT_IDENTITY_FAILED'};if($process.ExitCode-ne 0){Stop-Launch 'DOC04B_GIT_IDENTITY_FAILED'};return $stdout.Result.Trim()}finally{$process.Dispose();if(Test-Path -LiteralPath $boundary){Remove-Item -LiteralPath $boundary -Recurse -Force}}
}
function Get-NormalizedGitBlobSha1([string]$Path) {
    $text=[IO.File]::ReadAllText($Path,[Text.UTF8Encoding]::new($false)).Replace("`r`n","`n").Replace("`r","`n");$bytes=[Text.Encoding]::UTF8.GetBytes($text);$header=[Text.Encoding]::ASCII.GetBytes(('blob '+$bytes.Length+[char]0));$combined=New-Object byte[] ($header.Length+$bytes.Length);[Array]::Copy($header,0,$combined,0,$header.Length);[Array]::Copy($bytes,0,$combined,$header.Length,$bytes.Length);$sha=[Security.Cryptography.SHA1]::Create();try{$hash=$sha.ComputeHash($combined)}finally{$sha.Dispose()};return [BitConverter]::ToString($hash).Replace('-','').ToLowerInvariant()
}
function Test-IsWithin([string]$Candidate, [string]$Boundary) {
    $candidatePath = [System.IO.Path]::GetFullPath($Candidate).TrimEnd('\')
    $boundaryPath = [System.IO.Path]::GetFullPath($Boundary).TrimEnd('\')
    if ($candidatePath.Equals($boundaryPath, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    return $candidatePath.StartsWith($boundaryPath + '\', [System.StringComparison]::OrdinalIgnoreCase)
}
function Test-IsStrictDescendant([string]$Candidate, [string]$Boundary) {
    $candidatePath = [System.IO.Path]::GetFullPath($Candidate).TrimEnd('\')
    $boundaryPath = [System.IO.Path]::GetFullPath($Boundary).TrimEnd('\')
    return -not $candidatePath.Equals($boundaryPath, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-IsWithin $candidatePath $boundaryPath)
}
function Assert-NoReparseChain([string]$Path, [string]$Code) {
    $cursor = [System.IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { Stop-Launch $Code }
        }
        $parent = [System.IO.Path]::GetDirectoryName($cursor)
        if (-not $parent -or $parent -eq $cursor) { break }
        $cursor = $parent
    }
}
function Assert-NonReparseDirectory([string]$Path, [string]$Code) {
    Assert-NoReparseChain $Path $Code
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) { Stop-Launch $Code }
    $item = Get-Item -LiteralPath $Path -Force
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { Stop-Launch $Code }
}
function Assert-NonReparseTree([string]$Path, [string]$Code) {
    Assert-NonReparseDirectory $Path $Code
    foreach ($item in Get-ChildItem -LiteralPath $Path -Force -Recurse) {
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { Stop-Launch $Code }
    }
}
function Assert-RegularNonReparseFile([string]$Path, [string]$Code) {
    Assert-NoReparseChain $Path $Code
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { Stop-Launch $Code }
    $item = Get-Item -LiteralPath $Path -Force
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { Stop-Launch $Code }
}
function Assert-ExactPhysicalTree([string]$Repo, [string]$RelativeRoot, [string[]]$TrackedPaths, [string]$Code) {
    $root=Join-Path $Repo ($RelativeRoot -replace '/','\');Assert-NonReparseTree $root $Code
    $expectedFiles=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal);$expectedDirectories=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
    foreach($tracked in $TrackedPaths){if(-not $tracked.StartsWith($RelativeRoot+'/',[StringComparison]::Ordinal)){Stop-Launch $Code};[void]$expectedFiles.Add($tracked);$parent=[IO.Path]::GetDirectoryName($tracked.Replace('/','\'));while($parent -and $parent.Replace('\','/') -ne $RelativeRoot){[void]$expectedDirectories.Add($parent.Replace('\','/'));$parent=[IO.Path]::GetDirectoryName($parent)}}
    $actualFiles=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal);$actualDirectories=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal);$caseMap=@{}
    foreach($item in Get-ChildItem -LiteralPath $root -Force -Recurse){if(($item.Attributes-band[IO.FileAttributes]::ReparsePoint)-ne 0){Stop-Launch $Code};$relative=$item.FullName.Substring($Repo.Length).TrimStart('\').Replace('\','/');$caseKey=$relative.ToLowerInvariant();if($caseMap.ContainsKey($caseKey)-and$caseMap[$caseKey]-cne$relative){Stop-Launch 'DOC04B_SOURCE_FILESYSTEM_CASE_COLLISION'};$caseMap[$caseKey]=$relative;if($item.PSIsContainer){[void]$actualDirectories.Add($relative)}else{[void]$actualFiles.Add($relative)}}
    if($actualFiles.Count-ne$expectedFiles.Count-or@($actualFiles|Where-Object{-not$expectedFiles.Contains($_)}).Count-ne 0-or@($expectedFiles|Where-Object{-not$actualFiles.Contains($_)}).Count-ne 0){Stop-Launch $Code}
    if($actualDirectories.Count-ne$expectedDirectories.Count-or@($actualDirectories|Where-Object{-not$expectedDirectories.Contains($_)}).Count-ne 0-or@($expectedDirectories|Where-Object{-not$actualDirectories.Contains($_)}).Count-ne 0){Stop-Launch $Code}
}
function Assert-TrustedGitBoundary([string]$Repo,[string[]]$Paths,$Lock) {
    $attributes=Join-Path $Repo '.gitattributes';Assert-RegularNonReparseFile $attributes 'DOC04B_GITATTRIBUTES_INVALID'
    if((Get-NormalizedGitBlobSha1 $attributes)-ne[string]$Lock.trusted_git_policy.gitattributes_git_blob){Stop-Launch 'DOC04B_GITATTRIBUTES_BLOB_MISMATCH'}
    $infoAttributes=Join-Path $Repo '.git\info\attributes';if((Test-Path -LiteralPath $infoAttributes)-and(Get-Item -LiteralPath $infoAttributes).Length-ne 0){Stop-Launch 'DOC04B_GIT_INFO_ATTRIBUTES_FORBIDDEN'}
    $output=Invoke-Git @('-C',$Repo,'check-attr','--stdin','-a') (($Paths-join "`n")+"`n")
    foreach($line in @($output-split"`r?`n"|Where-Object{$_})){if($line-notmatch'^.+: ([^:]+): .+$'){Stop-Launch 'DOC04B_GIT_ATTRIBUTES_INVALID'};if($Matches[1]-in@('filter','ident','working-tree-encoding')-or$Matches[1]-notin@('text','eol')){Stop-Launch 'DOC04B_GIT_ATTRIBUTES_FORBIDDEN'}}
}
function Assert-PolicyPath([string]$Path, [string]$AuthorizedParent, $Policy, [string]$Code) {
    $full = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    $parent = [System.IO.Path]::GetFullPath($AuthorizedParent).TrimEnd('\')
    if (-not (Test-IsStrictDescendant $full $parent)) { Stop-Launch $Code }
    foreach ($boundary in @($Policy.forbidden_roots)) {
        if ($boundary -and (Test-IsWithin $full ([System.IO.Path]::GetFullPath([string]$boundary).TrimEnd('\')))) { Stop-Launch $Code }
    }
    Assert-NoReparseChain $parent $Code
    Assert-NoReparseChain $full $Code
    return $full
}
function Assert-SyntheticRoot([string]$Root, [string]$Repo, [string[]]$AdditionalForbidden, $Policy) {
    $full = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
    if ([string]::IsNullOrWhiteSpace($full) -or $full -eq [System.IO.Path]::GetPathRoot($full)) { Stop-Launch 'DOC04B_SYNTHETIC_ROOT_INVALID' }
    if (-not (Test-IsStrictDescendant $full ([string]$Policy.authorized_parent))) { Stop-Launch 'DOC04B_SYNTHETIC_ROOT_OUTSIDE_AUTHORIZED_PARENT' }
    Assert-NonReparseDirectory $full 'DOC04B_SYNTHETIC_ROOT_INVALID'
    $forbidden = @($Repo, (Join-Path $Repo 'data'), 'C:\ai-lab-core-backups', 'E:\', 'F:\') + @($Policy.forbidden_roots) + @($AdditionalForbidden)
    foreach ($boundary in $forbidden) {
        if (-not [string]::IsNullOrWhiteSpace($boundary) -and (Test-IsWithin $full $boundary)) { Stop-Launch 'DOC04B_SYNTHETIC_ROOT_FORBIDDEN' }
    }
    $windows = [Environment]::GetFolderPath('Windows')
    $system = [Environment]::GetFolderPath('System')
    $startup = [Environment]::GetFolderPath('Startup')
    foreach ($boundary in @($windows,$system,$startup)) {
        if ($boundary -and (Test-IsWithin $full $boundary)) { Stop-Launch 'DOC04B_SYNTHETIC_ROOT_FORBIDDEN' }
    }
    return $full
}
function Assert-ProductionConfigurationRoot([string]$Root, [string]$Data, $Policy) {
    $full = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
    if ([string]::IsNullOrWhiteSpace($full) -or $full -eq [System.IO.Path]::GetPathRoot($full)) { Stop-Launch 'DOC04B_PRODUCTION_ENVIRONMENT_ROOT_INVALID' }
    Assert-NonReparseDirectory $full 'DOC04B_PRODUCTION_ENVIRONMENT_ROOT_INVALID'
    $boundaries = @($Data) + @($Policy.production_configuration.forbidden_roots)
    foreach ($boundary in $boundaries) {
        if ($boundary -and (Test-IsWithin $full ([System.IO.Path]::GetFullPath([string]$boundary).TrimEnd('\')))) { Stop-Launch 'DOC04B_PRODUCTION_ENVIRONMENT_ROOT_FORBIDDEN' }
    }
    return $full
}
function Assert-ProductionDataRoot([string]$Environment,[string]$Data,$Lock) {
    $environmentFull=[IO.Path]::GetFullPath($Environment).TrimEnd('\');$dataFull=[IO.Path]::GetFullPath($Data).TrimEnd('\');$expected=[IO.Path]::GetFullPath((Join-Path $environmentFull ([string]$Lock.production_data_policy.canonical_relative_path))).TrimEnd('\')
    if(-not $dataFull.Equals($expected,[StringComparison]::OrdinalIgnoreCase)){Stop-Launch 'DOC04B_PRODUCTION_DATA_ROOT_NOT_CANONICAL'}
    Assert-NonReparseDirectory $dataFull 'DOC04B_PRODUCTION_DATA_ROOT_INVALID'
    $blockedRoots = @(
        'C:\ai-lab-core-backups',
        'E:\',
        'F:\',
        ([string]$Lock.path_policies.runtime_cache.authorized_runtime_parent),
        ([string]$Lock.path_policies.runtime_cache.authorized_cache_parent),
        $env:windir,
        $env:ProgramFiles,
        ${env:ProgramFiles(x86)},
        $env:ProgramData
    )
    foreach($blocked in $blockedRoots){
        if($blocked){
            $blockedFull = [IO.Path]::GetFullPath($blocked).TrimEnd('\')
            if(Test-IsWithin $dataFull $blockedFull){Stop-Launch 'DOC04B_PRODUCTION_DATA_ROOT_FORBIDDEN'}
        }
    }
    return $dataFull
}
function Get-StreamSha256([System.IO.FileStream]$Stream) {
    $Stream.Position = 0
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try { $hash = $algorithm.ComputeHash($Stream) } finally { $algorithm.Dispose(); $Stream.Position = 0 }
    return [System.BitConverter]::ToString($hash).Replace('-','').ToLowerInvariant()
}
function Open-VerifiedEnvironmentFile([string]$Path, [string]$ExpectedSha256) {
    Assert-RegularNonReparseFile $Path 'DOC04B_PRODUCTION_ENV_FILE_INVALID'
    try {
        $stream = [System.IO.File]::Open($Path,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::Read)
    } catch { Stop-Launch 'DOC04B_PRODUCTION_ENV_LOCK_FAILED' }
    try {
        if ((Get-StreamSha256 $stream) -cne $ExpectedSha256) { Stop-Launch 'DOC04B_PRODUCTION_ENV_HASH_MISMATCH' }
        return $stream
    } catch {
        $stream.Dispose()
        throw
    }
}
function Assert-Source([string]$Repo, [string]$Expected, $Lock) {
    $root = [System.IO.Path]::GetFullPath($Repo).TrimEnd('\')
    if ((Invoke-Git @('-C',$root,'rev-parse','HEAD')) -ne $Expected) { Stop-Launch 'DOC04B_GIT_HEAD_MISMATCH' }
    $protectedStatus = Invoke-Git @('-C',$root,'status','--porcelain=v1','--untracked-files=all','--','backend/app','operations/windows/doc04-metadata-repair','backend/requirements.txt','.gitattributes','compose/backend/docker-compose.yml')
    if ($protectedStatus) { Stop-Launch 'DOC04B_PROTECTED_SOURCE_DIRTY' }
    if ((Invoke-Git @('-C',$root,'rev-parse','HEAD:backend/app')) -ne [string]$Lock.source_closure.backend_app_git_tree_sha) { Stop-Launch 'DOC04B_BACKEND_APP_TREE_MISMATCH' }
    $treeOutput = Invoke-Git @('-C',$root,'ls-tree','-r','--full-tree','HEAD','--','backend/app')
    $tracked = @($treeOutput -split "`r?`n" | Where-Object { $_ })
    if (-not $tracked.Count) { Stop-Launch 'DOC04B_BACKEND_APP_TREE_EMPTY' }
    $expectedBlobs = New-Object System.Collections.Generic.List[string]
    $trackedPaths = New-Object System.Collections.Generic.List[string]
    foreach ($record in $tracked) {
        if ($record -notmatch '^(100644|100755) blob ([0-9a-f]{40})\t(.+)$') { Stop-Launch 'DOC04B_BACKEND_APP_TREE_ENTRY_INVALID' }
        $expectedBlob = [string]$Matches[2]
        $relative = [string]$Matches[3]
        $path = Join-Path $root ($relative -replace '/','\')
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { Stop-Launch 'DOC04B_BACKEND_APP_SOURCE_MISSING' }
        $item = Get-Item -LiteralPath $path -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { Stop-Launch 'DOC04B_BACKEND_APP_SOURCE_REPARSE' }
        $expectedBlobs.Add($expectedBlob)
        $trackedPaths.Add($relative)
    }
    $gitCommand = @(Get-Command git.exe -CommandType Application -ErrorAction Stop)[0]
    $actualBlobs = @((Invoke-Git @('-C',$root,'hash-object','--stdin-paths') (($trackedPaths.ToArray()-join "`n")+"`n")) -split "`r?`n")
    if ($actualBlobs.Count -ne $expectedBlobs.Count) { Stop-Launch 'DOC04B_GIT_IDENTITY_FAILED' }
    for ($index=0; $index -lt $expectedBlobs.Count; $index++) {
        if ([string]$actualBlobs[$index] -ne $expectedBlobs[$index]) { Stop-Launch 'DOC04B_BACKEND_APP_SOURCE_MODIFIED' }
    }
    $backendPaths=@($trackedPaths.ToArray());Assert-ExactPhysicalTree $root 'backend/app' $backendPaths 'DOC04B_SOURCE_FILESYSTEM_EXTRA_ENTRY'
    $toolingPaths=@($Lock.source_filesystem_policy.runtime_tooling_files|ForEach-Object{[string]$_});Assert-ExactPhysicalTree $root 'operations/windows/doc04-metadata-repair' $toolingPaths 'DOC04B_RUNTIME_TOOLING_FILESYSTEM_MISMATCH'
    $allProtected=@($backendPaths)+@($toolingPaths)+@($Lock.source_filesystem_policy.single_files|ForEach-Object{[string]$_});Assert-TrustedGitBoundary $root $allProtected $Lock
    foreach ($relative in $Lock.critical_git_paths) {
        $path = Join-Path $root ([string]$relative -replace '/','\')
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { Stop-Launch 'DOC04B_CRITICAL_SOURCE_MISSING' }
        $item = Get-Item -LiteralPath $path -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { Stop-Launch 'DOC04B_CRITICAL_SOURCE_REPARSE' }
        $expectedBlob = Invoke-Git @('-C',$root,'rev-parse',"HEAD:$relative")
        $actualBlob = Invoke-Git @('-C',$root,'hash-object',"--path=$relative",$path)
        if ($expectedBlob -ne $actualBlob) { Stop-Launch 'DOC04B_CRITICAL_SOURCE_MODIFIED' }
    }
    if((Invoke-Git @('-C',$root,'rev-parse','HEAD:backend/requirements.txt'))-ne[string]$Lock.backend_requirements_git_blob){Stop-Launch 'DOC04B_BACKEND_REQUIREMENTS_BLOB_MISMATCH'}
    if((Invoke-Git @('-C',$root,'rev-parse',('HEAD:'+ [string]$Lock.production_data_policy.compose_path)))-ne[string]$Lock.production_data_policy.compose_git_blob){Stop-Launch 'DOC04B_COMPOSE_BLOB_MISMATCH'}
    $compose=[IO.File]::ReadAllText((Join-Path $root ([string]$Lock.production_data_policy.compose_path -replace '/','\')),[Text.UTF8Encoding]::new($false))
    if(-not$compose.Contains([string]$Lock.production_data_policy.compose_mount)){Stop-Launch 'DOC04B_COMPOSE_DATA_MAPPING_MISMATCH'}
}
function Assert-Runtime([string]$Root, $Lock, [string]$ExpectedProfile) {
    $full = Assert-PolicyPath $Root $Lock.path_policies.runtime_cache.authorized_runtime_parent $Lock.path_policies.runtime_cache 'DOC04B_RUNTIME_PATH_FORBIDDEN'
    Assert-NonReparseTree $full 'DOC04B_RUNTIME_REPARSE_FORBIDDEN'
    $profileDefinition = $Lock.profiles.$ExpectedProfile
    if (-not $profileDefinition) { Stop-Launch 'DOC04B_RUNTIME_PROFILE_INVALID' }
    $markerPath = Join-Path $full '_NEXT_DOC04_RUNTIME_PROFILE.json'
    Assert-RegularNonReparseFile $markerPath 'DOC04B_RUNTIME_PROFILE_MARKER_INVALID'
    try { $marker = Get-Content -LiteralPath $markerPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { Stop-Launch 'DOC04B_RUNTIME_PROFILE_MARKER_INVALID' }
    if ($marker.profile -cne $ExpectedProfile -or $marker.schema -ne $Lock.schema) { Stop-Launch 'DOC04B_RUNTIME_PROFILE_MISMATCH' }
    $tree = Get-Tree $full
    if ($tree.sha256 -ne $profileDefinition.installed_runtime.expected_tree_sha256 -or $tree.file_count -ne [int]$profileDefinition.installed_runtime.expected_file_count) { Stop-Launch 'DOC04B_RUNTIME_TREE_MISMATCH' }
    foreach ($name in @('python.exe','python312.dll')) {
        $path = Join-Path $full $name
        $signature = Get-AuthenticodeSignature -LiteralPath $path
        if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid -or -not $signature.SignerCertificate.Subject.Contains($Lock.runtime_python.authenticode_subject_contains)) { Stop-Launch 'DOC04B_RUNTIME_SIGNATURE_INVALID' }
    }
    return $full
}
function ConvertTo-WindowsArgument([string]$Value) {
    if ($Value.Length -eq 0) { return '""' }
    if ($Value -notmatch '[\s"]') { return $Value }
    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append('"')
    [int]$slashes = 0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq '\') { $slashes++; continue }
        if ($character -eq '"') {
            [void]$builder.Append(('\' * (($slashes * 2) + 1)))
            [void]$builder.Append('"')
            $slashes = 0
            continue
        }
        if ($slashes -gt 0) { [void]$builder.Append(('\' * $slashes)); $slashes = 0 }
        [void]$builder.Append($character)
    }
    if ($slashes -gt 0) { [void]$builder.Append(('\' * ($slashes * 2))) }
    [void]$builder.Append('"')
    return $builder.ToString()
}
function Invoke-IsolatedProcess(
    [string]$Python,
    [string]$EntryPoint,
    [string[]]$Arguments,
    [string]$WorkingDirectory,
    [hashtable]$Environment,
    [int]$TimeoutMilliseconds
) {
    $invocationRoot=Join-Path $script:InvocationScratchParent ('invocation-'+[Guid]::NewGuid().ToString('N'))
    $scratch=Join-Path $invocationRoot 'scratch';$pycache=Join-Path $invocationRoot 'pycache';$gitHome=Join-Path $invocationRoot 'git-home';$gitXdg=Join-Path $invocationRoot 'git-xdg';$gitConfig=Join-Path $invocationRoot 'global.gitconfig';$gitAttributes=Join-Path $invocationRoot 'global.attributes'
    foreach($path in @($scratch,$pycache,$gitHome,$gitXdg)){[IO.Directory]::CreateDirectory($path)|Out-Null}
    [IO.File]::WriteAllText($gitConfig,'',[Text.UTF8Encoding]::new($false));[IO.File]::WriteAllText($gitAttributes,'',[Text.UTF8Encoding]::new($false))
    $dataBoundary=if($Environment.ContainsKey('NEXT_DOC04_DATA_ROOT')){[string]$Environment['NEXT_DOC04_DATA_ROOT']}else{''}
    foreach($boundary in @($script:RepoRootIdentity,$script:RuntimeRootIdentity,$WorkingDirectory,$dataBoundary,'C:\ai-lab-core-backups','E:\','F:\',$env:ProgramFiles,$env:ProgramData,$env:windir)){if($boundary-and(Test-IsWithin $invocationRoot $boundary)){Stop-Launch 'DOC04B_INVOCATION_SCRATCH_FORBIDDEN'}}
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $Python
    $allArguments = @('-I','-B','--check-hash-based-pycs','always','-X','utf8','-X',('pycache_prefix='+$pycache),$EntryPoint) + $Arguments
    $info.Arguments = (@($allArguments | ForEach-Object { ConvertTo-WindowsArgument ([string]$_) }) -join ' ')
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.WorkingDirectory = $WorkingDirectory
    $info.EnvironmentVariables.Clear()
    $childEnvironment=@{};foreach($item in $Environment.GetEnumerator()){$childEnvironment[[string]$item.Key]=[string]$item.Value}
    $childEnvironment['TEMP']=$scratch;$childEnvironment['TMP']=$scratch;$childEnvironment['GIT_CONFIG_NOSYSTEM']='1';$childEnvironment['GIT_ATTR_NOSYSTEM']='1';$childEnvironment['GIT_TERMINAL_PROMPT']='0';$childEnvironment['GIT_NO_REPLACE_OBJECTS']='1';$childEnvironment['GIT_OPTIONAL_LOCKS']='0';$childEnvironment['GIT_CONFIG_GLOBAL']=$gitConfig;$childEnvironment['HOME']=$gitHome;$childEnvironment['USERPROFILE']=$gitHome;$childEnvironment['XDG_CONFIG_HOME']=$gitXdg;$childEnvironment['NEXT_DOC04_GIT_ATTRIBUTES_FILE']=$gitAttributes;$childEnvironment['NEXT_DOC04_PYCACHE_PREFIX']=$pycache;$childEnvironment['NEXT_DOC04_INVOCATION_SCRATCH']=$invocationRoot;$childEnvironment['NEXT_DOC04_RUNTIME_ROOT']=$script:RuntimeRootIdentity
    foreach ($item in $childEnvironment.GetEnumerator()) { $info.EnvironmentVariables[[string]$item.Key] = [string]$item.Value }
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    try {
        if (-not $process.Start()) { Stop-Launch 'DOC04B_CHILD_START_FAILED' }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutMilliseconds)) {
            try { $process.Kill() } catch { }
            Stop-Launch 'DOC04B_CHILD_TIMEOUT'
        }
        $stdout = $stdoutTask.Result.Trim()
        $stderr = $stderrTask.Result.Trim()
        if ($stdout.Length -gt 65536 -or $stderr.Length -gt 65536 -or $stdout.Contains([char]0) -or $stderr.Contains([char]0)) { Stop-Launch 'DOC04B_CHILD_OUTPUT_UNBOUNDED' }
        return [pscustomobject]@{exit_code=$process.ExitCode;stdout=$stdout;stderr=$stderr}
    } finally {
        $process.Dispose()
        $cleanupViolation=''
        if((Test-Path -LiteralPath $pycache)-and@(Get-ChildItem -LiteralPath $pycache -Force -Recurse -File).Count-ne 0){$cleanupViolation='DOC04B_INVOCATION_PYCACHE_CREATED'}
        foreach($sourceRoot in @((Join-Path $script:RepoRootIdentity 'backend\app'),(Join-Path $script:RepoRootIdentity 'operations\windows\doc04-metadata-repair'))){if(Test-Path -LiteralPath $sourceRoot){if(@(Get-ChildItem -LiteralPath $sourceRoot -Force -Recurse -File|Where-Object{$_.Extension-in@('.pyc','.pyo')}).Count-ne 0){$cleanupViolation='DOC04B_SOURCE_PYCACHE_CREATED'}}}
        if(Test-Path -LiteralPath $invocationRoot){Remove-Item -LiteralPath $invocationRoot -Recurse -Force}
        if($cleanupViolation){Stop-Launch $cleanupViolation}
    }
}
function ConvertFrom-BoundedJson([string]$Value) {
    $lines = @($Value -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($lines.Count -ne 1) { Stop-Launch ('DOC04B_CHILD_OUTPUT_LINE_COUNT_' + [string]$lines.Count) }
    try { return ($lines[0] | ConvertFrom-Json) } catch { Stop-Launch 'DOC04B_CHILD_OUTPUT_JSON_INVALID' }
}
function ConvertTo-IsoTimestampArgument($Value) {
    if ($Value -is [DateTimeOffset]) {
        return $Value.ToString('o', [Globalization.CultureInfo]::InvariantCulture)
    }
    if ($Value -is [DateTime]) {
        return ([DateTimeOffset]$Value).ToString('o', [Globalization.CultureInfo]::InvariantCulture)
    }
    $text = [string]$Value
    if ($text -notmatch '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?(?:Z|[+-]\d{2}:\d{2})$') {
        Stop-Launch 'DOC04B_CHILD_TIMESTAMP_INVALID'
    }
    return $text
}
function New-MinimalEnvironment(
    [string]$Runtime,
    [string]$GitExe,
    [string]$WorkingDirectory,
    [string]$Policy,
    [string[]]$ForbiddenRoots,
    [string]$Profile,
    [string]$AllowedEnvFile = '',
    [string]$ExpectedEnvSha256 = '',
    [string]$NetworkHost = '',
    [int]$NetworkPort = 0
) {
    $systemRoot = [Environment]::GetEnvironmentVariable('SystemRoot','Process')
    $windir = [Environment]::GetEnvironmentVariable('WINDIR','Process')
    $comspec = [Environment]::GetEnvironmentVariable('ComSpec','Process')
    if (-not $systemRoot) { $systemRoot = $windir }
    if (-not $windir) { $windir = $systemRoot }
    if (-not $comspec) { $comspec = Join-Path $systemRoot 'System32\cmd.exe' }
    $path = @($Runtime,(Split-Path -Parent $GitExe),(Join-Path $systemRoot 'System32')) -join ';'
    $result = @{
        'SystemRoot'=$systemRoot;'WINDIR'=$windir;'ComSpec'=$comspec;'TEMP'=$WorkingDirectory;'TMP'=$WorkingDirectory;'PATH'=$path;
        'PYTHONDONTWRITEBYTECODE'='1';'PYTHONNOUSERSITE'='1';'PYTHONUTF8'='1';
        'NEXT_DOC04_EXPECTED_GIT_SHA'=$ExpectedGitSha;'NEXT_DOC04_GIT_EXE'=$GitExe;
        'NEXT_DOC04_RUNTIME_POLICY'=$Policy;'NEXT_DOC04_ENVIRONMENT_ROOT'=$WorkingDirectory;
        'NEXT_DOC04_WORKING_DIRECTORY'=$WorkingDirectory;
        'NEXT_DOC04_FORBIDDEN_ROOTS_JSON'=($ForbiddenRoots | ConvertTo-Json -Compress);
        'NEXT_DOC04_RUNTIME_PROFILE'=$Profile
    }
    if ($AllowedEnvFile) {
        $result['NEXT_DOC04_ALLOWED_ENV_FILE'] = $AllowedEnvFile
        $result['NEXT_DOC04_EXPECTED_ENV_SHA256'] = $ExpectedEnvSha256
    }
    if ($NetworkHost) {
        $result['NEXT_DOC04_NETWORK_ALLOWED_HOST'] = $NetworkHost
        $result['NEXT_DOC04_NETWORK_ALLOWED_PORT'] = [string]$NetworkPort
    }
    return $result
}
function Add-SyntheticApplicationEnvironment([hashtable]$Environment, [string]$WorkingDirectory, [string]$Database, [int]$Port, [string]$Password) {
    $Environment['ENVIRONMENT']='test';$Environment['POSTGRES_DB']=$Database;$Environment['POSTGRES_USER']='doc04b';
    $Environment['POSTGRES_PASSWORD']=$Password;$Environment['POSTGRES_HOST']='127.0.0.1';$Environment['POSTGRES_PORT']=[string]$Port;
    $Environment['SECRET_KEY']='synthetic-doc04b-key-not-production';$Environment['ADMIN_USERNAME']='synthetic';
    $Environment['ADMIN_EMAIL']='synthetic@example.invalid';$Environment['ADMIN_PASSWORD']='synthetic-only';
    $Environment['N8N_INGEST_API_KEY']='synthetic-only';$Environment['DATA_DIR']=(Join-Path $WorkingDirectory 'data')
}

$RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
$RuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot).TrimEnd('\')
$lockPath = Join-Path $RepoRoot 'operations\windows\doc04-metadata-repair\runtime-lock.json'
$lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($lock.schema -ne 'NEXT_STABIL_DOC04_WINDOWS_RUNTIME_LOCK_V5') { Stop-Launch 'DOC04B_RUNTIME_LOCK_SCHEMA_MISMATCH' }
Assert-Source $RepoRoot $ExpectedGitSha $lock
$expectedProfile = if ($PSCmdlet.ParameterSetName -in @('IsolatedTest','IsolatedAlembicUpgrade')) { 'Qualification' } else { 'Production' }
$RuntimeRoot = Assert-Runtime $RuntimeRoot $lock $expectedProfile
$python = Join-Path $RuntimeRoot 'python.exe'
$entrypoint = Join-Path $RepoRoot 'operations\windows\doc04-metadata-repair\runtime-entrypoint.py'
$gitExe = Get-TrustedGitExecutable
$script:InvocationScratchParent=[IO.Path]::GetFullPath([string]$lock.path_policies.nonproduction_working.authorized_parent).TrimEnd('\')
$script:RepoRootIdentity=$RepoRoot
$script:RuntimeRootIdentity=$RuntimeRoot
if(-not(Test-Path -LiteralPath $script:InvocationScratchParent)){[IO.Directory]::CreateDirectory($script:InvocationScratchParent)|Out-Null}

$nonProductionSets = @('Readiness','RepairHelp','CompatibilityVectors','IsolatedTest','IsolatedAlembicUpgrade','AuditEnvProbe','SyntheticProductionAudit','ProductionImportTrace','NetworkForbiddenProbe','RepairRelaySelfTest')
if ($PSCmdlet.ParameterSetName -in $nonProductionSets) {
    $SyntheticRoot = Assert-SyntheticRoot $SyntheticRoot $RepoRoot (@($SyntheticForbiddenRoots) + @($RuntimeRoot)) $lock.path_policies.nonproduction_working
    $workingDirectory = Join-Path $SyntheticRoot ('environment-' + [Guid]::NewGuid().ToString('N'))
    [System.IO.Directory]::CreateDirectory($workingDirectory) | Out-Null
    try {
        $forbiddenRoots = @($RepoRoot,(Join-Path $RepoRoot 'data'),'C:\ai-lab-core-backups','E:\','F:\',$RuntimeRoot) + @($lock.path_policies.nonproduction_working.forbidden_roots) + @($SyntheticForbiddenRoots)
        $policy = switch ($PSCmdlet.ParameterSetName) {
            'Readiness' {'readiness'} 'RepairHelp' {'repair-help'} 'CompatibilityVectors' {'compatibility-vectors'}
            'IsolatedTest' {'isolated-test'} 'IsolatedAlembicUpgrade' {'isolated-alembic-upgrade'}
            'AuditEnvProbe' {'nonproduction-audit-probe'} 'SyntheticProductionAudit' {'synthetic-production-audit'}
            'ProductionImportTrace' {'production-source-security-trace'} 'NetworkForbiddenProbe' {'network-forbidden-probe'} 'RepairRelaySelfTest' {'repair-relay-self-test'}
        }
        $networkPort = if ($PSCmdlet.ParameterSetName -in @('IsolatedTest','IsolatedAlembicUpgrade')) { $SyntheticDatabasePort } else { 0 }
        $networkHost = if ($networkPort) { '127.0.0.1' } else { '' }
        $environment = New-MinimalEnvironment $RuntimeRoot $gitExe $workingDirectory $policy $forbiddenRoots $expectedProfile '' '' $networkHost $networkPort
        if ($PSCmdlet.ParameterSetName -eq 'SyntheticProductionAudit') {
            [System.IO.File]::WriteAllText((Join-Path $workingDirectory '.env'),'synthetic-control=1',(New-Object System.Text.UTF8Encoding($false)))
            [System.IO.Directory]::CreateDirectory((Join-Path $workingDirectory 'second')) | Out-Null
            [System.IO.File]::WriteAllText((Join-Path $workingDirectory 'second\.env'),'synthetic-control=2',(New-Object System.Text.UTF8Encoding($false)))
            $environment['NEXT_DOC04_ALLOWED_ENV_FILE'] = Join-Path $workingDirectory '.env'
            $environment['NEXT_DOC04_EXPECTED_ENV_SHA256'] = Get-Sha256 (Join-Path $workingDirectory '.env')
            $arguments = @('synthetic-production-audit')
        } else {
            $databaseName = if ($PSCmdlet.ParameterSetName -in @('IsolatedTest','IsolatedAlembicUpgrade')) { $SyntheticDatabaseName } else { 'ai_lab_test_doc04b_readiness' }
            $databasePort = if ($PSCmdlet.ParameterSetName -in @('IsolatedTest','IsolatedAlembicUpgrade')) { $SyntheticDatabasePort } else { 65432 }
            $databasePassword = if ($PSCmdlet.ParameterSetName -in @('IsolatedTest','IsolatedAlembicUpgrade')) { $SyntheticDatabasePassword } else { 'synthetic-only' }
            Add-SyntheticApplicationEnvironment $environment $workingDirectory $databaseName $databasePort $databasePassword
            [System.IO.Directory]::CreateDirectory((Join-Path $workingDirectory 'data')) | Out-Null
            $arguments = switch ($PSCmdlet.ParameterSetName) {
                'Readiness' {@('smoke')} 'RepairHelp' {@('repair','--help')}
                'CompatibilityVectors' {@('compatibility-vectors')}
                'IsolatedTest' {@('isolated-test','--suite',$TestSuite)}
                'IsolatedAlembicUpgrade' {@('isolated-alembic-upgrade')}
                'AuditEnvProbe' {@('smoke')}
                'ProductionImportTrace' {@('production-source-security-trace')}
                'NetworkForbiddenProbe' {@('network-forbidden-probe','--case',$NetworkProbeCase)}
                'RepairRelaySelfTest' {@('repair-relay-self-test','--case',$RelayCase.ToLowerInvariant())}
            }
            if ($PSCmdlet.ParameterSetName -eq 'AuditEnvProbe') {
                [System.IO.File]::WriteAllText((Join-Path $workingDirectory '.env'),'synthetic-poison=1',(New-Object System.Text.UTF8Encoding($false)))
            }
        }
        $timeout = if ($PSCmdlet.ParameterSetName -in @('IsolatedTest','IsolatedAlembicUpgrade')) { 3600000 } else { 120000 }
        $child = Invoke-IsolatedProcess $python $entrypoint $arguments $workingDirectory $environment $timeout
        if ($PSCmdlet.ParameterSetName -eq 'RepairRelaySelfTest' -and $child.stdout -and -not $child.stderr) {
            $relayPayload = ConvertFrom-BoundedJson $child.stdout
            if ([string]$relayPayload.result -notmatch '^DOCUMENT_METADATA_REPAIR_[A-Z0-9_]{1,96}$' -or $relayPayload.executed -isnot [bool]) { Stop-Launch 'DOC04B_RELAY_RESULT_INVALID' }
            $child.stdout
            exit $child.exit_code
        }
        if ($PSCmdlet.ParameterSetName -eq 'AuditEnvProbe') {
            if ($child.exit_code -eq 0 -or $child.stdout) { Stop-Launch 'DOC04B_AUDIT_GUARD_NOT_ENFORCED' }
            $failure = ConvertFrom-BoundedJson $child.stderr
            if ($failure.result -ne 'DOC04_RUNTIME_ENV_FILE_FORBIDDEN' -or [int]$failure.env_file_open_attempts -lt 1) { Stop-Launch 'DOC04B_AUDIT_GUARD_NOT_ENFORCED' }
            [ordered]@{env_file_open_attempts=[int]$failure.env_file_open_attempts;result='DOC04B_AUDIT_GUARD_PASS'} | ConvertTo-Json -Compress
            exit 0
        }
        if ($child.exit_code -ne 0) {
            if (-not $child.stdout -and $child.stderr) {
                try {
                    $failure = ConvertFrom-BoundedJson $child.stderr
                    if ([string]$failure.result -eq 'DOC04B_ISOLATED_TEST_FAILED' -and $failure.PSObject.Properties.Name -contains 'failure_methods') {
                        $methods = @($failure.failure_methods | ForEach-Object { ([string]$_).ToUpperInvariant() })
                        if ($methods.Count -le 16 -and @($methods | Where-Object { $_ -notmatch '^TEST_[A-Z0-9_]{1,120}$' }).Count -eq 0) {
                            Stop-Launch (([string]$failure.result) + '_' + ($methods -join '_'))
                        }
                    }
                    if ([string]$failure.result -match '^DOC04[A-Z0-9_]+$') { Stop-Launch ([string]$failure.result) }
                } catch {
                    if ([string]$_.Exception.Message -match '^DOC04[A-Z0-9_]+$') { throw }
                }
            }
            Stop-Launch 'DOC04B_PORTABLE_INVOCATION_FAILED'
        }
        if ($child.stderr) { Stop-Launch 'DOC04B_PORTABLE_INVOCATION_FAILED' }
        $payload = ConvertFrom-BoundedJson $child.stdout
        if ($payload.PSObject.Properties.Name -contains 'cwd_identity_sha256') {
            $expectedCwdHash = Get-StringSha256 ([System.IO.Path]::GetFullPath($workingDirectory).TrimEnd('\').ToLowerInvariant())
            if ($payload.cwd_identity_sha256 -ne $expectedCwdHash) { Stop-Launch 'DOC04B_CHILD_WORKING_DIRECTORY_MISMATCH' }
        }
        $child.stdout
        exit 0
    } finally {
        if (-not (Test-IsWithin $workingDirectory $SyntheticRoot) -or $workingDirectory -eq $SyntheticRoot) { Stop-Launch 'DOC04B_UNOWNED_SYNTHETIC_CLEANUP_REFUSED' }
        if (Test-Path -LiteralPath $workingDirectory) { Remove-Item -LiteralPath $workingDirectory -Recurse -Force }
    }
}

if ($PSCmdlet.ParameterSetName -eq 'ProductionProfilePreflightIntegration') {
    if ($SyntheticDatabasePort -eq 5432 -or -not $SyntheticDatabaseName.StartsWith('ai_lab_test_doc04b_')) { Stop-Launch 'DOC04B_ISOLATED_DATABASE_REQUIRED' }
    $QualificationRuntimeRoot = Assert-Runtime ([System.IO.Path]::GetFullPath($QualificationRuntimeRoot).TrimEnd('\')) $lock 'Qualification'
    $SyntheticRoot = Assert-SyntheticRoot $SyntheticRoot $RepoRoot @($RuntimeRoot,$QualificationRuntimeRoot) $lock.path_policies.nonproduction_working
    $EnvironmentRoot = [System.IO.Path]::GetFullPath($EnvironmentRoot).TrimEnd('\')
    if (-not $EnvironmentRoot.Equals($RepoRoot,[System.StringComparison]::OrdinalIgnoreCase)) { Stop-Launch 'DOC04B_INTEGRATION_SAME_ROOT_REQUIRED' }
    $integrationRoot = Join-Path $SyntheticRoot ('production-profile-' + [Guid]::NewGuid().ToString('N'))
    [System.IO.Directory]::CreateDirectory($integrationRoot) | Out-Null
    $dataRoot = Join-Path $EnvironmentRoot 'data'
    $backupRoot = Join-Path $integrationRoot 'backup'
    if(-not(Test-Path -LiteralPath $dataRoot)){[System.IO.Directory]::CreateDirectory($dataRoot) | Out-Null}
    [System.IO.Directory]::CreateDirectory($backupRoot) | Out-Null
    $EnvironmentRoot = Assert-ProductionConfigurationRoot $EnvironmentRoot $dataRoot $lock.path_policies
    $dataRoot = Assert-ProductionDataRoot $EnvironmentRoot $dataRoot $lock
    $productionEnvFile = Join-Path $EnvironmentRoot '.env'
    $environmentHandle = $null
    $fixturePrepared = $false
    $qualificationEnvironment = $null
    try {
        $qualificationForbidden = @($RepoRoot,(Join-Path $RepoRoot 'data'),'C:\ai-lab-core-backups','E:\','F:\',$RuntimeRoot,$QualificationRuntimeRoot,$backupRoot) + @($lock.path_policies.nonproduction_working.forbidden_roots)
        $qualificationEnvironment = New-MinimalEnvironment $QualificationRuntimeRoot $gitExe $integrationRoot 'production-profile-preflight-fixture' $qualificationForbidden 'Qualification' '' '' '127.0.0.1' $SyntheticDatabasePort
        Add-SyntheticApplicationEnvironment $qualificationEnvironment $integrationRoot $SyntheticDatabaseName $SyntheticDatabasePort $SyntheticDatabasePassword
        $qualificationEnvironment['DATA_DIR'] = $dataRoot
        $qualificationEnvironment['NEXT_DOC04_DATA_ROOT'] = $dataRoot
        $qualificationEnvironment['NEXT_DOC04_PRODUCTION_ENVIRONMENT_ROOT'] = $EnvironmentRoot
        $qualificationEnvironment['NEXT_DOC04_SYNTHETIC_BACKUP_ROOT'] = $backupRoot
        $fixtureChild = Invoke-IsolatedProcess (Join-Path $QualificationRuntimeRoot 'python.exe') $entrypoint @('production-profile-preflight-fixture','--phase','prepare') $integrationRoot $qualificationEnvironment 3600000
        if ($fixtureChild.exit_code -ne 0 -or $fixtureChild.stderr) { Stop-Launch 'DOC04B_PRODUCTION_PROFILE_FIXTURE_FAILED' }
        $fixture = ConvertFrom-BoundedJson $fixtureChild.stdout
        if ($fixture.result -ne 'DOC04B_PRODUCTION_PROFILE_FIXTURE_READY') { Stop-Launch 'DOC04B_PRODUCTION_PROFILE_FIXTURE_FAILED' }
        $fixturePrepared = $true

        $environmentHandle = Open-VerifiedEnvironmentFile $productionEnvFile $ExpectedEnvironmentFileSha256
        $productionForbidden = @($dataRoot,$backupRoot) + @($lock.path_policies.production_working_forbidden_roots)
        $productionEnvironment = New-MinimalEnvironment $RuntimeRoot $gitExe $EnvironmentRoot 'production-profile-preflight-integration' $productionForbidden 'Production' $productionEnvFile $ExpectedEnvironmentFileSha256 '127.0.0.1' $SyntheticDatabasePort
        Add-SyntheticApplicationEnvironment $productionEnvironment $EnvironmentRoot $SyntheticDatabaseName $SyntheticDatabasePort $SyntheticDatabasePassword
        $productionEnvironment['DATA_DIR'] = $dataRoot
        $productionEnvironment['NEXT_DOC04_DATA_ROOT'] = $dataRoot
        $repairArgs = @(
            'repair','--preflight-production','--expected-database',$SyntheticDatabaseName,
            '--expected-git-sha',$ExpectedGitSha,'--expected-alembic-head',[string]$fixture.expected_alembic_head,
            '--expected-xmin',[string]$fixture.expected_xmin,'--expected-updated-at',(ConvertTo-IsoTimestampArgument $fixture.expected_updated_at),
            '--expected-storage-sha256',[string]$fixture.expected_storage_sha256,
            '--verified-backup-run-id',[string]$fixture.verified_backup_run_id,
            '--verified-backup-manifest-sha256',[string]$fixture.verified_backup_manifest_sha256,
            '--expected-backup-finished-at',(ConvertTo-IsoTimestampArgument $fixture.expected_backup_finished_at),
            '--maximum-backup-age-seconds','3600',
            '--expected-backup-destination-root-sha256',[string]$fixture.expected_backup_destination_root_sha256,
            '--expected-raw-before-sha256',[string]$fixture.expected_raw_before_sha256,
            '--expected-raw-candidate-sha256',[string]$fixture.expected_raw_candidate_sha256,
            '--expected-normalized-before-sha256',[string]$fixture.expected_normalized_before_sha256,
            '--expected-normalized-candidate-sha256',[string]$fixture.expected_normalized_candidate_sha256
        )
        if ($IntegrationCase -eq 'WrongBeforeHash') { $repairArgs[[array]::IndexOf($repairArgs,'--expected-raw-before-sha256') + 1] = ('0' * 64) }
        $productionChild = Invoke-IsolatedProcess $python $entrypoint $repairArgs $EnvironmentRoot $productionEnvironment 3600000
        if ((Get-StreamSha256 $environmentHandle) -cne $ExpectedEnvironmentFileSha256) { Stop-Launch 'DOC04B_PRODUCTION_ENV_CHANGED' }
        $environmentHandle.Dispose(); $environmentHandle = $null

        $verifyChild = Invoke-IsolatedProcess (Join-Path $QualificationRuntimeRoot 'python.exe') $entrypoint @('production-profile-preflight-fixture','--phase','verify') $integrationRoot $qualificationEnvironment 3600000
        if ($verifyChild.exit_code -ne 0 -or $verifyChild.stderr) { Stop-Launch 'DOC04B_PRODUCTION_PROFILE_FIXTURE_VERIFY_FAILED' }
        $verifiedFixture = ConvertFrom-BoundedJson $verifyChild.stdout
        if ($verifiedFixture.result -ne 'DOC04B_PRODUCTION_PROFILE_FIXTURE_UNCHANGED' -or $verifiedFixture.state_sha256 -ne $fixture.state_sha256) { Stop-Launch 'DOC04B_PRODUCTION_PROFILE_FIXTURE_CHANGED' }
        $cleanupChild = Invoke-IsolatedProcess (Join-Path $QualificationRuntimeRoot 'python.exe') $entrypoint @('production-profile-preflight-fixture','--phase','cleanup') $integrationRoot $qualificationEnvironment 3600000
        if ($cleanupChild.exit_code -ne 0 -or $cleanupChild.stderr -or (ConvertFrom-BoundedJson $cleanupChild.stdout).result -ne 'DOC04B_PRODUCTION_PROFILE_FIXTURE_CLEANED') { Stop-Launch 'DOC04B_PRODUCTION_PROFILE_FIXTURE_CLEANUP_FAILED' }
        $fixturePrepared = $false
        if ($productionChild.stderr -or -not $productionChild.stdout) { Stop-Launch 'DOC04B_PRODUCTION_INVOCATION_FAILED' }
        $payload = ConvertFrom-BoundedJson $productionChild.stdout
        if ([string]$payload.result -notmatch '^DOCUMENT_METADATA_REPAIR_[A-Z0-9_]{1,96}$' -or $payload.executed -isnot [bool]) { Stop-Launch 'DOC04B_PRODUCTION_RESULT_INVALID' }
        if ($IntegrationCase -eq 'Success' -and ($productionChild.exit_code -ne 0 -or $payload.result -ne 'DOCUMENT_METADATA_REPAIR_PRODUCTION_PREFLIGHT_OK' -or $payload.executed -or -not $payload.production_preflight)) { Stop-Launch 'DOC04B_PRODUCTION_PROFILE_PREFLIGHT_FAILED' }
        if ($IntegrationCase -eq 'WrongBeforeHash' -and ($productionChild.exit_code -eq 0 -or $payload.result -ne 'DOCUMENT_METADATA_REPAIR_BEFORE_HASH' -or $payload.executed)) { Stop-Launch 'DOC04B_PRODUCTION_PROFILE_REFUSAL_FAILED' }
        $productionChild.stdout
        exit $productionChild.exit_code
    } finally {
        if ($environmentHandle) { $environmentHandle.Dispose() }
        if ($fixturePrepared -and $qualificationEnvironment) {
            try { [void](Invoke-IsolatedProcess (Join-Path $QualificationRuntimeRoot 'python.exe') $entrypoint @('production-profile-preflight-fixture','--phase','cleanup') $integrationRoot $qualificationEnvironment 3600000) } catch { }
        }
        if (Test-Path -LiteralPath $integrationRoot) { Remove-Item -LiteralPath $integrationRoot -Recurse -Force }
    }
}

if (-not $AllowProductionAiLab -or [string]::IsNullOrWhiteSpace($OwnerApprovalId)) { Stop-Launch 'DOC04B_PRODUCTION_OWNER_GATE_REQUIRED' }
$EnvironmentRoot = [System.IO.Path]::GetFullPath($EnvironmentRoot).TrimEnd('\')
$DataRoot = [System.IO.Path]::GetFullPath($DataRoot).TrimEnd('\')
Assert-NonReparseDirectory $DataRoot 'DOC04B_PRODUCTION_DATA_ROOT_INVALID'
$EnvironmentRoot = Assert-ProductionConfigurationRoot $EnvironmentRoot $DataRoot $lock.path_policies
$DataRoot = Assert-ProductionDataRoot $EnvironmentRoot $DataRoot $lock
$productionEnvFile = Join-Path $EnvironmentRoot '.env'
$expectedEnvIdentity = [System.IO.Path]::GetFullPath($productionEnvFile)
if ((Invoke-Git @('-C',$RepoRoot,'branch','--show-current')) -ne 'main' -or (Invoke-Git @('-C',$RepoRoot,'rev-parse','origin/main')) -ne $ExpectedGitSha) { Stop-Launch 'DOC04B_PRODUCTION_MAIN_IDENTITY_REQUIRED' }
$repairArgs = @(
    'repair','--allow-production-ai-lab','--owner-approval-id',$OwnerApprovalId,
    '--expected-database','ai_lab','--expected-git-sha',$ExpectedGitSha,
    '--expected-alembic-head',$ExpectedAlembicHead,'--expected-xmin',$ExpectedXmin,
    '--expected-updated-at',$ExpectedUpdatedAt,'--expected-storage-sha256',$ExpectedStorageSha256,
    '--verified-backup-run-id',[string]$VerifiedBackupRunId,
    '--verified-backup-manifest-sha256',$VerifiedBackupManifestSha256,
    '--expected-backup-finished-at',$ExpectedBackupFinishedAt,
    '--maximum-backup-age-seconds',[string]$MaximumBackupAgeSeconds,
    '--expected-backup-destination-root-sha256',$ExpectedBackupDestinationRootSha256,
    '--expected-raw-before-sha256',$ExpectedRawBeforeSha256,
    '--expected-raw-candidate-sha256',$ExpectedRawCandidateSha256,
    '--expected-normalized-before-sha256',$ExpectedNormalizedBeforeSha256,
    '--expected-normalized-candidate-sha256',$ExpectedNormalizedCandidateSha256
)
$policy = if ($PSCmdlet.ParameterSetName -eq 'ProductionPreflight') { 'production-preflight' } elseif ($PSCmdlet.ParameterSetName -eq 'ExecuteProduction') { 'production-execute' } else { Stop-Launch 'DOC04B_PARAMETER_SET_INVALID' }
if ($policy -eq 'production-preflight') { $repairArgs += '--preflight-production' }
if ($policy -eq 'production-execute') {
    if (-not $IUnderstandThisWritesProduction -or $ConfirmationPhrase -cne 'DOC04_PRODUCTION_WRITE_APPROVED') { Stop-Launch 'DOC04B_PRODUCTION_WRITE_CONFIRMATION_REQUIRED' }
    $repairArgs += '--execute'
}
$forbiddenRoots = @($DataRoot) + @($lock.path_policies.production_working_forbidden_roots)
$productionEnvironment = New-MinimalEnvironment $RuntimeRoot $gitExe $EnvironmentRoot $policy $forbiddenRoots 'Production' $expectedEnvIdentity $ExpectedEnvironmentFileSha256 '127.0.0.1' 5432
$productionEnvironment['ENVIRONMENT']='production';$productionEnvironment['POSTGRES_DB']='ai_lab';$productionEnvironment['POSTGRES_HOST']='127.0.0.1';$productionEnvironment['POSTGRES_PORT']='5432';$productionEnvironment['DATA_DIR']=$DataRoot
$productionEnvironment['NEXT_DOC04_DATA_ROOT']=$DataRoot
$environmentHandle = Open-VerifiedEnvironmentFile $productionEnvFile $ExpectedEnvironmentFileSha256
try {
    $child = Invoke-IsolatedProcess $python $entrypoint $repairArgs $EnvironmentRoot $productionEnvironment 3600000
    if ((Get-StreamSha256 $environmentHandle) -cne $ExpectedEnvironmentFileSha256) { Stop-Launch 'DOC04B_PRODUCTION_ENV_CHANGED' }
} finally { $environmentHandle.Dispose() }
if ($child.stderr) { Stop-Launch 'DOC04B_PRODUCTION_INVOCATION_FAILED' }
$productionPayload = ConvertFrom-BoundedJson $child.stdout
if ([string]$productionPayload.result -notmatch '^DOCUMENT_METADATA_REPAIR_[A-Z0-9_]{1,96}$' -or $productionPayload.executed -isnot [bool]) { Stop-Launch 'DOC04B_PRODUCTION_RESULT_INVALID' }
$child.stdout
exit $child.exit_code
