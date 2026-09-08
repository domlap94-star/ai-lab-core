[CmdletBinding()]
param(
    [switch]$RunDockerProof,
    [string]$PostgresImage = "",
    [string]$QdrantImage = "",
    [string]$ClientImage = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$restore = Join-Path $repo "operations\hardening\restore-checkpoint.ps1"
$backup = Join-Path $repo "operations\hardening\backup-production.ps1"
$offline = Join-Path $repo "operations\hardening\verify-qdrant-snapshot-offline.ps1"
$root = Join-Path ([IO.Path]::GetTempPath()) ("next-stabil-r03-a1-unit-" + [Guid]::NewGuid().ToString("N"))
$passed = 0

function Assert-True {
    param([bool]$Condition, [string]$Name)
    if (-not $Condition) { throw "ASSERT_FAILED:$Name" }
    $script:passed++
    Write-Output "PASS $Name"
}

function Invoke-Recovery {
    param([string[]]$Arguments)
    $prior = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& powershell.exe -NoProfile -NonInteractive -File $restore @Arguments 2>&1)
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $prior }
    return [ordered]@{ exit_code = $code; text = ($output -join "`n") }
}

function Add-Artifact {
    param([string]$Checkpoint, [string]$Relative)
    $path = Join-Path $Checkpoint ($Relative.Replace('/', '\'))
    $item = Get-Item -LiteralPath $path
    return [ordered]@{
        file = $Relative
        bytes = [int64]$item.Length
        sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

function New-FakeQdrantSnapshot {
    param([string]$Destination)
    $source = Join-Path $root ("qdrant-fixture-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path (Join-Path $source "0") | Out-Null
    '{}' | Set-Content -LiteralPath (Join-Path $source "config.json") -Encoding UTF8
    '1.18.3' | Set-Content -LiteralPath (Join-Path $source "version.info") -Encoding UTF8
    '{}' | Set-Content -LiteralPath (Join-Path $source "0\shard_config.json") -Encoding UTF8
    & tar.exe -cf $Destination -C $source config.json version.info 0/shard_config.json
    if ($LASTEXITCODE -ne 0) { throw "fixture_tar_failed" }
}

function New-Archive {
    param([string]$Destination, [string]$Entry)
    $source = Join-Path $root ("archive-fixture-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path (Join-Path $source (Split-Path -Parent $Entry)) -Force | Out-Null
    'synthetic' | Set-Content -LiteralPath (Join-Path $source $Entry) -Encoding UTF8
    & tar.exe -czf $Destination -C $source $Entry.Replace('\', '/')
    if ($LASTEXITCODE -ne 0) { throw "fixture_archive_failed" }
}

function New-StorageArchive {
    param([string]$Destination, [switch]$HistoricalFourDomains)
    $source = Join-Path $root ("storage-fixture-" + [Guid]::NewGuid().ToString("N"))
    $domains = @("documents", "document-pages", "document-assets", "archive-extracted")
    if (-not $HistoricalFourDomains) { $domains += "knowledge-base" }
    foreach ($domain in $domains) {
        $directory = Join-Path $source $domain
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
        'synthetic' | Set-Content -LiteralPath (Join-Path $directory "fixture.txt") -Encoding UTF8
    }
    & tar.exe -czf $Destination -C $source @($domains)
    if ($LASTEXITCODE -ne 0) { throw "fixture_storage_archive_failed" }
}

function New-V2Checkpoint {
    param([string]$Name, [switch]$HistoricalWithoutStorageCoverage)
    $checkpoint = Join-Path $root $Name
    $artifactRoot = Join-Path $checkpoint "artifacts"
    $qdrantRoot = Join-Path $artifactRoot "qdrant"
    New-Item -ItemType Directory -Path $qdrantRoot -Force | Out-Null
    [IO.File]::WriteAllBytes((Join-Path $artifactRoot "postgres.dump"), [Text.Encoding]::ASCII.GetBytes("PGDMPsynthetic"))
    New-StorageArchive (Join-Path $artifactRoot "document-storage.tar.gz") -HistoricalFourDomains:$HistoricalWithoutStorageCoverage
    New-Archive (Join-Path $artifactRoot "release-stable.tar.gz") "release-channel\stable\manifest.json"
    New-Archive (Join-Path $artifactRoot "configuration.tar.gz") "configuration\runtime-images.json"
    '[]' | Set-Content -LiteralPath (Join-Path $artifactRoot "n8n-workflows.json") -Encoding UTF8
    '[]' | Set-Content -LiteralPath (Join-Path $artifactRoot "n8n-credentials.encrypted.json") -Encoding UTF8
    '{"schema":"NEXT_STABIL_RUNTIME_INVENTORY_V1","contains_secret_values":false}' | Set-Content -LiteralPath (Join-Path $artifactRoot "runtime-inventory.json") -Encoding UTF8
    $records = @()
    foreach ($collection in @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks")) {
        $relative = "artifacts/qdrant/$collection.snapshot"
        New-FakeQdrantSnapshot (Join-Path $checkpoint ($relative.Replace('/', '\')))
        $records += [ordered]@{
            collection = $collection; artifact_file = $relative; snapshot_name = "synthetic.snapshot"
            points_count = 1; indexed_vectors_count = 1; segments_count = 1
            vectors = [ordered]@{ size = 4; distance = "Cosine" }
            aliases = @(); structurally_valid = $true; structural_validation_reason = "valid"
            restore_status = "NOT_RUN_WAITING_APPROVAL"; restore_verified = $false
        }
    }
    $artifacts = @(
        Add-Artifact $checkpoint "artifacts/postgres.dump"
        Add-Artifact $checkpoint "artifacts/document-storage.tar.gz"
        Add-Artifact $checkpoint "artifacts/release-stable.tar.gz"
        Add-Artifact $checkpoint "artifacts/n8n-workflows.json"
        Add-Artifact $checkpoint "artifacts/n8n-credentials.encrypted.json"
        Add-Artifact $checkpoint "artifacts/configuration.tar.gz"
        Add-Artifact $checkpoint "artifacts/runtime-inventory.json"
        Add-Artifact $checkpoint "artifacts/qdrant/ai_lab_document_chunks.snapshot"
        Add-Artifact $checkpoint "artifacts/qdrant/ai_lab_knowledge_base_chunks.snapshot"
    )
    $manifest = [ordered]@{
        schema_version = "NEXT_STABIL_BACKUP_V2"; scope = "full"; app_version = "1.0.2+29"
        created_at = (Get-Date).ToUniversalTime().ToString("o"); source_head = ("a" * 40)
        tool_source_head = ("b" * 40); db_revision = "followup_assistant_chat_history_20260829"
        qdrant_collections = $records; required_qdrant_collections = @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks")
        artifact_hash_verified = $true; qdrant_snapshot_structurally_valid = $true
        qdrant_restore_verified = $false; qdrant_restore_error_code = "qdrant_restore_not_run_waiting_approval"
        document_directories = if ($HistoricalWithoutStorageCoverage) {
            @("documents", "document-pages", "document-assets", "archive-extracted")
        } else {
            @("documents", "document-pages", "document-assets", "archive-extracted", "knowledge-base")
        }
        capture_status = "COMPLETE"; scope_status = "COMPLETE"; provenance_status = "RECORDED"
        consistency_status = "COMPONENT_WINDOWS_RECORDED_NON_TRANSACTIONAL"
        restore_status = "NOT_RUN_WAITING_APPROVAL"; escrow_status = "NOT_RUN_WAITING_OWNER_DECISION"
        rto_status = "NOT_MEASURED"; secrets_in_protected_backup = $false; artifacts = $artifacts
    }
    if (-not $HistoricalWithoutStorageCoverage) {
        $manifest.storage_contract_version = "NEXT_STABIL_STORAGE_COVERAGE_V1"
        $manifest.storage_coverage = [ordered]@{
            status = "COMPLETE"
            required_domains = @("documents", "document-pages", "document-assets", "archive-extracted", "knowledge-base")
            domains = @(
                @("documents", "document-pages", "document-assets", "archive-extracted", "knowledge-base") |
                    ForEach-Object { [ordered]@{ directory = $_; file_count = [int64]1; bytes = [int64]12 } }
            )
            knowledge_base = [ordered]@{
                status = "COMPLETE"; reference_state = "COMPLETE"
                reference_count = [int64]1; matched_reference_count = [int64]1
                unique_referenced_file_count = [int64]1; storage_file_count = [int64]1
                storage_bytes = [int64]12; unreferenced_file_count = [int64]0
                missing_count = [int64]0; unreadable_count = [int64]0; outside_root_count = [int64]0
                size_mismatch_count = [int64]0; hash_mismatch_count = [int64]0
                reference_inventory_sha256 = ("e" * 64); storage_inventory_sha256 = ("f" * 64)
            }
        }
    }
    $manifest | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $checkpoint "backup-manifest.json") -Encoding UTF8
    return $checkpoint
}

function New-LegacyV1Checkpoint {
    param(
        [string]$Name,
        [ValidateSet("database", "full")]
        [string]$Scope,
        [bool]$QdrantRestoreVerified,
        [switch]$IncludeLaterStatusProperties
    )
    $checkpoint = Join-Path $root $Name
    $artifactRoot = Join-Path $checkpoint "artifacts"
    New-Item -ItemType Directory -Path $artifactRoot -Force | Out-Null
    [IO.File]::WriteAllBytes((Join-Path $artifactRoot "postgres.dump"), [Text.Encoding]::ASCII.GetBytes("PGDMPsynthetic-historical-v1"))
    $artifacts = @(Add-Artifact $checkpoint "artifacts/postgres.dump")
    if ($Scope -eq "full") {
        New-Archive (Join-Path $artifactRoot "document-storage.tar.gz") "documents\fixture.txt"
        New-Archive (Join-Path $artifactRoot "release-stable.tar.gz") "release-channel\stable\manifest.json"
        New-FakeQdrantSnapshot (Join-Path $artifactRoot "qdrant.snapshot")
        '[]' | Set-Content -LiteralPath (Join-Path $artifactRoot "n8n-workflows.json") -Encoding UTF8
        '[]' | Set-Content -LiteralPath (Join-Path $artifactRoot "n8n-credentials.encrypted.json") -Encoding UTF8
        New-Archive (Join-Path $artifactRoot "configuration.tar.gz") "configuration\runtime-images.json"
        $artifacts = @(
            Add-Artifact $checkpoint "artifacts/postgres.dump"
            Add-Artifact $checkpoint "artifacts/document-storage.tar.gz"
            Add-Artifact $checkpoint "artifacts/release-stable.tar.gz"
            Add-Artifact $checkpoint "artifacts/qdrant.snapshot"
            Add-Artifact $checkpoint "artifacts/n8n-workflows.json"
            Add-Artifact $checkpoint "artifacts/n8n-credentials.encrypted.json"
            Add-Artifact $checkpoint "artifacts/configuration.tar.gz"
        )
    }
    $manifest = [ordered]@{
        schema_version = "NEXT_STABIL_BACKUP_V1"; scope = $Scope
        run_id = $null; schedule_id = $null; trigger = "manual"
        app_version = "1.0.2+21"; created_at = "2026-08-21T00:00:00Z"
        source_head = ("c" * 40); release = "1.0.2+21"
        db_revision = "followup_admin_backup_restore_ui_20260821"
        qdrant_collection = "ai_lab_document_chunks"
        qdrant_snapshot_name = $(if ($Scope -eq "full") { "synthetic.snapshot" } else { $null })
        artifact_hash_verified = $true
        qdrant_snapshot_structurally_valid = $(if ($Scope -eq "full") { $true } else { $null })
        qdrant_snapshot_validation_reason = $(if ($Scope -eq "full") { "valid" } else { $null })
        qdrant_restore_verified = $(if ($Scope -eq "full") { $QdrantRestoreVerified } else { $null })
        qdrant_restore_result = $(if ($Scope -eq "full" -and $QdrantRestoreVerified) {
            [ordered]@{ points = 1; dimensions = 4; distance = "Cosine" }
        } else { $null })
        qdrant_restore_error_code = $(if ($Scope -eq "full" -and -not $QdrantRestoreVerified) { "qdrant_restore_drill_failed" } else { $null })
        document_directories = $(if ($Scope -eq "full") { @("documents", "document-pages", "document-assets", "archive-extracted") } else { @() })
        estimated_source_bytes = [int64]0
        secrets_in_protected_backup = $false
        secrets_note = "Synthetic historical V1 compatibility fixture."
        artifacts = $artifacts
    }
    if ($IncludeLaterStatusProperties) {
        foreach ($name in @("capture_status", "scope_status", "provenance_status", "consistency_status", "restore_status")) {
            $manifest[$name] = $null
        }
    }
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $checkpoint "backup-manifest.json") -Encoding UTF8
    return $checkpoint
}

function Test-RealWriterWithSyntheticBoundaries {
    $source = Join-Path $root "writer-source"
    $backupRoot = Join-Path $root "writer-backups"
    $runtimeInventory = Join-Path $root "writer-runtime-inventory.json"
    New-Item -ItemType Directory -Path $source, $backupRoot | Out-Null
    foreach ($relative in @(
        "data\documents\fixture.bin", "data\document-pages\fixture.bin",
        "data\document-assets\fixture.bin", "data\archive-extracted\fixture.bin",
        "data\knowledge-base\fixture-kb.bin",
        "release-channel\stable\manifest.json", "compose.yaml",
        "compose\backend\docker-compose.yml", "compose\postgres\docker-compose.yml",
        "compose\qdrant\docker-compose.yml", "compose\ollama\docker-compose.yml",
        "compose\n8n\docker-compose.yml", "compose\open-webui\docker-compose.yml",
        "backend\Dockerfile", "backend\requirements.txt"
    )) {
        $path = Join-Path $source $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
        '{}' | Set-Content -LiteralPath $path -Encoding UTF8
    }
    [ordered]@{
        schema = "NEXT_STABIL_RUNTIME_INVENTORY_V1"; contains_secret_values = $false
        captured_at = (Get-Date).ToUniversalTime().ToString("o"); components = @()
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $runtimeInventory -Encoding UTF8
    $snapshotFixture = Join-Path $root "writer-qdrant.snapshot"
    New-FakeQdrantSnapshot $snapshotFixture
    $global:R03A1MockCommands = New-Object Collections.Generic.List[string]
    $global:R03A1MockSnapshotCounter = 0
    $global:R03A1RecoveryRoot = $repo
    $global:R03A1FailKnowledgeSnapshot = $false
    $kbFixture = Join-Path $source "data\knowledge-base\fixture-kb.bin"
    [IO.File]::WriteAllBytes($kbFixture, [Text.Encoding]::ASCII.GetBytes("AAAA"))
    $kbRecord = [ordered]@{
        storage_path = $kbFixture
        file_size = [int64](Get-Item -LiteralPath $kbFixture).Length
        checksum_sha256 = (Get-FileHash -LiteralPath $kbFixture -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $global:R03A1KnowledgeBaseInventory = '[' + ($kbRecord | ConvertTo-Json -Compress) + ']'
    $global:R03A1KnowledgeBaseInventoryOverrideAfterFirst = $null
    $global:R03A1KnowledgeBaseInventoryQueryCount = 0
    try {
        function global:Get-PSDrive {
            param([string]$Name, [string]$PSProvider)
            [pscustomobject]@{ Name = $Name; Free = [int64]100GB }
        }
        function global:git {
            param([Parameter(ValueFromRemainingArguments = $true)][object[]]$Arguments)
            $global:R03A1MockCommands.Add("git " + ($Arguments -join " "))
            if (($Arguments -join " ") -match [regex]::Escape($global:R03A1RecoveryRoot)) { "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" }
            else { "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
            $global:LASTEXITCODE = 0
        }
        function global:icacls.exe {
            param([Parameter(ValueFromRemainingArguments = $true)][object[]]$Arguments)
            $global:R03A1MockCommands.Add("icacls " + ($Arguments -join " ")); $global:LASTEXITCODE = 0
        }
        function global:tar.exe {
            param([Parameter(ValueFromRemainingArguments = $true)][object[]]$Arguments)
            $global:R03A1MockCommands.Add("tar " + ($Arguments -join " "))
            & "$env:SystemRoot\System32\tar.exe" @Arguments
            $global:LASTEXITCODE = $LASTEXITCODE
        }
        function global:node.exe {
            param([Parameter(ValueFromRemainingArguments = $true)][object[]]$Arguments)
            $global:R03A1MockCommands.Add("node " + ($Arguments -join " "))
            '{"valid":true,"reason":"valid"}'; $global:LASTEXITCODE = 0
        }
        function global:curl.exe {
            param([Parameter(ValueFromRemainingArguments = $true)][object[]]$Arguments)
            $global:R03A1MockCommands.Add("curl " + ($Arguments -join " "))
            $index = [Array]::IndexOf($Arguments, "--output")
            if ($index -lt 0) { throw "mock_curl_output_missing" }
            Copy-Item -LiteralPath $snapshotFixture -Destination ([string]$Arguments[$index + 1])
            $global:LASTEXITCODE = 0
        }
        function global:docker.exe {
            param([Parameter(ValueFromRemainingArguments = $true)][object[]]$Arguments)
            $global:R03A1MockCommands.Add("docker " + ($Arguments -join " "))
            $joined = $Arguments -join " "
            if ($Arguments[0] -eq "cp") {
                $destination = [string]$Arguments[-1]
                if ([string]$Arguments[1] -match '^postgres:') { [IO.File]::WriteAllBytes($destination, [Text.Encoding]::ASCII.GetBytes("PGDMPwriter")) }
                elseif ([string]$Arguments[1] -match '^n8n:') { '[]' | Set-Content -LiteralPath $destination -Encoding UTF8 }
            } elseif ($Arguments[0] -eq "inspect" -and $Arguments.Count -eq 4 -and [string]$Arguments[2] -eq "--format") {
                if ([string]$Arguments[3] -eq '{{.Config.Image}}') { "synthetic/image@sha256:" + ("2" * 64) }
                elseif ([string]$Arguments[3] -eq '{{.Image}}') { "sha256:" + ("1" * 64) }
                else { throw "mock_docker_inspect_format_unexpected" }
            } elseif ($Arguments[0] -eq "image" -and $Arguments[1] -eq "inspect") {
                '["synthetic/image@sha256:' + ("2" * 64) + '"]'
            } elseif ($joined -match 'knowledge_base_items') {
                $global:R03A1KnowledgeBaseInventoryQueryCount++
                if ($global:R03A1KnowledgeBaseInventoryQueryCount -gt 1 -and
                    $null -ne $global:R03A1KnowledgeBaseInventoryOverrideAfterFirst) {
                    $global:R03A1KnowledgeBaseInventoryOverrideAfterFirst
                } else { $global:R03A1KnowledgeBaseInventory }
            } elseif ($joined -match 'SELECT version_num FROM alembic_version') {
                "followup_assistant_chat_history_20260829"
            }
            $global:LASTEXITCODE = 0
        }
        function global:docker {
            param([Parameter(ValueFromRemainingArguments = $true)][object[]]$Arguments)
            docker.exe @Arguments
        }
        function global:Invoke-RestMethod {
            param([string]$Method = "Get", [string]$Uri, [int]$TimeoutSec)
            $global:R03A1MockCommands.Add("rest $Method $Uri")
            if ($Uri -match '/aliases$') { return [pscustomobject]@{ status = "ok"; result = [pscustomobject]@{ aliases = @() } } }
            if ($Method -eq "Post") {
                if ($global:R03A1FailKnowledgeSnapshot -and $Uri -match 'ai_lab_knowledge_base_chunks') {
                    return [pscustomobject]@{ status = "error"; result = $null }
                }
                $global:R03A1MockSnapshotCounter++
                return [pscustomobject]@{ status = "ok"; result = [pscustomobject]@{ name = "synthetic-$($global:R03A1MockSnapshotCounter).snapshot"; creation_time = "2026-09-08T00:00:00Z" } }
            }
            return [pscustomobject]@{
                status = "ok"
                result = [pscustomobject]@{
                    points_count = 1; indexed_vectors_count = 1; segments_count = 1
                    config = [pscustomobject]@{ params = [pscustomobject]@{ vectors = [pscustomobject]@{ size = 4; distance = "Cosine" }; shard_number = 1; replication_factor = 1; write_consistency_factor = 1; on_disk_payload = $true } }
                }
            }
        }

        $writerOutput = @(& $backup -RepositoryRoot $source -BackupRoot $backupRoot -Release "1.0.2+29" `
            -ManifestFormat RecoveryPointV2 -QdrantProofMode CaptureOnly `
            -QdrantCollections @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks") `
            -CheckpointId "20990101T000000Z" -RuntimeInventoryPath $runtimeInventory)
        Assert-True ($LASTEXITCODE -eq 0 -and ($writerOutput -join "`n") -match 'BACKUP_COMPLETE=') "real_writer_v2_completes_with_synthetic_boundaries"
        $checkpoint = Join-Path $backupRoot "20990101T000000Z"
        $manifest = Get-Content -LiteralPath (Join-Path $checkpoint "backup-manifest.json") -Raw | ConvertFrom-Json
        Assert-True ($manifest.schema_version -eq "NEXT_STABIL_BACKUP_V2" -and @($manifest.qdrant_collections).Count -eq 2) "real_writer_binds_two_collections"
        Assert-True ($manifest.tool_source_head -eq ("b" * 40) -and $manifest.source_head -eq ("a" * 40)) "real_writer_records_tool_and_data_source_separately"
        Assert-True ($manifest.restore_status -eq "NOT_RUN_WAITING_APPROVAL" -and $manifest.qdrant_restore_verified -eq $false) "real_writer_does_not_claim_restore"
        Assert-True (-not (($global:R03A1MockCommands -join "`n") -match 'verify-qdrant-snapshot-restore')) "real_writer_capture_never_calls_restore_helper"
        Assert-True (@($manifest.document_directories) -contains "knowledge-base") "real_writer_declares_kb_source_domain"
        Assert-True ($manifest.storage_contract_version -eq "NEXT_STABIL_STORAGE_COVERAGE_V1" -and
            $manifest.storage_coverage.status -eq "COMPLETE" -and
            $manifest.storage_coverage.knowledge_base.reference_count -eq 1 -and
            $manifest.storage_coverage.knowledge_base.matched_reference_count -eq 1) "real_writer_records_verified_kb_source_coverage"
        $storageEntries = @(& "$env:SystemRoot\System32\tar.exe" -tzf (Join-Path $checkpoint "artifacts\document-storage.tar.gz"))
        Assert-True ($LASTEXITCODE -eq 0 -and @($storageEntries | Where-Object { ([string]$_).Replace('\','/') -eq 'knowledge-base/fixture-kb.bin' }).Count -eq 1) "real_writer_archives_kb_source_file"

        $commandsBeforeCollision = $global:R03A1MockCommands.Count
        $collision = $null
        try {
            & $backup -RepositoryRoot $source -BackupRoot $backupRoot -Release "1.0.2+29" `
                -ManifestFormat RecoveryPointV2 -QdrantProofMode CaptureOnly `
                -QdrantCollections @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks") `
                -CheckpointId "20990101T000000Z" -RuntimeInventoryPath $runtimeInventory | Out-Null
        } catch { $collision = $_.Exception.Message }
        Assert-True ($collision -eq "backup_checkpoint_collision") "writer_checkpoint_collision_rejected"
        Assert-True ($global:R03A1MockCommands.Count -eq $commandsBeforeCollision) "collision_rejected_before_external_capture_commands"

        $global:R03A1KnowledgeBaseInventory = '[{"storage_path":"Z:\\missing-kb-source.bin","file_size":4,"checksum_sha256":"' + ("a" * 64) + '"}]'
        $missingReferenceError = $null
        try {
            & $backup -RepositoryRoot $source -BackupRoot $backupRoot -Release "1.0.2+29" `
                -ManifestFormat RecoveryPointV2 -QdrantProofMode CaptureOnly `
                -QdrantCollections @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks") `
                -CheckpointId "20990101T000002Z" -RuntimeInventoryPath $runtimeInventory | Out-Null
        } catch { $missingReferenceError = $_.Exception.Message }
        Assert-True ($missingReferenceError -eq "knowledge_base_reference_outside_root" -and
            -not (Test-Path -LiteralPath (Join-Path $backupRoot "20990101T000002Z"))) "kb_reference_outside_root_rejected_before_capture"

        $global:R03A1KnowledgeBaseInventory = '[{"storage_path":"' + ($kbFixture.Replace('\','\\')) + '-missing","file_size":4,"checksum_sha256":"' + ("a" * 64) + '"}]'
        $missingFileError = $null
        try {
            & $backup -RepositoryRoot $source -BackupRoot $backupRoot -Release "1.0.2+29" `
                -ManifestFormat RecoveryPointV2 -QdrantProofMode CaptureOnly `
                -QdrantCollections @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks") `
                -CheckpointId "20990101T000003Z" -RuntimeInventoryPath $runtimeInventory | Out-Null
        } catch { $missingFileError = $_.Exception.Message }
        Assert-True ($missingFileError -eq "knowledge_base_reference_missing" -and
            -not (Test-Path -LiteralPath (Join-Path $backupRoot "20990101T000003Z"))) "missing_kb_source_rejected_before_capture"

        $sizeMismatchRecord = [ordered]@{
            storage_path = $kbFixture; file_size = [int64]5
            checksum_sha256 = [string]$kbRecord.checksum_sha256
        }
        $global:R03A1KnowledgeBaseInventory = '[' + ($sizeMismatchRecord | ConvertTo-Json -Compress) + ']'
        $sizeMismatchError = $null
        try {
            & $backup -RepositoryRoot $source -BackupRoot $backupRoot -Release "1.0.2+29" `
                -ManifestFormat RecoveryPointV2 -QdrantProofMode CaptureOnly `
                -QdrantCollections @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks") `
                -CheckpointId "20990101T000008Z" -RuntimeInventoryPath $runtimeInventory | Out-Null
        } catch { $sizeMismatchError = $_.Exception.Message }
        Assert-True ($sizeMismatchError -eq "knowledge_base_reference_size_mismatch" -and
            -not (Test-Path -LiteralPath (Join-Path $backupRoot "20990101T000008Z"))) "kb_source_size_mismatch_rejected"

        $global:R03A1KnowledgeBaseInventory = '[' + ($kbRecord | ConvertTo-Json -Compress) + ']'
        [IO.File]::WriteAllBytes($kbFixture, [Text.Encoding]::ASCII.GetBytes("BBBB"))
        $hashError = $null
        try {
            & $backup -RepositoryRoot $source -BackupRoot $backupRoot -Release "1.0.2+29" `
                -ManifestFormat RecoveryPointV2 -QdrantProofMode CaptureOnly `
                -QdrantCollections @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks") `
                -CheckpointId "20990101T000004Z" -RuntimeInventoryPath $runtimeInventory | Out-Null
        } catch { $hashError = $_.Exception.Message }
        Assert-True ($hashError -eq "knowledge_base_reference_hash_mismatch" -and
            -not (Test-Path -LiteralPath (Join-Path $backupRoot "20990101T000004Z"))) "same_size_kb_content_tamper_rejected"
        [IO.File]::WriteAllBytes($kbFixture, [Text.Encoding]::ASCII.GetBytes("AAAA"))

        Remove-Item -LiteralPath $kbFixture
        $global:R03A1KnowledgeBaseInventory = '[]'
        & $backup -RepositoryRoot $source -BackupRoot $backupRoot -Release "1.0.2+29" `
            -ManifestFormat RecoveryPointV2 -QdrantProofMode CaptureOnly `
            -QdrantCollections @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks") `
            -CheckpointId "20990101T000005Z" -RuntimeInventoryPath $runtimeInventory | Out-Null
        $emptyManifest = Get-Content -LiteralPath (Join-Path $backupRoot "20990101T000005Z\backup-manifest.json") -Raw | ConvertFrom-Json
        Assert-True ($emptyManifest.storage_coverage.knowledge_base.reference_count -eq 0 -and
            $emptyManifest.storage_coverage.knowledge_base.reference_state -eq "EMPTY_CONFIRMED") "empty_kb_corpus_is_explicitly_confirmed"
        [IO.File]::WriteAllBytes($kbFixture, [Text.Encoding]::ASCII.GetBytes("AAAA"))
        $global:R03A1KnowledgeBaseInventory = '[' + ($kbRecord | ConvertTo-Json -Compress) + ']'

        $junctionTarget = Join-Path $root "junction-target"
        $junctionPath = Join-Path $source "data\knowledge-base\unsafe-link"
        New-Item -ItemType Directory -Path $junctionTarget | Out-Null
        New-Item -ItemType Junction -Path $junctionPath -Target $junctionTarget | Out-Null
        $linkError = $null
        try {
            & $backup -RepositoryRoot $source -BackupRoot $backupRoot -Release "1.0.2+29" `
                -ManifestFormat RecoveryPointV2 -QdrantProofMode CaptureOnly `
                -QdrantCollections @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks") `
                -CheckpointId "20990101T000006Z" -RuntimeInventoryPath $runtimeInventory | Out-Null
        } catch { $linkError = $_.Exception.Message }
        Remove-Item -LiteralPath $junctionPath -Force
        Assert-True ($linkError -eq "storage_domain_reparse_point_rejected:knowledge-base" -and
            -not (Test-Path -LiteralPath (Join-Path $backupRoot "20990101T000006Z"))) "kb_reparse_point_rejected_before_capture"

        $global:R03A1KnowledgeBaseInventoryQueryCount = 0
        $global:R03A1KnowledgeBaseInventoryOverrideAfterFirst = '[]'
        $changedInventoryError = $null
        try {
            & $backup -RepositoryRoot $source -BackupRoot $backupRoot -Release "1.0.2+29" `
                -ManifestFormat RecoveryPointV2 -QdrantProofMode CaptureOnly `
                -QdrantCollections @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks") `
                -CheckpointId "20990101T000007Z" -RuntimeInventoryPath $runtimeInventory | Out-Null
        } catch { $changedInventoryError = $_.Exception.Message }
        $global:R03A1KnowledgeBaseInventoryOverrideAfterFirst = $null
        Assert-True ($changedInventoryError -eq "knowledge_base_inventory_changed_during_capture" -and
            -not (Test-Path -LiteralPath (Join-Path $backupRoot "20990101T000007Z\backup-manifest.json"))) "kb_inventory_change_during_capture_prevents_complete_manifest"

        $global:R03A1FailKnowledgeSnapshot = $true
        $interruptedError = $null
        try {
            & $backup -RepositoryRoot $source -BackupRoot $backupRoot -Release "1.0.2+29" `
                -ManifestFormat RecoveryPointV2 -QdrantProofMode CaptureOnly `
                -QdrantCollections @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks") `
                -CheckpointId "20990101T000001Z" -RuntimeInventoryPath $runtimeInventory | Out-Null
        } catch { $interruptedError = $_.Exception.Message }
        $interruptedCheckpoint = Join-Path $backupRoot "20990101T000001Z"
        Assert-True ($interruptedError -eq "qdrant_snapshot_create_failed") "interrupted_capture_reports_exact_failure"
        Assert-True ((Test-Path -LiteralPath $interruptedCheckpoint -PathType Container) -and
            -not (Test-Path -LiteralPath (Join-Path $interruptedCheckpoint "backup-manifest.json") -PathType Leaf)) "interrupted_capture_never_writes_complete_manifest"
        return $checkpoint
    }
    finally {
        foreach ($name in @("Get-PSDrive", "git", "icacls.exe", "tar.exe", "node.exe", "curl.exe", "docker", "docker.exe", "Invoke-RestMethod")) {
            Remove-Item -LiteralPath ("function:" + $name) -Force -ErrorAction SilentlyContinue
        }
        Remove-Variable -Name R03A1MockCommands,R03A1MockSnapshotCounter,R03A1RecoveryRoot,R03A1FailKnowledgeSnapshot,R03A1KnowledgeBaseInventory,R03A1KnowledgeBaseInventoryOverrideAfterFirst,R03A1KnowledgeBaseInventoryQueryCount -Scope Global -ErrorAction SilentlyContinue
    }
}

function Test-ProofTargetGuardsWithMocks {
    param([string]$Checkpoint)
    $owner = "next-stabil-r03-a1-test-12345678"
    $container = "$owner-postgres"
    $network = "$owner-network"
    $stateRoot = Join-Path $root "$owner-state"
    $global:R03A1TargetGuardMode = "ports"
    $global:R03A1TargetGuardContainer = $container
    $global:R03A1TargetGuardNetwork = $network
    $global:R03A1TargetGuardOwner = $owner
    try {
        function global:docker.exe {
            param([Parameter(ValueFromRemainingArguments = $true)][object[]]$Arguments)
            $joined = $Arguments -join " "
            if ($Arguments[0] -eq "inspect") {
                if ($joined -match [regex]::Escape('{{.Name}}')) { "/$global:R03A1TargetGuardContainer" }
                elseif ($joined -match [regex]::Escape('{{json .Config.Labels}}')) { '{"next.stabil.owner":"' + $global:R03A1TargetGuardOwner + '","next.stabil.purpose":"r03-isolated-proof"}' }
                elseif ($joined -match [regex]::Escape('{{.HostConfig.Privileged}}')) { 'false' }
                elseif ($joined -match [regex]::Escape('{{json .HostConfig.PortBindings}}')) {
                    if ($global:R03A1TargetGuardMode -eq "ports") { '{"5432/tcp":[{"HostIp":"127.0.0.1","HostPort":"59999"}]}' } else { '{}' }
                }
                elseif ($joined -match [regex]::Escape('{{.HostConfig.NetworkMode}}')) { $global:R03A1TargetGuardNetwork }
                elseif ($joined -match [regex]::Escape('{{json .NetworkSettings.Networks}}')) { '{"' + $global:R03A1TargetGuardNetwork + '":{"NetworkID":"synthetic"}}' }
                elseif ($joined -match [regex]::Escape('{{json .Mounts}}')) { '[{"Type":"bind","Source":"C:\\\\unsafe","Destination":"/var/lib/postgresql/data","Name":""}]' }
            } elseif ($Arguments[0] -eq "network" -and $Arguments[1] -eq "inspect") {
                if ($joined -match [regex]::Escape('{{.Internal}}')) { 'true' }
                else { '{"next.stabil.owner":"' + $global:R03A1TargetGuardOwner + '"}' }
            }
            $global:LASTEXITCODE = 0
        }
        $portError = $null
        try {
            & $restore -CheckpointPath $Checkpoint -Mode Full -ProofOnly -ProofPostgresContainer $container `
                -ProofTargetOwner $owner -ProofQdrantClientImage ("sha256:" + ("d" * 64)) -ProofStateRoot $stateRoot | Out-Null
        } catch { $portError = $_.Exception.Message }
        Assert-True ($portError -eq "proof_target_host_ports_rejected") "proof_rejects_host_ports"
        Assert-True (-not (Test-Path -LiteralPath $stateRoot)) "host_port_rejection_precedes_state_write"

        $global:R03A1TargetGuardMode = "mount"
        $mountError = $null
        try {
            & $restore -CheckpointPath $Checkpoint -Mode Full -ProofOnly -ProofPostgresContainer $container `
                -ProofTargetOwner $owner -ProofQdrantClientImage ("sha256:" + ("d" * 64)) -ProofStateRoot $stateRoot | Out-Null
        } catch { $mountError = $_.Exception.Message }
        Assert-True ($mountError -eq "proof_target_mount_invalid") "proof_rejects_bind_mount"
        Assert-True (-not (Test-Path -LiteralPath $stateRoot)) "mount_rejection_precedes_state_write"
    }
    finally {
        Remove-Item -LiteralPath "function:docker.exe" -Force -ErrorAction SilentlyContinue
        Remove-Variable -Name R03A1TargetGuardMode,R03A1TargetGuardContainer,R03A1TargetGuardNetwork,R03A1TargetGuardOwner -Scope Global -ErrorAction SilentlyContinue
    }
}

try {
    New-Item -ItemType Directory -Path $root | Out-Null
    foreach ($scriptPath in @($backup, $restore, $offline)) {
        $tokens = $null; $errors = $null
        [void][Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$tokens, [ref]$errors)
        Assert-True (@($errors).Count -eq 0) ("parse_" + [IO.Path]::GetFileName($scriptPath))
    }

    $backupText = Get-Content -LiteralPath $backup -Raw
    $restoreText = Get-Content -LiteralPath $restore -Raw
    $offlineText = Get-Content -LiteralPath $offline -Raw
    Assert-True ($backupText -match 'RecoveryPointV2' -and $backupText -match 'QdrantCollections') "writer_v2_two_collection_contract"
    Assert-True ($backupText -match 'CaptureOnly' -and $backupText -match 'qdrant_restore_not_run_waiting_approval') "capture_mode_records_restore_not_run"
    Assert-True ($backupText -match '\$toolRoot.+qdrant_snapshot_validator' -and $backupText -match 'tool_source_head') "helper_identity_separate_from_data_source"
    Assert-True ($backupText -match 'Never open the' -and $backupText -notmatch 'Join-Path \$repo "\.env"') "capture_does_not_open_runtime_env"
    Assert-True ($backupText -match 'docker\.exe inspect \$containerName --format ''\{\{\.Config\.Image\}\}''') "image_inventory_uses_bounded_docker_fields"
    Assert-True ($backupText -notmatch '& docker inspect \$containerName \| ConvertFrom-Json') "image_inventory_does_not_materialize_container_environment"
    Assert-True ($backupText -match 'docker\.exe exec postgres psql' -and
        $backupText -match 'BEGIN TRANSACTION READ ONLY' -and $backupText -match 'knowledge_base_items') "kb_inventory_uses_bounded_read_only_database_query"
    Assert-True ($restoreText -match 'Assert-IsolatedPostgresTarget' -and $restoreText -notmatch 'docker\.exe exec postgres') "proof_has_explicit_postgres_target"
    Assert-True ($offlineText -match 'network.+create.+--internal' -and $offlineText -notmatch '127\.0\.0\.1:\$port' -and $offlineText -notmatch '"-p"') "qdrant_proof_has_no_host_port"
    Assert-True ($offlineText -match 'qdrant_restore_target_collision' -and $offlineText -match 'next\.stabil\.owner') "qdrant_proof_has_owned_collision_guard"
    $legacyReaderPaths = @(
        (Join-Path $repo "operations\hardening\verify-restore-checkpoint.ps1"),
        (Join-Path $repo "tools\windows-disaster-recovery\src\CheckpointValidator.cs"),
        (Join-Path $repo "operations\supervisor\server.js")
    )
    foreach ($legacyReader in $legacyReaderPaths) {
        $legacyText = Get-Content -LiteralPath $legacyReader -Raw
        Assert-True ($legacyText -match 'NEXT_STABIL_BACKUP_V1' -and $legacyText -notmatch 'NEXT_STABIL_BACKUP_V2') ("legacy_reader_refuses_v2_" + [IO.Path]::GetFileName($legacyReader))
    }

    $writerTestOutput = @(Test-RealWriterWithSyntheticBoundaries)
    $writerCheckpoint = [string]$writerTestOutput[-1]
    if ($writerTestOutput.Count -gt 1) { $writerTestOutput[0..($writerTestOutput.Count - 2)] | Write-Output }
    $writerReadResult = Invoke-Recovery @("-CheckpointPath", $writerCheckpoint, "-Mode", "Full", "-ValidateOnly")
    if ($writerReadResult.exit_code -ne 0) { Write-Output ("SYNTHETIC_READER_DIAGNOSTIC=" + $writerReadResult.text) }
    Assert-True ($writerReadResult.exit_code -eq 0 -and $writerReadResult.text -match '"capture_complete":true') "real_writer_output_is_accepted_by_real_reader"

    $historicalDatabase = New-LegacyV1Checkpoint "legacy-v1-historical-database" "database" $false
    $historicalDatabaseResult = Invoke-Recovery @("-CheckpointPath", $historicalDatabase, "-Mode", "Database", "-ValidateOnly")
    Assert-True ($historicalDatabaseResult.exit_code -eq 0 -and $historicalDatabaseResult.text -match 'RECOVERY_VALIDATION_JSON=') "historical_v1_database_without_later_status_fields_is_readable"
    Assert-True ($historicalDatabaseResult.text -match '"capture_complete":false' -and
        $historicalDatabaseResult.text -match '"capture_status":null' -and
        $historicalDatabaseResult.text -match '"restore_status":null') "historical_v1_missing_statuses_are_unknown_not_fabricated"

    $legacyWithNull = New-LegacyV1Checkpoint "legacy-v1-with-null-statuses" "database" $false -IncludeLaterStatusProperties
    $legacyWithNullResult = Invoke-Recovery @("-CheckpointPath", $legacyWithNull, "-Mode", "Database", "-ValidateOnly")
    Assert-True ($legacyWithNullResult.exit_code -eq 0 -and $legacyWithNullResult.text -match '"capture_status":null') "legacy_v1_with_explicit_null_statuses_remains_readable"

    $historicalFull = New-LegacyV1Checkpoint "legacy-v1-historical-full" "full" $true
    $historicalFullResult = Invoke-Recovery @("-CheckpointPath", $historicalFull, "-Mode", "Full", "-ValidateOnly")
    Assert-True ($historicalFullResult.exit_code -eq 0 -and $historicalFullResult.text -match '"full_eligible":true' -and
        $historicalFullResult.text -match '"capture_status":null') "historical_v1_full_with_prior_qdrant_proof_is_readable"

    $historicalFullNoProof = New-LegacyV1Checkpoint "legacy-v1-historical-full-no-proof" "full" $false
    $historicalFullNoProofResult = Invoke-Recovery @("-CheckpointPath", $historicalFullNoProof, "-Mode", "Full", "-ValidateOnly")
    Assert-True ($historicalFullNoProofResult.exit_code -ne 0 -and
        $historicalFullNoProofResult.text -match 'qdrant_restore_verification_required') "historical_v1_full_without_qdrant_proof_remains_rejected"

    $v2 = New-V2Checkpoint "v2-valid"
    $v2Result = Invoke-Recovery @("-CheckpointPath", $v2, "-Mode", "Full", "-ValidateOnly")
    Assert-True ($v2Result.exit_code -eq 0 -and $v2Result.text -match '"capture_complete":true') "v2_reader_accepts_complete_two_collection_capture"
    Assert-True ($v2Result.text -match 'ai_lab_document_chunks' -and $v2Result.text -match 'ai_lab_knowledge_base_chunks') "v2_reader_reports_both_collections"
    Assert-True ($v2Result.text -match '"full_eligible":false' -and $v2Result.text -match 'NOT_RUN_WAITING_APPROVAL') "capture_does_not_fabricate_restore_evidence"
    Assert-True ($v2Result.text -match '"storage_coverage_status":"COMPLETE"' -and
        $v2Result.text -match '"storage_coverage_verified":true' -and $v2Result.text -match '"kb_reference_count":1') "v2_reader_verifies_current_kb_source_contract"
    Test-ProofTargetGuardsWithMocks $v2

    $historicalV2 = New-V2Checkpoint "v2-historical-four-domains" -HistoricalWithoutStorageCoverage
    $historicalV2Result = Invoke-Recovery @("-CheckpointPath", $historicalV2, "-Mode", "Full", "-ValidateOnly")
    Assert-True ($historicalV2Result.exit_code -eq 0 -and
        $historicalV2Result.text -match '"storage_coverage_status":"NOT_RECORDED"' -and
        $historicalV2Result.text -match '"storage_coverage_verified":false' -and
        $historicalV2Result.text -match '"capture_complete":false') "historical_v2_remains_readable_without_claiming_current_storage_coverage"

    $missingCoverage = New-V2Checkpoint "v2-current-missing-storage-coverage"
    $missingCoveragePath = Join-Path $missingCoverage "backup-manifest.json"
    $missingCoverageManifest = Get-Content -LiteralPath $missingCoveragePath -Raw | ConvertFrom-Json
    $missingCoverageManifest.PSObject.Properties.Remove("storage_coverage")
    $missingCoverageManifest | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $missingCoveragePath -Encoding UTF8
    $missingCoverageResult = Invoke-Recovery @("-CheckpointPath", $missingCoverage, "-Mode", "Full", "-ValidateOnly")
    Assert-True ($missingCoverageResult.exit_code -ne 0 -and
        $missingCoverageResult.text -match 'backup_storage_coverage_missing') "current_v2_missing_storage_coverage_rejected"

    $missingKbDomain = New-V2Checkpoint "v2-current-missing-kb-archive-domain"
    $missingKbDomainArchive = Join-Path $missingKbDomain "artifacts\document-storage.tar.gz"
    Remove-Item -LiteralPath $missingKbDomainArchive
    New-StorageArchive $missingKbDomainArchive -HistoricalFourDomains
    $missingKbDomainPath = Join-Path $missingKbDomain "backup-manifest.json"
    $missingKbDomainManifest = Get-Content -LiteralPath $missingKbDomainPath -Raw | ConvertFrom-Json
    foreach ($artifact in @($missingKbDomainManifest.artifacts)) {
        if ([string]$artifact.file -eq "artifacts/document-storage.tar.gz") {
            $item = Get-Item -LiteralPath $missingKbDomainArchive
            $artifact.bytes = [int64]$item.Length
            $artifact.sha256 = (Get-FileHash -LiteralPath $missingKbDomainArchive -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    $missingKbDomainManifest | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $missingKbDomainPath -Encoding UTF8
    $missingKbDomainResult = Invoke-Recovery @("-CheckpointPath", $missingKbDomain, "-Mode", "Full", "-ValidateOnly")
    Assert-True ($missingKbDomainResult.exit_code -ne 0 -and
        $missingKbDomainResult.text -match 'backup_storage_archive_domain_missing') "current_v2_missing_kb_archive_domain_rejected"

    $missingStatus = New-V2Checkpoint "v2-missing-required-status"
    $missingStatusPath = Join-Path $missingStatus "backup-manifest.json"
    $missingStatusManifest = Get-Content -LiteralPath $missingStatusPath -Raw | ConvertFrom-Json
    $missingStatusManifest.PSObject.Properties.Remove("consistency_status")
    $missingStatusManifest | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $missingStatusPath -Encoding UTF8
    $missingStatusResult = Invoke-Recovery @("-CheckpointPath", $missingStatus, "-Mode", "Full", "-ValidateOnly")
    Assert-True ($missingStatusResult.exit_code -ne 0 -and
        $missingStatusResult.text -match 'backup_manifest_v2_status_missing') "v2_missing_required_status_rejected"

    $missingArtifact = New-V2Checkpoint "v2-missing-artifact"
    [IO.File]::Delete((Join-Path $missingArtifact "artifacts\runtime-inventory.json"))
    $missingArtifactResult = Invoke-Recovery @("-CheckpointPath", $missingArtifact, "-Mode", "Full", "-ValidateOnly")
    Assert-True ($missingArtifactResult.exit_code -ne 0 -and
        $missingArtifactResult.text -match 'backup_artifact_missing') "v2_missing_artifact_rejected"

    $missing = New-V2Checkpoint "v2-missing-kb"
    $missingManifestPath = Join-Path $missing "backup-manifest.json"
    $missingManifest = Get-Content -LiteralPath $missingManifestPath -Raw | ConvertFrom-Json
    $missingManifest.qdrant_collections = @($missingManifest.qdrant_collections | Where-Object { $_.collection -ne "ai_lab_knowledge_base_chunks" })
    $missingManifest | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $missingManifestPath -Encoding UTF8
    $missingResult = Invoke-Recovery @("-CheckpointPath", $missing, "-Mode", "Full", "-ValidateOnly")
    Assert-True ($missingResult.exit_code -ne 0 -and $missingResult.text -match 'backup_qdrant_collection_coverage_invalid') "missing_collection_rejected"

    $badHash = New-V2Checkpoint "v2-bad-hash"
    Add-Content -LiteralPath (Join-Path $badHash "artifacts\runtime-inventory.json") -Value "tamper"
    $hashResult = Invoke-Recovery @("-CheckpointPath", $badHash, "-Mode", "Full", "-ValidateOnly")
    Assert-True ($hashResult.exit_code -ne 0 -and $hashResult.text -match 'backup_artifact_size_mismatch|backup_artifact_hash_mismatch') "bad_hash_rejected"

    $unsupported = New-V2Checkpoint "v3-unsupported"
    $unsupportedPath = Join-Path $unsupported "backup-manifest.json"
    $unsupportedManifest = Get-Content -LiteralPath $unsupportedPath -Raw | ConvertFrom-Json
    $unsupportedManifest.schema_version = "NEXT_STABIL_BACKUP_V3"
    $unsupportedManifest | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $unsupportedPath -Encoding UTF8
    $unsupportedResult = Invoke-Recovery @("-CheckpointPath", $unsupported, "-Mode", "Full", "-ValidateOnly")
    Assert-True ($unsupportedResult.exit_code -ne 0 -and $unsupportedResult.text -match 'backup_manifest_unsupported') "unsupported_manifest_rejected"

    $productionTarget = Invoke-Recovery @("-CheckpointPath", $v2, "-Mode", "Full", "-ProofOnly", "-ProofPostgresContainer", "postgres", "-ProofTargetOwner", "next-stabil-r03-a1-test-12345678", "-ProofQdrantClientImage", ("sha256:" + ("d" * 64)), "-ProofStateRoot", (Join-Path $root "next-stabil-r03-a1-test-12345678-state"))
    Assert-True ($productionTarget.exit_code -ne 0 -and $productionTarget.text -match 'proof_target_name_rejected') "production_postgres_target_rejected_before_proof"

    if ($RunDockerProof) {
        if ($PostgresImage -notmatch '@sha256:[a-f0-9]{64}$' -or $QdrantImage -notmatch '@sha256:[a-f0-9]{64}$' -or $ClientImage -notmatch '^sha256:[a-f0-9]{64}$') {
            throw "docker_proof_images_not_pinned"
        }
        # The Docker integration is deliberately delegated to the bounded
        # operation test below; it owns exact resources and produces its own log.
        & (Join-Path $PSScriptRoot "test-r03-a1-synthetic-proof.ps1") `
            -PostgresImage $PostgresImage -QdrantImage $QdrantImage -ClientImage $ClientImage
        if ($LASTEXITCODE -ne 0) { throw "synthetic_docker_proof_failed" }
        Assert-True $true "synthetic_docker_proof"
    }

    Write-Output "R03_A1_RECOVERY_TOOL_TESTS_PASS=$passed"
}
finally {
    if (Test-Path -LiteralPath $root) {
        $resolved = [IO.Path]::GetFullPath($root)
        $temp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        if ($resolved.StartsWith($temp, [StringComparison]::OrdinalIgnoreCase) -and
            (Split-Path -Leaf $resolved) -like "next-stabil-r03-a1-unit-*") {
            Remove-Item -LiteralPath $resolved -Recurse -Force
        }
    }
}
