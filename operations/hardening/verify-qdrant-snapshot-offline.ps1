[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SnapshotPath,
    [string]$QdrantImage = "qdrant/qdrant@sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286",
    [Parameter(Mandatory = $true)]
    [string]$TargetCollection,
    [Nullable[long]]$ExpectedPoints = $null,
    [Nullable[int]]$ExpectedDimensions = $null,
    [string]$ExpectedDistance = "",
    [Parameter(Mandatory = $true)]
    [string]$OperationId,
    [Parameter(Mandatory = $true)]
    [string]$ClientImage,
    [switch]$KeepResources
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

function Invoke-Docker {
    param([string[]]$Arguments)
    $prior = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $lines = @(& docker.exe @Arguments 2>&1)
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $prior }
    if ($code -ne 0) { throw "docker_command_failed:$($Arguments[0])" }
    $lines | Write-Output
}

function Invoke-DockerCapture {
    param([string[]]$Arguments)
    $prior = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $lines = @(& docker.exe @Arguments 2>&1)
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $prior }
    if ($code -ne 0) {
        $safe = (([string]($lines | Select-Object -Last 1)) -replace '[^A-Za-z0-9_.: -]', '_')
        if ($safe.Length -gt 160) { $safe = $safe.Substring(0, 160) }
        throw "docker_command_failed:$($Arguments[0]):$safe"
    }
    return ($lines -join "")
}

function Test-DockerObjectExists {
    param([string[]]$Arguments)
    $prior = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & docker.exe @Arguments 1>$null 2>$null
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $prior }
    return $code -eq 0
}

function Convert-ToPythonCommand {
    param([string]$Code)
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Code))
    return "import base64;exec(base64.b64decode('$encoded'))"
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
}

function Assert-IsolatedContainer {
    param([string]$Container, [string]$ExpectedNetwork, [string]$ExpectedOwner, [string]$ExpectedVolume = "")
    $privileged = (& docker.exe inspect $Container --format '{{.HostConfig.Privileged}}').Trim()
    $ports = ((& docker.exe inspect $Container --format '{{json .HostConfig.PortBindings}}') -join "").Trim()
    $networkMode = (& docker.exe inspect $Container --format '{{.HostConfig.NetworkMode}}').Trim()
    $labels = ((& docker.exe inspect $Container --format '{{json .Config.Labels}}') -join "") | ConvertFrom-Json
    $mountJson = ((& docker.exe inspect $Container --format '{{json .Mounts}}') -join "")
    $mountValue = $mountJson | ConvertFrom-Json
    $mounts = @()
    if ($null -ne $mountValue) { $mounts = @($mountValue) }
    if ($LASTEXITCODE -ne 0 -or $privileged -ne "false" -or $ports -notin @("null", "{}") -or
        $networkMode -ne $ExpectedNetwork -or [string]$labels.'next.stabil.owner' -ne $ExpectedOwner -or
        [string]$labels.'next.stabil.purpose' -ne "r03-isolated-proof") {
        throw "qdrant_restore_isolation_failed"
    }
    if ([string]::IsNullOrWhiteSpace($ExpectedVolume)) {
        $unsafeClientMounts = @($mounts | Where-Object {
            $_.PSObject.Properties.Name -notcontains "Type" -or
            $_.PSObject.Properties.Name -notcontains "Destination" -or
            [string]$_.Type -ne "tmpfs" -or [string]$_.Destination -ne "/tmp"
        })
        if ($unsafeClientMounts.Count -ne 0) { throw "qdrant_restore_client_mount_rejected" }
    } else {
        if ($mounts.Count -ne 1 -or [string]$mounts[0].Type -ne "volume" -or
            [string]$mounts[0].Name -ne $ExpectedVolume -or
            [string]$mounts[0].Destination -ne "/qdrant/storage") {
            throw "qdrant_restore_volume_mount_invalid"
        }
    }
}

