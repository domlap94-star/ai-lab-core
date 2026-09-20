$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$script:Assertions = 0
function Assert-P4Package {
    param([bool]$Condition, [string]$Name)
    $script:Assertions++
    if (-not $Condition) { throw ('ASSERT_FAILED: ' + $Name) }
}

$runtimeDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $runtimeDirectory 'start-host-services.ps1') -DefinitionOnly

$script:OriginalP4GetMonotonicMilliseconds = ${function:Get-MonotonicMilliseconds}
$script:ActiveP4SyntheticClock = $null
function Get-MonotonicMilliseconds {
    if ($null -ne $script:ActiveP4SyntheticClock) { return [int64]$script:ActiveP4SyntheticClock.milliseconds }
    return [int64](& $script:OriginalP4GetMonotonicMilliseconds)
}

$token = [guid]::NewGuid().ToString('N')
$fixtureRoot = Join-Path $env:TEMP ('NEXT Stabil D21 P4 Package {0}' -f $token)
$installRoot = Join-Path $fixtureRoot 'install'
$targetRoot = Join-Path $fixtureRoot 'active-data-target'
$dataLink = Join-Path $installRoot 'data'
$manifestPath = Join-Path $installRoot 'operations\runtime\startup-set.json'

function Write-P4Fixture {
    param([string]$Path, [string]$Text)
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) { [void](New-Item -ItemType Directory -Path $parent -Force) }
    [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
}

function Copy-P4Object {
    param($Value)
    return ($Value | ConvertTo-Json -Depth 40 | ConvertFrom-Json)
}

function Save-P4Manifest {
    param($Manifest)
    Write-P4Fixture -Path $manifestPath -Text ($Manifest | ConvertTo-Json -Depth 40)
}

function New-P4Container {
    param(
        [string]$Service,
        [string]$ContainerName,
        [string]$ContainerId,
        [string]$ImageHex,
        [string]$DigestHex,
        [int]$Order,
        [string]$HealthRequirement,
        [object[]]$Mounts,
        [object[]]$Ports,
        [string[]]$Dependencies = @()
    )
    return [pscustomobject][ordered]@{
        service = $Service
        container_name = $ContainerName
        compose_project = 'ai-lab-core'
        container_id = $ContainerId
        image_id = 'sha256:' + $ImageHex
        image_identity_mode = 'REPO_DIGEST'
        repo_digest = 'sha256:' + $DigestHex
        startup_order = $Order
        health_requirement = $HealthRequirement
        depends_on_healthy = @($Dependencies)
        mounts = @($Mounts)
        ports = @($Ports)
    }
}

