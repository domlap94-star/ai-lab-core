[CmdletBinding()]
param(
    [string]$Image = "qdrant/qdrant@sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286",
    [string]$OutputRoot = (Join-Path $env:TEMP ("next-stabil-qdrant-topology-" + [Guid]::NewGuid().ToString("N"))),
    [switch]$KeepArtifacts
)

$ErrorActionPreference = "Stop"
$productionStorage = [IO.Path]::GetFullPath("C:\ai-lab-core\data\qdrant").TrimEnd('\')
$resolvedOutput = [IO.Path]::GetFullPath($OutputRoot).TrimEnd('\')
$resolvedTemp = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')
if (-not $resolvedOutput.StartsWith($resolvedTemp + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw "qdrant_test_output_must_be_under_temp"
}
if ($resolvedOutput.Equals($productionStorage, [StringComparison]::OrdinalIgnoreCase) -or
    $resolvedOutput.StartsWith($productionStorage + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw "qdrant_test_refuses_production_storage"
}

$token = [Guid]::NewGuid().ToString("N").Substring(0, 10)
$collection = "ai_lab_test_trash_qdrant_$token"
$names = @{
    BindSource = "next-qdrant-bind-source-$token"
    BindTarget = "next-qdrant-bind-target-$token"
    NamedSource = "next-qdrant-named-source-$token"
    NamedTarget = "next-qdrant-named-target-$token"
    Migrated = "next-qdrant-migrated-$token"
    MigratedTarget = "next-qdrant-migrated-target-$token"
}
$volumes = @{
    BindTarget = "next_qdrant_bind_target_$token"
    NamedSource = "next_qdrant_named_source_$token"
    NamedTarget = "next_qdrant_named_target_$token"
    Migrated = "next_qdrant_migrated_$token"
    MigratedTarget = "next_qdrant_migrated_target_$token"
}
$ports = @{ BindSource = 16431; BindTarget = 16432; NamedSource = 16433; NamedTarget = 16434; Migrated = 16435; MigratedTarget = 16436 }
$bindRoot = Join-Path $resolvedOutput "bind-storage"
$downloads = Join-Path $resolvedOutput "snapshots"
New-Item -ItemType Directory -Path $bindRoot, $downloads -Force | Out-Null

function Invoke-Docker([string[]]$Arguments) {
    & docker.exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "docker_command_failed" }
}

function Wait-Qdrant([int]$Port) {
    if ($Port -eq 6333) { throw "qdrant_test_refuses_production_endpoint" }
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $status = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/" -TimeoutSec 2
            if ($status.version -eq "1.18.3") { return }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    throw "qdrant_test_container_not_ready"
}

function Start-Qdrant([string]$Name, [int]$Port, [string]$Mount) {
    if ($Name -notlike "next-qdrant-*") { throw "qdrant_test_container_name_rejected" }
    if ($Port -eq 6333) { throw "qdrant_test_refuses_production_endpoint" }
    Invoke-Docker @("run", "-d", "--name", $Name, "-p", "127.0.0.1:${Port}:6333", "-v", "${Mount}:/qdrant/storage", $Image)
    Wait-Qdrant $Port
}

function Seed-Collection([int]$Port) {
    if ($collection -eq "ai_lab_document_chunks") { throw "qdrant_test_refuses_production_collection" }
    $create = @{ vectors = @{ size = 1024; distance = "Cosine" }; wal_config = @{ wal_capacity_mb = 1; wal_segments_ahead = 0 } } | ConvertTo-Json -Depth 5 -Compress
    Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:$Port/collections/$collection" -ContentType "application/json" -Body $create | Out-Null
    for ($batch = 0; $batch -lt 4; $batch++) {
        $batchPoints = @()
        for ($offset = 0; $offset -lt 100; $offset++) {
            $id = ($batch * 100) + $offset + 1
            $hotIndex = $id % 1024
            $vector = @(for ($i = 0; $i -lt 1024; $i++) { if ($i -eq $hotIndex) { 1.0 } else { 0.0 } })
            $batchPoints += @{ id = $id; vector = $vector; payload = @{ document_id = 9001; chunk_id = 7000 + $id; marker = "point-$id" } }
        }
        $points = @{ points = $batchPoints } | ConvertTo-Json -Depth 8 -Compress
        Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:$Port/collections/$collection/points?wait=true" -ContentType "application/json" -Body $points | Out-Null
    }
}

function Get-CollectionProof([int]$Port) {
    $info = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/collections/$collection"
    $scrollBody = @{ ids = @(1, 400); with_payload = $true; with_vector = $false } | ConvertTo-Json -Compress
    $scroll = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$Port/collections/$collection/points" -ContentType "application/json" -Body $scrollBody
    [ordered]@{
        points = $info.result.points_count
        vectors = $info.result.config.params.vectors.size
        distance = $info.result.config.params.vectors.distance
        ids = @($scroll.result | ForEach-Object { $_.id } | Sort-Object)
        markers = @($scroll.result | ForEach-Object { $_.payload.marker } | Sort-Object)
    }
}

function New-Snapshot([int]$Port, [string]$Label) {
    try {
        $created = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$Port/collections/$collection/snapshots" -TimeoutSec 120
    } catch {
        $detail = $_.Exception.Message
        if ($_.Exception.Response) {
            try {
                $reader = New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())
                $detail = $reader.ReadToEnd()
                $reader.Dispose()
            } catch { }
        }
        throw "qdrant_snapshot_create_failed:$detail"
    }
    if ($created.status -ne "ok") { throw "qdrant_snapshot_create_failed" }
    $path = Join-Path $downloads "$Label.snapshot"
    & curl.exe --fail --silent --show-error --location --max-time 120 --output $path "http://127.0.0.1:$Port/collections/$collection/snapshots/$($created.result.name)"
    if ($LASTEXITCODE -ne 0) { throw "qdrant_snapshot_download_failed" }
    return $path
}

function Inspect-FirstIndex([string]$Snapshot) {
    $entries = @(& tar.exe -tf $Snapshot)
    if ($LASTEXITCODE -ne 0) { throw "qdrant_snapshot_archive_invalid" }
    $entry = $entries | Where-Object { ($_ -replace '^\./', '') -match '^\d+/wal/first-index$' } | Select-Object -First 1
    if (-not $entry) { return [ordered]@{ entry = $null; bytes = 0; all_nul = $false; text = $null; missing = $true } }
    $stage = Join-Path $resolvedOutput ("inspect-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $stage | Out-Null
    try {
        & tar.exe -xf $Snapshot -C $stage $entry
        if ($LASTEXITCODE -ne 0) { throw "qdrant_snapshot_first_index_extract_failed" }
        $file = Join-Path $stage ($entry -replace '/', '\')
        $bytes = [IO.File]::ReadAllBytes($file)
        $allNul = $bytes.Length -gt 0 -and (@($bytes | Where-Object { $_ -ne 0 }).Count -eq 0)
        return [ordered]@{ entry = $entry; bytes = $bytes.Length; all_nul = $allNul; text = if ($allNul) { $null } else { [Text.Encoding]::UTF8.GetString($bytes) } }
    } finally {
        if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
    }
}

function Restore-Snapshot([int]$Port, [string]$Snapshot) {
    if ($Port -eq 6333) { throw "qdrant_test_refuses_production_endpoint" }
    $output = & curl.exe --silent --show-error --write-out "`nHTTP_STATUS=%{http_code}" -X POST -F "snapshot=@$Snapshot" "http://127.0.0.1:$Port/collections/$collection/snapshots/upload?priority=snapshot"
    $httpLine = $output | Where-Object { $_ -like "HTTP_STATUS=*" } | Select-Object -Last 1
    $status = [int](($httpLine -split '=', 2)[1])
    [ordered]@{ status = $status; body = (($output | Where-Object { $_ -notlike "HTTP_STATUS=*" }) -join "`n") }
}

function Remove-TestResources {
    foreach ($name in $names.Values) {
        if ($name -like "next-qdrant-*") {
            $exists = & docker.exe ps -a --filter "name=^/$name$" --format "{{.Names}}" 2>$null
            if ($exists -eq $name) { & docker.exe rm -f $name | Out-Null }
        }
    }
    foreach ($volume in $volumes.Values) {
        if ($volume -like "next_qdrant_*") {
            $exists = & docker.exe volume ls --filter "name=^$volume$" --format "{{.Name}}" 2>$null
            if ($exists -eq $volume) { & docker.exe volume rm $volume | Out-Null }
        }
    }
}

$result = [ordered]@{ token = $token; collection = $collection; image = $Image; output_root = $resolvedOutput }
try {
    Start-Qdrant $names.NamedSource $ports.NamedSource $volumes.NamedSource
    Seed-Collection $ports.NamedSource
    $namedSnapshot = New-Snapshot $ports.NamedSource "named"
    $result.named_first_index = Inspect-FirstIndex $namedSnapshot
    Start-Qdrant $names.NamedTarget $ports.NamedTarget $volumes.NamedTarget
    $result.named_restore = Restore-Snapshot $ports.NamedTarget $namedSnapshot
    if ($result.named_restore.status -eq 200) { $result.named_proof = Get-CollectionProof $ports.NamedTarget }

    Start-Qdrant $names.BindSource $ports.BindSource $bindRoot
    Seed-Collection $ports.BindSource
    $result.bind_source_proof = Get-CollectionProof $ports.BindSource
    try {
        $bindSnapshot = New-Snapshot $ports.BindSource "bind"
        $result.bind_snapshot_created = $true
        $result.bind_first_index = Inspect-FirstIndex $bindSnapshot
        Start-Qdrant $names.BindTarget $ports.BindTarget $volumes.BindTarget
        $result.bind_restore = Restore-Snapshot $ports.BindTarget $bindSnapshot
        if ($result.bind_restore.status -eq 200) { $result.bind_restore_proof = Get-CollectionProof $ports.BindTarget }
    } catch {
        $result.bind_snapshot_created = $false
        $result.bind_snapshot_error = $_.Exception.Message
    }

    Invoke-Docker @("stop", $names.BindSource)
    Invoke-Docker @("volume", "create", $volumes.Migrated)
    Invoke-Docker @("run", "--rm", "-v", "${bindRoot}:/from:ro", "-v", "$($volumes.Migrated):/to", $Image, "sh", "-c", "cp -a /from/. /to/")
    Start-Qdrant $names.Migrated $ports.Migrated $volumes.Migrated
    $result.migrated_proof = Get-CollectionProof $ports.Migrated
    $migratedSnapshot = New-Snapshot $ports.Migrated "migrated"
    $result.migrated_first_index = Inspect-FirstIndex $migratedSnapshot
    Start-Qdrant $names.MigratedTarget $ports.MigratedTarget $volumes.MigratedTarget
    $result.migrated_restore = Restore-Snapshot $ports.MigratedTarget $migratedSnapshot
    if ($result.migrated_restore.status -eq 200) { $result.migrated_restore_proof = Get-CollectionProof $ports.MigratedTarget }

    Invoke-Docker @("stop", $names.Migrated)
    Invoke-Docker @("start", $names.BindSource)
    Wait-Qdrant $ports.BindSource
    $result.rollback_proof = Get-CollectionProof $ports.BindSource
    $result | ConvertTo-Json -Depth 8
} finally {
    Remove-TestResources
    if (-not $KeepArtifacts -and (Test-Path -LiteralPath $resolvedOutput)) {
        $confirmed = [IO.Path]::GetFullPath($resolvedOutput).TrimEnd('\')
        if (-not $confirmed.StartsWith($resolvedTemp + '\next-stabil-qdrant-topology-', [StringComparison]::OrdinalIgnoreCase)) {
            throw "qdrant_test_cleanup_refused"
        }
        Remove-Item -LiteralPath $confirmed -Recurse -Force
    }
}
