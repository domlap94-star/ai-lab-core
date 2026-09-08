[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PostgresImage,
    [Parameter(Mandatory = $true)]
    [string]$QdrantImage,
    [Parameter(Mandatory = $true)]
    [string]$ClientImage
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

if ($PostgresImage -notmatch '@sha256:[a-f0-9]{64}$' -or
    $QdrantImage -notmatch '@sha256:[a-f0-9]{64}$' -or
    $ClientImage -notmatch '^sha256:[a-f0-9]{64}$') {
    throw "synthetic_proof_images_not_pinned"
}

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$restore = Join-Path $repo "operations\hardening\restore-checkpoint.ps1"
$token = [Guid]::NewGuid().ToString("N").Substring(0, 12)
$owner = "next-stabil-r03-a1-test-$token"
$network = "$owner-network"
$sourcePostgres = "$owner-source-postgres"
$sourcePostgresVolume = "$owner-source-postgres-data"
$targetPostgres = "$owner-postgres"
$targetPostgresVolume = "$owner-postgres-data"
$sourceQdrant = "$owner-source-qdrant"
$sourceQdrantVolume = "$owner-source-qdrant-data"
$sourceClient = "$owner-source-client"
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) $owner
$checkpoint = Join-Path $tempRoot "checkpoint"
$stateRoot = Join-Path $tempRoot "$owner-state"
$created = New-Object Collections.Generic.List[string]

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

function Convert-ToPythonCommand {
    param([string]$Code)
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Code))
    return "import base64;exec(base64.b64decode('$encoded'))"
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

