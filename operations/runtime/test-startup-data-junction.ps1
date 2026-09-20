$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$script:Assertions = 0
function Assert-DataJunction {
    param([bool]$Condition, [string]$Name)
    $script:Assertions++
    if (-not $Condition) { throw ('ASSERT_FAILED: ' + $Name) }
}

$runtimeDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $runtimeDirectory 'start-host-services.ps1') -DefinitionOnly

$script:OriginalDataJunctionGetMonotonicMilliseconds = ${function:Get-MonotonicMilliseconds}
$script:DataJunctionSyntheticClock = [int64]0
function Get-MonotonicMilliseconds {
    $current = [int64]$script:DataJunctionSyntheticClock
    $script:DataJunctionSyntheticClock = $current + 1
    return $current
}

$token = [guid]::NewGuid().ToString('N')
$fixtureRoot = Join-Path $env:TEMP ('NEXT Stabil D21 Data Junction {0}' -f $token)
$installRoot = Join-Path $fixtureRoot 'install'
$targetRoot = Join-Path $fixtureRoot 'active-data-target'
$dataLink = Join-Path $installRoot 'data'
$manifestPath = Join-Path $installRoot 'operations\runtime\startup-set.json'

function Write-TestText {
    param([string]$Path, [string]$Text)
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) { [void](New-Item -ItemType Directory -Path $parent -Force) }
    [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
}

function Copy-TestObject {
    param($Value)
    return ($Value | ConvertTo-Json -Depth 30 | ConvertFrom-Json)
}

