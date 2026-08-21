[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SnapshotPath,
    [string]$QdrantImage = "qdrant/qdrant@sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286",
    [string]$TargetCollection = "ai_lab_document_chunks",
    [Nullable[long]]$ExpectedPoints = $null,
    [Nullable[int]]$ExpectedDimensions = $null,
    [string]$ExpectedDistance = "",
    [switch]$KeepVolume
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

function Invoke-Docker {
    param([string[]]$Arguments)
    & docker.exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "docker_command_failed:$($Arguments[0])" }
}

function Assert-SnapshotStructure {
    param([string]$Path)
    $entries = @(& tar.exe -tf $Path)
    if ($LASTEXITCODE -ne 0 -or $entries.Count -eq 0) { throw "qdrant_snapshot_archive_invalid" }
    $normalized = @($entries | ForEach-Object { ([string]$_).Replace('\', '/').TrimStart('.', '/') } | Where-Object { $_ })
    foreach ($entry in $normalized) {
        if ($entry.StartsWith('/') -or $entry -match '^[A-Za-z]:' -or $entry -match '(^|/)[.][.](/|$)') {
            throw "qdrant_snapshot_archive_path_invalid"
        }
    }
    if ($normalized -notcontains "config.json" -or $normalized -notcontains "version.info" -or
        -not ($normalized | Where-Object { $_ -match '^[0-9]+/shard_config[.]json$' } | Select-Object -First 1)) {
        throw "qdrant_snapshot_metadata_missing"
    }
    foreach ($entry in @($normalized | Where-Object { $_ -match '^[0-9]+/wal/first-index$' })) {
        $text = ((& tar.exe -xOf $Path $entry 2>$null) -join "`n")
        if ($LASTEXITCODE -ne 0) { throw "qdrant_snapshot_first_index_read_failed" }
        if ([string]::IsNullOrEmpty($text) -or $text.Trim([char]0, [char]9, [char]10, [char]13, [char]32).Length -eq 0) {
            throw "qdrant_snapshot_first_index_empty_or_nul"
        }
        $metadata = $text | ConvertFrom-Json
        if ($null -eq $metadata.ack_index -or [int64]$metadata.ack_index -lt 0) {
            throw "qdrant_snapshot_first_index_invalid"
        }
    }
}

$snapshot = (Resolve-Path -LiteralPath $SnapshotPath).Path
if ((Get-Item -LiteralPath $snapshot).Length -le 0) { throw "qdrant_snapshot_empty" }
if ($QdrantImage -notmatch '@sha256:[a-f0-9]{64}$') { throw "qdrant_restore_image_not_pinned" }
if ($TargetCollection -ne "ai_lab_document_chunks") { throw "qdrant_restore_collection_rejected" }
Assert-SnapshotStructure $snapshot

$token = [Guid]::NewGuid().ToString("N").Substring(0, 10)
$container = "next-recovery-qdrant-$token"
$volume = "next_recovery_qdrant_$token"
$listener = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback, 0)
$listener.Start(); $port = ([Net.IPEndPoint]$listener.LocalEndpoint).Port; $listener.Stop()
if ($port -eq 6333) { throw "qdrant_restore_production_port_refused" }
$containerCreated = $false; $volumeCreated = $false; $success = $false
try {
    Invoke-Docker @("volume", "create", $volume) | Out-Null; $volumeCreated = $true
    Invoke-Docker @("run", "-d", "--name", $container, "-p", "127.0.0.1:${port}:6333", "-v", "${volume}:/qdrant/storage", $QdrantImage) | Out-Null
    $containerCreated = $true
    $health = $null
    for ($attempt = 0; $attempt -lt 90; $attempt++) {
        try { $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/" -TimeoutSec 2; if ($health.version) { break } } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $health) { throw "qdrant_restore_container_health_timeout" }
    $mount = (& docker.exe inspect $container --format '{{range .Mounts}}{{.Type}}|{{.Name}}|{{.Destination}}{{end}}').Trim()
    if ($LASTEXITCODE -ne 0 -or $mount -ne "volume|$volume|/qdrant/storage") { throw "qdrant_restore_isolation_failed" }

    $upload = & curl.exe --silent --show-error --write-out "`nHTTP_STATUS=%{http_code}" -X POST -F "snapshot=@$snapshot" `
        "http://127.0.0.1:$port/collections/$TargetCollection/snapshots/upload?priority=snapshot"
    if ($LASTEXITCODE -ne 0) { throw "qdrant_restore_upload_failed" }
    $statusLine = $upload | Where-Object { $_ -like "HTTP_STATUS=*" } | Select-Object -Last 1
    if (-not $statusLine -or [int](($statusLine -split '=', 2)[1]) -ne 200) { throw "qdrant_restore_http_failure" }
    $info = Invoke-RestMethod -Uri "http://127.0.0.1:$port/collections/$TargetCollection" -TimeoutSec 20
    $points = [int64]$info.result.points_count
    $dimensions = [int]$info.result.config.params.vectors.size
    $distance = [string]$info.result.config.params.vectors.distance
    if ($null -ne $ExpectedPoints -and $points -ne [int64]$ExpectedPoints) { throw "qdrant_restore_point_count_mismatch" }
    if ($null -ne $ExpectedDimensions -and $dimensions -ne [int]$ExpectedDimensions) { throw "qdrant_restore_dimensions_mismatch" }
    if ($ExpectedDistance -and $distance -ne $ExpectedDistance) { throw "qdrant_restore_distance_mismatch" }
    $success = $true
    [ordered]@{
        verified = $true; qdrant_version = [string]$health.version; points = $points
        dimensions = $dimensions; distance = $distance; production_volume_mounted = $false
        temporary_volume = if ($KeepVolume) { $volume } else { $null }
        temporary_container = if ($KeepVolume) { $container } else { $null }
        port = if ($KeepVolume) { $port } else { $null }
    } | ConvertTo-Json -Compress
}
finally {
    if (-not ($KeepVolume -and $success)) {
        if ($containerCreated -and $container -like "next-recovery-qdrant-*") { & docker.exe rm -f $container 2>$null | Out-Null }
        if ($volumeCreated -and $volume -like "next_recovery_qdrant_*") { & docker.exe volume rm $volume 2>$null | Out-Null }
    }
}