function New-P4Manifest {
    $relativeFiles = [ordered]@{
        compose_config = 'compose.yaml'
        compose_helper = 'operations/windows/start-compose-after-docker.ps1'
        public_gateway_script = 'operations/gateway/public_web_server.cjs'
        private_gateway_script = 'operations/gateway/web_server.cjs'
        supervisor_script = 'operations/supervisor/server.js'
        startup_launcher = 'operations/runtime/start-host-services.ps1'
        startup_runtime = 'operations/runtime/startup-runtime.ps1'
        backend_override = 'operations/runtime/approved-compose/R04-D21-P3-core.override.yml'
    }
    $files = @()
    foreach ($role in $relativeFiles.Keys) {
        $path = Join-Path $installRoot $relativeFiles[$role]
        Write-P4Fixture -Path $path -Text ('fixture-' + $role)
        $files += [pscustomobject]@{ role = $role; path = $relativeFiles[$role]; sha256 = Get-StartupSha256 -Path $path }
    }
    $toolDirectory = Join-Path $fixtureRoot 'external-tools'
    $tools = @()
    foreach ($name in @('docker_cli', 'docker_desktop', 'node')) {
        $path = Join-Path $toolDirectory ($name + '.exe')
        Write-P4Fixture -Path $path -Text ('fixture-tool-' + $name)
        $tools += [pscustomobject]@{ name = $name; path = $path; sha256 = Get-StartupSha256 -Path $path }
    }
    $nodePath = [string](@($tools | Where-Object { $_.name -eq 'node' })[0].path)
    $dataBindings = @(
        [pscustomobject]@{ service = 'backend'; role = 'APPLICATION_DATA'; source = (Join-Path $dataLink 'application'); destination = '/data' },
        [pscustomobject]@{ service = 'postgres'; role = 'POSTGRESQL_DATA'; source = (Join-Path $dataLink 'postgres'); destination = '/var/lib/postgresql/data' },
        [pscustomobject]@{ service = 'n8n'; role = 'N8N_DATA'; source = (Join-Path $dataLink 'n8n'); destination = '/home/node/.n8n' },
        [pscustomobject]@{ service = 'open-webui'; role = 'OPENWEBUI_DATA'; source = (Join-Path $dataLink 'openwebui'); destination = '/app/backend/data' },
        [pscustomobject]@{ service = 'ollama'; role = 'OLLAMA_DATA'; source = (Join-Path $dataLink 'ollama'); destination = '/root/.ollama' }
    )
    foreach ($binding in $dataBindings) { [void](New-Item -ItemType Directory -Path ([string]$binding.source).Replace($dataLink, $targetRoot) -Force) }
    [void](New-Item -ItemType Directory -Path (Join-Path $installRoot 'backend') -Force)
    $containers = @(
        (New-P4Container -Service 'backend' -ContainerName 'ai-lab-backend' -ContainerId ('1' * 64) -ImageHex ('a' * 64) -DigestHex ('b' * 64) -Order 60 -HealthRequirement 'RUNNING' -Dependencies @('postgres') -Mounts @(
            [pscustomobject]@{ source = (Join-Path $installRoot 'backend'); destination = '/app'; type = 'bind'; read_only = $true },
            [pscustomobject]@{ source = (Join-Path $dataLink 'application'); destination = '/data'; type = 'bind'; read_only = $false }
        ) -Ports @([pscustomobject]@{ host_ip = '127.0.0.1'; host_port = 18000; container_port = 8000; protocol = 'tcp' })),
        (New-P4Container -Service 'postgres' -ContainerName 'postgres' -ContainerId ('2' * 64) -ImageHex ('c' * 64) -DigestHex ('d' * 64) -Order 10 -HealthRequirement 'HEALTHY' -Mounts @(
            [pscustomobject]@{ source = (Join-Path $dataLink 'postgres'); destination = '/var/lib/postgresql/data'; type = 'bind'; read_only = $false }
        ) -Ports @([pscustomobject]@{ host_ip = '127.0.0.1'; host_port = 15432; container_port = 5432; protocol = 'tcp' })),
        (New-P4Container -Service 'qdrant' -ContainerName 'qdrant' -ContainerId ('3' * 64) -ImageHex ('e' * 64) -DigestHex ('f' * 64) -Order 20 -HealthRequirement 'RUNNING' -Mounts @(
            [pscustomobject]@{ source = 'qdrant_storage'; destination = '/qdrant/storage'; type = 'volume'; read_only = $false }
        ) -Ports @(
            [pscustomobject]@{ host_ip = '127.0.0.1'; host_port = 16333; container_port = 6333; protocol = 'tcp' },
            [pscustomobject]@{ host_ip = '127.0.0.1'; host_port = 16334; container_port = 6334; protocol = 'tcp' }
        )),
        (New-P4Container -Service 'n8n' -ContainerName 'n8n' -ContainerId ('4' * 64) -ImageHex ('1' * 64) -DigestHex ('2' * 64) -Order 30 -HealthRequirement 'RUNNING' -Mounts @(
            [pscustomobject]@{ source = (Join-Path $dataLink 'n8n'); destination = '/home/node/.n8n'; type = 'bind'; read_only = $false }
        ) -Ports @([pscustomobject]@{ host_ip = '127.0.0.1'; host_port = 15678; container_port = 5678; protocol = 'tcp' })),
        (New-P4Container -Service 'open-webui' -ContainerName 'open-webui' -ContainerId ('5' * 64) -ImageHex ('3' * 64) -DigestHex ('4' * 64) -Order 40 -HealthRequirement 'RUNNING' -Mounts @(
            [pscustomobject]@{ source = (Join-Path $dataLink 'openwebui'); destination = '/app/backend/data'; type = 'bind'; read_only = $false }
        ) -Ports @([pscustomobject]@{ host_ip = '127.0.0.1'; host_port = 13000; container_port = 8080; protocol = 'tcp' })),
        (New-P4Container -Service 'ollama' -ContainerName 'ollama' -ContainerId ('6' * 64) -ImageHex ('5' * 64) -DigestHex ('6' * 64) -Order 50 -HealthRequirement 'RUNNING' -Mounts @(
            [pscustomobject]@{ source = (Join-Path $dataLink 'ollama'); destination = '/root/.ollama'; type = 'bind'; read_only = $false }
        ) -Ports @([pscustomobject]@{ host_ip = '127.0.0.1'; host_port = 21434; container_port = 11434; protocol = 'tcp' }))
    )
    $hostServices = @(
        [pscustomobject]@{ name = 'public_gateway'; policy = 'REQUIRED'; launch_kind = 'TASK'; task_name = 'P4 public'; task_path = '\'; executable = $nodePath; arguments = @('operations/gateway/public_web_server.cjs'); working_directory = $installRoot; listener_host = '127.0.0.1'; listener_port = 18789; script_ref = 'public_gateway_script'; tool_ref = 'node' },
        [pscustomobject]@{ name = 'private_gateway'; policy = 'REQUIRED'; launch_kind = 'TASK'; task_name = 'P4 private'; task_path = '\'; executable = $nodePath; arguments = @('operations/gateway/web_server.cjs'); working_directory = $installRoot; listener_host = '127.0.0.1'; listener_port = 18788; script_ref = 'private_gateway_script'; tool_ref = 'node' },
        [pscustomobject]@{ name = 'supervisor'; policy = 'INTENTIONALLY_STOPPED'; launch_kind = 'TASK'; task_name = 'P4 supervisor'; task_path = '\'; executable = $nodePath; arguments = @('operations/supervisor/server.js'); working_directory = $installRoot; listener_host = '127.0.0.1'; listener_port = 18787; script_ref = 'supervisor_script'; tool_ref = 'node' }
    )
    return [pscustomobject][ordered]@{
        schema = 'NEXT_STABIL_STARTUP_SET_V1'
        component_identity_schema = 'NEXT_STABIL_COMPONENT_COMPATIBILITY_V1'
        startup_package_schema = 'NEXT_STABIL_STARTUP_PACKAGE_V1'
        set_id = 'R04-D21-P4A-SYNTHETIC'
        root = $installRoot
        approval = [pscustomobject]@{ status = 'APPROVED_FOR_START'; set_id = 'R04-D21-P4A-SYNTHETIC'; decision_id = 'TEST_ONLY' }
        timeouts = [pscustomobject]@{ native_command_ms = 50; engine_stage_ms = 30; service_stage_ms = 30; poll_ms = 1; max_output_chars = 4096 }
        files = $files
        external_tools = $tools
        data_topology = [pscustomobject]@{ schema = 'NEXT_STABIL_DATA_TOPOLOGY_V1'; logical_path = $dataLink; target = $targetRoot; link_type = 'DIRECTORY_JUNCTION'; purpose = 'ACTIVE_DATA_ONLY'; bindings = $dataBindings }
        docker = [pscustomobject]@{ context = 'desktop-linux-test'; endpoint = 'npipe:////./pipe/nextStabilSynthetic'; process_name = 'Docker Desktop Synthetic'; cli_tool = 'docker_cli'; desktop_tool = 'docker_desktop' }
        containers = $containers
        host_services = $hostServices
        readiness = @(
            [pscustomobject]@{ name = 'backend'; uri = 'http://127.0.0.1:18000/health'; expected_status = 200 },
            [pscustomobject]@{ name = 'web'; uri = 'http://127.0.0.1:18789/'; expected_status = 200 },
            [pscustomobject]@{ name = 'public_control_boundary'; uri = 'http://127.0.0.1:18789/control'; expected_status = 404 }
        )
        client = [pscustomobject]@{ policy = 'DISABLED' }
    }
}

function New-P4State {
    param($Manifest, [bool]$Running = $true)
    $containers = @{}
    foreach ($expected in $Manifest.containers) {
        $observed = Copy-P4Object $expected
        $observed | Add-Member -NotePropertyName full_id -NotePropertyValue ([string]$expected.container_id)
        $observed | Add-Member -NotePropertyName running -NotePropertyValue $Running
        $observed | Add-Member -NotePropertyName state_status -NotePropertyValue $(if ($Running) { 'running' } else { 'exited' })
        $observed | Add-Member -NotePropertyName configured_ports -NotePropertyValue @($expected.ports)
        $observed | Add-Member -NotePropertyName active_ports -NotePropertyValue $(if ($Running) { @($expected.ports) } else { @() })
        $observed | Add-Member -NotePropertyName repo_digest_state -NotePropertyValue 'OBSERVED'
        $observed | Add-Member -NotePropertyName health_status -NotePropertyValue $(if ($expected.service -eq 'postgres' -and $Running) { 'healthy' } else { 'NONE' })
        $containers[[string]$expected.service] = $observed
    }
    $drillObservations = @()
    foreach ($drill in @(
        [pscustomobject]@{ id = ('7' * 64); name = 'next-stabil-r03-a1-drill-20260908-a4-qdrant-2-client' },
        [pscustomobject]@{ id = ('8' * 64); name = 'next-stabil-r03-a1-drill-20260908-a4-qdrant-1-client' },
        [pscustomobject]@{ id = ('9' * 64); name = 'next-stabil-r03-a1-drill-20260908-a1-qdrant-2-client' },
        [pscustomobject]@{ id = ('a' * 64); name = 'next-stabil-r03-a1-drill-20260908-a1-qdrant-1-client' }
    )) {
        $drillObservations += [pscustomobject]@{
            full_id = $drill.id
            container_name = $drill.name
            compose_project = 'ai-lab-core'
            service = 'backend'
            image_id = 'sha256:' + ('a' * 64)
            repo_digest = 'sha256:' + ('b' * 64)
            repo_digest_state = 'OBSERVED'
            running = $false
            state_status = 'exited'
            health_status = 'NOT_CONFIGURED'
            mounts = @()
            configured_ports = @()
            active_ports = @()
        }
    }
    $hosts = @{}
    foreach ($service in $Manifest.host_services) {
        if ($service.policy -eq 'REQUIRED') {
            $ready = Copy-P4Object $service
            $ready | Add-Member -NotePropertyName listener_ready -NotePropertyValue $true
            $hosts[[string]$service.name] = @($ready)
        }
        else { $hosts[[string]$service.name] = @() }
    }
    return [hashtable]@{
        calls = New-Object System.Collections.Generic.List[string]
        containers = $containers
        hosts = $hosts
        container_starts = New-Object System.Collections.Generic.List[string]
        host_starts = @{}
        postgres_health_mode = 'NORMAL'
        postgres_running_observations = 0
        extra_container_observations = @{ backend = $drillObservations }
        test_clock = [hashtable]@{ milliseconds = [int64]0 }
    }
}

function New-P4Adapters {
    param([hashtable]$State)
    return [pscustomobject]@{
        GetDockerEnvironment = { $State.calls.Add('docker.environment'); [pscustomobject]@{ context = 'desktop-linux-test'; endpoint = 'npipe:////./pipe/nextStabilSynthetic'; docker_host_override = ''; docker_context_override = '' } }.GetNewClosure()
        ObserveEngine = { $State.calls.Add('engine.observe'); [pscustomobject]@{ status = 'RESPONDING'; version = 'synthetic' } }.GetNewClosure()
        ObserveDockerDesktopProcess = { param($Definition) throw 'UNEXPECTED_DESKTOP_OBSERVE' }.GetNewClosure()
        StartDockerDesktop = { param($Definition) throw 'UNEXPECTED_DESKTOP_START' }.GetNewClosure()
        ObserveContainer = {
            param($Expected)
            $service = [string]$Expected.service
            $State.calls.Add('container.observe.' + $service)
            $State.test_clock.milliseconds = [int64]$State.test_clock.milliseconds + 1
            $observed = $State.containers[$service]
            if ($service -eq 'postgres' -and [bool]$observed.running) {
                $State.postgres_running_observations++
                if ($State.postgres_health_mode -eq 'STUCK') { $observed.health_status = 'starting' }
                elseif ($State.postgres_running_observations -eq 1) { $observed.health_status = 'starting' }
                else { $observed.health_status = 'healthy' }
                $State.calls.Add(('postgres.health.' + [string]$observed.health_status))
            }
            return @($observed) + @($State.extra_container_observations[$service])
        }.GetNewClosure()
        StartExistingContainer = {
            param($FullId, $Timeout)
            $service = @($State.containers.Keys | Where-Object { [string]$State.containers[$_].full_id -eq [string]$FullId })[0]
            $State.calls.Add('container.start.' + $service)
            $State.container_starts.Add($service)
            $State.test_clock.milliseconds = [int64]$State.test_clock.milliseconds + 1
            $State.containers[$service].running = $true
            $State.containers[$service].state_status = 'running'
            $State.containers[$service].active_ports = @($State.containers[$service].ports)
            if ($service -eq 'postgres') { $State.containers[$service].health_status = 'starting' }
            [pscustomobject]@{ status = 'SUCCESS'; process_left_running = $false }
        }.GetNewClosure()
        ObserveHostService = { param($Expected, $Timeout) $State.calls.Add('host.observe.' + [string]$Expected.name); $State.test_clock.milliseconds = [int64]$State.test_clock.milliseconds + 1; @($State.hosts[[string]$Expected.name]) }.GetNewClosure()
        StartHostService = {
            param($Expected, $Timeout)
            $name = [string]$Expected.name
            $State.calls.Add('host.start.' + $name)
            $State.test_clock.milliseconds = [int64]$State.test_clock.milliseconds + 1
            if (-not $State.host_starts.ContainsKey($name)) { $State.host_starts[$name] = 0 }
            $State.host_starts[$name]++
            $ready = Copy-P4Object $Expected
            $ready | Add-Member -NotePropertyName listener_ready -NotePropertyValue $true
            $State.hosts[$name] = @($ready)
            [pscustomobject]@{ status = 'SUCCESS'; operation_may_have_started = $false }
        }.GetNewClosure()
        CheckReadiness = { param($Definition) $State.calls.Add('readiness.' + [string]$Definition.name); $State.test_clock.milliseconds = [int64]$State.test_clock.milliseconds + 1; [pscustomobject]@{ status = [int]$Definition.expected_status } }.GetNewClosure()
        Sleep = { param($Milliseconds) $State.test_clock.milliseconds = [int64]$State.test_clock.milliseconds + [Math]::Max(0, [int]$Milliseconds) }.GetNewClosure()
    }
}

function New-P4NativeEnvelope {
    param(
        [string]$Status,
        [string]$Stdout = '',
        [string]$Stderr = '',
        [int]$ExitCode = 0,
        [bool]$StdoutTruncated = $false,
        [bool]$StderrTruncated = $false
    )
    return [pscustomobject]@{
        status = $Status
        started = $true
        timed_out = $false
        exit_code = $ExitCode
        pid = 5151
        process_left_running = $false
        duration_ms = 1
        stdout = $Stdout
        stderr = $Stderr
        stdout_truncated = $StdoutTruncated
        stderr_truncated = $StderrTruncated
    }
}

function New-P4RealAdapterState {
    param($Manifest, [bool]$Running = $true)
    $state = New-P4State -Manifest $Manifest -Running $Running
    $state.raw_host_modes = @{ public_gateway = 'READY'; private_gateway = 'READY'; supervisor = 'ABSENT' }
    $state.raw_native_calls = New-Object System.Collections.Generic.List[object]
    $state.raw_host_starts = @{ public_gateway = 0; private_gateway = 0; supervisor = 0 }
    $state.inspect_stdout_truncated = @{}
    $state.selector_stdout_truncated = @{}
    $state.selector_stderr_truncated = @{}
    $state.selector_override = @{}
    $state.read_delay_service = ''
    $state.read_delay_ms = 0
    return $state
}

function ConvertTo-P4DockerProjectionJson {
    param($Observed, [hashtable]$State)
    $configured = [ordered]@{}
    $active = [ordered]@{}
    $portSource = if (Test-StartupProperty -InputObject $Observed -Name 'ports') { @($Observed.ports) } else { @($Observed.configured_ports) }
    foreach ($port in $portSource) {
        $key = ([string]$port.container_port) + '/' + ([string]$port.protocol)
        $binding = [ordered]@{ HostIp = [string]$port.host_ip; HostPort = [string]$port.host_port }
        $configured[$key] = @($binding)
        if ([bool]$Observed.running) { $active[$key] = @($binding) }
    }
    $mounts = @(@($Observed.mounts) | ForEach-Object {
        [ordered]@{
            Type = [string]$_.type
            Name = $(if ([string]$_.type -eq 'volume') { [string]$_.source } else { '' })
            Source = $(if ([string]$_.type -eq 'volume') { '' } else { [string]$_.source })
            Destination = [string]$_.destination
            RW = -not [bool]$_.read_only
        }
    })
    $health = $null
    if ([string]$Observed.service -eq 'postgres' -and [bool]$Observed.running) {
        $State.postgres_running_observations++
        if ($State.postgres_health_mode -eq 'STUCK' -or $State.postgres_running_observations -eq 1) { $health = 'starting' }
        else { $health = 'healthy' }
        $Observed.health_status = $health
        $State.calls.Add('raw.postgres.health.' + $health)
    }
    elseif ([string]$Observed.health_status -in @('healthy', 'starting', 'unhealthy')) { $health = [string]$Observed.health_status }
    $projection = [ordered]@{
        id = [string]$Observed.full_id
        name = '/' + [string]$Observed.container_name
        image_id = [string]$Observed.image_id
        compose_project = [string]$Observed.compose_project
        compose_service = [string]$Observed.service
        state = [ordered]@{ status = [string]$Observed.state_status; running = [bool]$Observed.running; health = $health }
        mounts = $mounts
        configured_ports = $configured
        active_ports = $active
    }
    return ($projection | ConvertTo-Json -Depth 20 -Compress)
}

function New-P4HostOperationPayload {
    param($Expected, [string]$Mode)
    $task = [pscustomobject]@{
        execute = [string]$Expected.executable
        arguments = Join-WindowsNativeArguments -ArgumentList @($Expected.arguments | ForEach-Object { [string]$_ })
        working_directory = [string]$Expected.working_directory
    }
    if ($Mode -eq 'ABSENT') { return [pscustomobject]@{ status = 'SUCCESS'; task = $task; processes = @(); listeners = @() } }
    $processId = 6000 + [int]$Expected.listener_port % 1000
    $command = Join-WindowsNativeArguments -ArgumentList (@([string]$Expected.executable) + @($Expected.arguments | ForEach-Object { [string]$_ }))
    return [pscustomobject]@{
        status = 'SUCCESS'
        task = $task
        processes = @([pscustomobject]@{ process_id = $processId; executable_path = [string]$Expected.executable; command_line = $command; creation_date = [datetime]'2026-09-20T00:00:00Z' })
        listeners = @([pscustomobject]@{ local_address = [string]$Expected.listener_host; local_port = [int]$Expected.listener_port; owning_process = $processId })
    }
}

function New-P4RealSystemBoundary {
    param($Manifest, [hashtable]$State)
    $invokeNative = {
        param($FilePath, $Arguments, $Timeout, $MaximumOutput)
        $joined = @($Arguments) -join ' '
        $service = ''
        $targetId = if (@($Arguments).Count -gt 0) { [string]$Arguments[-1] } else { '' }
        foreach ($candidate in $State.containers.Keys) {
            if ([string]$State.containers[$candidate].full_id -eq $targetId -or [string]$State.containers[$candidate].image_id -eq $targetId) { $service = [string]$candidate; break }
        }
        if ([string]::IsNullOrWhiteSpace($service)) {
            foreach ($extraService in $State.extra_container_observations.Keys) {
                if (@($State.extra_container_observations[$extraService] | Where-Object { [string]$_.full_id -eq $targetId }).Count -gt 0) { $service = [string]$extraService; break }
            }
        }
        if ($joined -like '*label=com.docker.compose.service=*') {
            $serviceFilter = @($Arguments | Where-Object { [string]$_ -like 'label=com.docker.compose.service=*' } | Select-Object -Last 1)
            if ($serviceFilter.Count -eq 1) { $service = ([string]$serviceFilter[0]).Substring(([string]$serviceFilter[0]).LastIndexOf('=') + 1) }
        }
        $State.raw_native_calls.Add([pscustomobject]@{ command = $joined; timeout = [int]$Timeout; service = $service })
        $nativeCost = 1
        if ([int]$State.read_delay_ms -gt 0 -and $service -eq [string]$State.read_delay_service -and $joined -notlike '--context desktop-linux-test start*') { $nativeCost = [int]$State.read_delay_ms }
        $State.test_clock.milliseconds = [int64]$State.test_clock.milliseconds + [Math]::Max(0, $nativeCost)
        if ($joined -eq 'context show') { return New-P4NativeEnvelope -Status 'SUCCESS' -Stdout 'desktop-linux-test' }
        if ($joined -like 'context inspect desktop-linux-test*') { return New-P4NativeEnvelope -Status 'SUCCESS' -Stdout 'npipe:////./pipe/nextStabilSynthetic' }
        if ($joined -like '--context desktop-linux-test version*') { return New-P4NativeEnvelope -Status 'SUCCESS' -Stdout '27.0.0-synthetic' }
        if ($joined -like '--context desktop-linux-test inspect --type container --format*') {
            $observed = $null
            foreach ($candidate in $State.containers.Values) { if ([string]$candidate.full_id -eq $targetId) { $observed = $candidate; break } }
            if ($null -eq $observed) {
                foreach ($extraSet in $State.extra_container_observations.Values) {
                    foreach ($candidate in @($extraSet)) { if ([string]$candidate.full_id -eq $targetId) { $observed = $candidate; break } }
                    if ($null -ne $observed) { break }
                }
            }
            if ($null -eq $observed) { return New-P4NativeEnvelope -Status 'NONZERO_EXIT' -Stderr 'Error response from daemon: No such container: synthetic' -ExitCode 1 }
            return New-P4NativeEnvelope -Status 'SUCCESS' -Stdout (ConvertTo-P4DockerProjectionJson -Observed $observed -State $State) -StdoutTruncated ([bool]$State.inspect_stdout_truncated[$targetId])
        }
        if ($joined -like '--context desktop-linux-test image inspect*') {
            $observed = @()
            foreach ($candidate in $State.containers.Keys) {
                if ([string]$State.containers[$candidate].image_id -eq $targetId) { $observed = @($State.containers[$candidate]); break }
            }
            if ($observed.Count -eq 0) {
                foreach ($extraSet in $State.extra_container_observations.Values) {
                    $extraImage = @($extraSet | Where-Object { [string]$_.image_id -eq $targetId } | Select-Object -First 1)
                    if ($extraImage.Count -eq 1) { $observed = $extraImage; break }
                }
            }
            if ($observed.Count -eq 0) { return New-P4NativeEnvelope -Status 'NONZERO_EXIT' -Stderr 'Error response from daemon: No such image: synthetic' -ExitCode 1 }
            $digest = 'synthetic/' + [string]$observed[0].service + '@' + [string]$observed[0].repo_digest
            return New-P4NativeEnvelope -Status 'SUCCESS' -Stdout (@($digest) | ConvertTo-Json -Compress)
        }
        if ($joined -like '--context desktop-linux-test container ls --all --no-trunc*') {
            $ids = New-Object System.Collections.Generic.List[string]
            if ($State.containers.ContainsKey($service)) { $ids.Add([string]$State.containers[$service].full_id) }
            foreach ($extra in @($State.extra_container_observations[$service])) { $ids.Add([string]$extra.full_id) }
            $text = if ($State.selector_override.ContainsKey($service)) { [string]$State.selector_override[$service] } else { @($ids) -join "`r`n" }
            $status = if ([string]::IsNullOrWhiteSpace($text)) { 'EMPTY_OUTPUT' } else { 'SUCCESS' }
            return New-P4NativeEnvelope -Status $status -Stdout $text -StdoutTruncated ([bool]$State.selector_stdout_truncated[$service]) -StderrTruncated ([bool]$State.selector_stderr_truncated[$service])
        }
        if ($joined -like '--context desktop-linux-test start*') {
            $match = @($State.containers.Keys | Where-Object { [string]$State.containers[$_].full_id -eq $targetId })
            if ($match.Count -ne 1) { return New-P4NativeEnvelope -Status 'NONZERO_EXIT' -Stderr 'synthetic exact start target missing' -ExitCode 1 }
            $startedService = [string]$match[0]
            $State.container_starts.Add($startedService)
            $State.calls.Add('raw.container.start.' + $startedService)
            $State.containers[$startedService].running = $true
            $State.containers[$startedService].state_status = 'running'
            return New-P4NativeEnvelope -Status 'SUCCESS' -Stdout $targetId
        }
        throw ('UNEXPECTED_REAL_NATIVE_CALL:' + $joined)
    }.GetNewClosure()
    $invokeHost = {
        param($Operation, $Expected, $Timeout, $MaximumOutput)
        $name = [string]$Expected.name
        $State.test_clock.milliseconds = [int64]$State.test_clock.milliseconds + 1
        if ($Operation -eq 'OBSERVE') {
            $payload = New-P4HostOperationPayload -Expected $Expected -Mode ([string]$State.raw_host_modes[$name])
            return [pscustomobject]@{ status = 'SUCCESS'; result = $payload; job_left_running = $false }
        }
        if ($Operation -eq 'START') {
            $State.raw_host_starts[$name]++
            $State.raw_host_modes[$name] = 'READY'
            return [pscustomobject]@{ status = 'SUCCESS'; result = [pscustomobject]@{ status = 'SUCCESS' }; job_left_running = $false }
        }
        throw ('UNEXPECTED_REAL_HOST_OPERATION:' + $Operation)
    }.GetNewClosure()
    return [pscustomobject]@{
        InvokeNative = $invokeNative
        GetEnvironmentState = { [pscustomobject]@{ docker_host_override = ''; docker_context_override = '' } }
        ObserveDesktop = { param($ProcessName, $ExpectedPath) throw 'UNEXPECTED_REAL_DESKTOP_OBSERVE' }
        StartDesktop = { param($ExpectedPath) throw 'UNEXPECTED_REAL_DESKTOP_START' }
        InvokeHostOperation = $invokeHost
        InvokeHttp = { param($Uri, $Timeout) $State.test_clock.milliseconds = [int64]$State.test_clock.milliseconds + 1; [pscustomobject]@{ status = $(if ([string]$Uri -match '/control$') { 404 } else { 200 }) } }.GetNewClosure()
        Sleep = { param($Milliseconds) $State.test_clock.milliseconds = [int64]$State.test_clock.milliseconds + [Math]::Max(0, [int]$Milliseconds) }.GetNewClosure()
    }
}

function Invoke-P4RealAdapterPlan {
    param($Manifest, [hashtable]$State)
    Save-P4Manifest $Manifest
    $boundary = New-P4RealSystemBoundary -Manifest $Manifest -State $State
    $adapters = New-RealStartupAdapters -Manifest $Manifest -SystemBoundary $boundary
    $State.test_clock.milliseconds = [int64]0
    $script:ActiveP4SyntheticClock = $State.test_clock
    try {
        return Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters $adapters -AllowSyntheticRoot
    }
    finally {
        $script:ActiveP4SyntheticClock = $null
    }
}

function Invoke-P4Plan {
    param($Manifest, [hashtable]$State)
    Save-P4Manifest $Manifest
    $State.test_clock.milliseconds = [int64]0
    $script:ActiveP4SyntheticClock = $State.test_clock
    try {
        return Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-P4Adapters $State) -AllowSyntheticRoot
    }
    finally {
        $script:ActiveP4SyntheticClock = $null
    }
}

try {
    [void](New-Item -ItemType Directory -Path $installRoot -Force)
    [void](New-Item -ItemType Directory -Path $targetRoot -Force)
    [void](New-Item -ItemType Junction -Path $dataLink -Target $targetRoot)
    $manifest = New-P4Manifest

    $notApproved = Copy-P4Object $manifest
    $notApproved.approval.status = 'NOT_APPROVED'
    $notApprovedState = New-P4State $notApproved
    $notApprovedResult = Invoke-P4Plan $notApproved $notApprovedState
    Assert-P4Package ($notApprovedResult.code -eq 'MANIFEST_REFUSED' -and @($notApprovedResult.details) -contains 'START_NOT_APPROVED' -and $notApprovedState.calls.Count -eq 0) 'NOT_APPROVED package refuses before adapters'

    $readyState = New-P4State $manifest
    $readyResult = Invoke-P4Plan $manifest $readyState
    $readyRepeat = Invoke-P4Plan $manifest $readyState
    Assert-P4Package ($readyResult.code -eq 'BASE_READY_LIMITED' -and $readyRepeat.code -eq 'BASE_READY_LIMITED') ('six-service package reaches limited readiness twice; first=' + ($readyResult | ConvertTo-Json -Depth 8 -Compress) + '; second=' + ($readyRepeat | ConvertTo-Json -Depth 8 -Compress))
    Assert-P4Package ($readyState.container_starts.Count -eq 0 -and $readyState.host_starts.Count -eq 0) 'ready package starts no containers or host services'
    Assert-P4Package (@($readyResult.events | Where-Object { $_.action -eq 'IGNORE_RETAINED_INACTIVE_DRILL' }).Count -eq 4) 'six-service plan accounts for four retained stopped drills without selecting them'

    $privateState = New-P4State $manifest
    $privateState.hosts.private_gateway = @()
    $privateFirst = Invoke-P4Plan $manifest $privateState
    $privateSecond = Invoke-P4Plan $manifest $privateState
    Assert-P4Package ($privateFirst.code -eq 'BASE_READY_LIMITED' -and $privateSecond.code -eq 'BASE_READY_LIMITED') 'missing private gateway reaches readiness after one fake start'
    Assert-P4Package ($privateState.host_starts.private_gateway -eq 1 -and -not $privateState.host_starts.ContainsKey('supervisor')) 'private gateway starts once and Supervisor never starts'

    $coldState = New-P4State $manifest $false
    $coldResult = Invoke-P4Plan $manifest $coldState
    Assert-P4Package ($coldResult.code -eq 'BASE_READY_LIMITED') ('cold package reaches limited readiness; actual=' + ($coldResult | ConvertTo-Json -Depth 10 -Compress))
    Assert-P4Package ($coldState.container_starts[0] -eq 'postgres' -and $coldState.container_starts[-1] -eq 'backend') ('postgres starts before backend; actual=' + (@($coldState.container_starts) -join ','))
    $healthyIndex = @($coldState.calls).IndexOf('postgres.health.healthy')
    $backendStartIndex = @($coldState.calls).IndexOf('container.start.backend')
    Assert-P4Package ($healthyIndex -ge 0 -and $backendStartIndex -gt $healthyIndex) 'backend starts only after PostgreSQL health is confirmed'

    $blockedDbState = New-P4State $manifest $false
    $blockedDbState.postgres_health_mode = 'STUCK'
    $blockedDb = Invoke-P4Plan $manifest $blockedDbState
    Assert-P4Package ($blockedDb.code -eq 'CONTAINER_HEALTH_UNKNOWN' -and -not (@($blockedDbState.container_starts) -contains 'backend')) ('unknown PostgreSQL health reaches deadline and never starts backend; actual=' + ($blockedDb | ConvertTo-Json -Depth 10 -Compress) + '; starts=' + (@($blockedDbState.container_starts) -join ','))

    $wrongIdState = New-P4State $manifest
    $wrongIdState.containers.backend.full_id = '9' * 64
    $wrongIdState.containers.backend.running = $false
    $wrongId = Invoke-P4Plan $manifest $wrongIdState
    Assert-P4Package ($wrongId.code -eq 'CONTROLLED_DEPLOY_REQUIRED' -and -not (@($wrongIdState.container_starts) -contains 'backend')) 'missing pinned full container ID blocks without adopting a same-role object'

    $wrongNameState = New-P4State $manifest
    $wrongNameState.containers.backend.container_name = 'backend'
    $wrongName = Invoke-P4Plan $manifest $wrongNameState
    Assert-P4Package ($wrongName.code -eq 'IDENTITY_MISMATCH') 'runtime container name is independent from service label'

    $activeConflictState = New-P4State $manifest
    $activeConflict = Copy-P4Object $activeConflictState.containers.backend
    $activeConflict.full_id = 'e' * 64
    $activeConflict.container_name = 'foreign-backend'
    $activeConflictState.extra_container_observations.backend += $activeConflict
    $activeConflictResult = Invoke-P4Plan $manifest $activeConflictState
    Assert-P4Package ($activeConflictResult.code -eq 'CONTAINER_ROLE_CONFLICT' -and $activeConflictState.container_starts.Count -eq 0) 'active same-role competitor blocks the complete plan'

    # Whole-plan composition with the production validator, parser, real
    # adapters and phase logic. Only the lowest Docker/host/HTTP boundaries
    # below are synthetic.
    $realReadyState = New-P4RealAdapterState -Manifest $manifest
    $realReadyFirst = Invoke-P4RealAdapterPlan -Manifest $manifest -State $realReadyState
    $realReadySecond = Invoke-P4RealAdapterPlan -Manifest $manifest -State $realReadyState
    Assert-P4Package ($realReadyFirst.code -eq 'BASE_READY_LIMITED' -and $realReadySecond.code -eq 'BASE_READY_LIMITED') ('real-adapter 6+4 topology reaches limited readiness twice; first=' + ($realReadyFirst | ConvertTo-Json -Depth 8 -Compress) + ';second=' + ($realReadySecond | ConvertTo-Json -Depth 8 -Compress))
    Assert-P4Package ($realReadyState.container_starts.Count -eq 0 -and ($realReadyState.raw_host_starts.Values | Measure-Object -Sum).Sum -eq 0) 'real-adapter ready topology performs zero starts'
    Assert-P4Package (@($realReadyFirst.events | Where-Object { $_.action -eq 'IGNORE_RETAINED_INACTIVE_DRILL' }).Count -eq 4) 'real-adapter plan accounts for all four retained drills'

    $realPrivateState = New-P4RealAdapterState -Manifest $manifest
    $realPrivateState.raw_host_modes.private_gateway = 'ABSENT'
    $realPrivateFirst = Invoke-P4RealAdapterPlan -Manifest $manifest -State $realPrivateState
    $realPrivateSecond = Invoke-P4RealAdapterPlan -Manifest $manifest -State $realPrivateState
    Assert-P4Package ($realPrivateFirst.code -eq 'BASE_READY_LIMITED' -and $realPrivateSecond.code -eq 'BASE_READY_LIMITED') 'real-adapter private gateway reaches readiness and repeats'
    Assert-P4Package ($realPrivateState.raw_host_starts.private_gateway -eq 1 -and $realPrivateState.raw_host_starts.supervisor -eq 0) 'real-adapter private gateway starts once and Supervisor never starts'

    $realColdState = New-P4RealAdapterState -Manifest $manifest -Running $false
    $realCold = Invoke-P4RealAdapterPlan -Manifest $manifest -State $realColdState
    $realHealthyIndex = @($realColdState.calls).IndexOf('raw.postgres.health.healthy')
    $realBackendStartIndex = @($realColdState.calls).IndexOf('raw.container.start.backend')
    Assert-P4Package ($realCold.code -eq 'BASE_READY_LIMITED') ('real-adapter cold fixture reaches limited readiness; actual=' + $realCold.code)
    Assert-P4Package ($realColdState.container_starts[0] -eq 'postgres' -and $realColdState.container_starts[-1] -eq 'backend') ('real-adapter cold starts pinned PostgreSQL before pinned backend; actual=' + (@($realColdState.container_starts) -join ','))
    Assert-P4Package ($realHealthyIndex -ge 0 -and $realBackendStartIndex -gt $realHealthyIndex) 'real-adapter backend starts only after PostgreSQL running and healthy'

    foreach ($observationCase in @('A_SELECTOR_TRUNCATED', 'B_INSPECT_TRUNCATED', 'C_EMPTY_SELECTOR_TRUNCATED')) {
        $incompleteState = New-P4RealAdapterState -Manifest $manifest
        $incompleteState.containers.backend.running = $false
        $incompleteState.containers.backend.state_status = 'exited'
        switch ($observationCase) {
            'A_SELECTOR_TRUNCATED' { $incompleteState.selector_stdout_truncated.backend = $true; $incompleteState.selector_override.backend = [string]$incompleteState.containers.backend.full_id }
            'B_INSPECT_TRUNCATED' { $incompleteState.inspect_stdout_truncated[[string]$incompleteState.containers.backend.full_id] = $true }
            'C_EMPTY_SELECTOR_TRUNCATED' { $incompleteState.selector_stdout_truncated.backend = $true; $incompleteState.selector_override.backend = '' }
        }
        $incompleteResult = Invoke-P4RealAdapterPlan -Manifest $manifest -State $incompleteState
        Assert-P4Package ($incompleteResult.code -eq 'ADAPTER_FAILURE' -and $incompleteState.container_starts.Count -eq 0) ('real-adapter incomplete envelope blocks the whole plan: ' + $observationCase + ';actual=' + $incompleteResult.code)
    }

    $deadlineManifest = Copy-P4Object $manifest
    $deadlineManifest.timeouts.native_command_ms = 200
    $deadlineManifest.timeouts.service_stage_ms = 250
    $deadlineState = New-P4RealAdapterState -Manifest $deadlineManifest
    $deadlineState.read_delay_service = 'backend'
    $deadlineState.read_delay_ms = 60
    $deadlineResult = Invoke-P4RealAdapterPlan -Manifest $deadlineManifest -State $deadlineState
    $backendBudgets = @($deadlineState.raw_native_calls | Where-Object { $_.service -eq 'backend' } | ForEach-Object { [int]$_.timeout })
    $deadlineDecreased = $false
    for ($index = 1; $index -lt $backendBudgets.Count; $index++) { if ($backendBudgets[$index] -lt $backendBudgets[$index - 1]) { $deadlineDecreased = $true; break } }
    Assert-P4Package ($deadlineResult.code -eq 'CONTAINER_OBSERVATION_DEADLINE_EXCEEDED' -and $deadlineState.container_starts.Count -eq 0) ('real-adapter shared deadline blocks the whole plan without start; actual=' + $deadlineResult.code)
    Assert-P4Package ($deadlineDecreased -and $backendBudgets.Count -lt 7) ('real-adapter stops further backend reads with decreasing budgets; budgets=' + ($backendBudgets -join ','))

    foreach ($stateStatus in @('paused', 'restarting')) {
        $pinnedState = New-P4RealAdapterState -Manifest $manifest
        $pinnedState.containers.backend.state_status = $stateStatus
        $pinnedState.containers.backend.running = $true
        $pinnedResult = Invoke-P4RealAdapterPlan -Manifest $manifest -State $pinnedState
        Assert-P4Package ($pinnedResult.code -eq 'CONTAINER_STATE_NOT_READY' -and $pinnedState.container_starts.Count -eq 0) ('real-adapter pinned backend state blocks: ' + $stateStatus)

        $postgresState = New-P4RealAdapterState -Manifest $manifest
        $postgresState.containers.postgres.state_status = $stateStatus
        $postgresState.containers.postgres.running = $true
        $postgresState.containers.postgres.health_status = 'healthy'
        $postgresState.postgres_running_observations = 1
        $postgresResult = Invoke-P4RealAdapterPlan -Manifest $manifest -State $postgresState
        Assert-P4Package ($postgresResult.code -eq 'CONTAINER_STATE_NOT_READY' -and $postgresState.container_starts.Count -eq 0) ('real-adapter pinned PostgreSQL stale healthy blocks: ' + $stateStatus)
    }

    $realMissing = New-P4RealAdapterState -Manifest $manifest
    $realMissing.containers.backend.full_id = 'd' * 64
    $realMissingResult = Invoke-P4RealAdapterPlan -Manifest $manifest -State $realMissing
    Assert-P4Package ($realMissingResult.code -in @('CONTROLLED_DEPLOY_REQUIRED', 'CONTAINER_ROLE_CONFLICT') -and $realMissing.container_starts.Count -eq 0) 'real-adapter missing pinned ID is never adopted or started'

    $realConflict = New-P4RealAdapterState -Manifest $manifest
    $realForeign = Copy-P4Object $realConflict.containers.backend
    $realForeign.full_id = 'e' * 64
    $realForeign.container_name = 'foreign-backend'
    $realConflict.extra_container_observations.backend += $realForeign
    $realConflictResult = Invoke-P4RealAdapterPlan -Manifest $manifest -State $realConflict
    Assert-P4Package ($realConflictResult.code -eq 'CONTAINER_ROLE_CONFLICT' -and $realConflict.container_starts.Count -eq 0) 'real-adapter active same-role conflict blocks without start'

    foreach ($driftCase in @('name', 'label', 'image', 'mount', 'port')) {
        $driftState = New-P4RealAdapterState -Manifest $manifest
        switch ($driftCase) {
            'name' { $driftState.containers.backend.container_name = 'foreign-backend' }
            'label' { $driftState.containers.backend.compose_project = 'foreign-project' }
            'image' { $driftState.containers.backend.image_id = 'sha256:' + ('9' * 64) }
            'mount' { $driftState.containers.backend.mounts[0].source = (Join-Path $fixtureRoot 'foreign-backend') }
            'port' { $driftState.containers.backend.ports[0].host_port = 18001 }
        }
        $driftResult = Invoke-P4RealAdapterPlan -Manifest $manifest -State $driftState
        Assert-P4Package ($driftResult.code -eq 'IDENTITY_MISMATCH' -and $driftState.container_starts.Count -eq 0) ('real-adapter drift blocks without start: ' + $driftCase + ';actual=' + ($driftResult | ConvertTo-Json -Depth 8 -Compress))
    }

    $backend = @($manifest.containers | Where-Object { $_.service -eq 'backend' })[0]
    $localExpected = Copy-P4Object $backend
    $localExpected.image_identity_mode = 'LOCAL_IMAGE_ID_CONFIRMED_NO_REPO_DIGEST'
    $localExpected.repo_digest = 'CONFIRMED_ABSENT'
    $localObserved = Copy-P4Object $readyState.containers.backend
    $localObserved.repo_digest = ''
    $localObserved.repo_digest_state = 'CONFIRMED_ABSENT'
    $localPass = Test-ApprovedContainerIdentity -Expected $localExpected -Observed $localObserved
    Assert-P4Package $localPass.valid 'explicit backend local-image mode accepts exact image and confirmed digest absence'
    $localObserved.repo_digest_state = 'UNKNOWN'
    $localUnknown = Test-ApprovedContainerIdentity -Expected $localExpected -Observed $localObserved
    Assert-P4Package (-not $localUnknown.valid) 'local-image mode refuses unknown digest observation'
    $foreignLocal = Copy-P4Object $manifest
    $foreignLocal.containers[1].image_identity_mode = 'LOCAL_IMAGE_ID_CONFIRMED_NO_REPO_DIGEST'
    $foreignLocal.containers[1].repo_digest = 'CONFIRMED_ABSENT'
    Save-P4Manifest $foreignLocal
    $foreignValidation = Test-StartupSetManifest -Manifest $foreignLocal -ManifestPath $manifestPath -ExpectedRoot $installRoot -AllowSyntheticRoot
    Assert-P4Package (-not $foreignValidation.valid -and @($foreignValidation.errors) -contains 'CONTAINER_LOCAL_IMAGE_MODE_FORBIDDEN:postgres') 'local-image mode is never a fallback for external services'

    Write-Output ('D21_P4_STARTUP_PACKAGE_TEST_PASS assertions={0}' -f $script:Assertions)
}
finally {
    $script:ActiveP4SyntheticClock = $null
    Set-Item -Path Function:\Get-MonotonicMilliseconds -Value $script:OriginalP4GetMonotonicMilliseconds
    if (Test-Path -LiteralPath $dataLink) {
        $item = Get-Item -LiteralPath $dataLink -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -and $item.FullName -eq $dataLink) { [System.IO.Directory]::Delete($dataLink) }
    }
    if (Test-Path -LiteralPath $fixtureRoot) {
        $resolved = [System.IO.Path]::GetFullPath($fixtureRoot)
        $tempRoot = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
        if ($resolved.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and $resolved -match 'NEXT Stabil D21 P4 Package [0-9a-f]{32}$') {
            Remove-Item -LiteralPath $resolved -Recurse -Force
        }
    }
}