$snapshot = (Resolve-Path -LiteralPath $SnapshotPath).Path
if ((Get-Item -LiteralPath $snapshot).Length -le 0) { throw "qdrant_snapshot_empty" }
if ($QdrantImage -notmatch '@sha256:[a-f0-9]{64}$') { throw "qdrant_restore_image_not_pinned" }
if ($ClientImage -notmatch '^sha256:[a-f0-9]{64}$') { throw "qdrant_restore_client_image_not_pinned" }
if ($TargetCollection -notin @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks")) {
    throw "qdrant_restore_collection_rejected"
}
if ($OperationId -notmatch '^next-stabil-r03-a1-(test|drill)-[a-z0-9-]{8,80}-qdrant-[1-9][0-9]*$') {
    throw "qdrant_restore_operation_id_invalid"
}
Assert-SnapshotStructure $snapshot

$network = "$OperationId-network"
$container = "$OperationId-server"
$client = "$OperationId-client"
$volume = "$OperationId-data"
foreach ($check in @(
    @("network", "inspect", $network),
    @("container", "inspect", $container),
    @("container", "inspect", $client),
    @("volume", "inspect", $volume)
)) {
    if (Test-DockerObjectExists $check) { throw "qdrant_restore_target_collision" }
}

$networkCreated = $false
$volumeCreated = $false
$containerCreated = $false
$clientCreated = $false
$success = $false
try {
    Invoke-Docker @("network", "create", "--internal", "--label", "next.stabil.owner=$OperationId", "--label", "next.stabil.purpose=r03-isolated-proof", $network) | Out-Null
    $networkCreated = $true
    Invoke-Docker @("volume", "create", "--label", "next.stabil.owner=$OperationId", "--label", "next.stabil.purpose=r03-isolated-proof", $volume) | Out-Null
    $volumeCreated = $true
    Invoke-Docker @("run", "-d", "--name", $container, "--network", $network,
        "--label", "next.stabil.owner=$OperationId", "--label", "next.stabil.purpose=r03-isolated-proof",
        "--mount", "type=volume,src=$volume,dst=/qdrant/storage", $QdrantImage) | Out-Null
    $containerCreated = $true
    Invoke-Docker @("run", "-d", "--name", $client, "--network", $network,
        "--label", "next.stabil.owner=$OperationId", "--label", "next.stabil.purpose=r03-isolated-proof",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=512m", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--entrypoint", "sleep", $ClientImage, "1800") | Out-Null
    $clientCreated = $true

    $networkInternal = (& docker.exe network inspect $network --format '{{.Internal}}').Trim()
    $networkLabels = ((& docker.exe network inspect $network --format '{{json .Labels}}') -join "") | ConvertFrom-Json
    $volumeLabels = ((& docker.exe volume inspect $volume --format '{{json .Labels}}') -join "") | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $networkInternal -ne "true" -or
        [string]$networkLabels.'next.stabil.owner' -ne $OperationId -or
        [string]$volumeLabels.'next.stabil.owner' -ne $OperationId) {
        throw "qdrant_restore_resource_ownership_invalid"
    }
    Assert-IsolatedContainer $container $network $OperationId $volume
    Assert-IsolatedContainer $client $network $OperationId

    $healthCode = @'
import json, time, urllib.request
url = "http://REPLACE_CONTAINER:6333/"
last = None
for _ in range(90):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            last = json.loads(response.read().decode("utf-8"))
        if last.get("version"):
            print(json.dumps(last, separators=(",", ":")))
            break
    except Exception:
        time.sleep(0.5)
else:
    raise SystemExit("qdrant_restore_container_health_timeout")
'@.Replace('REPLACE_CONTAINER', $container)
    $healthJson = Invoke-DockerCapture @("exec", $client, "python", "-c", (Convert-ToPythonCommand $healthCode))
    $health = $healthJson | ConvertFrom-Json
    if ([string]::IsNullOrWhiteSpace([string]$health.version)) { throw "qdrant_restore_container_health_timeout" }

    Invoke-Docker @("cp", $snapshot, "${client}:/qdrant.snapshot") | Out-Null
    $uploadCode = @'
