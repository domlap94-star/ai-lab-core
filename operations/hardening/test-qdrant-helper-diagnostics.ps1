[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$script:Assertions = 0
function Assert-R26D41 {
    param([bool]$Condition, [string]$Message)
    $script:Assertions++
    if (-not $Condition) { throw "ASSERTION_FAILED:$Message" }
}

function Import-SelectedFunctions {
    param([string]$Path, [string[]]$Names)
    $tokens = $null
    $errors = $null
    $ast = [Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$errors)
    Assert-R26D41 (@($errors).Count -eq 0) "parser:$Path"
    foreach ($name in $Names) {
        $definitions = @($ast.FindAll({
            param($node)
            $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name
        }, $true))
        Assert-R26D41 ($definitions.Count -eq 1) "function_unique:$name"
        $definitionText = $definitions[0].Extent.Text -replace ('^function\s+' + [regex]::Escape($name)), ("function script:$name")
        Invoke-Expression $definitionText
    }
}

function Write-TestJson {
    param([string]$Path, $Value)
    [IO.File]::WriteAllText($Path, (($Value | ConvertTo-Json -Depth 16) + "`n"), (New-Object Text.UTF8Encoding($false)))
}

function New-ResultState {
    param([string]$Stage = 'COMPLETE', [string]$Code = 'OK')
    return @{
        started_at = [DateTime]::UtcNow.ToString('o'); message = $Code; primary_container_id = 'primary-id'
        primary_stopped = $true; primary_restarted = $true; primary_ready = $true
        helper_name = 'test-helper'; helper_created = $true; helper_removed = $true
        staging_root = 'F:\test'; staging_volume = 'F:'; staging_residue_count = 0
        helper_container_residue_count = 0; collections = @(); records = @()
        error_type = ''; bounded_stdout = ''; bounded_stderr = ''; original_error = $null; cleanup_error = ''
        cleanup_stage = $Stage; staging_inventory = @()
        primary_restart_count_before = 0; primary_restart_count_after = 0
        primary_image_id = 'sha256:image'; primary_image_reference = 'qdrant/qdrant@sha256:digest'
        primary_restart_policy = 'unless-stopped'; storage_volume_name = 'qdrant_storage'
    }
}

function New-InspectDocument {
    param(
        [string]$Id = 'primary-id', [bool]$Running = $true, [string]$Status = 'running',
        [bool]$Restarting = $false, [int64]$RestartCount = 0, [object[]]$Mounts = $null
    )
    if ($null -eq $Mounts) {
        $Mounts = @([ordered]@{ Type = 'volume'; Name = 'qdrant_storage'; Source = '/var/lib/docker/volumes/qdrant_storage/_data'; Destination = '/qdrant/storage' })
    }
    return [ordered]@{
        Id = $Id; Image = 'sha256:image'; Config = [ordered]@{ Image = 'qdrant/qdrant@sha256:digest' }
        HostConfig = [ordered]@{ RestartPolicy = [ordered]@{ Name = 'unless-stopped' } }
        State = [ordered]@{ Running = $Running; Status = $Status; Restarting = $Restarting }
        RestartCount = $RestartCount; Mounts = @($Mounts)
    }
}

function New-InspectCapture {
    param([object[]]$Documents, [int]$ExitCode = 0, [string]$Stdout = '', [string]$Stderr = '')
    if ([string]::IsNullOrEmpty($Stdout) -and $null -ne $Documents) {
        $Stdout = ConvertTo-Json -InputObject @($Documents) -Depth 12
    }
    return [pscustomobject][ordered]@{
        arguments = @('inspect', 'qdrant'); exit_code = $ExitCode; stdout = $Stdout; stderr = $Stderr
    }
}

function Assert-ThrowsCode {
    param([scriptblock]$Action, [string]$Code)
    $message = ''
    try { & $Action } catch { $message = [string]$_.Exception.Message }
    Assert-R26D41 ($message -match ('^' + [regex]::Escape($Code))) "throws:$Code actual=$message"
}

$helperPath = Join-Path $PSScriptRoot 'invoke-qdrant-backup-helper.ps1'
$runnerPath = Join-Path $PSScriptRoot 'backup-production.ps1'
Import-SelectedFunctions -Path $helperPath -Names @(
    'ConvertTo-NsR26BoundedSafeText', 'Write-NsR26JsonAtomic',
    'Test-NsR26SafeCollectionName', 'Test-NsR26SafeSnapshotName',
    'Read-NsR26HelperRequest', 'Resolve-NsR26CollectionSnapshotPath',
    'New-NsR26HelperResultDocument', 'ConvertFrom-NsR26DockerInspectionCapture',
    'Get-NsR26DockerContainerInspection', 'Get-NsR26QdrantStorageMount',
    'Assert-NsR26PrimaryStoppedState', 'Assert-NsR26PrimaryRestartedState'
)
Import-SelectedFunctions -Path $runnerPath -Names @(
    'ConvertTo-NativeArgumentString', 'Get-BoundedQdrantDiagnosticText',
    'Invoke-QdrantHelperProcess', 'Write-QdrantHelperEvidence',
    'Assert-QdrantHelperProcessPass'
)

$root = Join-Path $env:LOCALAPPDATA ('Temp\NEXT-STABIL-R26-D42-' + [Guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $helperText = Get-Content -LiteralPath $helperPath -Raw -Encoding UTF8
    Assert-R26D41 (-not $helperText.Contains(([string][char]123 + [char]123))) 'no_template_open_delimiter'
    Assert-R26D41 (-not $helperText.Contains(([string][char]125 + [char]125))) 'no_template_close_delimiter'
    Assert-R26D41 ($helperText -notmatch "(?im)docker(?:\.exe)?\s+inspect\s+(?:-f|--format)\b") 'no_docker_inspect_format'
    Assert-R26D41 ($helperText -notmatch "(?im)docker(?:\.exe)?\s+ps\s+--format\b") 'no_docker_ps_format'

    $inspectDocument = New-InspectDocument
    $inspectCapture = New-InspectCapture -Documents @($inspectDocument)
    $inspection = ConvertFrom-NsR26DockerInspectionCapture -Capture $inspectCapture
    $storageMount = Get-NsR26QdrantStorageMount -Inspection $inspection
    Assert-R26D41 ($inspection.id -eq 'primary-id') 'inspect_primary_id'
    Assert-R26D41 ($inspection.image_id -eq 'sha256:image') 'inspect_image_id'
    Assert-R26D41 ($inspection.image_reference -eq 'qdrant/qdrant@sha256:digest') 'inspect_image_reference'
    Assert-R26D41 ($inspection.restart_policy -eq 'unless-stopped') 'inspect_restart_policy'
    Assert-R26D41 ($inspection.running -eq $true -and $inspection.restarting -eq $false) 'inspect_running_state'
    Assert-R26D41 ($storageMount.Name -eq 'qdrant_storage') 'inspect_storage_volume'
    Assert-R26D41 ($storageMount.Destination -ceq '/qdrant/storage') 'inspect_storage_destination'

    $script:CapturedInspectName = ''
    $viaCentralFunction = Get-NsR26DockerContainerInspection -ContainerName 'qdrant' -CaptureInvoker {
        param($name)
        $script:CapturedInspectName = $name
        return New-InspectCapture -Documents @((New-InspectDocument))
    }
    Assert-R26D41 ($script:CapturedInspectName -eq 'qdrant') 'central_inspect_container_name'
    Assert-R26D41 (($viaCentralFunction.inspect_arguments -join '|') -eq 'inspect|qdrant') 'central_inspect_arguments_exact'
    Assert-R26D41 (($viaCentralFunction.inspect_arguments -join ' ') -notmatch '(\{\{|\}\}|/qdrant/storage|-f|--format)') 'central_inspect_arguments_no_template'

    Assert-ThrowsCode -Code 'QDRANT_STORAGE_MOUNT_MISSING' -Action {
        Get-NsR26QdrantStorageMount -Inspection (ConvertFrom-NsR26DockerInspectionCapture -Capture (New-InspectCapture -Documents @((New-InspectDocument -Mounts @()))))
    }
    $twoMounts = @(
        [ordered]@{ Type = 'volume'; Name = 'one'; Source = '/one'; Destination = '/qdrant/storage' },
        [ordered]@{ Type = 'volume'; Name = 'two'; Source = '/two'; Destination = '/qdrant/storage' }
    )
    Assert-ThrowsCode -Code 'QDRANT_STORAGE_MOUNT_AMBIGUOUS' -Action {
        Get-NsR26QdrantStorageMount -Inspection (ConvertFrom-NsR26DockerInspectionCapture -Capture (New-InspectCapture -Documents @((New-InspectDocument -Mounts $twoMounts))))
    }
    Assert-ThrowsCode -Code 'QDRANT_STORAGE_MOUNT_NOT_VOLUME' -Action {
        $mount = @([ordered]@{ Type = 'bind'; Name = 'wrong'; Source = 'D:\wrong'; Destination = '/qdrant/storage' })
        Get-NsR26QdrantStorageMount -Inspection (ConvertFrom-NsR26DockerInspectionCapture -Capture (New-InspectCapture -Documents @((New-InspectDocument -Mounts $mount))))
    }
    Assert-ThrowsCode -Code 'QDRANT_STORAGE_VOLUME_NAME_MISSING' -Action {
        $mount = @([ordered]@{ Type = 'volume'; Name = ''; Source = '/source'; Destination = '/qdrant/storage' })
        Get-NsR26QdrantStorageMount -Inspection (ConvertFrom-NsR26DockerInspectionCapture -Capture (New-InspectCapture -Documents @((New-InspectDocument -Mounts $mount))))
    }
    Assert-ThrowsCode -Code 'QDRANT_STORAGE_SOURCE_EMPTY' -Action {
        $mount = @([ordered]@{ Type = 'volume'; Name = 'named'; Source = ''; Destination = '/qdrant/storage' })
        Get-NsR26QdrantStorageMount -Inspection (ConvertFrom-NsR26DockerInspectionCapture -Capture (New-InspectCapture -Documents @((New-InspectDocument -Mounts $mount))))
    }
    Assert-ThrowsCode -Code 'DOCKER_INSPECT_JSON_INVALID' -Action {
        ConvertFrom-NsR26DockerInspectionCapture -Capture (New-InspectCapture -Documents $null -Stdout '{invalid')
    }
    Assert-ThrowsCode -Code 'DOCKER_INSPECT_OBJECT_MISSING' -Action {
        ConvertFrom-NsR26DockerInspectionCapture -Capture (New-InspectCapture -Documents @())
    }
    Assert-ThrowsCode -Code 'DOCKER_INSPECT_OBJECT_AMBIGUOUS' -Action {
        ConvertFrom-NsR26DockerInspectionCapture -Capture (New-InspectCapture -Documents @((New-InspectDocument -Id 'one'), (New-InspectDocument -Id 'two')))
    }
    Assert-ThrowsCode -Code 'DOCKER_INSPECT_EXIT_7' -Action {
        ConvertFrom-NsR26DockerInspectionCapture -Capture (New-InspectCapture -Documents $null -ExitCode 7 -Stdout '' -Stderr 'synthetic inspect error')
    }

    $runningInspection = ConvertFrom-NsR26DockerInspectionCapture -Capture (New-InspectCapture -Documents @((New-InspectDocument)))
    $stoppedInspection = ConvertFrom-NsR26DockerInspectionCapture -Capture (New-InspectCapture -Documents @((New-InspectDocument -Running $false -Status 'exited')))
    $restartedInspection = ConvertFrom-NsR26DockerInspectionCapture -Capture (New-InspectCapture -Documents @((New-InspectDocument -Running $true -Status 'running')))
    Assert-R26D41 (Assert-NsR26PrimaryStoppedState -Before $runningInspection -After $stoppedInspection) 'state_stopped_pass'
    Assert-R26D41 (Assert-NsR26PrimaryRestartedState -Before $runningInspection -After $restartedInspection) 'state_restarted_pass'
    Assert-ThrowsCode -Code 'QDRANT_PRIMARY_IDENTITY_CHANGED' -Action { Assert-NsR26PrimaryRestartedState -Before $runningInspection -After (ConvertFrom-NsR26DockerInspectionCapture -Capture (New-InspectCapture -Documents @((New-InspectDocument -Id 'changed')))) }
    Assert-ThrowsCode -Code 'QDRANT_PRIMARY_NOT_RUNNING' -Action { Assert-NsR26PrimaryRestartedState -Before $runningInspection -After (ConvertFrom-NsR26DockerInspectionCapture -Capture (New-InspectCapture -Documents @((New-InspectDocument -Restarting $true)))) }
    Assert-ThrowsCode -Code 'QDRANT_PRIMARY_RESTART_COUNT_CHANGED' -Action { Assert-NsR26PrimaryRestartedState -Before $runningInspection -After (ConvertFrom-NsR26DockerInspectionCapture -Capture (New-InspectCapture -Documents @((New-InspectDocument -RestartCount 1)))) }

    $requestPath = Join-Path $root 'request.json'
    Write-TestJson $requestPath ([ordered]@{
        schema = 'NEXT_STABIL_QDRANT_BACKUP_HELPER_REQUEST_V1'; operation_id = 'r26-d42-test'
        backup_root = 'F:\dump'; artifact_root = 'F:\dump\checkpoint\artifacts\qdrant'
        collections = @('ai_lab_document_chunks', 'ai_lab_knowledge_base_chunks')
        validator_path = 'C:\ai-lab-core\operations\supervisor\qdrant_snapshot_validator.js'; helper_port = 16333
    })
    $request = Read-NsR26HelperRequest -LiteralPath $requestPath
    Assert-R26D41 ($request.collections.Count -eq 2) 'request_collection_count'
    Assert-R26D41 ($request.collections[0] -eq 'ai_lab_document_chunks') 'request_collection_order_0'
    Assert-R26D41 ($request.collections[1] -eq 'ai_lab_knowledge_base_chunks') 'request_collection_order_1'
    Assert-R26D41 ($request.helper_port -eq 16333) 'request_helper_port'

    $staging = Join-Path $root 'staging'
    $collectionRoot = Join-Path $staging 'ai_lab_document_chunks'
    New-Item -ItemType Directory -Path $collectionRoot -Force | Out-Null
    $nested = Join-Path $collectionRoot 'snapshot-1.snapshot'
    [IO.File]::WriteAllBytes($nested, [byte[]](1, 2, 3, 4))
    $resolved = Resolve-NsR26CollectionSnapshotPath -StagingRoot $staging -Collection 'ai_lab_document_chunks' -SnapshotName 'snapshot-1.snapshot'
    Assert-R26D41 ($resolved -eq [IO.Path]::GetFullPath($nested)) 'nested_snapshot_resolved'
    Assert-R26D41 ($resolved -ne (Join-Path $staging 'snapshot-1.snapshot')) 'root_snapshot_not_selected'

    foreach ($unsafe in @('..', '..snapshot', 'one/two', 'one\two', 'C:\absolute.snapshot')) {
        $rejected = $false
        try { [void](Test-NsR26SafeSnapshotName -Name $unsafe) } catch { $rejected = $true }
        Assert-R26D41 $rejected "unsafe_snapshot_rejected:$unsafe"
    }
    foreach ($unsafeCollection in @('..', 'one/two', 'one\two', 'C:\absolute')) {
        $rejected = $false
        try { [void](Test-NsR26SafeCollectionName -Name $unsafeCollection) } catch { $rejected = $true }
        Assert-R26D41 $rejected "unsafe_collection_rejected:$unsafeCollection"
    }

    $realStage = Join-Path $root 'real-stage'
    $realCollection = Join-Path $realStage 'ai_lab_document_chunks'
    New-Item -ItemType Directory -Path $realCollection -Force | Out-Null
    [IO.File]::WriteAllBytes((Join-Path $realCollection 'reparse.snapshot'), [byte[]](1))
    $junctionStage = Join-Path $root 'junction-stage'
    New-Item -ItemType Junction -Path $junctionStage -Target $realStage | Out-Null
    $reparseRejected = $false
    try { [void](Resolve-NsR26CollectionSnapshotPath -StagingRoot $junctionStage -Collection 'ai_lab_document_chunks' -SnapshotName 'reparse.snapshot') } catch { $reparseRejected = $_.Exception.Message -match 'SNAPSHOT_REPARSE_REJECTED' }
    Assert-R26D41 $reparseRejected 'reparse_staging_rejected'

    foreach ($failure in @(
        @{ stage = 'START_HELPER'; code = 'DOCKER_EXIT_125' },
        @{ stage = 'WAIT_HELPER_READY'; code = 'QDRANT_HELPER_NOT_READY' },
        @{ stage = 'SNAPSHOT_LOCATE:ai_lab_document_chunks'; code = 'SNAPSHOT_NESTED_PATH_MISSING' },
        @{ stage = 'SNAPSHOT_VALIDATE:ai_lab_document_chunks'; code = 'QDRANT_SNAPSHOT_INVALID' }
    )) {
        $state = New-ResultState -Stage $failure.stage -Code $failure.code
        $state.primary_ready = $false
        $state.original_error = [ordered]@{ stage = $failure.stage; code = $failure.code; message = 'synthetic'; error_type = 'Synthetic' }
        $document = New-NsR26HelperResultDocument -Status 'FAIL' -Stage $failure.stage -Code $failure.code -State $state
        Assert-R26D41 ($document.status -eq 'FAIL') "failure_status:$($failure.stage)"
        Assert-R26D41 ($document.stage -eq $failure.stage) "failure_stage:$($failure.stage)"
        Assert-R26D41 ($document.code -eq $failure.code) "failure_code:$($failure.stage)"
        Assert-R26D41 ($document.original_error.code -eq $failure.code) "failure_original_error:$($failure.stage)"
    }

    $successState = New-ResultState
    $successState.records = @(
        [ordered]@{ collection = 'ai_lab_document_chunks'; artifact = 'F:\one.snapshot' },
        [ordered]@{ collection = 'ai_lab_knowledge_base_chunks'; artifact = 'F:\two.snapshot' }
    )
    $successDocument = New-NsR26HelperResultDocument -Status 'PASS' -Stage 'COMPLETE' -Code 'OK' -State $successState
    Assert-R26D41 ($successDocument.status -eq 'PASS' -and $successDocument.records.Count -eq 2) 'success_document_records'
    Assert-R26D41 ($successDocument.helper_residue_count -eq 0 -and $successDocument.staging_residue_count -eq 0) 'success_document_residue'

    $stubPath = Join-Path $root 'stub.ps1'
    [IO.File]::WriteAllText($stubPath, @'
param([string]$RequestPath,[string]$ResultPath)
$mode=(Get-Content -LiteralPath $RequestPath -Raw|ConvertFrom-Json).mode
if($mode -eq 'timeout'){Start-Sleep -Seconds 3;exit 9}
if($mode -eq 'missing'){[Console]::Error.Write('missing result');exit 8}
if($mode -eq 'invalid'){[IO.File]::WriteAllText($ResultPath,'{invalid');exit 7}
$status=if($mode -eq 'pass'){'PASS'}else{'FAIL'}
$code=if($mode -eq 'pass'){'OK'}else{'SYNTHETIC_FAILURE'}
$result=[ordered]@{schema='NEXT_STABIL_QDRANT_BACKUP_HELPER_RESULT_V1';status=$status;stage=if($mode -eq 'pass'){'COMPLETE'}else{'WAIT_HELPER_READY'};code=$code;helper_removed=$true;primary_restarted=$true;primary_ready=($mode -eq 'pass');staging_volume='F:';helper_container_residue_count=0;staging_residue_count=0;records=@(@{collection='ai_lab_document_chunks'},@{collection='ai_lab_knowledge_base_chunks'})}
[IO.File]::WriteAllText($ResultPath,(ConvertTo-Json $result -Depth 8),(New-Object Text.UTF8Encoding($false)))
if($mode -eq 'pass'){exit 0};[Console]::Error.Write('synthetic helper failure');exit 6
'@, (New-Object Text.UTF8Encoding($false)))
    foreach ($case in @(
        @{ mode = 'pass'; timeout = 10; expected = 'PASS'; code = 'OK'; exit = 0 },
        @{ mode = 'fail'; timeout = 10; expected = 'FAIL'; code = 'SYNTHETIC_FAILURE'; exit = 6 },
        @{ mode = 'missing'; timeout = 10; expected = 'MISSING'; code = 'QDRANT_HELPER_RESULT_MISSING'; exit = 8 },
        @{ mode = 'invalid'; timeout = 10; expected = 'INVALID'; code = 'QDRANT_HELPER_RESULT_INVALID'; exit = 7 },
        @{ mode = 'timeout'; timeout = 1; expected = 'MISSING'; code = 'HELPER_TIMEOUT'; exit = $null }
    )) {
        $stubRequest = Join-Path $root ("stub-{0}.json" -f $case.mode)
        $stubResult = Join-Path $root ("stub-{0}-result.json" -f $case.mode)
        Write-TestJson $stubRequest ([ordered]@{ mode = $case.mode })
        $capture = Invoke-QdrantHelperProcess -HelperScript $stubPath -RequestPath $stubRequest -ResultPath $stubResult -TimeoutSeconds $case.timeout
        Assert-R26D41 ($capture.result_status -eq $case.expected) "capture_status:$($case.mode)"
        Assert-R26D41 ($capture.code -eq $case.code) "capture_code:$($case.mode)"
        if ($null -ne $case.exit) { Assert-R26D41 ($capture.exit_code -eq $case.exit) "capture_exit:$($case.mode)" }
        if ($case.mode -eq 'timeout') {
            Assert-R26D41 ($capture.timed_out -eq $true) 'capture_timeout_true'
            Assert-R26D41 ($capture.exit_code -ne 0) 'capture_timeout_nonzero_exit'
        }
        if ($case.mode -eq 'fail') { Assert-R26D41 ($capture.stderr -match 'synthetic helper failure') 'capture_stderr_preserved' }
        if ($case.mode -eq 'pass') {
            Assert-QdrantHelperProcessPass -Capture $capture -RequiredCollections @('ai_lab_document_chunks', 'ai_lab_knowledge_base_chunks')
            $evidenceRoot = Join-Path $root 'evidence'
            Write-QdrantHelperEvidence -Capture $capture -EvidenceRoot $evidenceRoot
            Assert-R26D41 (Test-Path -LiteralPath (Join-Path $evidenceRoot 'qdrant-helper-result.json') -PathType Leaf) 'evidence_result_written'
        }
    }

    $bounded = Get-BoundedQdrantDiagnosticText ('x' * 9000)
    Assert-R26D41 ($bounded.Length -eq 8192) 'diagnostic_bounded'
    Write-Output "PASS_QDRANT_HELPER_JSON_INSPECT_PS51 assertions=$script:Assertions"
}
finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
