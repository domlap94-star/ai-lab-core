[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$script:Assertions = 0
function Assert-R26D44 {
    param([bool]$Condition, [string]$Message)
    $script:Assertions++
    if (-not $Condition) { throw "ASSERTION_FAILED:$Message" }
}

function Assert-ThrowsD44 {
    param([scriptblock]$Action, [string]$Code)
    $actual = ''
    try { & $Action } catch { $actual = [string]$_.Exception.Message }
    Assert-R26D44 ($actual -match ('^' + [regex]::Escape($Code))) "throws:$Code actual=$actual"
}

function Import-D44Functions {
    param([string]$Path, [string[]]$Names)
    $tokens = $null
    $errors = $null
    $ast = [Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$errors)
    Assert-R26D44 (@($errors).Count -eq 0) "parser:$Path"
    foreach ($name in $Names) {
        $definitions = @($ast.FindAll({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name }, $true))
        Assert-R26D44 ($definitions.Count -eq 1) "function_unique:$name"
        $text = $definitions[0].Extent.Text -replace ('^function\s+' + [regex]::Escape($name)), ("function script:$name")
        Invoke-Expression $text
    }
}

function New-D44Capture {
    param([int]$Status, [string]$Body = '', [bool]$NetworkError = $false)
    return [pscustomobject][ordered]@{
        transport_success = -not $NetworkError; network_error = $NetworkError; status_code = if ($NetworkError) { $null } else { $Status }
        reason_phrase = if ($Status -eq 500) { 'Internal Server Error' } else { 'OK' }
        response_body = $Body; response_headers = [ordered]@{ Server = 'synthetic' }; duration_ms = 11
    }
}

function New-D44HelperHealth {
    param([bool]$Running = $true, [bool]$Oom = $false, [int]$Ready = 200, [string]$Logs = '')
    return [pscustomobject][ordered]@{ running = $Running; oom_killed = $Oom; ready_status = $Ready; stdout = $Logs; stderr = '' }
}

function New-D44ArtifactCase {
    param([string]$Root, [string]$Name = 'one.snapshot', [bool]$Checksum = $true, [bool]$Mismatch = $false, [bool]$Tmp = $false)
    $stage = Join-Path $Root 'stage'
    $collectionRoot = Join-Path $stage 'ai_lab_document_chunks'
    $artifacts = Join-Path $Root 'artifacts'
    New-Item -ItemType Directory -Path $collectionRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $artifacts -Force | Out-Null
    $snapshot = Join-Path $collectionRoot $Name
    [IO.File]::WriteAllBytes($snapshot, [Text.Encoding]::UTF8.GetBytes('synthetic-qdrant-snapshot'))
    $hash = (Get-FileHash -LiteralPath $snapshot -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Checksum) {
        $value = if ($Mismatch) { ('0' * 64) } else { $hash }
        [IO.File]::WriteAllText(($snapshot + '.checksum'), $value, (New-Object Text.UTF8Encoding($false)))
    }
    if ($Tmp) { [IO.File]::WriteAllText((Join-Path $collectionRoot 'active.tmp'), 'tmp') }
    return [pscustomobject]@{ stage = $stage; artifacts = $artifacts; snapshot = $snapshot; hash = $hash }
}

$helperPath = Join-Path $PSScriptRoot 'invoke-qdrant-backup-helper.ps1'
$runnerPath = Join-Path $PSScriptRoot 'backup-production.ps1'
Import-D44Functions -Path $helperPath -Names @(
    'ConvertTo-NsR26BoundedSafeText', 'Test-NsR26SafeCollectionName', 'Test-NsR26SafeSnapshotName',
    'Resolve-NsR26CollectionSnapshotPath', 'ConvertTo-NsR26SafeHeaderMap', 'Invoke-NsR26QdrantHttpCapture',
    'Get-NsR26SnapshotFileInventory', 'Wait-NsR26SnapshotStable', 'Invoke-NsR26SnapshotValidator',
    'Complete-NsR26SnapshotArtifact'
)

$root = Join-Path $env:LOCALAPPDATA ('Temp\NEXT-STABIL-R26-D44-' + [Guid]::NewGuid().ToString('N'))
$validator = { param($validatorPath, $snapshotPath) [pscustomobject]@{ exit_code = 0; output = '{"valid":true,"reason":"synthetic_valid"}' } }
$sleepNone = { param($milliseconds) }
try {
    New-Item -ItemType Directory -Path $root -Force | Out-Null

    foreach ($case in @(
        @{ name='200_json'; status=200; body='{"status":"ok"}'; network=$false; expected=200 },
        @{ name='500_json'; status=500; body='{"status":"error","result":"after artifact"}'; network=$false; expected=500 },
        @{ name='500_text'; status=500; body='internal error'; network=$false; expected=500 },
        @{ name='connection'; status=0; body='connection refused'; network=$true; expected=$null },
        @{ name='timeout'; status=0; body='timeout'; network=$true; expected=$null }
    )) {
        $capture = Invoke-NsR26QdrantHttpCapture -Uri 'http://127.0.0.1:1/synthetic' -Method Post -TransportInvoker {
            param($uri, $method, $timeout)
            [pscustomobject]@{ status_code=$case.status; reason_phrase='synthetic'; response_body=$case.body; response_content_type='application/json'; response_headers=[ordered]@{}; exception_type=if($case.network -or $case.status -eq 500){'System.Net.WebException'}else{''}; network_error=$case.network }
        }
        Assert-R26D44 ($capture.status_code -eq $case.expected) "http_status:$($case.name)"
        Assert-R26D44 ($capture.status_code -is [int] -or $null -eq $capture.status_code) "http_status_numeric:$($case.name)"
        Assert-R26D44 ($capture.network_error -eq $case.network) "http_network:$($case.name)"
        if ($case.status -eq 500) {
            Assert-R26D44 ($capture.response_body -eq $case.body) "http_500_body:$($case.name)"
            Assert-R26D44 ($capture.exception_type -eq 'System.Net.WebException') "http_500_exception:$($case.name)"
        }
    }
    $boundedCapture = Invoke-NsR26QdrantHttpCapture -Uri 'http://127.0.0.1/synthetic' -Method Post -MaximumBodyCharacters 64 -TransportInvoker {
        param($uri, $method, $timeout) [pscustomobject]@{ status_code=500; reason_phrase='error'; response_body=('x'*1000); response_content_type='text/plain'; response_headers=[ordered]@{}; exception_type='System.Net.WebException'; network_error=$false }
    }
    Assert-R26D44 ($boundedCapture.response_body.Length -eq 64 -and $boundedCapture.response_body_truncated) 'http_body_bounded'
    $headers = New-Object Net.WebHeaderCollection
    $headers.Add('Server', 'synthetic')
    $headers.Add('Set-Cookie', 'sensitive')
    $safeHeaders = ConvertTo-NsR26SafeHeaderMap -Headers $headers
    Assert-R26D44 ($safeHeaders.Server -eq 'synthetic') 'header_preserved'
    Assert-R26D44 ($safeHeaders.'Set-Cookie' -eq 'REDACTED') 'header_secret_redacted'

    $normalRoot = Join-Path $root 'normal'
    $normal = New-D44ArtifactCase -Root $normalRoot
    $normalBody = '{"status":"ok","result":{"name":"one.snapshot"}}'
    $normalResult = Complete-NsR26SnapshotArtifact -StagingRoot $normal.stage -ArtifactRoot $normal.artifacts -Collection 'ai_lab_document_chunks' -PreInventory @() -HttpCapture (New-D44Capture -Status 200 -Body $normalBody) -ValidatorPath 'validator.js' -HelperHealth (New-D44HelperHealth) -ValidatorInvoker $validator -StabilityIntervalMilliseconds 0 -SleepInvoker $sleepNone
    Assert-R26D44 ($normalResult.creation_outcome -eq 'HTTP_2XX_NORMAL') 'normal_outcome'
    Assert-R26D44 ((Test-Path $normalResult.snapshot_artifact) -and (Test-Path $normalResult.checksum_artifact)) 'normal_two_artifacts'

    $postCounter = 0
    $reconciledRoot = Join-Path $root 'reconciled'
    $reconciled = New-D44ArtifactCase -Root $reconciledRoot
    $http500 = Invoke-NsR26QdrantHttpCapture -Uri 'http://127.0.0.1/synthetic' -Method Post -TransportInvoker {
        param($uri, $method, $timeout) $script:postCounter++; [pscustomobject]@{ status_code=500; reason_phrase='Internal Server Error'; response_body='{"status":"error"}'; response_content_type='application/json'; response_headers=[ordered]@{}; exception_type='System.Net.WebException'; network_error=$false }
    }
    $reconciledResult = Complete-NsR26SnapshotArtifact -StagingRoot $reconciled.stage -ArtifactRoot $reconciled.artifacts -Collection 'ai_lab_document_chunks' -PreInventory @() -HttpCapture $http500 -ValidatorPath 'validator.js' -HelperHealth (New-D44HelperHealth) -ValidatorInvoker $validator -StabilityIntervalMilliseconds 0 -SleepInvoker $sleepNone
    Assert-R26D44 ($reconciledResult.creation_outcome -eq 'ARTIFACT_RECONCILED_AFTER_HTTP_500') 'reconciled_outcome'
    Assert-R26D44 ($reconciledResult.creation_http_status -eq 500) 'reconciled_status'
    Assert-R26D44 ($reconciledResult.snapshot_sha256 -eq $reconciledResult.qdrant_checksum) 'reconciled_checksum'
    Assert-R26D44 ($script:postCounter -eq 1) 'no_retry_post_count_one'
    Assert-R26D44 ((Test-Path $reconciledResult.snapshot_artifact) -and (Test-Path $reconciledResult.checksum_artifact)) 'reconciled_two_artifacts'
    Assert-R26D44 (@(Get-NsR26SnapshotFileInventory -StagingRoot $reconciled.stage -Collection 'ai_lab_document_chunks').Count -eq 0) 'reconciled_staging_empty'

    $noArtifactStage = Join-Path $root 'no-artifact\stage'
    New-Item -ItemType Directory -Path $noArtifactStage -Force | Out-Null
    Assert-ThrowsD44 -Code 'QDRANT_HTTP500_NO_ARTIFACT' -Action { Complete-NsR26SnapshotArtifact -StagingRoot $noArtifactStage -ArtifactRoot (Join-Path $root 'no-artifact\artifacts') -Collection 'ai_lab_document_chunks' -PreInventory @() -HttpCapture (New-D44Capture -Status 500) -ValidatorPath 'v' -HelperHealth (New-D44HelperHealth) -ValidatorInvoker $validator -StabilityIntervalMilliseconds 0 -SleepInvoker $sleepNone }

    $missingChecksum = New-D44ArtifactCase -Root (Join-Path $root 'missing-checksum') -Checksum $false
    Assert-ThrowsD44 -Code 'QDRANT_HTTP500_CHECKSUM_MISSING' -Action { Complete-NsR26SnapshotArtifact -StagingRoot $missingChecksum.stage -ArtifactRoot $missingChecksum.artifacts -Collection 'ai_lab_document_chunks' -PreInventory @() -HttpCapture (New-D44Capture -Status 500) -ValidatorPath 'v' -HelperHealth (New-D44HelperHealth) -ValidatorInvoker $validator -StabilityIntervalMilliseconds 0 -SleepInvoker $sleepNone }

    $mismatch = New-D44ArtifactCase -Root (Join-Path $root 'mismatch') -Mismatch $true
    Assert-ThrowsD44 -Code 'QDRANT_CHECKSUM_MISMATCH' -Action { Complete-NsR26SnapshotArtifact -StagingRoot $mismatch.stage -ArtifactRoot $mismatch.artifacts -Collection 'ai_lab_document_chunks' -PreInventory @() -HttpCapture (New-D44Capture -Status 500) -ValidatorPath 'v' -HelperHealth (New-D44HelperHealth) -ValidatorInvoker $validator -StabilityIntervalMilliseconds 0 -SleepInvoker $sleepNone }

    $invalidValidator = New-D44ArtifactCase -Root (Join-Path $root 'validator')
    Assert-ThrowsD44 -Code 'QDRANT_SNAPSHOT_INVALID' -Action { Complete-NsR26SnapshotArtifact -StagingRoot $invalidValidator.stage -ArtifactRoot $invalidValidator.artifacts -Collection 'ai_lab_document_chunks' -PreInventory @() -HttpCapture (New-D44Capture -Status 500) -ValidatorPath 'v' -HelperHealth (New-D44HelperHealth) -ValidatorInvoker { param($v,$s) [pscustomobject]@{exit_code=1;output='invalid'} } -StabilityIntervalMilliseconds 0 -SleepInvoker $sleepNone }

    $ambiguous = New-D44ArtifactCase -Root (Join-Path $root 'ambiguous')
    $second = Join-Path (Split-Path $ambiguous.snapshot -Parent) 'two.snapshot'
    Copy-Item $ambiguous.snapshot $second
    Copy-Item ($ambiguous.snapshot + '.checksum') ($second + '.checksum')
    Assert-ThrowsD44 -Code 'QDRANT_SNAPSHOT_ARTIFACT_AMBIGUOUS' -Action { Complete-NsR26SnapshotArtifact -StagingRoot $ambiguous.stage -ArtifactRoot $ambiguous.artifacts -Collection 'ai_lab_document_chunks' -PreInventory @() -HttpCapture (New-D44Capture -Status 500) -ValidatorPath 'v' -HelperHealth (New-D44HelperHealth) -ValidatorInvoker $validator -StabilityIntervalMilliseconds 0 -SleepInvoker $sleepNone }

    $tmpCase = New-D44ArtifactCase -Root (Join-Path $root 'tmp') -Tmp $true
    Assert-ThrowsD44 -Code 'QDRANT_HTTP500_ARTIFACT_NOT_FINALIZED' -Action { Complete-NsR26SnapshotArtifact -StagingRoot $tmpCase.stage -ArtifactRoot $tmpCase.artifacts -Collection 'ai_lab_document_chunks' -PreInventory @() -HttpCapture (New-D44Capture -Status 500) -ValidatorPath 'v' -HelperHealth (New-D44HelperHealth) -ValidatorInvoker $validator -StabilityIntervalMilliseconds 0 -SleepInvoker $sleepNone }

    $unstable = New-D44ArtifactCase -Root (Join-Path $root 'unstable')
    $changed = $false
    Assert-ThrowsD44 -Code 'QDRANT_SNAPSHOT_ARTIFACT_UNSTABLE' -Action { Wait-NsR26SnapshotStable -LiteralPath $unstable.snapshot -IntervalMilliseconds 0 -SleepInvoker { param($ms) if(-not $script:changed){[IO.File]::AppendAllText($unstable.snapshot,'x');$script:changed=$true} } }

    foreach ($healthCase in @(
        @{ name='not_ready'; health=(New-D44HelperHealth -Ready 503); code='QDRANT_HELPER_NOT_HEALTHY_AFTER_SNAPSHOT' },
        @{ name='oom'; health=(New-D44HelperHealth -Oom $true); code='QDRANT_HELPER_NOT_HEALTHY_AFTER_SNAPSHOT' },
        @{ name='fatal'; health=(New-D44HelperHealth -Logs 'fatal synthetic'); code='QDRANT_HELPER_FATAL_LOG' }
    )) {
        $caseArtifact = New-D44ArtifactCase -Root (Join-Path $root $healthCase.name)
        Assert-ThrowsD44 -Code $healthCase.code -Action { Complete-NsR26SnapshotArtifact -StagingRoot $caseArtifact.stage -ArtifactRoot $caseArtifact.artifacts -Collection 'ai_lab_document_chunks' -PreInventory @() -HttpCapture (New-D44Capture -Status 500) -ValidatorPath 'v' -HelperHealth $healthCase.health -ValidatorInvoker $validator -StabilityIntervalMilliseconds 0 -SleepInvoker $sleepNone }
    }

    $helperText = Get-Content -LiteralPath $helperPath -Raw -Encoding UTF8
    $runnerText = Get-Content -LiteralPath $runnerPath -Raw -Encoding UTF8
    Assert-R26D44 ($helperText -match 'qdrant-helper-container-logs\.txt') 'helper_log_capture_path'
    Assert-R26D44 ($helperText -match 'CAPTURE_HELPER_DIAGNOSTICS') 'logs_before_removal_stage'
    Assert-R26D44 ($helperText.IndexOf("CAPTURE_HELPER_DIAGNOSTICS") -lt $helperText.IndexOf("STOP_HELPER")) 'logs_before_stop_order'
    Assert-R26D44 ($runnerText -match '\$record\.checksum_artifact') 'runner_checksum_record'
    Assert-R26D44 ($runnerText -match '\$_\.snapshot\.checksum') 'manifest_checksum_required'
    Write-Output "PASS_QDRANT_HTTP_RECONCILIATION_PS51 assertions=$script:Assertions"
}
finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