function New-DataJunctionManifest {
    $relativeFiles = [ordered]@{
        compose_config = 'compose.yaml'
        compose_helper = 'operations/windows/start-compose-after-docker.ps1'
        public_gateway_script = 'operations/gateway/public_web_server.cjs'
        private_gateway_script = 'operations/gateway/web_server.cjs'
        supervisor_script = 'operations/supervisor/server.js'
    }
    $files = @()
    foreach ($role in $relativeFiles.Keys) {
        $path = Join-Path $installRoot $relativeFiles[$role]
        Write-TestText -Path $path -Text ('fixture-' + $role)
        $files += [pscustomobject]@{ role = $role; path = $relativeFiles[$role]; sha256 = Get-StartupSha256 -Path $path }
    }
    $toolDirectory = Join-Path $fixtureRoot 'external-tools'
    $tools = @()
    foreach ($name in @('docker_cli', 'docker_desktop', 'node')) {
        $path = Join-Path $toolDirectory ($name + '.exe')
        Write-TestText -Path $path -Text ('fixture-tool-' + $name)
        $tools += [pscustomobject]@{ name = $name; path = $path; sha256 = Get-StartupSha256 -Path $path }
    }
    $nodePath = [string](@($tools | Where-Object { $_.name -eq 'node' })[0].path)
    $appMount = [pscustomobject]@{ source = (Join-Path $installRoot 'backend'); destination = '/app'; type = 'bind'; read_only = $true }
    $dataMount = [pscustomobject]@{ source = (Join-Path $dataLink 'application'); destination = '/data'; type = 'bind'; read_only = $false }
    $port = [pscustomobject]@{ host_ip = '127.0.0.1'; host_port = 18000; container_port = 8000; protocol = 'tcp' }
    $services = @(
        [pscustomobject]@{ name = 'public_gateway'; policy = 'REQUIRED'; launch_kind = 'TASK'; task_name = 'D21 data public'; task_path = '\'; executable = $nodePath; arguments = @('operations/gateway/public_web_server.cjs'); working_directory = $installRoot; listener_host = '127.0.0.1'; listener_port = 18789; script_ref = 'public_gateway_script'; tool_ref = 'node' },
        [pscustomobject]@{ name = 'private_gateway'; policy = 'REQUIRED'; launch_kind = 'TASK'; task_name = 'D21 data private'; task_path = '\'; executable = $nodePath; arguments = @('operations/gateway/web_server.cjs'); working_directory = $installRoot; listener_host = '127.0.0.1'; listener_port = 18788; script_ref = 'private_gateway_script'; tool_ref = 'node' },
        [pscustomobject]@{ name = 'supervisor'; policy = 'INTENTIONALLY_STOPPED'; launch_kind = 'TASK'; task_name = 'D21 data supervisor'; task_path = '\'; executable = $nodePath; arguments = @('operations/supervisor/server.js'); working_directory = $installRoot; listener_host = '127.0.0.1'; listener_port = 18787; script_ref = 'supervisor_script'; tool_ref = 'node' }
    )
    return [pscustomobject][ordered]@{
        schema = 'NEXT_STABIL_STARTUP_SET_V1'
        component_identity_schema = 'NEXT_STABIL_COMPONENT_COMPATIBILITY_V1'
        set_id = 'D21-DATA-JUNCTION-SYNTHETIC'
        root = $installRoot
        approval = [pscustomobject]@{ status = 'APPROVED_FOR_START'; set_id = 'D21-DATA-JUNCTION-SYNTHETIC'; decision_id = 'TEST_ONLY' }
        timeouts = [pscustomobject]@{ native_command_ms = 50; engine_stage_ms = 20; service_stage_ms = 20; poll_ms = 1; max_output_chars = 4096 }
        files = $files
        external_tools = $tools
        data_topology = [pscustomobject][ordered]@{
            schema = 'NEXT_STABIL_DATA_TOPOLOGY_V1'
            logical_path = $dataLink
            target = $targetRoot
            link_type = 'DIRECTORY_JUNCTION'
            purpose = 'ACTIVE_DATA_ONLY'
            bindings = @([pscustomobject]@{ service = 'backend'; role = 'APPLICATION_DATA'; source = (Join-Path $dataLink 'application'); destination = '/data' })
        }
        docker = [pscustomobject]@{ context = 'desktop-linux-test'; endpoint = 'npipe:////./pipe/nextStabilSynthetic'; process_name = 'Docker Desktop Synthetic'; cli_tool = 'docker_cli'; desktop_tool = 'docker_desktop' }
        containers = @([pscustomobject]@{ service = 'backend'; container_name = 'd21-data-backend'; compose_project = 'd21-data'; image_id = ('sha256:' + ('a' * 64)); repo_digest = ('sha256:' + ('b' * 64)); mounts = @($appMount, $dataMount); ports = @($port) })
        host_services = $services
        readiness = @(
            [pscustomobject]@{ name = 'backend'; uri = 'http://127.0.0.1:18000/health'; expected_status = 200 },
            [pscustomobject]@{ name = 'web'; uri = 'http://127.0.0.1:18789/'; expected_status = 200 },
            [pscustomobject]@{ name = 'public_control_boundary'; uri = 'http://127.0.0.1:18789/control'; expected_status = 404 }
        )
        client = [pscustomobject]@{ policy = 'DISABLED' }
    }
}

function Save-DataJunctionManifest {
    param($Manifest)
    Write-TestText -Path $manifestPath -Text ($Manifest | ConvertTo-Json -Depth 30)
}

function Set-DataJunctionBindingVariant {
    param(
        $Manifest,
        [string]$Service,
        [string]$Role,
        [string]$RelativeSource,
        [string]$Destination
    )
    $source = Join-Path $dataLink $RelativeSource
    $target = Join-Path $targetRoot $RelativeSource
    [void](New-Item -ItemType Directory -Path $target -Force)
    $Manifest.data_topology.bindings[0].service = $Service
    $Manifest.data_topology.bindings[0].role = $Role
    $Manifest.data_topology.bindings[0].source = $source
    $Manifest.data_topology.bindings[0].destination = $Destination
    $Manifest.containers[0].service = $Service
    $Manifest.containers[0].mounts[1].source = $source
    $Manifest.containers[0].mounts[1].destination = $Destination
    return $Manifest
}

function Assert-DataManifestRefusedBeforeAdapters {
    param($Manifest, [string]$ExpectedError, [string]$Name)
    Save-DataJunctionManifest $Manifest
    $blockedState = New-DataJunctionState $Manifest
    $blocked = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-DataJunctionAdapters $blockedState) -AllowSyntheticRoot
    $detail = @($blocked.details) -join ';'
    Assert-DataJunction ($blocked.code -eq 'MANIFEST_REFUSED' -and $detail -match $ExpectedError -and $blockedState.calls.Count -eq 0) ($Name + '; actual=' + ($blocked | ConvertTo-Json -Depth 8 -Compress))
}

function New-DataJunctionState {
    param($Manifest)
    $container = Copy-TestObject $Manifest.containers[0]
    $container | Add-Member -NotePropertyName running -NotePropertyValue $true
    $container | Add-Member -NotePropertyName state_status -NotePropertyValue 'running'
    $container | Add-Member -NotePropertyName full_id -NotePropertyValue ('d' * 64)
    $hosts = @{}
    foreach ($service in @($Manifest.host_services | Where-Object { $_.policy -eq 'REQUIRED' })) {
        $observed = Copy-TestObject $service
        $observed | Add-Member -NotePropertyName listener_ready -NotePropertyValue $true
        $hosts[$service.name] = @($observed)
    }
    return [hashtable]@{ calls = New-Object System.Collections.Generic.List[string]; container = $container; hosts = $hosts; starts = 0 }
}

function New-DataJunctionAdapters {
    param([hashtable]$State)
    return [pscustomobject]@{
        GetDockerEnvironment = { $State.calls.Add('docker.environment'); [pscustomobject]@{ context = 'desktop-linux-test'; endpoint = 'npipe:////./pipe/nextStabilSynthetic'; docker_host_override = ''; docker_context_override = '' } }.GetNewClosure()
        ObserveEngine = { $State.calls.Add('engine.observe'); [pscustomobject]@{ status = 'RESPONDING'; version = 'synthetic' } }.GetNewClosure()
        ObserveDockerDesktopProcess = { param($Definition) $State.calls.Add('desktop.observe'); @() }.GetNewClosure()
        StartDockerDesktop = { param($Definition) $State.calls.Add('desktop.start'); [pscustomobject]@{ status = 'REFUSED' } }.GetNewClosure()
        ObserveContainer = { param($Expected) $State.calls.Add('container.observe'); @($State.container) }.GetNewClosure()
        StartExistingContainer = {
            param($FullId, $Timeout)
            $State.calls.Add('container.start')
            $State.starts++
            $State.container.running = $true
            $State.container.state_status = 'running'
            [pscustomobject]@{ status = 'SUCCESS' }
        }.GetNewClosure()
        ObserveHostService = { param($Expected, $Timeout) $State.calls.Add('host.observe.' + [string]$Expected.name); if ($State.hosts.ContainsKey([string]$Expected.name)) { @($State.hosts[[string]$Expected.name]) } else { @() } }.GetNewClosure()
        StartHostService = { param($Expected, $Timeout) $State.calls.Add('host.start.' + [string]$Expected.name); [pscustomobject]@{ status = 'SUCCESS' } }.GetNewClosure()
        CheckReadiness = { param($Definition) $State.calls.Add('readiness.' + [string]$Definition.name); [pscustomobject]@{ status = [int]$Definition.expected_status } }.GetNewClosure()
        Sleep = { param($Milliseconds) }.GetNewClosure()
    }
}

try {
    [void](New-Item -ItemType Directory -Path $installRoot -Force)
    [void](New-Item -ItemType Directory -Path (Join-Path $targetRoot 'application') -Force)
    [void](New-Item -ItemType Directory -Path (Join-Path $installRoot 'backend') -Force)
    [void](New-Item -ItemType Junction -Path $dataLink -Target $targetRoot)

    $manifest = New-DataJunctionManifest
    Save-DataJunctionManifest $manifest
    $state = New-DataJunctionState $manifest
    $result = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-DataJunctionAdapters $state) -AllowSyntheticRoot
    Assert-DataJunction ($result.code -eq 'BASE_READY_LIMITED') ('owner-approved DATA_ONLY junction reaches the synthetic plan; actual=' + ($result | ConvertTo-Json -Depth 8 -Compress))
    Assert-DataJunction ($state.starts -eq 0) 'already-ready synthetic resources are not duplicated'

    $callCount = $state.calls.Count
    $repeat = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-DataJunctionAdapters $state) -AllowSyntheticRoot
    Assert-DataJunction ($repeat.code -eq 'BASE_READY_LIMITED' -and $state.starts -eq 0 -and $state.calls.Count -gt $callCount) 'second run re-observes without duplicating resources'

    $approvedVariants = @(
        [pscustomobject]@{ service = 'backend'; role = 'APPLICATION_DATA'; source = 'application'; destination = '/data' },
        [pscustomobject]@{ service = 'postgres'; role = 'POSTGRESQL_DATA'; source = 'postgres'; destination = '/var/lib/postgresql/data' },
        [pscustomobject]@{ service = 'n8n'; role = 'N8N_DATA'; source = 'n8n'; destination = '/home/node/.n8n' },
        [pscustomobject]@{ service = 'open-webui'; role = 'OPENWEBUI_DATA'; source = 'openwebui'; destination = '/app/backend/data' },
        [pscustomobject]@{ service = 'ollama'; role = 'OLLAMA_DATA'; source = 'ollama'; destination = '/root/.ollama' }
    )
    foreach ($variant in $approvedVariants) {
        $positive = Set-DataJunctionBindingVariant -Manifest (Copy-TestObject $manifest) -Service $variant.service -Role $variant.role -RelativeSource $variant.source -Destination $variant.destination
        Save-DataJunctionManifest $positive
        $positiveState = New-DataJunctionState $positive
        $positiveResult = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-DataJunctionAdapters $positiveState) -AllowSyntheticRoot
        Assert-DataJunction ($positiveResult.code -eq 'BASE_READY_LIMITED' -and $positiveState.calls.Count -gt 0 -and $positiveState.starts -eq 0) ('approved data binding reaches the synthetic plan: ' + $variant.service)
        $positiveRepeat = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-DataJunctionAdapters $positiveState) -AllowSyntheticRoot
        Assert-DataJunction ($positiveRepeat.code -eq 'BASE_READY_LIMITED' -and $positiveState.starts -eq 0) ('approved data binding remains idempotent: ' + $variant.service)
    }

    $sentinelTarget = Join-Path $targetRoot 'application\sentinel.txt'
    $sentinelLink = Join-Path $dataLink 'application\sentinel.txt'
    Write-TestText -Path $sentinelTarget -Text 'target-visible-through-link'
    Assert-DataJunction ((Get-Content -LiteralPath $sentinelLink -Raw) -eq 'target-visible-through-link') 'sentinel written at target is visible through synthetic junction'
    Write-TestText -Path $sentinelLink -Text 'link-visible-at-target'
    Assert-DataJunction ((Get-Content -LiteralPath $sentinelTarget -Raw) -eq 'link-visible-at-target') 'sentinel written through junction changes the owned target'

    $notApproved = Copy-TestObject $manifest
    $notApproved.approval.status = 'NOT_APPROVED'
    Save-DataJunctionManifest $notApproved
    $blockedState = New-DataJunctionState $manifest
    $blocked = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-DataJunctionAdapters $blockedState) -AllowSyntheticRoot
    Assert-DataJunction ($blocked.code -eq 'MANIFEST_REFUSED' -and @($blocked.details) -contains 'START_NOT_APPROVED' -and $blockedState.calls.Count -eq 0) 'data topology does not approve startup or invoke adapters'

    $wrongTarget = Copy-TestObject $manifest
    $wrongTarget.data_topology.target = Join-Path $fixtureRoot 'wrong-target'
    [void](New-Item -ItemType Directory -Path $wrongTarget.data_topology.target -Force)
    Save-DataJunctionManifest $wrongTarget
    $blockedState = New-DataJunctionState $manifest
    $blocked = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-DataJunctionAdapters $blockedState) -AllowSyntheticRoot
    Assert-DataJunction ($blocked.code -eq 'MANIFEST_REFUSED' -and (@($blocked.details) -join ';') -match 'DATA_TOPOLOGY_JUNCTION_TARGET_MISMATCH' -and $blockedState.calls.Count -eq 0) 'different target is refused before effects'

    $missingTarget = Copy-TestObject $manifest
    $missingTarget.data_topology.target = Join-Path $fixtureRoot 'missing-target'
    Save-DataJunctionManifest $missingTarget
    $blockedState = New-DataJunctionState $manifest
    $blocked = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-DataJunctionAdapters $blockedState) -AllowSyntheticRoot
    Assert-DataJunction ($blocked.code -eq 'MANIFEST_REFUSED' -and $blockedState.calls.Count -eq 0 -and -not (Test-Path -LiteralPath $missingTarget.data_topology.target)) 'missing target refuses without creating fallback data'

    $plainManifest = Copy-TestObject $manifest
    [System.IO.Directory]::Delete($dataLink)
    [void](New-Item -ItemType Directory -Path (Join-Path $dataLink 'application') -Force)
    Save-DataJunctionManifest $plainManifest
    $blockedState = New-DataJunctionState $manifest
    $blocked = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-DataJunctionAdapters $blockedState) -AllowSyntheticRoot
    Assert-DataJunction ($blocked.code -eq 'MANIFEST_REFUSED' -and (@($blocked.details) -join ';') -match 'DATA_TOPOLOGY_NOT_DIRECTORY_JUNCTION' -and $blockedState.calls.Count -eq 0) 'plain directory is not accepted as the approved junction'
    Remove-Item -LiteralPath $dataLink -Recurse -Force
    [void](New-Item -ItemType Junction -Path $dataLink -Target $targetRoot)

    $originalMetadataFunction = (Get-Command Get-StartupDirectoryLinkMetadata -CommandType Function).Definition
    try {
        Set-Item -Path Function:\Get-StartupDirectoryLinkMetadata -Value { param([string]$Path) [pscustomobject]@{ status = 'UNKNOWN'; link_type = ''; target = '' } }
        $unknown = Test-StartupSetManifest -Manifest $manifest -ManifestPath $manifestPath -ExpectedRoot $installRoot -AllowSyntheticRoot
    }
    finally {
        Set-Item -Path Function:\Get-StartupDirectoryLinkMetadata -Value ([scriptblock]::Create($originalMetadataFunction))
    }
    Assert-DataJunction (-not $unknown.valid -and (@($unknown.errors) -join ';') -match 'DATA_TOPOLOGY_LINK_UNKNOWN') 'unreadable junction metadata is UNKNOWN/refused'

    $originalMetadataFunction = (Get-Command Get-StartupDirectoryLinkMetadata -CommandType Function).Definition
    try {
        Set-Item -Path Function:\Get-StartupDirectoryLinkMetadata -Value { param([string]$Path) [pscustomobject]@{ status = 'PRESENT'; link_type = 'SYMBOLICLINK'; target = $targetRoot } }.GetNewClosure()
        $wrongLinkType = Test-StartupSetManifest -Manifest $manifest -ManifestPath $manifestPath -ExpectedRoot $installRoot -AllowSyntheticRoot
    }
    finally {
        Set-Item -Path Function:\Get-StartupDirectoryLinkMetadata -Value ([scriptblock]::Create($originalMetadataFunction))
    }
    Assert-DataJunction (-not $wrongLinkType.valid -and (@($wrongLinkType.errors) -join ';') -match 'DATA_TOPOLOGY_NOT_DIRECTORY_JUNCTION') 'symbolic-link metadata is not accepted as a directory junction'

    $nestedTarget = Join-Path $fixtureRoot 'nested-target'
    $nestedLinkAtTarget = Join-Path $targetRoot 'application\nested-junction'
    [void](New-Item -ItemType Directory -Path $nestedTarget -Force)
    [void](New-Item -ItemType Junction -Path $nestedLinkAtTarget -Target $nestedTarget)
    $nested = Copy-TestObject $manifest
    $nested.data_topology.bindings[0].source = Join-Path $dataLink 'application\nested-junction'
    $nested.containers[0].mounts[1].source = $nested.data_topology.bindings[0].source
    Save-DataJunctionManifest $nested
    $blockedState = New-DataJunctionState $nested
    $blocked = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-DataJunctionAdapters $blockedState) -AllowSyntheticRoot
    Assert-DataJunction ($blocked.code -eq 'MANIFEST_REFUSED' -and (@($blocked.details) -join ';') -match 'UNEXPECTED_REPARSE_POINT' -and $blockedState.calls.Count -eq 0) 'nested junction does not extend the DATA_ONLY exception'
    [System.IO.Directory]::Delete($nestedLinkAtTarget)

    $data2 = Copy-TestObject $manifest
    $data2.data_topology.logical_path = Join-Path $installRoot 'data2'
    Save-DataJunctionManifest $data2
    $blockedState = New-DataJunctionState $manifest
    $blocked = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-DataJunctionAdapters $blockedState) -AllowSyntheticRoot
    Assert-DataJunction ($blocked.code -eq 'MANIFEST_REFUSED' -and (@($blocked.details) -join ';') -match 'DATA_TOPOLOGY_LOGICAL_PATH_MISMATCH' -and $blockedState.calls.Count -eq 0) 'data2 prefix trick is refused'

    $traversal = Copy-TestObject $manifest
    $traversal.data_topology.bindings[0].source = Join-Path $dataLink 'application\..\..\backend'
    $traversal.containers[0].mounts[1].source = $traversal.data_topology.bindings[0].source
    Save-DataJunctionManifest $traversal
    $blockedState = New-DataJunctionState $traversal
    $blocked = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-DataJunctionAdapters $blockedState) -AllowSyntheticRoot
    Assert-DataJunction ($blocked.code -eq 'MANIFEST_REFUSED' -and (@($blocked.details) -join ';') -match 'DATA_BINDING_SOURCE_OUTSIDE_DATA' -and $blockedState.calls.Count -eq 0) 'data traversal cannot escape the approved data root'

    $wrongContractPairs = @(
        [pscustomobject]@{ service = 'postgres'; role = 'N8N_DATA'; source = 'postgres'; destination = '/home/node/.n8n' },
        [pscustomobject]@{ service = 'backend'; role = 'OPENWEBUI_DATA'; source = 'application'; destination = '/app/backend/data' },
        [pscustomobject]@{ service = 'unknown-service'; role = 'APPLICATION_DATA'; source = 'application'; destination = '/data' },
        [pscustomobject]@{ service = 'backend'; role = 'UNKNOWN_DATA'; source = 'application'; destination = '/data' }
    )
    foreach ($pair in $wrongContractPairs) {
        $wrongPair = Set-DataJunctionBindingVariant -Manifest (Copy-TestObject $manifest) -Service $pair.service -Role $pair.role -RelativeSource $pair.source -Destination $pair.destination
        Assert-DataManifestRefusedBeforeAdapters -Manifest $wrongPair -ExpectedError 'DATA_BINDING_(CONTRACT_MISMATCH|ROLE_INVALID)' -Name ('service role destination contract is fixed: ' + $pair.service + '/' + $pair.role)
    }

    foreach ($destination in @('/app', '/app/app', '/app/.', '/app/', '/app/../app', '/app/backend/data', '/unapproved', '/Data')) {
        $wrongDestination = Copy-TestObject $manifest
        $wrongDestination.data_topology.bindings[0].destination = $destination
        $wrongDestination.containers[0].mounts[1].destination = $destination
        Assert-DataManifestRefusedBeforeAdapters -Manifest $wrongDestination -ExpectedError 'DATA_BINDING_CONTRACT_MISMATCH' -Name ('backend application data refuses unapproved destination ' + $destination)
    }

    $emptyDestination = Copy-TestObject $manifest
    $emptyDestination.data_topology.bindings[0].destination = ''
    $emptyDestination.containers[0].mounts[1].destination = ''
    Assert-DataManifestRefusedBeforeAdapters -Manifest $emptyDestination -ExpectedError 'DATA_BINDING_DESTINATION_INVALID' -Name 'empty destination is refused before adapters'

    $additionalDataMount = Copy-TestObject $manifest
    $additionalDataMount.containers[0].mounts += [pscustomobject]@{ source = (Join-Path $dataLink 'application'); destination = '/extra'; type = 'bind'; read_only = $false }
    Assert-DataManifestRefusedBeforeAdapters -Manifest $additionalDataMount -ExpectedError 'CONTAINER_BIND_REPARSE_POINT' -Name 'additional unapproved mount through the junction is refused'

    $appThroughData = Copy-TestObject $manifest
    $appThroughData.data_topology.bindings[0].destination = '/app'
    $appThroughData.containers[0].mounts = @($appThroughData.containers[0].mounts[1])
    $appThroughData.containers[0].mounts[0].destination = '/app'
    Save-DataJunctionManifest $appThroughData
    $blockedState = New-DataJunctionState $appThroughData
    $blocked = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-DataJunctionAdapters $blockedState) -AllowSyntheticRoot
    Assert-DataJunction ($blocked.code -eq 'MANIFEST_REFUSED' -and (@($blocked.details) -join ';') -match 'DATA_BINDING_CONTRACT_MISMATCH' -and $blockedState.calls.Count -eq 0) '/app cannot use the data-only exception'

    $directTarget = Copy-TestObject $manifest
    $directTarget.containers[0].mounts[1].source = Join-Path $targetRoot 'application'
    Save-DataJunctionManifest $directTarget
    $blockedState = New-DataJunctionState $directTarget
    $blocked = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-DataJunctionAdapters $blockedState) -AllowSyntheticRoot
    Assert-DataJunction ($blocked.code -eq 'MANIFEST_REFUSED' -and (@($blocked.details) -join ';') -match 'CONTAINER_BIND_OUTSIDE_ROOT' -and $blockedState.calls.Count -eq 0) 'direct target path is not executable mount authority'

    $toolThroughData = Copy-TestObject $manifest
    $nodeDataPath = Join-Path $dataLink 'application\node.exe'
    Write-TestText -Path $nodeDataPath -Text 'not-an-approved-tool-location'
    $nodeTool = @($toolThroughData.external_tools | Where-Object { $_.name -eq 'node' })[0]
    $nodeTool.path = $nodeDataPath
    $nodeTool.sha256 = Get-StartupSha256 -Path $nodeDataPath
    foreach ($hostService in $toolThroughData.host_services) { $hostService.executable = $nodeDataPath }
    Save-DataJunctionManifest $toolThroughData
    $blockedState = New-DataJunctionState $toolThroughData
    $blocked = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-DataJunctionAdapters $blockedState) -AllowSyntheticRoot
    Assert-DataJunction ($blocked.code -eq 'MANIFEST_REFUSED' -and (@($blocked.details) -join ';') -match 'TOOL_PATH_USES_ACTIVE_DATA' -and $blockedState.calls.Count -eq 0) 'executables cannot use the data-only exception'

    $cwdThroughData = Copy-TestObject $manifest
    $cwdThroughData.host_services[0].working_directory = Join-Path $dataLink 'application'
    Save-DataJunctionManifest $cwdThroughData
    $blockedState = New-DataJunctionState $cwdThroughData
    $blocked = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-DataJunctionAdapters $blockedState) -AllowSyntheticRoot
    Assert-DataJunction ($blocked.code -eq 'MANIFEST_REFUSED' -and (@($blocked.details) -join ';') -match 'HOST_SERVICE_WORKING_DIRECTORY_MISMATCH' -and $blockedState.calls.Count -eq 0) 'host-service CWD remains bound to the code root'

    $scriptThroughData = Copy-TestObject $manifest
    $scriptDataPath = Join-Path $dataLink 'application\public_web_server.cjs'
    Write-TestText -Path $scriptDataPath -Text 'not-an-approved-code-location'
    $scriptFile = @($scriptThroughData.files | Where-Object { $_.role -eq 'public_gateway_script' })[0]
    $scriptFile.path = 'data\application\public_web_server.cjs'
    $scriptFile.sha256 = Get-StartupSha256 -Path $scriptDataPath
    $scriptThroughData.host_services[0].arguments = @('data\application\public_web_server.cjs')
    Save-DataJunctionManifest $scriptThroughData
    $blockedState = New-DataJunctionState $scriptThroughData
    $blocked = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-DataJunctionAdapters $blockedState) -AllowSyntheticRoot
    Assert-DataJunction ($blocked.code -eq 'MANIFEST_REFUSED' -and (@($blocked.details) -join ';') -match 'FILE_REPARSE_POINT' -and $blockedState.calls.Count -eq 0) 'script_ref remains forbidden through active data'

    $allCalls = @($state.calls) -join ';'
    Assert-DataJunction ($allCalls -notmatch '(?i)backup|restore|supervisor\.start|host\.start\.supervisor') 'data validation adds no backup restore or Supervisor action'

    Write-Output ('D21_DATA_JUNCTION_TEST_PASS assertions={0}' -f $script:Assertions)
}
finally {
    Set-Item -Path Function:\Get-MonotonicMilliseconds -Value $script:OriginalDataJunctionGetMonotonicMilliseconds
    $nestedLinkAtTarget = Join-Path $targetRoot 'application\nested-junction'
    if (Test-Path -LiteralPath $nestedLinkAtTarget) {
        $nestedItem = Get-Item -LiteralPath $nestedLinkAtTarget -Force
        if (($nestedItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -and $nestedItem.FullName -eq $nestedLinkAtTarget) { [System.IO.Directory]::Delete($nestedLinkAtTarget) }
    }
    if (Test-Path -LiteralPath $dataLink) {
        $item = Get-Item -LiteralPath $dataLink -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -and $item.FullName -eq $dataLink) {
            [System.IO.Directory]::Delete($dataLink)
        }
    }
    if (Test-Path -LiteralPath $fixtureRoot) {
        $resolved = [System.IO.Path]::GetFullPath($fixtureRoot)
        $tempRoot = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
        if ($resolved.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and $resolved -match 'NEXT Stabil D21 Data Junction [0-9a-f]{32}$') {
            Remove-Item -LiteralPath $resolved -Recurse -Force
        }
    }
}