function Add-Artifact {
    param([string]$Relative)
    $path = Join-Path $checkpoint ($Relative.Replace('/', '\'))
    $item = Get-Item -LiteralPath $path
    return [ordered]@{ file = $Relative; bytes = [int64]$item.Length; sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
}

function Assert-NoPortsAndOwnedNetwork {
    param([string]$Container)
    $ports = ((& docker.exe inspect $Container --format '{{json .HostConfig.PortBindings}}') -join "").Trim()
    $mode = (& docker.exe inspect $Container --format '{{.HostConfig.NetworkMode}}').Trim()
    $privileged = (& docker.exe inspect $Container --format '{{.HostConfig.Privileged}}').Trim()
    if ($LASTEXITCODE -ne 0 -or $ports -notin @("null", "{}") -or $mode -ne $network -or $privileged -ne "false") {
        throw "synthetic_resource_isolation_failed"
    }
}

function New-Archive {
    param([string]$Destination, [string]$Source, [string[]]$Entries)
    & tar.exe -czf $Destination -C $Source @Entries
    if ($LASTEXITCODE -ne 0) { throw "synthetic_archive_failed" }
}

try {
    foreach ($name in @($network, $sourcePostgres, $targetPostgres, $sourceQdrant, $sourceClient, $sourcePostgresVolume, $targetPostgresVolume, $sourceQdrantVolume)) {
        $commands = if ($name -eq $network) { @("network", "inspect", $name) } elseif ($name -like "*-data") { @("volume", "inspect", $name) } else { @("container", "inspect", $name) }
        if (Test-DockerObjectExists $commands) { throw "synthetic_resource_collision:$name" }
    }
    $resourceAllowlist = @($network, $sourcePostgres, $targetPostgres, $sourceQdrant, $sourceClient,
        $sourcePostgresVolume, $targetPostgresVolume, $sourceQdrantVolume)
    foreach ($index in 1..2) {
        $proofOwner = "$owner-qdrant-$index"
        $resourceAllowlist += @("$proofOwner-network", "$proofOwner-server", "$proofOwner-client", "$proofOwner-data")
    }
    Write-Output "SYNTHETIC_PROOF_OWNER=$owner"
    Write-Output ("SYNTHETIC_RESOURCE_ALLOWLIST=" + ($resourceAllowlist | ConvertTo-Json -Compress))
    Write-Output "SYNTHETIC_RESOURCE_CREATION=BEGIN"
    New-Item -ItemType Directory -Path (Join-Path $checkpoint "artifacts\qdrant") -Force | Out-Null

    Invoke-Docker @("network", "create", "--internal", "--label", "next.stabil.owner=$owner", "--label", "next.stabil.purpose=r03-isolated-proof", $network) | Out-Null
    $created.Add("network:$network")
    foreach ($volume in @($sourcePostgresVolume, $targetPostgresVolume, $sourceQdrantVolume)) {
        Invoke-Docker @("volume", "create", "--label", "next.stabil.owner=$owner", "--label", "next.stabil.purpose=r03-isolated-proof", $volume) | Out-Null
        $created.Add("volume:$volume")
    }
    Invoke-Docker @("run", "-d", "--name", $sourcePostgres, "--network", $network,
        "--label", "next.stabil.owner=$owner", "--label", "next.stabil.purpose=r03-isolated-proof",
        "--mount", "type=volume,src=$sourcePostgresVolume,dst=/var/lib/postgresql/data",
        "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "-e", "POSTGRES_USER=postgres", "-e", "POSTGRES_DB=ai_lab", $PostgresImage) | Out-Null
    $created.Add("container:$sourcePostgres")
    Invoke-Docker @("run", "-d", "--name", $targetPostgres, "--network", $network,
        "--label", "next.stabil.owner=$owner", "--label", "next.stabil.purpose=r03-isolated-proof",
        "--mount", "type=volume,src=$targetPostgresVolume,dst=/var/lib/postgresql/data",
        "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "-e", "POSTGRES_USER=postgres", "-e", "POSTGRES_DB=ai_lab", $PostgresImage) | Out-Null
    $created.Add("container:$targetPostgres")
    Invoke-Docker @("run", "-d", "--name", $sourceQdrant, "--network", $network,
        "--label", "next.stabil.owner=$owner", "--label", "next.stabil.purpose=r03-isolated-proof",
        "--mount", "type=volume,src=$sourceQdrantVolume,dst=/qdrant/storage", $QdrantImage) | Out-Null
    $created.Add("container:$sourceQdrant")
    Invoke-Docker @("run", "-d", "--name", $sourceClient, "--network", $network,
        "--label", "next.stabil.owner=$owner", "--label", "next.stabil.purpose=r03-isolated-proof",
        "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--entrypoint", "sleep", $ClientImage, "1800") | Out-Null
    $created.Add("container:$sourceClient")

    $internal = (& docker.exe network inspect $network --format '{{.Internal}}').Trim()
    $labels = ((& docker.exe network inspect $network --format '{{json .Labels}}') -join "") | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $internal -ne "true" -or [string]$labels.'next.stabil.owner' -ne $owner) { throw "synthetic_network_not_internal" }
    foreach ($container in @($sourcePostgres, $targetPostgres, $sourceQdrant, $sourceClient)) { Assert-NoPortsAndOwnedNetwork $container }

    foreach ($container in @($sourcePostgres, $targetPostgres)) {
        $ready = $false
        for ($attempt = 0; $attempt -lt 90; $attempt++) {
            & docker.exe exec $container pg_isready -U postgres -d ai_lab *> $null
            if ($LASTEXITCODE -eq 0) { $ready = $true; break }
            Start-Sleep -Milliseconds 500
        }
        if (-not $ready) { throw "synthetic_postgres_health_timeout" }
    }

    $sql = @"
CREATE TABLE alembic_version(version_num varchar(255) PRIMARY KEY);
INSERT INTO alembic_version VALUES ('followup_assistant_chat_history_20260829');
CREATE TABLE clients(id integer PRIMARY KEY);
CREATE TABLE users(id integer PRIMARY KEY);
CREATE TABLE documents(id integer PRIMARY KEY);
CREATE TABLE work_items(id integer PRIMARY KEY);
CREATE TABLE projects(id integer PRIMARY KEY);
CREATE TABLE change_history_events(id integer PRIMARY KEY);
INSERT INTO clients VALUES (1);
INSERT INTO users VALUES (1);
INSERT INTO documents VALUES (1);
INSERT INTO work_items VALUES (1);
INSERT INTO projects VALUES (1);
INSERT INTO change_history_events VALUES (1);
"@
    Invoke-Docker @("exec", $sourcePostgres, "psql", "-U", "postgres", "-d", "ai_lab", "-v", "ON_ERROR_STOP=1", "-c", $sql) | Out-Null
    Invoke-Docker @("exec", $sourcePostgres, "pg_dump", "-U", "postgres", "-d", "ai_lab", "--format=custom", "--no-owner", "--file=/tmp/postgres.dump") | Out-Null
    Invoke-Docker @("cp", "${sourcePostgres}:/tmp/postgres.dump", (Join-Path $checkpoint "artifacts\postgres.dump")) | Out-Null

    $qdrantSetup = @'
import json, time, urllib.request
base = "http://REPLACE_QDRANT:6333"
def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))
for _ in range(90):
    try:
        with urllib.request.urlopen(base + "/", timeout=2) as response:
            response.read()
        break
    except Exception:
        time.sleep(0.5)
else:
    raise SystemExit("qdrant health timeout")
results = {}
for index, name in enumerate(["ai_lab_document_chunks", "ai_lab_knowledge_base_chunks"], 1):
    call("PUT", "/collections/" + name, {"vectors": {"size": 4, "distance": "Cosine"}})
    call("PUT", "/collections/" + name + "/points?wait=true", {"points": [{"id": index, "vector": [0.1, 0.2, 0.3, 0.4], "payload": {"fixture": "r03-a1-synthetic"}}]})
    results[name] = call("POST", "/collections/" + name + "/snapshots")["result"]["name"]
print(json.dumps(results, separators=(",", ":")))
'@.Replace('REPLACE_QDRANT', $sourceQdrant)
    $snapshotNamesJson = Invoke-DockerCapture @("exec", $sourceClient, "python", "-c", (Convert-ToPythonCommand $qdrantSetup))
    $snapshotNames = $snapshotNamesJson | ConvertFrom-Json
    $qdrantRecords = @()
    foreach ($collection in @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks")) {
        $snapshotName = [string]$snapshotNames.$collection
        if ([string]::IsNullOrWhiteSpace($snapshotName)) { throw "synthetic_snapshot_name_missing" }
        $relative = "artifacts/qdrant/$collection.snapshot"
        Invoke-Docker @("cp", "${sourceQdrant}:/qdrant/snapshots/$collection/$snapshotName", (Join-Path $checkpoint ($relative.Replace('/', '\')))) | Out-Null
        $qdrantRecords += [ordered]@{
            collection = $collection; artifact_file = $relative; snapshot_name = $snapshotName
            points_count = 1; indexed_vectors_count = 1; segments_count = 1
            vectors = [ordered]@{ size = 4; distance = "Cosine" }
            aliases = @(); structurally_valid = $true; structural_validation_reason = "valid"
            restore_status = "NOT_RUN_WAITING_APPROVAL"; restore_verified = $false
        }
    }

    $fixture = Join-Path $tempRoot "fixture"
    foreach ($relative in @("documents\fixture.bin", "document-pages\fixture.bin", "document-assets\fixture.bin", "archive-extracted\fixture.bin", "release-channel\stable\manifest.json", "configuration\runtime-images.json")) {
        $path = Join-Path $fixture $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
        'synthetic' | Set-Content -LiteralPath $path -Encoding UTF8
    }
    New-Archive (Join-Path $checkpoint "artifacts\document-storage.tar.gz") $fixture @("documents", "document-pages", "document-assets", "archive-extracted")
    New-Archive (Join-Path $checkpoint "artifacts\release-stable.tar.gz") $fixture @("release-channel/stable")
    New-Archive (Join-Path $checkpoint "artifacts\configuration.tar.gz") $fixture @("configuration")
    '[]' | Set-Content -LiteralPath (Join-Path $checkpoint "artifacts\n8n-workflows.json") -Encoding UTF8
    '[]' | Set-Content -LiteralPath (Join-Path $checkpoint "artifacts\n8n-credentials.encrypted.json") -Encoding UTF8
    [ordered]@{ schema = "NEXT_STABIL_RUNTIME_INVENTORY_V1"; contains_secret_values = $false; synthetic = $true } |
        ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $checkpoint "artifacts\runtime-inventory.json") -Encoding UTF8
    $artifactPaths = @(
        "artifacts/postgres.dump", "artifacts/document-storage.tar.gz", "artifacts/release-stable.tar.gz",
        "artifacts/n8n-workflows.json", "artifacts/n8n-credentials.encrypted.json", "artifacts/configuration.tar.gz",
        "artifacts/runtime-inventory.json", "artifacts/qdrant/ai_lab_document_chunks.snapshot",
        "artifacts/qdrant/ai_lab_knowledge_base_chunks.snapshot"
    )
    $manifest = [ordered]@{
        schema_version = "NEXT_STABIL_BACKUP_V2"; scope = "full"; app_version = "1.0.2+29"
        created_at = (Get-Date).ToUniversalTime().ToString("o"); source_head = ("a" * 40); tool_source_head = ("b" * 40)
        db_revision = "followup_assistant_chat_history_20260829"; qdrant_collections = $qdrantRecords
        required_qdrant_collections = @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks")
        artifact_hash_verified = $true; qdrant_snapshot_structurally_valid = $true
        qdrant_restore_verified = $false; qdrant_restore_error_code = "qdrant_restore_not_run_waiting_approval"
        capture_status = "COMPLETE"; scope_status = "COMPLETE"; provenance_status = "RECORDED"
        consistency_status = "SYNTHETIC_FIXTURE"; restore_status = "NOT_RUN_WAITING_APPROVAL"
        escrow_status = "NOT_APPLICABLE_SYNTHETIC"; rto_status = "NOT_MEASURED"
        secrets_in_protected_backup = $false; artifacts = @($artifactPaths | ForEach-Object { Add-Artifact $_ })
    }
    $manifest | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $checkpoint "backup-manifest.json") -Encoding UTF8

    $validate = @(& powershell.exe -NoProfile -NonInteractive -File $restore -CheckpointPath $checkpoint -Mode Full -ValidateOnly 2>&1)
    if ($LASTEXITCODE -ne 0 -or ($validate -join "`n") -notmatch '"capture_complete":true') { throw "synthetic_checkpoint_validation_failed" }
    $proof = @(& powershell.exe -NoProfile -NonInteractive -File $restore -CheckpointPath $checkpoint -Mode Full -ProofOnly `
        -OperationId $token -ProofPostgresContainer $targetPostgres -ProofPostgresUser postgres `
        -ProofTargetOwner $owner -ProofQdrantClientImage $ClientImage -ProofStateRoot $stateRoot 2>&1)
    if ($LASTEXITCODE -ne 0 -or ($proof -join "`n") -notmatch 'RECOVERY_FINAL_STATUS=PASS') {
        throw ("synthetic_full_proof_failed:" + (($proof | Select-Object -Last 5) -join "|"))
    }
    foreach ($index in 1..2) {
        $proofOwner = "$owner-qdrant-$index"
        $leftovers = @(& docker.exe ps -a --filter "label=next.stabil.owner=$proofOwner" --format '{{.Names}}')
        if ($LASTEXITCODE -ne 0 -or $leftovers.Count -ne 0) { throw "synthetic_qdrant_proof_cleanup_failed" }
    }
    Write-Output "SYNTHETIC_PROOF_ISOLATION=INTERNAL_NETWORK_NO_HOST_PORTS"
    Write-Output "SYNTHETIC_PROOF_RESULT=PASS"
}
finally {
    foreach ($container in @($sourceClient, $sourceQdrant, $targetPostgres, $sourcePostgres)) {
        if ($created -contains "container:$container") { & docker.exe rm -f $container 2>$null | Out-Null }
    }
    foreach ($volume in @($sourceQdrantVolume, $targetPostgresVolume, $sourcePostgresVolume)) {
        if ($created -contains "volume:$volume") { & docker.exe volume rm $volume 2>$null | Out-Null }
    }
    if ($created -contains "network:$network") { & docker.exe network rm $network 2>$null | Out-Null }
    if (Test-Path -LiteralPath $tempRoot) {
        $resolved = [IO.Path]::GetFullPath($tempRoot)
        $temp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        if ($resolved.StartsWith($temp, [StringComparison]::OrdinalIgnoreCase) -and (Split-Path -Leaf $resolved) -eq $owner) {
            Remove-Item -LiteralPath $resolved -Recurse -Force
        }
    }
}
