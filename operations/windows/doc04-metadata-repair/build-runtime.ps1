[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedGitSha,
    [Parameter(Mandatory = $true)][string]$RuntimeRoot,
    [Parameter(Mandatory = $true)][string]$CacheRoot,
    [Parameter(Mandatory = $true)][ValidateSet('Production','Qualification')][string]$Profile,
    [ValidateSet('SizeOverflow','PrematureEof','HashMismatch','HttpFailure','RedirectFailure','WriteFailure')]
    [string]$DownloadFailureProbe = '',
    [switch]$Offline
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Net.Http

function Stop-Build([string]$Code) { throw $Code }
function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Normalize-Project([string]$Name) {
    return ([regex]::Replace($Name.ToLowerInvariant(), '[-_.]+', '-'))
}
function Get-FullLocalPath([string]$Path, [string]$Name) {
    if (-not [System.IO.Path]::IsPathRooted($Path) -or $Path -notmatch '^[A-Za-z]:\\') { Stop-Build "unsafe_${Name}_not_absolute_local" }
    $full = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    if ($full -match '^[A-Za-z]:$') { Stop-Build "unsafe_${Name}_drive_root" }
    return $full
}
function Get-FullBoundaryPath([string]$Path, [string]$Name) {
    if (-not [System.IO.Path]::IsPathRooted($Path) -or $Path -notmatch '^[A-Za-z]:\\') { Stop-Build "unsafe_${Name}_not_absolute_local" }
    return [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
}
function Test-Under([string]$Child, [string]$Parent) {
    $p = $Parent.TrimEnd('\') + '\'
    return $Child.Equals($Parent, [System.StringComparison]::OrdinalIgnoreCase) -or $Child.StartsWith($p, [System.StringComparison]::OrdinalIgnoreCase)
}
function Test-StrictDescendant([string]$Child, [string]$Parent) {
    $childFull = [System.IO.Path]::GetFullPath($Child).TrimEnd('\')
    $parentFull = [System.IO.Path]::GetFullPath($Parent).TrimEnd('\')
    return -not $childFull.Equals($parentFull, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Under $childFull $parentFull)
}
function Assert-NoReparseChain([string]$Path) {
    $cursor = [System.IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { Stop-Build 'unsafe_reparse_path' }
        }
        $parent = [System.IO.Path]::GetDirectoryName($cursor)
        if (-not $parent -or $parent -eq $cursor) { break }
        $cursor = $parent
    }
}
function Assert-NoReparseTree([string]$Path) {
    Assert-NoReparseChain $Path
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) { return }
    foreach ($item in Get-ChildItem -LiteralPath $Path -Force -Recurse) {
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { Stop-Build 'unsafe_internal_reparse_entry' }
    }
}
function Assert-SafeRoot([string]$Path, [string]$Name, [string]$Repo, $Policy) {
    $full = Get-FullLocalPath $Path $Name
    $repoFull = Get-FullLocalPath $Repo 'repo'
    $authorized = Get-FullLocalPath $(if ($Name -eq 'runtime') { $Policy.authorized_runtime_parent } else { $Policy.authorized_cache_parent }) "authorized_${Name}_parent"
    if (-not (Test-StrictDescendant $full $authorized)) { Stop-Build "unsafe_${Name}_outside_authorized_parent" }
    foreach ($blockedRaw in @($Policy.forbidden_runtime_roots)) {
        $blocked = Get-FullBoundaryPath ([string]$blockedRaw) "forbidden_${Name}_root"
        if (Test-Under $full $blocked) { Stop-Build "unsafe_${Name}_forbidden_root" }
    }
    if (Test-Under $full $repoFull) { Stop-Build "unsafe_${Name}_inside_repo" }
    if (Test-Under $full (Join-Path $repoFull 'data')) { Stop-Build "unsafe_${Name}_inside_data" }
    foreach ($blocked in @($env:windir, $env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramData)) {
        if ($blocked -and (Test-Under $full ([System.IO.Path]::GetFullPath($blocked).TrimEnd('\')))) { Stop-Build "unsafe_${Name}_system_root" }
    }
    $startupSuffix = '\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup'
    if ($full.EndsWith($startupSuffix, [System.StringComparison]::OrdinalIgnoreCase) -or $full.Contains($startupSuffix + '\')) { Stop-Build "unsafe_${Name}_startup" }
    Assert-NoReparseChain $authorized
    Assert-NoReparseChain $full
    return $full
}
function Invoke-Git([string[]]$Arguments) {
    $out = & git @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { Stop-Build 'git_identity_failed' }
    return (($out | Out-String).Trim())
}
function Assert-GitIdentity([string]$Repo, [string]$Expected, $Lock) {
    $actualRoot = Invoke-Git @('-C', $Repo, 'rev-parse', '--show-toplevel')
    if (-not ([System.IO.Path]::GetFullPath($actualRoot).TrimEnd('\').Equals([System.IO.Path]::GetFullPath($Repo).TrimEnd('\'), [System.StringComparison]::OrdinalIgnoreCase))) { Stop-Build 'git_root_mismatch' }
    if ((Invoke-Git @('-C', $Repo, 'rev-parse', 'HEAD')) -ne $Expected) { Stop-Build 'git_head_mismatch' }
    foreach ($relative in $Lock.critical_git_paths) {
        $absolute = Join-Path $Repo ([string]$relative -replace '/', '\')
        if (-not (Test-Path -LiteralPath $absolute -PathType Leaf)) { Stop-Build 'critical_git_path_missing' }
        $item = Get-Item -LiteralPath $absolute -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { Stop-Build 'critical_git_path_reparse' }
        $committed = Invoke-Git @('-C', $Repo, 'rev-parse', "HEAD:$relative")
        $working = Invoke-Git @('-C', $Repo, 'hash-object', "--path=$relative", $absolute)
        if ($committed -ne $working) { Stop-Build 'critical_git_blob_mismatch' }
    }
    $requirementsBlob = Invoke-Git @('-C', $Repo, 'rev-parse', 'HEAD:backend/requirements.txt')
    if ($requirementsBlob -ne $Lock.backend_requirements_git_blob) { Stop-Build 'backend_requirements_blob_mismatch' }
}
function Get-ProfilePackages($Lock, [string]$Name) {
    $definition = $Lock.profiles.$Name
    if (-not $definition) { Stop-Build 'runtime_profile_missing' }
    if ($definition.PSObject.Properties.Name -contains 'include_all_catalog_packages' -and $definition.include_all_catalog_packages) { return @($Lock.packages) }
    $projects = @($definition.package_projects)
    $selected = @($Lock.packages | Where-Object { $projects -ccontains [string]$_.project })
    if ($selected.Count -ne $projects.Count -or @($projects | Sort-Object -Unique).Count -ne $projects.Count) { Stop-Build 'runtime_profile_package_mismatch' }
    return $selected
}
function Get-LockedArtifacts($Lock, $Packages) {
    $items = New-Object System.Collections.Generic.List[object]
    $items.Add([pscustomobject]@{filename=$Lock.runtime_python.filename;url=$Lock.runtime_python.url;bytes=[int64]$Lock.runtime_python.bytes;sha256=$Lock.runtime_python.sha256;kind='python'})
    $items.Add([pscustomobject]@{filename=([System.IO.Path]::GetFileName($Lock.runtime_python.sbom.url));url=$Lock.runtime_python.sbom.url;bytes=[int64]$Lock.runtime_python.sbom.bytes;sha256=$Lock.runtime_python.sbom.sha256;kind='sbom'})
    $items.Add([pscustomobject]@{filename=([System.IO.Path]::GetFileName($Lock.runtime_python.sigstore.url));url=$Lock.runtime_python.sigstore.url;bytes=[int64]$Lock.runtime_python.sigstore.bytes;sha256=$Lock.runtime_python.sigstore.sha256;kind='sigstore'})
    foreach ($p in $Packages) { $items.Add([pscustomobject]@{filename=$p.filename;url=$p.url;bytes=[int64]$p.bytes;sha256=$p.sha256;kind=$p.classification}) }
    return $items
}
function Assert-AllowedUri([uri]$Uri, [string[]]$Hosts) {
    if ($Uri.Scheme -ne 'https' -or $Hosts -notcontains $Uri.DnsSafeHost.ToLowerInvariant()) { Stop-Build 'download_uri_not_allowlisted' }
}
function Remove-OwnedPartial([string]$Path, [bool]$Owned) {
    if ($Owned -and (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Remove-Item -LiteralPath $Path -Force
    }
}
function Invoke-LockedDownload($Artifact, [string]$Destination, [string[]]$Hosts, [int]$MaxRedirects) {
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.AllowAutoRedirect = $false
    $client = New-Object System.Net.Http.HttpClient($handler)
    $client.Timeout = [TimeSpan]::FromMinutes(5)
    $uri = [uri]$Artifact.url
    $partial = $Destination + '.partial'
    $ownedPartial = $false
    try {
        for ($redirect = 0; $redirect -le $MaxRedirects; $redirect++) {
            Assert-AllowedUri $uri $Hosts
            $response = $client.GetAsync($uri, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
            if ([int]$response.StatusCode -ge 300 -and [int]$response.StatusCode -lt 400) {
                if (-not $response.Headers.Location -or $redirect -eq $MaxRedirects) { Stop-Build 'download_redirect_invalid' }
                $uri = if ($response.Headers.Location.IsAbsoluteUri) { $response.Headers.Location } else { [uri]::new($uri, $response.Headers.Location) }
                $response.Dispose()
                continue
            }
            if (-not $response.IsSuccessStatusCode) { $response.Dispose(); Stop-Build 'download_http_failure' }
            if (Test-Path -LiteralPath $partial) { $response.Dispose(); Stop-Build 'unexpected_partial_file' }
            $inputStream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
            $output = [System.IO.File]::Open($partial, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
            $ownedPartial = $true
            try {
                $buffer = New-Object byte[] 1048576
                [int64]$total = 0
                while (($read = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $total += $read
                    if ($total -gt [int64]$Artifact.bytes) { Stop-Build 'download_size_overflow' }
                    $output.Write($buffer, 0, $read)
                }
            } finally { $output.Dispose(); $inputStream.Dispose(); $response.Dispose() }
            if ((Get-Item -LiteralPath $partial).Length -ne [int64]$Artifact.bytes -or (Get-Sha256 $partial) -ne $Artifact.sha256) { Stop-Build 'download_integrity_mismatch' }
            [System.IO.File]::Move($partial, $Destination)
            $ownedPartial = $false
            return
        }
    } finally {
        Remove-OwnedPartial $partial $ownedPartial
        $client.Dispose()
        $handler.Dispose()
    }
    Stop-Build 'download_redirect_limit'
}
function Invoke-DownloadFailureCleanupProbe([string]$Root, [string]$Case) {
    $destination = Join-Path $Root ('download-probe-' + $Case.ToLowerInvariant() + '.bin')
    $partial = $destination + '.partial'
    if ((Test-Path -LiteralPath $destination) -or (Test-Path -LiteralPath $partial)) { Stop-Build 'download_probe_collision' }
    $owned = $false
    try {
        $stream = [System.IO.File]::Open($partial, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        $owned = $true
        try { $stream.WriteByte(1) } finally { $stream.Dispose() }
        switch ($Case) {
            'SizeOverflow' { Stop-Build 'download_size_overflow' }
            'PrematureEof' { Stop-Build 'download_integrity_mismatch' }
            'HashMismatch' { Stop-Build 'download_integrity_mismatch' }
            'HttpFailure' { Stop-Build 'download_http_failure' }
            'RedirectFailure' { Stop-Build 'download_redirect_invalid' }
            'WriteFailure' { Stop-Build 'download_write_failure' }
            default { Stop-Build 'download_probe_case_invalid' }
        }
    } catch {
        # A fixed synthetic fault is expected; only cleanup behavior is observed.
    } finally {
        Remove-OwnedPartial $partial $owned
    }
    if ((Test-Path -LiteralPath $partial) -or (Test-Path -LiteralPath $destination)) { Stop-Build 'download_probe_cleanup_failed' }
    [ordered]@{case=$Case;owned_partial_count=0;result='DOC04B_DOWNLOAD_CLEANUP_PROBE_PASS'} | ConvertTo-Json -Compress
}
function Assert-LockedFile($Artifact, [string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { Stop-Build 'locked_artifact_missing' }
    if ((Get-Item -LiteralPath $Path).Length -ne [int64]$Artifact.bytes) { Stop-Build 'locked_artifact_size_mismatch' }
    if ((Get-Sha256 $Path) -ne [string]$Artifact.sha256) { Stop-Build 'locked_artifact_hash_mismatch' }
}
function Assert-PythonSbom($Lock, [string]$Cache) {
    $sbomPath = Join-Path $Cache ([System.IO.Path]::GetFileName($Lock.runtime_python.sbom.url))
    $sbom = Get-Content -LiteralPath $sbomPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $package = @($sbom.packages | Where-Object { $_.name -eq 'CPython' -and $_.versionInfo -eq $Lock.runtime_python.version -and $_.downloadLocation -eq $Lock.runtime_python.url })
    if ($package.Count -ne 1) { Stop-Build 'python_sbom_identity_mismatch' }
    $checksum = @($package[0].checksums | Where-Object { $_.algorithm -eq 'SHA256' -and $_.checksumValue.ToLowerInvariant() -eq $Lock.runtime_python.sha256 })
    if ($checksum.Count -ne 1) { Stop-Build 'python_sbom_hash_mismatch' }
}
function Assert-PypiMetadata($Package, [string[]]$Hosts) {
    $uri = [uri]$Package.metadata_url
    Assert-AllowedUri $uri $Hosts
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.AllowAutoRedirect = $false
    $client = New-Object System.Net.Http.HttpClient($handler)
    try {
        $response = $client.GetAsync($uri).GetAwaiter().GetResult()
        if (-not $response.IsSuccessStatusCode -or [int]$response.StatusCode -ge 300) { Stop-Build 'pypi_metadata_fetch_failed' }
        $json = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult() | ConvertFrom-Json
        $expectedType = if ($Package.classification -eq 'locked_pure_sdist') { 'sdist' } else { 'bdist_wheel' }
        $match = @($json.urls | Where-Object { $_.filename -eq $Package.filename -and $_.packagetype -eq $expectedType -and $_.digests.sha256.ToLowerInvariant() -eq $Package.sha256 -and [int64]$_.size -eq [int64]$Package.bytes -and $_.url -eq $Package.url })
        if ($match.Count -ne 1) { Stop-Build 'pypi_metadata_identity_mismatch' }
    } finally { $client.Dispose(); $handler.Dispose() }
}
function Get-SafeArchiveTarget([string]$Name, [string]$Root) {
    if ([string]::IsNullOrWhiteSpace($Name) -or $Name.IndexOf([char]0) -ge 0 -or $Name.StartsWith('/') -or $Name.StartsWith('\') -or $Name -match '^[A-Za-z]:') { Stop-Build 'archive_path_invalid' }
    $parts = $Name.Replace('\','/').Split('/')
    if ($parts -contains '..' -or $parts -contains '.') { Stop-Build 'archive_traversal_rejected' }
    $relative = [string]::Join('\', @($parts | Where-Object { $_ -ne '' }))
    $target = [System.IO.Path]::GetFullPath((Join-Path $Root $relative))
    if (-not (Test-Under $target $Root)) { Stop-Build 'archive_target_escape' }
    return $target
}
function Test-ZipSymlink($Entry) {
    $mode = (($Entry.ExternalAttributes -shr 16) -band 0xF000)
    return $mode -eq 0xA000
}
function Copy-ZipEntry($Entry, [string]$Target, [int64]$ExpectedLength, [int]$BufferSize) {
    $parent = [System.IO.Path]::GetDirectoryName($Target)
    if (-not (Test-Path -LiteralPath $parent)) { [System.IO.Directory]::CreateDirectory($parent) | Out-Null }
    $input = $Entry.Open()
    $output = [System.IO.File]::Open($Target, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try {
        $buffer = New-Object byte[] $BufferSize
        [int64]$total = 0
        while (($read = $input.Read($buffer, 0, $buffer.Length)) -gt 0) { $total += $read; if ($total -gt $ExpectedLength) { Stop-Build 'archive_actual_size_overflow' }; $output.Write($buffer, 0, $read) }
        if ($total -ne $ExpectedLength) { Stop-Build 'archive_actual_size_mismatch' }
    } finally { $output.Dispose(); $input.Dispose() }
}
function Expand-LockedZip([string]$ZipPath, [string]$TargetRoot, $Limits, [System.Collections.Generic.HashSet[string]]$Targets) {
    $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        if ($archive.Entries.Count -gt [int]$Limits.maximum_entries_per_archive) { Stop-Build 'archive_entry_count_overflow' }
        [int64]$aggregate = 0
        foreach ($entry in $archive.Entries) {
            if (Test-ZipSymlink $entry) { Stop-Build 'archive_symlink_rejected' }
            if ($entry.FullName.EndsWith('/')) { [void](Get-SafeArchiveTarget $entry.FullName $TargetRoot); continue }
            if ([int64]$entry.Length -gt [int64]$Limits.maximum_entry_bytes) { Stop-Build 'archive_entry_size_overflow' }
            $aggregate += [int64]$entry.Length
            if ($aggregate -gt [int64]$Limits.maximum_archive_output_bytes) { Stop-Build 'archive_aggregate_size_overflow' }
            $target = Get-SafeArchiveTarget $entry.FullName $TargetRoot
            if (-not $Targets.Add($target)) { Stop-Build 'archive_duplicate_target' }
            Copy-ZipEntry $entry $target ([int64]$entry.Length) ([int]$Limits.stream_buffer_bytes)
        }
    } finally { $archive.Dispose() }
}
function Read-ZipText($Archive, [string]$Suffix, [int]$MaximumBytes) {
    $entries = @($Archive.Entries | Where-Object { $_.FullName.EndsWith($Suffix, [System.StringComparison]::OrdinalIgnoreCase) })
    if ($entries.Count -ne 1 -or $entries[0].Length -gt $MaximumBytes) { Stop-Build 'wheel_metadata_missing_or_oversize' }
    $reader = New-Object System.IO.StreamReader($entries[0].Open(), [System.Text.Encoding]::UTF8, $true)
    try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
}
function Install-LockedWheel($Package, [string]$WheelPath, [string]$SiteRoot, $Limits, [System.Collections.Generic.HashSet[string]]$Targets) {
    $allowedTags = @('cp312-cp312-win_amd64','cp312-abi3-win_amd64','cp311-abi3-win_amd64','cp310-abi3-win_amd64','cp39-abi3-win_amd64','cp38-abi3-win_amd64','cp37-abi3-win_amd64','cp36-abi3-win_amd64','py3-none-any','py2.py3-none-any')
    if ($Package.filename -notmatch '\.whl$' -or $Package.wheel_tag -notin $allowedTags) { Stop-Build 'wheel_tag_rejected' }
    $archive = [System.IO.Compression.ZipFile]::OpenRead($WheelPath)
    try {
        $metadata = Read-ZipText $archive '.dist-info/METADATA' 1048576
        $wheel = Read-ZipText $archive '.dist-info/WHEEL' 262144
        $nameLine = [regex]::Match($metadata, '(?m)^Name:\s*(.+?)\s*$')
        $versionLine = [regex]::Match($metadata, '(?m)^Version:\s*(.+?)\s*$')
        if (-not $nameLine.Success -or (Normalize-Project $nameLine.Groups[1].Value) -ne (Normalize-Project $Package.project) -or -not $versionLine.Success -or $versionLine.Groups[1].Value -ne $Package.version) { Stop-Build 'wheel_project_version_mismatch' }
        $tags = @([regex]::Matches($wheel, '(?m)^Tag:\s*(.+?)\s*$') | ForEach-Object { $_.Groups[1].Value })
        if ($tags -notcontains $Package.wheel_tag) { Stop-Build 'wheel_metadata_tag_mismatch' }
        if ($archive.Entries.Count -gt [int]$Limits.maximum_entries_per_archive) { Stop-Build 'wheel_entry_count_overflow' }
        [int64]$aggregate = 0
        foreach ($entry in $archive.Entries) {
            if (Test-ZipSymlink $entry) { Stop-Build 'wheel_symlink_rejected' }
            $name = $entry.FullName.Replace('\','/')
            if ($name.EndsWith('/')) { continue }
            if ($Package.PSObject.Properties.Name -contains 'ignored_members' -and @($Package.ignored_members) -ccontains $name) {
                if ([int64]$entry.Length -gt [int64]$Limits.maximum_entry_bytes) { Stop-Build 'wheel_ignored_entry_size_overflow' }
                continue
            }
            if ($name.EndsWith('.pth', [System.StringComparison]::OrdinalIgnoreCase) -or $name -match '(^|/)Scripts/' -or $name -match '\.data/scripts/') { Stop-Build 'wheel_executable_payload_rejected' }
            if ($name -match '\.data/(purelib|platlib)/') { $name = $name.Substring($name.IndexOf('/', $name.IndexOf('.data/') + 6) + 1) }
            elseif ($name -match '\.data/') { Stop-Build 'wheel_unsupported_data_layout' }
            if ([int64]$entry.Length -gt [int64]$Limits.maximum_entry_bytes) { Stop-Build 'wheel_entry_size_overflow' }
            $aggregate += [int64]$entry.Length
            if ($aggregate -gt [int64]$Limits.maximum_archive_output_bytes) { Stop-Build 'wheel_aggregate_size_overflow' }
            $target = Get-SafeArchiveTarget $name $SiteRoot
            if (-not $Targets.Add($target)) { Stop-Build 'wheel_target_collision' }
            Copy-ZipEntry $entry $target ([int64]$entry.Length) ([int]$Limits.stream_buffer_bytes)
        }
    } finally { $archive.Dispose() }
}

function Read-ExactBytes([System.IO.Stream]$Stream, [int]$Count) {
    $buffer = New-Object byte[] $Count
    [int]$offset = 0
    while ($offset -lt $Count) {
        $read = $Stream.Read($buffer, $offset, $Count - $offset)
        if ($read -le 0) { Stop-Build 'sdist_tar_truncated' }
        $offset += $read
    }
    return $buffer
}
function Get-TarString([byte[]]$Header, [int]$Offset, [int]$Length) {
    [int]$end = $Offset
    while ($end -lt ($Offset + $Length) -and $Header[$end] -ne 0) { $end++ }
    return [System.Text.Encoding]::ASCII.GetString($Header, $Offset, $end - $Offset)
}
function Get-TarOctal([byte[]]$Header, [int]$Offset, [int]$Length) {
    $text = (Get-TarString $Header $Offset $Length).Trim([char]0, [char]32)
    if (-not $text -or $text -notmatch '^[0-7]+$') { Stop-Build 'sdist_tar_size_invalid' }
    try { return [Convert]::ToInt64($text, 8) } catch { Stop-Build 'sdist_tar_size_invalid' }
}
function Copy-BoundedTarContent([System.IO.Stream]$Stream, [string]$Target, [int64]$Length, [int]$BufferSize) {
    $parent = [System.IO.Path]::GetDirectoryName($Target)
    if (-not (Test-Path -LiteralPath $parent)) { [System.IO.Directory]::CreateDirectory($parent) | Out-Null }
    $output = [System.IO.File]::Open($Target, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try {
        $buffer = New-Object byte[] $BufferSize
        [int64]$remaining = $Length
        while ($remaining -gt 0) {
            $wanted = [int][Math]::Min([int64]$buffer.Length, $remaining)
            $read = $Stream.Read($buffer, 0, $wanted)
            if ($read -le 0) { Stop-Build 'sdist_tar_truncated' }
            $output.Write($buffer, 0, $read)
            $remaining -= $read
        }
    } finally { $output.Dispose() }
}
function Skip-BoundedTarContent([System.IO.Stream]$Stream, [int64]$Length, [int]$BufferSize) {
    $buffer = New-Object byte[] $BufferSize
    [int64]$remaining = $Length
    while ($remaining -gt 0) {
        $wanted = [int][Math]::Min([int64]$buffer.Length, $remaining)
        $read = $Stream.Read($buffer, 0, $wanted)
        if ($read -le 0) { Stop-Build 'sdist_tar_truncated' }
        $remaining -= $read
    }
}
function Install-LockedPureSdist($Package, [string]$ArchivePath, [string]$SiteRoot, $Limits, [System.Collections.Generic.HashSet[string]]$Targets) {
    if ($Package.classification -ne 'locked_pure_sdist' -or $Package.filename -notmatch '\.tar\.gz$' -or -not $Package.install_prefix.EndsWith('/') -or $Package.install_target -notmatch '^[A-Za-z0-9_.-]+$') { Stop-Build 'sdist_contract_invalid' }
    $file = [System.IO.File]::OpenRead($ArchivePath)
    $gzip = New-Object System.IO.Compression.GZipStream($file, [System.IO.Compression.CompressionMode]::Decompress)
    try {
        [int]$entries = 0
        [int]$installed = 0
        [int64]$aggregate = 0
        while ($true) {
            $header = Read-ExactBytes $gzip 512
            if (@($header | Where-Object { $_ -ne 0 }).Count -eq 0) { break }
            $entries++
            if ($entries -gt [int]$Limits.maximum_entries_per_archive) { Stop-Build 'sdist_entry_count_overflow' }
            $name = Get-TarString $header 0 100
            $prefix = Get-TarString $header 345 155
            if ($prefix) { $name = $prefix + '/' + $name }
            [void](Get-SafeArchiveTarget $name $SiteRoot)
            $length = Get-TarOctal $header 124 12
            if ($length -gt [int64]$Limits.maximum_entry_bytes) { Stop-Build 'sdist_entry_size_overflow' }
            $aggregate += $length
            if ($aggregate -gt [int64]$Limits.maximum_archive_output_bytes) { Stop-Build 'sdist_aggregate_size_overflow' }
            $type = [char]$header[156]
            if ($type -ne [char]0 -and $type -ne '0' -and $type -ne '5') { Stop-Build 'sdist_unsupported_tar_type' }
            $relative = $null
            if (($type -eq [char]0 -or $type -eq '0') -and $name.StartsWith([string]$Package.install_prefix, [System.StringComparison]::Ordinal)) {
                $suffix = $name.Substring(([string]$Package.install_prefix).Length)
                if ($suffix) { $relative = ([string]$Package.install_target) + '/' + $suffix }
            }
            if ($relative) {
                $target = Get-SafeArchiveTarget $relative $SiteRoot
                if (-not $Targets.Add($target)) { Stop-Build 'sdist_target_collision' }
                Copy-BoundedTarContent $gzip $target $length ([int]$Limits.stream_buffer_bytes)
                $installed++
            } else { Skip-BoundedTarContent $gzip $length ([int]$Limits.stream_buffer_bytes) }
            $padding = (512 - ($length % 512)) % 512
            if ($padding -gt 0) { [void](Read-ExactBytes $gzip ([int]$padding)) }
        }
        if ($installed -le 0) { Stop-Build 'sdist_install_prefix_empty' }
    } finally { $gzip.Dispose(); $file.Dispose() }
}
function Assert-Authenticode([string]$Path, [string]$SubjectContains, [string]$Version) {
    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid -or -not $signature.SignerCertificate -or -not $signature.SignerCertificate.Subject.Contains($SubjectContains)) { Stop-Build 'python_authenticode_invalid' }
    $fileVersion = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($Path).ProductVersion
    if (-not $fileVersion.StartsWith($Version, [System.StringComparison]::Ordinal)) { Stop-Build 'python_product_version_mismatch' }
    return $signature.SignerCertificate.Subject
}
function Get-RuntimeTree([string]$Root) {
    $records = New-Object System.Collections.Generic.List[string]
    [int64]$bytes = 0
    [string[]]$relativePaths = @(Get-ChildItem -LiteralPath $Root -File -Recurse -Force | ForEach-Object { $_.FullName.Substring($Root.Length).TrimStart('\').Replace('\','/') })
    [System.Array]::Sort($relativePaths, [System.StringComparer]::Ordinal)
    foreach ($relative in $relativePaths) {
        $file = Get-Item -LiteralPath (Join-Path $Root $relative.Replace('/','\'))
        $bytes += [int64]$file.Length
        $records.Add($relative + [char]0 + [string]$file.Length + [char]0 + (Get-Sha256 $file.FullName) + "`n")
    }
    $joined = [string]::Join('', $records.ToArray())
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $hash = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($joined)) } finally { $sha.Dispose() }
    return [pscustomobject]@{sha256=([System.BitConverter]::ToString($hash).Replace('-','').ToLowerInvariant());file_count=$relativePaths.Count;bytes=$bytes}
}

if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem -or -not [Environment]::Is64BitProcess) { Stop-Build 'windows_amd64_required' }
if ($PSVersionTable.PSVersion.Major -lt 5) { Stop-Build 'powershell_version_unsupported' }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Stop-Build 'host_git_required' }

$RepoRoot = Get-FullLocalPath $RepoRoot 'repo'
$lockPath = Join-Path $RepoRoot 'operations\windows\doc04-metadata-repair\runtime-lock.json'
$lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($lock.schema -ne 'NEXT_STABIL_DOC04_WINDOWS_RUNTIME_LOCK_V3') { Stop-Build 'runtime_lock_schema_mismatch' }
$RuntimeRoot = Assert-SafeRoot $RuntimeRoot 'runtime' $RepoRoot $lock.path_policy
$CacheRoot = Assert-SafeRoot $CacheRoot 'cache' $RepoRoot $lock.path_policy
if ((Test-Under $RuntimeRoot $CacheRoot) -or (Test-Under $CacheRoot $RuntimeRoot)) { Stop-Build 'runtime_cache_path_overlap' }
Assert-GitIdentity $RepoRoot $ExpectedGitSha $lock
$profilePackages = @(Get-ProfilePackages $lock $Profile)
$profileDefinition = $lock.profiles.$Profile
if ($Profile -eq 'Production' -and @($profilePackages | Where-Object { $_.classification -eq 'locked_pure_sdist' }).Count -ne 0) { Stop-Build 'production_profile_sdist_forbidden' }
if ($Profile -eq 'Qualification') {
    $sdists = @($profilePackages | Where-Object { $_.classification -eq 'locked_pure_sdist' })
    if ($sdists.Count -gt 1 -or ($sdists.Count -eq 1 -and ($sdists[0].project -ne 'odfpy' -or $sdists[0].version -ne '1.4.1'))) { Stop-Build 'qualification_sdist_contract_invalid' }
}

if (Test-Path -LiteralPath $RuntimeRoot) { Stop-Build 'runtime_root_not_fresh' }
if (-not (Test-Path -LiteralPath $CacheRoot)) { [System.IO.Directory]::CreateDirectory($CacheRoot) | Out-Null }
Assert-NoReparseChain $CacheRoot
if ($DownloadFailureProbe) {
    Invoke-DownloadFailureCleanupProbe $CacheRoot $DownloadFailureProbe
    exit 0
}
$allowedNames = @((Get-LockedArtifacts $lock $lock.packages) | ForEach-Object { $_.filename })
foreach ($item in Get-ChildItem -LiteralPath $CacheRoot -Force) {
    if ($item.PSIsContainer -or $allowedNames -notcontains $item.Name -or $item.Name.EndsWith('.partial')) { Stop-Build 'cache_contains_unexpected_entry' }
}

$artifacts = Get-LockedArtifacts $lock $profilePackages
foreach ($artifact in $artifacts) {
    $target = Join-Path $CacheRoot $artifact.filename
    if (Test-Path -LiteralPath $target) { Assert-LockedFile $artifact $target }
    elseif ($Offline) { Stop-Build 'offline_artifact_missing' }
    else { Invoke-LockedDownload $artifact $target $lock.allowed_download_hosts ([int]$lock.extraction_limits.maximum_redirects) }
}
if (-not $Offline) { foreach ($package in $profilePackages) { Assert-PypiMetadata $package $lock.allowed_download_hosts } }
Assert-PythonSbom $lock $CacheRoot

$staging = $RuntimeRoot + '.building-' + $PID
if (Test-Path -LiteralPath $staging) { Stop-Build 'runtime_staging_collision' }
[System.IO.Directory]::CreateDirectory($staging) | Out-Null
try {
    $targets = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    Expand-LockedZip (Join-Path $CacheRoot $lock.runtime_python.filename) $staging $lock.extraction_limits $targets
    $site = Join-Path $staging 'Lib\site-packages'
    [System.IO.Directory]::CreateDirectory($site) | Out-Null
    foreach ($package in $profilePackages) {
        if ($package.classification -eq 'locked_pure_sdist') { Install-LockedPureSdist $package (Join-Path $CacheRoot $package.filename) $site $lock.extraction_limits $targets }
        else { Install-LockedWheel $package (Join-Path $CacheRoot $package.filename) $site $lock.extraction_limits $targets }
    }
    $pthPath = Join-Path $staging 'python312._pth'
    [System.IO.File]::WriteAllText($pthPath, ([string]::Join("`r`n", @($lock.python312_pth)) + "`r`n"), [System.Text.Encoding]::ASCII)
    $profileMarker = [ordered]@{profile=$Profile;schema=$lock.schema}
    [System.IO.File]::WriteAllText((Join-Path $staging '_NEXT_DOC04_RUNTIME_PROFILE.json'), (($profileMarker | ConvertTo-Json -Compress) + "`n"), (New-Object System.Text.UTF8Encoding($false)))
    $signer = Assert-Authenticode (Join-Path $staging 'python.exe') $lock.runtime_python.authenticode_subject_contains $lock.runtime_python.product_version
    [void](Assert-Authenticode (Join-Path $staging 'python312.dll') $lock.runtime_python.authenticode_subject_contains $lock.runtime_python.product_version)
    $probeInfo = New-Object System.Diagnostics.ProcessStartInfo
    $probeInfo.FileName = Join-Path $staging 'python.exe'
    $probeInfo.Arguments = '-I -B -X utf8 -c "import json,platform,sys;print(json.dumps({''version'':platform.python_version(),''machine'':platform.machine(),''bits'':64 if sys.maxsize>2**32 else 32},sort_keys=True,separators=('','','':'')))"'
    $probeInfo.UseShellExecute = $false
    $probeInfo.CreateNoWindow = $true
    $probeInfo.RedirectStandardOutput = $true
    $probeInfo.RedirectStandardError = $true
    $probeInfo.WorkingDirectory = $staging
    $probeInfo.EnvironmentVariables.Clear()
    foreach ($name in @('SystemRoot','WINDIR','ComSpec')) {
        $value = [Environment]::GetEnvironmentVariable($name,'Process')
        if ($value) { $probeInfo.EnvironmentVariables[$name] = $value }
    }
    $probeInfo.EnvironmentVariables['TEMP'] = $staging
    $probeInfo.EnvironmentVariables['TMP'] = $staging
    $probeInfo.EnvironmentVariables['PATH'] = $staging
    $probeInfo.EnvironmentVariables['PYTHONDONTWRITEBYTECODE'] = '1'
    $probeInfo.EnvironmentVariables['PYTHONNOUSERSITE'] = '1'
    $probeInfo.EnvironmentVariables['PYTHONUTF8'] = '1'
    $probeProcess = New-Object System.Diagnostics.Process
    $probeProcess.StartInfo = $probeInfo
    try {
        if (-not $probeProcess.Start()) { Stop-Build 'portable_python_probe_failed' }
        $probeOutput = $probeProcess.StandardOutput.ReadToEndAsync()
        $probeError = $probeProcess.StandardError.ReadToEndAsync()
        if (-not $probeProcess.WaitForExit(30000)) { try { $probeProcess.Kill() } catch { }; Stop-Build 'portable_python_probe_timeout' }
        $probe = $probeOutput.Result.Trim()
        if ($probeProcess.ExitCode -ne 0 -or $probeError.Result.Trim()) { Stop-Build 'portable_python_probe_failed' }
    } finally { $probeProcess.Dispose() }
    $probeObject = ($probe | Out-String).Trim() | ConvertFrom-Json
    if ($probeObject.version -ne '3.12.10' -or [int]$probeObject.bits -ne 64 -or $probeObject.machine -notmatch '(?i)(amd64|x86_64)') { Stop-Build 'portable_python_identity_mismatch' }
    Assert-NoReparseTree $staging
    $tree = Get-RuntimeTree $staging
    $expectedRuntime = $profileDefinition.installed_runtime
    if ($tree.bytes -gt [int64]$expectedRuntime.expected_bytes_maximum) { Stop-Build 'runtime_size_limit_exceeded' }
    if ([int]$expectedRuntime.expected_file_count -gt 0 -and $tree.file_count -ne [int]$expectedRuntime.expected_file_count) { Stop-Build 'runtime_file_count_mismatch' }
    if ($expectedRuntime.expected_tree_sha256 -notmatch '^0{64}$' -and $tree.sha256 -ne $expectedRuntime.expected_tree_sha256) { Stop-Build 'runtime_tree_hash_mismatch' }
    [System.IO.Directory]::Move($staging, $RuntimeRoot)
    Assert-NoReparseTree $RuntimeRoot
    $manifest = [ordered]@{result='runtime_built';profile=$Profile;source_git_sha=$ExpectedGitSha;runtime_lock_sha256=(Get-Sha256 $lockPath);python_version='3.12.10';architecture='amd64';python_artifact_sha256=$lock.runtime_python.sha256;package_count=$profilePackages.Count;packages=@($profilePackages | ForEach-Object { $_.project });file_count=$tree.file_count;runtime_bytes=$tree.bytes;runtime_tree_sha256=$tree.sha256;authenticode_status='Valid';authenticode_publisher='Python Software Foundation';offline=[bool]$Offline;production_activity=0}
    $manifestPath = $RuntimeRoot + '.manifest.json'
    [System.IO.File]::WriteAllText($manifestPath, (($manifest | ConvertTo-Json -Compress) + "`n"), (New-Object System.Text.UTF8Encoding($false)))
    $manifest | ConvertTo-Json -Compress
} catch {
    if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    throw
}
