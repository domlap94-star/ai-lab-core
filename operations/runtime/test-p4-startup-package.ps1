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
        $observed | Add-Member -NotePropertyName configured_ports -NotePropertyValue @($expected.ports)
        $observed | Add-Member -NotePropertyName active_ports -NotePropertyValue $(if ($Running) { @($expected.ports) } else { @() })
        $observed | Add-Member -NotePropertyName repo_digest_state -NotePropertyValue 'OBSERVED'
        $observed | Add-Member -NotePropertyName health_status -NotePropertyValue $(if ($expected.service -eq 'postgres' -and $Running) { 'healthy' } else { 'NONE' })
        $containers[[string]$expected.service] = $observed
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
            $observed = $State.containers[$service]
            if ($service -eq 'postgres' -and [bool]$observed.running) {
                $State.postgres_running_observations++
                if ($State.postgres_health_mode -eq 'STUCK') { $observed.health_status = 'starting' }
                elseif ($State.postgres_running_observations -eq 1) { $observed.health_status = 'starting' }
                else { $observed.health_status = 'healthy' }
                $State.calls.Add(('postgres.health.' + [string]$observed.health_status))
            }
            @($observed)
        }.GetNewClosure()
        StartExistingContainer = {
            param($FullId, $Timeout)
            $service = @($State.containers.Keys | Where-Object { [string]$State.containers[$_].full_id -eq [string]$FullId })[0]
            $State.calls.Add('container.start.' + $service)
            $State.container_starts.Add($service)
            $State.containers[$service].running = $true
            $State.containers[$service].active_ports = @($State.containers[$service].ports)
            if ($service -eq 'postgres') { $State.containers[$service].health_status = 'starting' }
            [pscustomobject]@{ status = 'SUCCESS'; process_left_running = $false }
        }.GetNewClosure()
        ObserveHostService = { param($Expected, $Timeout) $State.calls.Add('host.observe.' + [string]$Expected.name); @($State.hosts[[string]$Expected.name]) }.GetNewClosure()
        StartHostService = {
            param($Expected, $Timeout)
            $name = [string]$Expected.name
            $State.calls.Add('host.start.' + $name)
            if (-not $State.host_starts.ContainsKey($name)) { $State.host_starts[$name] = 0 }
            $State.host_starts[$name]++
            $ready = Copy-P4Object $Expected
            $ready | Add-Member -NotePropertyName listener_ready -NotePropertyValue $true
            $State.hosts[$name] = @($ready)
            [pscustomobject]@{ status = 'SUCCESS'; operation_may_have_started = $false }
        }.GetNewClosure()
        CheckReadiness = { param($Definition) $State.calls.Add('readiness.' + [string]$Definition.name); [pscustomobject]@{ status = [int]$Definition.expected_status } }.GetNewClosure()
        Sleep = { param($Milliseconds) }.GetNewClosure()
    }
}

function Invoke-P4Plan {
    param($Manifest, [hashtable]$State)
    Save-P4Manifest $Manifest
    return Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $installRoot -Adapters (New-P4Adapters $State) -AllowSyntheticRoot
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
    Assert-P4Package ($readyResult.code -eq 'BASE_READY_LIMITED' -and $readyRepeat.code -eq 'BASE_READY_LIMITED') 'six-service package reaches limited readiness twice'
    Assert-P4Package ($readyState.container_starts.Count -eq 0 -and $readyState.host_starts.Count -eq 0) 'ready package starts no containers or host services'

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
    Assert-P4Package ($wrongId.code -eq 'IDENTITY_MISMATCH' -and -not (@($wrongIdState.container_starts) -contains 'backend')) 'changed full container ID blocks before start'

    $wrongNameState = New-P4State $manifest
    $wrongNameState.containers.backend.container_name = 'backend'
    $wrongName = Invoke-P4Plan $manifest $wrongNameState
    Assert-P4Package ($wrongName.code -eq 'IDENTITY_MISMATCH') 'runtime container name is independent from service label'

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
