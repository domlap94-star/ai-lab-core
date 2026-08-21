[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SnapshotPath,
    [string]$SourceCollection = "ai_lab_document_chunks",
    [string]$SourceUrl = "http://127.0.0.1:6333",
    [Parameter(Mandatory = $true)]
    [string]$QdrantImage
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$snapshot = (Resolve-Path -LiteralPath $SnapshotPath).Path
if ((Get-Item -LiteralPath $snapshot).Length -le 0) { throw "qdrant_snapshot_empty" }
if ($QdrantImage -notmatch '@sha256:[a-f0-9]{64}$') { throw "qdrant_restore_image_not_pinned" }
if ($SourceCollection -ne "ai_lab_document_chunks") { throw "qdrant_restore_source_collection_rejected" }
if ($SourceUrl -ne "http://127.0.0.1:6333") { throw "qdrant_restore_source_url_rejected" }

$validator = Join-Path $PSScriptRoot "..\supervisor\qdrant_snapshot_validator.js"
$validationJson = (& node.exe $validator $snapshot 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($validationJson -join ""))) {
    throw "qdrant_snapshot_validation_failed"
}
$validation = ($validationJson -join "") | ConvertFrom-Json
if ($validation.valid -ne $true) { throw "qdrant_snapshot_invalid" }

$sourceInfo = Invoke-RestMethod -Uri "$SourceUrl/collections/$SourceCollection" -TimeoutSec 15
$sourceScrollBody = @{ limit = 5; with_payload = $true; with_vector = $false } | ConvertTo-Json -Compress
$sourceScroll = Invoke-RestMethod -Method Post `
    -Uri "$SourceUrl/collections/$SourceCollection/points/scroll" `
    -ContentType "application/json" -Body $sourceScrollBody -TimeoutSec 15
$sourceProof = @($sourceScroll.result.points | Sort-Object id | ForEach-Object {
    $embeddingVersion = if ($_.payload.PSObject.Properties.Name -contains "embedding_version") {
        $_.payload.embedding_version
    } else { $null }
    "{0}|{1}|{2}|{3}" -f $_.id, $_.payload.document_id, $_.payload.chunk_id, $embeddingVersion
})

$token = [Guid]::NewGuid().ToString("N").Substring(0, 10)
$container = "next-qdrant-backup-restore-$token"
$volume = "next_qdrant_backup_restore_$token"
$targetCollection = "ai_lab_restore_test_document_chunks_$token"
$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = ([Net.IPEndPoint]$listener.LocalEndpoint).Port
$listener.Stop()
if ($port -eq 6333) { throw "qdrant_restore_production_port_refused" }
$containerCreated = $false
$volumeCreated = $false
try {
    & docker.exe volume create $volume | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "qdrant_restore_volume_create_failed" }
    $volumeCreated = $true
    & docker.exe run -d --name $container -p "127.0.0.1:${port}:6333" `
        -v "${volume}:/qdrant/storage" $QdrantImage | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "qdrant_restore_container_start_failed" }
    $containerCreated = $true

    $health = $null
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/" -TimeoutSec 2
            if (-not [string]::IsNullOrWhiteSpace($health.version)) { break }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $health) { throw "qdrant_restore_container_health_timeout" }
    $mount = (& docker.exe inspect $container --format '{{range .Mounts}}{{.Type}}|{{.Name}}|{{.Destination}}{{end}}').Trim()
    if ($mount -ne "volume|$volume|/qdrant/storage") { throw "qdrant_restore_isolation_failed" }

    $upload = & curl.exe --silent --show-error --write-out "`nHTTP_STATUS=%{http_code}" `
        -X POST -F "snapshot=@$snapshot" `
        "http://127.0.0.1:$port/collections/$targetCollection/snapshots/upload?priority=snapshot"
    if ($LASTEXITCODE -ne 0) { throw "qdrant_restore_upload_failed" }
    $httpLine = $upload | Where-Object { $_ -like "HTTP_STATUS=*" } | Select-Object -Last 1
    $status = [int](($httpLine -split '=', 2)[1])
    if ($status -ne 200) { throw "qdrant_restore_http_$status" }

    $restoredInfo = Invoke-RestMethod -Uri "http://127.0.0.1:$port/collections/$targetCollection" -TimeoutSec 15
    if ([int64]$restoredInfo.result.points_count -ne [int64]$sourceInfo.result.points_count) {
        throw "qdrant_restore_point_count_mismatch"
    }
    if ([int]$restoredInfo.result.config.params.vectors.size -ne [int]$sourceInfo.result.config.params.vectors.size -or
        [string]$restoredInfo.result.config.params.vectors.distance -ne [string]$sourceInfo.result.config.params.vectors.distance) {
        throw "qdrant_restore_vector_config_mismatch"
    }
    $restoredScroll = Invoke-RestMethod -Method Post `
        -Uri "http://127.0.0.1:$port/collections/$targetCollection/points/scroll" `
        -ContentType "application/json" -Body $sourceScrollBody -TimeoutSec 15
    $restoredProof = @($restoredScroll.result.points | Sort-Object id | ForEach-Object {
        $embeddingVersion = if ($_.payload.PSObject.Properties.Name -contains "embedding_version") {
            $_.payload.embedding_version
        } else { $null }
        "{0}|{1}|{2}|{3}" -f $_.id, $_.payload.document_id, $_.payload.chunk_id, $embeddingVersion
    })
    if (($sourceProof -join "`n") -ne ($restoredProof -join "`n")) {
        throw "qdrant_restore_representative_payload_mismatch"
    }

    [ordered]@{
        verified = $true
        qdrant_version = [string]$health.version
        points = [int64]$restoredInfo.result.points_count
        dimensions = [int]$restoredInfo.result.config.params.vectors.size
        distance = [string]$restoredInfo.result.config.params.vectors.distance
        representative_payloads_match = $true
        production_volume_mounted = $false
    } | ConvertTo-Json -Compress
}
finally {
    if ($containerCreated -and $container -like "next-qdrant-backup-restore-*") {
        & docker.exe rm -f $container 2>$null | Out-Null
    }
    if ($volumeCreated -and $volume -like "next_qdrant_backup_restore_*") {
        & docker.exe volume rm $volume 2>$null | Out-Null
    }
}