import http.client, json, os
host = "REPLACE_CONTAINER"
path = "/collections/REPLACE_COLLECTION/snapshots/upload?priority=snapshot"
snapshot = "/qdrant.snapshot"
boundary = "next-stabil-r03-a1-boundary"
prefix = ("--" + boundary + "\r\nContent-Disposition: form-data; name=\"snapshot\"; filename=\"qdrant.snapshot\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode("ascii")
suffix = ("\r\n--" + boundary + "--\r\n").encode("ascii")
connection = http.client.HTTPConnection(host, 6333, timeout=900)
connection.putrequest("POST", path)
connection.putheader("Content-Type", "multipart/form-data; boundary=" + boundary)
connection.putheader("Content-Length", str(len(prefix) + os.path.getsize(snapshot) + len(suffix)))
connection.endheaders()
connection.send(prefix)
with open(snapshot, "rb") as stream:
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        connection.send(chunk)
connection.send(suffix)
response = connection.getresponse()
payload = response.read()
if response.status < 200 or response.status >= 300:
    raise SystemExit("qdrant_restore_http_" + str(response.status))
print(json.dumps(json.loads(payload.decode("utf-8")), separators=(",", ":")))
'@.Replace('REPLACE_CONTAINER', $container).Replace('REPLACE_COLLECTION', $TargetCollection)
    $uploadJson = Invoke-DockerCapture @("exec", $client, "python", "-c", (Convert-ToPythonCommand $uploadCode))
    $upload = $uploadJson | ConvertFrom-Json
    if ($upload.status -ne "ok") { throw "qdrant_restore_upload_failed" }

    $infoCode = @'
import json, urllib.request
with urllib.request.urlopen("http://REPLACE_CONTAINER:6333/collections/REPLACE_COLLECTION", timeout=30) as response:
    print(json.dumps(json.loads(response.read().decode("utf-8")), separators=(",", ":")))
'@.Replace('REPLACE_CONTAINER', $container).Replace('REPLACE_COLLECTION', $TargetCollection)
    $infoJson = Invoke-DockerCapture @("exec", $client, "python", "-c", (Convert-ToPythonCommand $infoCode))
    $info = $infoJson | ConvertFrom-Json
    if ($info.status -ne "ok") { throw "qdrant_restore_collection_info_failed" }
    $points = [int64]$info.result.points_count
    $dimensions = [int]$info.result.config.params.vectors.size
    $distance = [string]$info.result.config.params.vectors.distance
    if ($null -ne $ExpectedPoints -and $points -ne [int64]$ExpectedPoints) { throw "qdrant_restore_point_count_mismatch" }
    if ($null -ne $ExpectedDimensions -and $dimensions -ne [int]$ExpectedDimensions) { throw "qdrant_restore_dimensions_mismatch" }
    if ($ExpectedDistance -and $distance -ne $ExpectedDistance) { throw "qdrant_restore_distance_mismatch" }
    $success = $true
    [ordered]@{
        verified = $true
        collection = $TargetCollection
        qdrant_version = [string]$health.version
        points = $points
        dimensions = $dimensions
        distance = $distance
        production_volume_mounted = $false
        host_ports = 0
        internal_network = $true
        owner = $OperationId
        retained_resources = if ($KeepResources) { @($network, $volume, $container, $client) } else { @() }
    } | ConvertTo-Json -Compress
}
finally {
    if (-not ($KeepResources -and $success)) {
        if ($clientCreated -and $client -eq "$OperationId-client") { & docker.exe rm -f $client 2>$null | Out-Null }
        if ($containerCreated -and $container -eq "$OperationId-server") { & docker.exe rm -f $container 2>$null | Out-Null }
        if ($volumeCreated -and $volume -eq "$OperationId-data") { & docker.exe volume rm $volume 2>$null | Out-Null }
        if ($networkCreated -and $network -eq "$OperationId-network") { & docker.exe network rm $network 2>$null | Out-Null }
    }
}
