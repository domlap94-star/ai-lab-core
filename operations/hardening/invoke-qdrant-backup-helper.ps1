[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RequestPath,
    [Parameter(Mandatory = $true)][string]$ResultPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function ConvertTo-NsR26BoundedSafeText {
    param([AllowNull()]$Value, [int]$MaximumCharacters = 4096)
    $text = [string]$Value
    $text = [regex]::Replace($text, '(?i)(password|token|secret|authorization)=([^\s;]+)', '$1=REDACTED')
    $text = [regex]::Replace($text, '[\x00-\x08\x0B\x0C\x0E-\x1F]', '?')
    if ($text.Length -gt $MaximumCharacters) { return $text.Substring(0, $MaximumCharacters) }
    return $text
}

function Write-NsR26JsonAtomic {
    param([Parameter(Mandatory = $true)][string]$LiteralPath, [Parameter(Mandatory = $true)]$Value)
    $directory = Split-Path -Parent $LiteralPath
    if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
        [void](New-Item -ItemType Directory -Path $directory -Force)
    }
    $temporary = $LiteralPath + '.tmp-' + $PID
    [IO.File]::WriteAllText($temporary, (($Value | ConvertTo-Json -Depth 40) + "`n"), (New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $temporary -Destination $LiteralPath -Force
}

function Test-NsR26SafeCollectionName {
    param([Parameter(Mandatory = $true)][string]$Name)
    if ($Name -notmatch '^[A-Za-z0-9_-]{1,128}$' -or $Name.Contains('..') -or [IO.Path]::IsPathRooted($Name)) {
        throw "COLLECTION_NAME_UNSAFE:$Name"
    }
    return $true
}

function Test-NsR26SafeSnapshotName {
    param([Parameter(Mandatory = $true)][string]$Name)
    if ($Name -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{0,255}$' -or $Name.Contains('..') -or
        $Name.Contains('/') -or $Name.Contains('\') -or [IO.Path]::IsPathRooted($Name)) {
        throw "SNAPSHOT_NAME_UNSAFE:$Name"
    }
    return $true
}

function Read-NsR26HelperRequest {
    param([Parameter(Mandatory = $true)][string]$LiteralPath)
    if (-not (Test-Path -LiteralPath $LiteralPath -PathType Leaf)) { throw 'HELPER_REQUEST_MISSING' }
    try { $request = Get-Content -LiteralPath $LiteralPath -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { throw 'HELPER_REQUEST_INVALID_JSON' }
    if ([string]$request.schema -ne 'NEXT_STABIL_QDRANT_BACKUP_HELPER_REQUEST_V1') { throw 'HELPER_REQUEST_SCHEMA' }
    foreach ($name in @('backup_root', 'artifact_root', 'operation_id', 'validator_path')) {
        if ([string]::IsNullOrWhiteSpace([string]$request.$name)) { throw "HELPER_REQUEST_FIELD:$name" }
    }
    $collections = @($request.collections)
    if ($collections.Count -eq 0) { throw 'HELPER_REQUEST_COLLECTIONS_EMPTY' }
    foreach ($collection in $collections) { [void](Test-NsR26SafeCollectionName -Name ([string]$collection)) }
    $port = [int]$request.helper_port
    if ($port -lt 1024 -or $port -gt 65535) { throw 'HELPER_REQUEST_PORT' }
    return [pscustomobject][ordered]@{
        backup_root = [string]$request.backup_root
        artifact_root = [string]$request.artifact_root
        collections = @($collections | ForEach-Object { [string]$_ })
        operation_id = [string]$request.operation_id
        validator_path = [string]$request.validator_path
        helper_port = $port
    }
}

function Resolve-NsR26CollectionSnapshotPath {
    param(
        [Parameter(Mandatory = $true)][string]$StagingRoot,
        [Parameter(Mandatory = $true)][string]$Collection,
        [Parameter(Mandatory = $true)][string]$SnapshotName
    )
    [void](Test-NsR26SafeCollectionName -Name $Collection)
    [void](Test-NsR26SafeSnapshotName -Name $SnapshotName)
    $staging = [IO.Path]::GetFullPath($StagingRoot).TrimEnd('\')
    $collectionRoot = [IO.Path]::GetFullPath((Join-Path $staging $Collection)).TrimEnd('\')
    $snapshotPath = [IO.Path]::GetFullPath((Join-Path $collectionRoot $SnapshotName))
    $prefix = $staging + '\'
    if (-not $collectionRoot.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or
        -not $snapshotPath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'SNAPSHOT_PATH_ESCAPE'
    }
    foreach ($path in @($staging, $collectionRoot)) {
        if (-not (Test-Path -LiteralPath $path -PathType Container)) { throw "SNAPSHOT_DIRECTORY_MISSING:$path" }
        if (((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "SNAPSHOT_REPARSE_REJECTED:$path"
        }
    }
    if (-not (Test-Path -LiteralPath $snapshotPath -PathType Leaf)) { throw "SNAPSHOT_NESTED_PATH_MISSING:$Collection" }
    $item = Get-Item -LiteralPath $snapshotPath -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "SNAPSHOT_REPARSE_REJECTED:$snapshotPath" }
    if ([int64]$item.Length -le 0) { throw "SNAPSHOT_EMPTY:$Collection" }
    return $snapshotPath
}

function Invoke-NsR26Docker {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $output = @(& docker.exe @Arguments 2>&1)
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        $bounded = ConvertTo-NsR26BoundedSafeText -Value ($output -join ' ') -MaximumCharacters 2048
        throw "DOCKER_EXIT_${exitCode}:$bounded"
    }
    return $output
}

function Invoke-NsR26DockerInspectCapture {
    param([Parameter(Mandatory = $true)][string]$ContainerName)
    if ($ContainerName -notmatch '^[A-Za-z0-9_.-]+$') { throw 'DOCKER_CONTAINER_NAME_UNSAFE' }
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = 'docker.exe'
    $start.Arguments = "inspect $ContainerName"
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    if (-not $process.Start()) { throw 'DOCKER_INSPECT_PROCESS_NOT_STARTED' }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $capture = [pscustomobject][ordered]@{
        arguments = @('inspect', $ContainerName)
        exit_code = [int]$process.ExitCode
        stdout = ConvertTo-NsR26BoundedSafeText -Value ([string]$stdoutTask.Result) -MaximumCharacters 1048576
        stderr = ConvertTo-NsR26BoundedSafeText -Value ([string]$stderrTask.Result) -MaximumCharacters 8192
    }
    $script:NsR26LastDockerInspectCapture = $capture
    return $capture
}

function ConvertFrom-NsR26DockerInspectionCapture {
    param([Parameter(Mandatory = $true)]$Capture)
    if ([int]$Capture.exit_code -ne 0) {
        throw "DOCKER_INSPECT_EXIT_$([int]$Capture.exit_code):$(ConvertTo-NsR26BoundedSafeText -Value $Capture.stderr -MaximumCharacters 2048)"
    }
    try { $documents = @(([string]$Capture.stdout | ConvertFrom-Json)) }
    catch { throw "DOCKER_INSPECT_JSON_INVALID:$(ConvertTo-NsR26BoundedSafeText -Value $_.Exception.Message -MaximumCharacters 1024)" }
    if ($documents.Count -eq 0) { throw 'DOCKER_INSPECT_OBJECT_MISSING' }
    if ($documents.Count -ne 1) { throw 'DOCKER_INSPECT_OBJECT_AMBIGUOUS' }
    $document = $documents[0]
    foreach ($property in @('Id', 'Image', 'Config', 'HostConfig', 'State', 'RestartCount', 'Mounts')) {
        if ($null -eq $document.PSObject.Properties[$property]) { throw "DOCKER_INSPECT_FIELD_MISSING:$property" }
    }
    if ($null -eq $document.Config.PSObject.Properties['Image']) { throw 'DOCKER_INSPECT_FIELD_MISSING:Config.Image' }
    if ($null -eq $document.HostConfig.PSObject.Properties['RestartPolicy'] -or
        $null -eq $document.HostConfig.RestartPolicy.PSObject.Properties['Name']) {
        throw 'DOCKER_INSPECT_FIELD_MISSING:HostConfig.RestartPolicy.Name'
    }
    foreach ($property in @('Running', 'Status', 'Restarting')) {
        if ($null -eq $document.State.PSObject.Properties[$property]) { throw "DOCKER_INSPECT_FIELD_MISSING:State.$property" }
    }
    return [pscustomobject][ordered]@{
        id = [string]$document.Id
        image_id = [string]$document.Image
        image_reference = [string]$document.Config.Image
        restart_policy = [string]$document.HostConfig.RestartPolicy.Name
        running = [bool]$document.State.Running
        status = [string]$document.State.Status
        restarting = [bool]$document.State.Restarting
        restart_count = [int64]$document.RestartCount
        mounts = @($document.Mounts)
        inspect_stdout = [string]$Capture.stdout
        inspect_stderr = [string]$Capture.stderr
        inspect_arguments = @($Capture.arguments)
    }
}

function Get-NsR26DockerContainerInspection {
    param(
        [string]$ContainerName = 'qdrant',
        [AllowNull()][scriptblock]$CaptureInvoker = $null
    )
    $capture = if ($null -eq $CaptureInvoker) {
        Invoke-NsR26DockerInspectCapture -ContainerName $ContainerName
    } else {
        & $CaptureInvoker $ContainerName
    }
    $script:NsR26LastDockerInspectCapture = $capture
    return ConvertFrom-NsR26DockerInspectionCapture -Capture $capture
}

function Get-NsR26QdrantStorageMount {
    param([Parameter(Mandatory = $true)]$Inspection)
    $matches = @($Inspection.mounts | Where-Object { [string]$_.Destination -ceq '/qdrant/storage' })
    if ($matches.Count -eq 0) { throw 'QDRANT_STORAGE_MOUNT_MISSING' }
    if ($matches.Count -gt 1) { throw 'QDRANT_STORAGE_MOUNT_AMBIGUOUS' }
    $mount = $matches[0]
    if ([string]$mount.Type -cne 'volume') { throw 'QDRANT_STORAGE_MOUNT_NOT_VOLUME' }
    if ([string]::IsNullOrWhiteSpace([string]$mount.Name)) { throw 'QDRANT_STORAGE_VOLUME_NAME_MISSING' }
    if ($null -ne $mount.PSObject.Properties['Source'] -and [string]::IsNullOrWhiteSpace([string]$mount.Source)) {
        throw 'QDRANT_STORAGE_SOURCE_EMPTY'
    }
    return $mount
}

function Assert-NsR26PrimaryStoppedState {
    param([Parameter(Mandatory = $true)]$Before, [Parameter(Mandatory = $true)]$After)
    if ([string]$After.id -ne [string]$Before.id) { throw 'QDRANT_PRIMARY_IDENTITY_CHANGED' }
    if ($After.running -ne $false -or $After.restarting -ne $false -or [string]$After.status -ne 'exited') {
        throw 'QDRANT_PRIMARY_NOT_STOPPED'
    }
    return $true
}

function Assert-NsR26PrimaryRestartedState {
    param([Parameter(Mandatory = $true)]$Before, [Parameter(Mandatory = $true)]$After)
    if ([string]$After.id -ne [string]$Before.id) { throw 'QDRANT_PRIMARY_IDENTITY_CHANGED' }
    if ($After.running -ne $true -or $After.restarting -ne $false -or [string]$After.status -ne 'running') {
        throw 'QDRANT_PRIMARY_NOT_RUNNING'
    }
    if ([int64]$After.restart_count -ne [int64]$Before.restart_count) { throw 'QDRANT_PRIMARY_RESTART_COUNT_CHANGED' }
    if ([string]$After.image_id -ne [string]$Before.image_id -or
        [string]$After.image_reference -ne [string]$Before.image_reference -or
        [string]$After.restart_policy -ne [string]$Before.restart_policy) {
        throw 'QDRANT_PRIMARY_CONFIGURATION_CHANGED'
    }
    return $true
}

function Invoke-NsR26QdrantApi {
    param([Parameter(Mandatory = $true)][string]$Uri, [string]$Method = 'Get')
    return Invoke-RestMethod -Method $Method -Uri $Uri -TimeoutSec 900
}

function Get-NsR26CollectionInventory {
    param([Parameter(Mandatory = $true)][string[]]$Collections, [Parameter(Mandatory = $true)][string]$BaseUri)
    $records = @()
    foreach ($collection in $Collections) {
        $info = Invoke-NsR26QdrantApi -Uri "$BaseUri/collections/$collection"
        $aliases = Invoke-NsR26QdrantApi -Uri "$BaseUri/collections/$collection/aliases"
        if ($info.status -ne 'ok' -or $aliases.status -ne 'ok') { throw "QDRANT_INVENTORY_FAILED:$collection" }
        $records += @([ordered]@{
            collection = $collection
            points_count = [int64]$info.result.points_count
            indexed_vectors_count = [int64]$info.result.indexed_vectors_count
            segments_count = [int]$info.result.segments_count
            config = $info.result.config
            aliases = @($aliases.result.aliases | ForEach-Object { [string]$_.alias_name } | Sort-Object)
        })
    }
    return $records
}

function Get-NsR26StagingInventory {
    param([AllowNull()][string]$StagingRoot)
    if ([string]::IsNullOrWhiteSpace($StagingRoot) -or -not (Test-Path -LiteralPath $StagingRoot)) { return @() }
    $root = [IO.Path]::GetFullPath($StagingRoot).TrimEnd('\') + '\'
    return @(Get-ChildItem -LiteralPath $StagingRoot -Recurse -Force | Select-Object -First 256 | ForEach-Object {
        [ordered]@{
            relative_path = ([IO.Path]::GetFullPath($_.FullName)).Substring($root.Length).Replace('\', '/')
            kind = if ($_.PSIsContainer) { 'directory' } else { 'file' }
            bytes = if ($_.PSIsContainer) { $null } else { [int64]$_.Length }
            reparse = [bool](($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)
        }
    })
}

function New-NsR26HelperResultDocument {
    param(
        [Parameter(Mandatory = $true)][string]$Status,
        [Parameter(Mandatory = $true)][string]$Stage,
        [Parameter(Mandatory = $true)][string]$Code,
        [Parameter(Mandatory = $true)][hashtable]$State
    )
    return [ordered]@{
        schema = 'NEXT_STABIL_QDRANT_BACKUP_HELPER_RESULT_V1'
        status = $Status
        stage = $Stage
        code = $Code
        message = ConvertTo-NsR26BoundedSafeText -Value $State.message
        started_at = [string]$State.started_at
        finished_at = [DateTime]::UtcNow.ToString('o')
        primary_container_id = [string]$State.primary_container_id
        primary_stopped = [bool]$State.primary_stopped
        primary_restarted = [bool]$State.primary_restarted
        primary_ready = [bool]$State.primary_ready
        helper_name = [string]$State.helper_name
        helper_created = [bool]$State.helper_created
        helper_removed = [bool]$State.helper_removed
        staging_root = [string]$State.staging_root
        staging_volume = [string]$State.staging_volume
        staging_residue_count = [int]$State.staging_residue_count
        helper_residue_count = [int]$State.helper_container_residue_count
        helper_container_residue_count = [int]$State.helper_container_residue_count
        collections = @($State.collections)
        records = @($State.records)
        error_type = [string]$State.error_type
        bounded_stdout = ConvertTo-NsR26BoundedSafeText -Value $State.bounded_stdout
        bounded_stderr = ConvertTo-NsR26BoundedSafeText -Value $State.bounded_stderr
        original_error = $State.original_error
        cleanup_error = ConvertTo-NsR26BoundedSafeText -Value $State.cleanup_error
        cleanup_stage = [string]$State.cleanup_stage
        staging_inventory = @($State.staging_inventory)
        primary_restart_count_before = $State.primary_restart_count_before
        primary_restart_count_after = $State.primary_restart_count_after
        primary_image_id = [string]$State.primary_image_id
        primary_image_reference = [string]$State.primary_image_reference
        primary_restart_policy = [string]$State.primary_restart_policy
        storage_volume_name = [string]$State.storage_volume_name
    }
}

function Get-NsR26ErrorCode {
    param([Parameter(Mandatory = $true)][System.Management.Automation.ErrorRecord]$ErrorRecord)
    $message = [string]$ErrorRecord.Exception.Message
    if ($message -match '^([A-Z][A-Z0-9_]+)') { return $Matches[1] }
    return 'QDRANT_HELPER_UNHANDLED'
}

function Invoke-NsR26QdrantHelper {
    param([Parameter(Mandatory = $true)][string]$HelperRequestPath, [Parameter(Mandatory = $true)][string]$HelperResultPath)
    $stage = 'REQUEST_VALIDATION'
    $failureStage = ''
    $failureCode = ''
    $success = $false
    $request = $null
    $baseUri = 'http://127.0.0.1:6333'
    $helperBaseUri = ''
    $stagingRoot = ''
    $primaryId = ''
    $before = @()
    $after = @()
    $records = @()
    $helperName = ''
    $helperCreated = $false
    $primaryStopped = $false
    $primaryInspection = $null
    $script:NsR26LastDockerInspectCapture = $null
    $state = @{
        started_at = [DateTime]::UtcNow.ToString('o'); message = ''; primary_container_id = ''
        primary_stopped = $false; primary_restarted = $false; primary_ready = $false
        helper_name = ''; helper_created = $false; helper_removed = $false
        staging_root = ''; staging_volume = ''; staging_residue_count = 0
        helper_container_residue_count = 0; collections = @(); records = @()
        error_type = ''; bounded_stdout = ''; bounded_stderr = ''; original_error = $null; cleanup_error = ''
        cleanup_stage = ''; staging_inventory = @()
        primary_restart_count_before = $null; primary_restart_count_after = $null
        primary_image_id = ''; primary_image_reference = ''; primary_restart_policy = ''; storage_volume_name = ''
    }
    $cleanupErrors = New-Object Collections.Generic.List[string]
    try {
        $request = Read-NsR26HelperRequest -LiteralPath $HelperRequestPath
        $helperBaseUri = "http://127.0.0.1:$($request.helper_port)"
        $stage = 'PRE_INVENTORY'
        $primaryInspection = Get-NsR26DockerContainerInspection -ContainerName 'qdrant'
        $storageMount = Get-NsR26QdrantStorageMount -Inspection $primaryInspection
        $primaryId = [string]$primaryInspection.id
        $imageId = [string]$primaryInspection.image_id
        $imageReference = [string]$primaryInspection.image_reference
        $restartPolicy = [string]$primaryInspection.restart_policy
        $volume = [string]$storageMount.Name
        $state.primary_restart_count_before = [int64]$primaryInspection.restart_count
        $state.primary_image_id = $imageId
        $state.primary_image_reference = $imageReference
        $state.primary_restart_policy = $restartPolicy
        $state.storage_volume_name = $volume
        $before = @(Get-NsR26CollectionInventory -Collections $request.collections -BaseUri $baseUri)
        $stage = 'STAGING_PREPARE'
        $backupRoot = [IO.Path]::GetFullPath($request.backup_root).TrimEnd('\')
        if ([IO.Path]::GetPathRoot($backupRoot).TrimEnd('\').ToUpperInvariant() -ne 'F:') { throw 'QDRANT_STAGING_NOT_ON_F' }
        if (((Get-Item -LiteralPath $backupRoot -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'QDRANT_BACKUP_ROOT_REPARSE' }
        if ([int64](Get-PSDrive F).Free -lt 5GB) { throw 'QDRANT_STAGING_SPACE_LOW' }
        $safeOperationId = $request.operation_id -replace '[^A-Za-z0-9_.-]', '-'
        $stagingRoot = Join-Path $backupRoot ".next-stabil-qdrant-staging\$safeOperationId"
        if (Test-Path -LiteralPath $stagingRoot) { throw 'QDRANT_STAGING_COLLISION' }
        [void](New-Item -ItemType Directory -Path $stagingRoot -Force)
        if (((Get-Item -LiteralPath $stagingRoot -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'QDRANT_STAGING_REPARSE' }
        [void](New-Item -ItemType Directory -Path $request.artifact_root -Force)
        $probe = Join-Path $stagingRoot '.probe'
        [IO.File]::WriteAllText($probe, 'probe', (New-Object Text.UTF8Encoding($false)))
        Remove-Item -LiteralPath $probe -Force
        $helperName = "next-stabil-qdrant-backup-$safeOperationId"
        $stage = 'STOP_PRIMARY'
        [void](Invoke-NsR26Docker -Arguments @('stop', '-t', '60', 'qdrant'))
        $primaryStopped = $true
        $stage = 'CONFIRM_PRIMARY_STOPPED'
        $stoppedInspection = Get-NsR26DockerContainerInspection -ContainerName 'qdrant'
        [void](Assert-NsR26PrimaryStoppedState -Before $primaryInspection -After $stoppedInspection)
        $stage = 'START_HELPER'
        $mount = "type=bind,src=$stagingRoot,dst=/qdrant/snapshots"
        [void](Invoke-NsR26Docker -Arguments @(
            'run', '-d', '--name', $helperName, '--pull', 'never', '--restart', 'no',
            '-p', "127.0.0.1:$($request.helper_port):6333",
            '--mount', "source=$volume,target=/qdrant/storage", '--mount', $mount,
            '-e', 'QDRANT__STORAGE__SNAPSHOTS_PATH=/qdrant/snapshots',
            '-e', 'QDRANT__STORAGE__TEMP_PATH=/qdrant/snapshots/temp', $imageId
        ))
        $helperCreated = $true
        $stage = 'WAIT_HELPER_READY'
        $deadline = (Get-Date).AddMinutes(3)
        $ready = $null
        do {
            Start-Sleep -Seconds 2
            try { $ready = Invoke-WebRequest -UseBasicParsing -Uri "$helperBaseUri/readyz" -TimeoutSec 3 } catch { $ready = $null }
        } while (($null -eq $ready -or $ready.StatusCode -ne 200) -and (Get-Date) -lt $deadline)
        if ($null -eq $ready -or $ready.StatusCode -ne 200) { throw 'QDRANT_HELPER_NOT_READY' }
        foreach ($collection in $request.collections) {
            $baseline = @($before | Where-Object { $_.collection -eq $collection })[0]
            $stage = "SNAPSHOT_CREATE:$collection"
            $response = Invoke-NsR26QdrantApi -Uri "$helperBaseUri/collections/$collection/snapshots" -Method 'Post'
            if ($response.status -ne 'ok' -or [string]::IsNullOrWhiteSpace([string]$response.result.name)) {
                throw "QDRANT_SNAPSHOT_CREATE_FAILED:$collection"
            }
            $snapshotName = [string]$response.result.name
            $stage = "SNAPSHOT_LOCATE:$collection"
            $sourceSnapshotPath = Resolve-NsR26CollectionSnapshotPath -StagingRoot $stagingRoot -Collection $collection -SnapshotName $snapshotName
            $stage = "SNAPSHOT_VALIDATE:$collection"
            $validationOutput = @(& node.exe $request.validator_path $sourceSnapshotPath 2>&1)
            $validationExitCode = $LASTEXITCODE
            if ($validationExitCode -ne 0 -or $validationOutput.Count -eq 0) { throw "QDRANT_SNAPSHOT_INVALID:$collection" }
            try { $validation = ($validationOutput -join '') | ConvertFrom-Json } catch { throw "QDRANT_SNAPSHOT_VALIDATOR_JSON:$collection" }
            if ($validation.valid -ne $true) { throw "QDRANT_SNAPSHOT_INVALID:$collection" }
            $stage = "SNAPSHOT_MOVE:$collection"
            $destination = Join-Path $request.artifact_root "$collection.snapshot"
            if (Test-Path -LiteralPath $destination) { throw "QDRANT_ARTIFACT_COLLISION:$collection" }
            Move-Item -LiteralPath $sourceSnapshotPath -Destination $destination
            $item = Get-Item -LiteralPath $destination
            $records += @([ordered]@{
                collection = $collection; artifact = $destination; bytes = [int64]$item.Length
                sha256 = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
                snapshot_name = $snapshotName; points_count = $baseline.points_count
                indexed_vectors_count = $baseline.indexed_vectors_count; segments_count = $baseline.segments_count
                config = $baseline.config; aliases = $baseline.aliases; structurally_valid = $true
                structural_validation_reason = [string]$validation.reason
            })
        }
        $success = $true
        $state.message = 'QDRANT_HELPER_WORK_COMPLETE'
        $state.original_error = $null
        $state.error_type = ''
        $state.bounded_stderr = ''
        $null = $imageReference
        $null = $restartPolicy
    }
    catch {
        $failureStage = $stage
        $failureCode = Get-NsR26ErrorCode -ErrorRecord $_
        $state.message = ConvertTo-NsR26BoundedSafeText -Value $_.Exception.Message
        $state.error_type = $_.Exception.GetType().FullName
        if ($null -ne $script:NsR26LastDockerInspectCapture) {
            $state.bounded_stdout = ConvertTo-NsR26BoundedSafeText -Value $script:NsR26LastDockerInspectCapture.stdout -MaximumCharacters 8192
            $state.bounded_stderr = ConvertTo-NsR26BoundedSafeText -Value $script:NsR26LastDockerInspectCapture.stderr -MaximumCharacters 8192
        }
        if ([string]::IsNullOrWhiteSpace([string]$state.bounded_stderr)) { $state.bounded_stderr = $state.message }
        $state.original_error = [ordered]@{ stage = $failureStage; code = $failureCode; message = $state.message; error_type = $state.error_type }
        if (-not [string]::IsNullOrWhiteSpace($stagingRoot)) { $state.staging_inventory = @(Get-NsR26StagingInventory -StagingRoot $stagingRoot) }
    }
    finally {
        if ($helperCreated -or -not [string]::IsNullOrWhiteSpace($helperName)) {
            $state.cleanup_stage = 'STOP_HELPER'
            try {
                $stopOutput = @(& docker.exe stop -t 30 $helperName 2>&1)
                if ($LASTEXITCODE -ne 0) { throw "exit=$LASTEXITCODE output=$(ConvertTo-NsR26BoundedSafeText -Value ($stopOutput -join ' '))" }
            } catch { $cleanupErrors.Add("STOP_HELPER:$($_.Exception.Message)") }
            $state.cleanup_stage = 'REMOVE_HELPER'
            try {
                $removeOutput = @(& docker.exe rm -f $helperName 2>&1)
                if ($LASTEXITCODE -ne 0) { throw "exit=$LASTEXITCODE output=$(ConvertTo-NsR26BoundedSafeText -Value ($removeOutput -join ' '))" }
            } catch { $cleanupErrors.Add("REMOVE_HELPER:$($_.Exception.Message)") }
        }
        if ($primaryStopped) {
            $state.cleanup_stage = 'START_PRIMARY'
            try { [void](Invoke-NsR26Docker -Arguments @('start', 'qdrant')); $state.primary_restarted = $true }
            catch { $cleanupErrors.Add("START_PRIMARY:$($_.Exception.Message)") }
            if ($state.primary_restarted) {
                $state.cleanup_stage = 'WAIT_PRIMARY_READY'
                try {
                    $deadline = (Get-Date).AddMinutes(3)
                    $primaryReadyResponse = $null
                    do {
                        Start-Sleep -Seconds 2
                        try { $primaryReadyResponse = Invoke-WebRequest -UseBasicParsing -Uri "$baseUri/readyz" -TimeoutSec 3 } catch { $primaryReadyResponse = $null }
                    } while (($null -eq $primaryReadyResponse -or $primaryReadyResponse.StatusCode -ne 200) -and (Get-Date) -lt $deadline)
                    $state.primary_ready = $null -ne $primaryReadyResponse -and $primaryReadyResponse.StatusCode -eq 200
                    if (-not $state.primary_ready) { throw 'QDRANT_PRIMARY_NOT_READY' }
                    $afterPrimaryInspection = Get-NsR26DockerContainerInspection -ContainerName 'qdrant'
                    [void](Assert-NsR26PrimaryRestartedState -Before $primaryInspection -After $afterPrimaryInspection)
                    $state.primary_restart_count_after = [int64]$afterPrimaryInspection.restart_count
                }
                catch { $cleanupErrors.Add("WAIT_PRIMARY_READY:$($_.Exception.Message)") }
            }
        }
        if ($state.primary_ready -and $null -ne $request) {
            $state.cleanup_stage = 'POST_INVENTORY'
            try {
                $after = @(Get-NsR26CollectionInventory -Collections $request.collections -BaseUri $baseUri)
                foreach ($baseline in $before) {
                    $observed = @($after | Where-Object { $_.collection -eq $baseline.collection })[0]
                    if ($observed.points_count -ne $baseline.points_count -or
                        $observed.indexed_vectors_count -ne $baseline.indexed_vectors_count -or
                        (($observed.aliases -join '|') -ne ($baseline.aliases -join '|'))) {
                        throw "QDRANT_POST_STATE_MISMATCH:$($baseline.collection)"
                    }
                }
            }
            catch { $cleanupErrors.Add("POST_INVENTORY:$($_.Exception.Message)") }
        }
        if (-not [string]::IsNullOrWhiteSpace($stagingRoot) -and (Test-Path -LiteralPath $stagingRoot)) {
            $state.cleanup_stage = 'CLEAN_STAGING'
            try { Remove-Item -LiteralPath $stagingRoot -Recurse -Force }
            catch { $cleanupErrors.Add("CLEAN_STAGING:$($_.Exception.Message)") }
        }
        try {
            if (-not [string]::IsNullOrWhiteSpace($helperName)) {
                $remaining = @(Invoke-NsR26Docker -Arguments @('container', 'ls', '--all', '--quiet', '--no-trunc', '--filter', "name=^/$helperName$"))
                $state.helper_container_residue_count = @($remaining | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) }).Count
            }
            $state.helper_removed = $state.helper_container_residue_count -eq 0
        }
        catch { $cleanupErrors.Add("HELPER_RESIDUE:$($_.Exception.Message)") }
        $state.staging_residue_count = if (-not [string]::IsNullOrWhiteSpace($stagingRoot) -and (Test-Path -LiteralPath $stagingRoot)) {
            @(Get-ChildItem -LiteralPath $stagingRoot -Recurse -Force -ErrorAction SilentlyContinue).Count
        } else { 0 }
        $state.primary_container_id = $primaryId
        $state.primary_stopped = $primaryStopped
        $state.helper_name = $helperName
        $state.helper_created = $helperCreated
        $state.staging_root = $stagingRoot
        $state.staging_volume = if ([string]::IsNullOrWhiteSpace($stagingRoot)) { '' } else { [IO.Path]::GetPathRoot($stagingRoot).TrimEnd('\').ToUpperInvariant() }
        $state.collections = @($after)
        $state.records = @($records)
        $state.cleanup_error = ConvertTo-NsR26BoundedSafeText -Value ($cleanupErrors -join ' | ')
        $cleanupPass = $cleanupErrors.Count -eq 0 -and $state.helper_removed -and $state.primary_restarted -and
            $state.primary_ready -and $state.staging_residue_count -eq 0 -and $state.helper_container_residue_count -eq 0
        if ($success -and $cleanupPass -and $null -ne $request -and $records.Count -eq $request.collections.Count) {
            $finalStatus = 'PASS'; $finalStage = 'COMPLETE'; $finalCode = 'OK'; $state.cleanup_stage = 'COMPLETE'
        }
        else {
            $finalStatus = 'FAIL'
            $finalStage = if (-not [string]::IsNullOrWhiteSpace($failureStage)) { $failureStage } else { $state.cleanup_stage }
            $finalCode = if (-not [string]::IsNullOrWhiteSpace($failureCode)) { $failureCode } else { 'QDRANT_HELPER_CLEANUP_FAILED' }
            if ($cleanupErrors.Count -gt 0 -and $null -eq $state.original_error) {
                $state.original_error = [ordered]@{ stage = $finalStage; code = $finalCode; message = $state.cleanup_error; error_type = 'CleanupFailure' }
            }
        }
        $document = New-NsR26HelperResultDocument -Status $finalStatus -Stage $finalStage -Code $finalCode -State $state
        try { Write-NsR26JsonAtomic -LiteralPath $HelperResultPath -Value $document }
        catch { $finalStatus = 'FAIL'; $finalCode = 'HELPER_RESULT_WRITE_FAILED' }
    }
    if (Test-Path -LiteralPath $HelperResultPath -PathType Leaf) {
        Write-Output ((Get-Content -LiteralPath $HelperResultPath -Raw -Encoding UTF8 | ConvertFrom-Json) | ConvertTo-Json -Depth 40 -Compress)
    }
    return $(if ($finalStatus -eq 'PASS') { 0 } else { 1 })
}

$helperExitCode = Invoke-NsR26QdrantHelper -HelperRequestPath $RequestPath -HelperResultPath $ResultPath
exit $helperExitCode
