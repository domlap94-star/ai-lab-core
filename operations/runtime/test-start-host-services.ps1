$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$script:Assertions = 0
function Assert-Startup {
    param([bool]$Condition, [string]$Name)
    $script:Assertions++
    if (-not $Condition) { throw ('ASSERT_FAILED: ' + $Name) }
}

$runtimeDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $runtimeDirectory 'start-host-services.ps1') -DefinitionOnly
. (Join-Path (Split-Path -Parent $runtimeDirectory) 'windows\start-compose-after-docker.ps1') -ImportDefinitionsOnly

$testRoot = Join-Path $env:TEMP ('NEXT Stabil D21 P1 {0}' -f ([guid]::NewGuid().ToString('N')))
$manifestPath = Join-Path $testRoot 'operations\runtime\startup-set.json'
$powershellPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

function Write-TestText {
    param([string]$Path, [string]$Text)
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) { [void](New-Item -ItemType Directory -Path $parent -Force) }
    [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
}

function Copy-TestObject {
    param($Value)
    return ($Value | ConvertTo-Json -Depth 20 | ConvertFrom-Json)
}

function Save-TestManifest {
    param($Manifest)
    Write-TestText -Path $manifestPath -Text ($Manifest | ConvertTo-Json -Depth 20)
}

function New-TestManifest {
    $relativeFiles = [ordered]@{
        compose_config = 'compose.yaml'
        compose_helper = 'operations/windows/start-compose-after-docker.ps1'
        public_gateway_script = 'operations/gateway/public_web_server.cjs'
        private_gateway_script = 'operations/gateway/web_server.cjs'
        supervisor_script = 'operations/supervisor/server.js'
    }
    $files = @()
    foreach ($role in $relativeFiles.Keys) {
        $path = Join-Path $testRoot $relativeFiles[$role]
        Write-TestText -Path $path -Text ('fixture-' + $role)
        $files += [pscustomobject]@{ role = $role; path = $relativeFiles[$role]; sha256 = Get-StartupSha256 -Path $path }
    }
    $toolDirectory = Join-Path $testRoot 'external tools'
    $tools = @()
    foreach ($name in @('docker_cli', 'docker_desktop', 'node')) {
        $path = Join-Path $toolDirectory ($name + '.exe')
        Write-TestText -Path $path -Text ('fixture-tool-' + $name)
        $tools += [pscustomobject]@{ name = $name; path = $path; sha256 = Get-StartupSha256 -Path $path }
    }
    $image = 'sha256:' + ('a' * 64)
    $digest = 'sha256:' + ('b' * 64)
    $mount = [pscustomobject]@{ source = (Join-Path $testRoot 'backend'); destination = '/app'; type = 'bind'; read_only = $true }
    $port = [pscustomobject]@{ host_ip = '127.0.0.1'; host_port = 18000; container_port = 8000; protocol = 'tcp' }
    $nodePath = [string](@($tools | Where-Object { $_.name -eq 'node' })[0].path)
    $public = [pscustomobject]@{ name = 'public_gateway'; policy = 'REQUIRED'; launch_kind = 'TASK'; task_name = 'D21 P1 public'; task_path = '\'; executable = $nodePath; arguments = @('operations/gateway/public_web_server.cjs'); working_directory = $testRoot; listener_host = '127.0.0.1'; listener_port = 18789; script_ref = 'public_gateway_script'; tool_ref = 'node' }
    $private = [pscustomobject]@{ name = 'private_gateway'; policy = 'REQUIRED'; launch_kind = 'TASK'; task_name = 'D21 P1 private'; task_path = '\'; executable = $nodePath; arguments = @('operations/gateway/web_server.cjs'); working_directory = $testRoot; listener_host = '127.0.0.1'; listener_port = 18788; script_ref = 'private_gateway_script'; tool_ref = 'node' }
    $supervisor = [pscustomobject]@{ name = 'supervisor'; policy = 'INTENTIONALLY_STOPPED'; launch_kind = 'TASK'; task_name = 'D21 P1 supervisor'; task_path = '\'; executable = $nodePath; arguments = @('operations/supervisor/server.js'); working_directory = $testRoot; listener_host = '127.0.0.1'; listener_port = 18787; script_ref = 'supervisor_script'; tool_ref = 'node' }
    return [pscustomobject][ordered]@{
        schema = 'NEXT_STABIL_STARTUP_SET_V1'
        component_identity_schema = 'NEXT_STABIL_COMPONENT_COMPATIBILITY_V1'
        set_id = 'D21-P1-SYNTHETIC'
        root = $testRoot
        approval = [pscustomobject]@{ status = 'APPROVED_FOR_START'; set_id = 'D21-P1-SYNTHETIC'; decision_id = 'TEST_ONLY' }
        timeouts = [pscustomobject]@{ native_command_ms = 50; engine_stage_ms = 20; service_stage_ms = 20; poll_ms = 1; max_output_chars = 4096 }
        files = $files
        external_tools = $tools
        docker = [pscustomobject]@{ context = 'desktop-linux-test'; endpoint = 'npipe:////./pipe/nextStabilSynthetic'; process_name = 'Docker Desktop Synthetic'; cli_tool = 'docker_cli'; desktop_tool = 'docker_desktop' }
        containers = @([pscustomobject]@{ service = 'backend'; container_name = 'd21-p1-backend'; compose_project = 'd21-p1'; image_id = $image; repo_digest = $digest; mounts = @($mount); ports = @($port) })
        host_services = @($public, $private, $supervisor)
        readiness = @(
            [pscustomobject]@{ name = 'backend'; uri = 'http://127.0.0.1:18000/health'; expected_status = 200 },
            [pscustomobject]@{ name = 'web'; uri = 'http://127.0.0.1:18789/'; expected_status = 200 },
            [pscustomobject]@{ name = 'public_control_boundary'; uri = 'http://127.0.0.1:18789/control'; expected_status = 404 }
        )
        client = [pscustomobject]@{ policy = 'DISABLED' }
    }
}

function New-FakeStartupState {
    param($Manifest)
    $container = Copy-TestObject $Manifest.containers[0]
    $container | Add-Member -NotePropertyName running -NotePropertyValue $true
    $container | Add-Member -NotePropertyName full_id -NotePropertyValue ('d' * 64)
    $hostMap = @{}
    foreach ($service in @($Manifest.host_services | Where-Object { $_.policy -eq 'REQUIRED' })) {
        $observed = Copy-TestObject $service
        $observed | Add-Member -NotePropertyName listener_ready -NotePropertyValue $true
        $hostMap[$service.name] = @($observed)
    }
    return [hashtable]@{
        calls = New-Object System.Collections.Generic.List[string]
        engine_sequence = @('RESPONDING')
        engine_index = 0
        desktop = @()
        containers = @{ backend = @($container) }
        hosts = $hostMap
        readiness = @{ backend = 200; web = 200; public_control_boundary = 404 }
        container_starts = 0
        container_start_targets = New-Object System.Collections.Generic.List[string]
        change_container_id_after_start = $false
        desktop_starts = 0
        host_starts = @{}
        container_start_status = 'SUCCESS'
        desktop_start_status = 'ACCEPTED'
        host_start_status = 'SUCCESS'
        throw_engine = ''
    }
}

function New-FakeStartupAdapters {
    param([hashtable]$State)
    $getEnvironment = {
        $State.calls.Add('docker.environment')
        [pscustomobject]@{ context = 'desktop-linux-test'; endpoint = 'npipe:////./pipe/nextStabilSynthetic'; docker_host_override = ''; docker_context_override = '' }
    }.GetNewClosure()
    $observeEngine = {
        $State.calls.Add('engine.observe')
        if (-not [string]::IsNullOrWhiteSpace($State.throw_engine)) { throw $State.throw_engine }
        $index = [Math]::Min($State.engine_index, $State.engine_sequence.Count - 1)
        $status = $State.engine_sequence[$index]
        $State.engine_index++
        [pscustomobject]@{ status = $status; version = if ($status -eq 'RESPONDING') { '28.3.3' } else { '' } }
    }.GetNewClosure()
    $observeDesktop = { param($Definition) $State.calls.Add('desktop.observe'); return @($State.desktop) }.GetNewClosure()
    $startDesktop = { param($Definition) $State.calls.Add('desktop.start'); $State.desktop_starts++; [pscustomobject]@{ status = $State.desktop_start_status } }.GetNewClosure()
    $observeContainer = {
        param($Expected)
        $service = [string]$Expected.service
        $State.calls.Add('container.observe.' + $service)
        return @($State.containers[$service])
    }.GetNewClosure()
    $startContainer = {
        param($Name, $Timeout)
        $State.calls.Add('container.start.' + $Name)
        $State.container_starts++
        $State.container_start_targets.Add([string]$Name)
        if ($State.container_start_status -eq 'SUCCESS') {
            $State.containers.backend[0].running = $true
            if ($State.change_container_id_after_start) { $State.containers.backend[0].full_id = 'e' * 64 }
        }
        [pscustomobject]@{ status = $State.container_start_status }
    }.GetNewClosure()
    $observeHost = {
        param($Expected)
        $name = [string]$Expected.name
        $State.calls.Add('host.observe.' + $name)
        if ($State.hosts.ContainsKey($name)) { return @($State.hosts[$name]) }
        return @()
    }.GetNewClosure()
    $startHost = {
        param($Expected, $Timeout)
        $name = [string]$Expected.name
        $State.calls.Add('host.start.' + $name)
        if (-not $State.host_starts.ContainsKey($name)) { $State.host_starts[$name] = 0 }
        $State.host_starts[$name]++
        [pscustomobject]@{ status = $State.host_start_status }
    }.GetNewClosure()
    $check = {
        param($Definition)
        $State.calls.Add('readiness.' + [string]$Definition.name)
        [pscustomobject]@{ status = [int]$State.readiness[[string]$Definition.name] }
    }.GetNewClosure()
    $sleep = { param($Milliseconds) }.GetNewClosure()
    return [pscustomobject]@{
        GetDockerEnvironment = $getEnvironment
        ObserveEngine = $observeEngine
        ObserveDockerDesktopProcess = $observeDesktop
        StartDockerDesktop = $startDesktop
        ObserveContainer = $observeContainer
        StartExistingContainer = $startContainer
        ObserveHostService = $observeHost
        StartHostService = $startHost
        CheckReadiness = $check
        Sleep = $sleep
    }
}

function Invoke-TestPlan {
    param($Manifest, [hashtable]$State)
    Save-TestManifest -Manifest $Manifest
    return Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $testRoot -Adapters (New-FakeStartupAdapters -State $State) -AllowSyntheticRoot
}

try {
    [void](New-Item -ItemType Directory -Path $testRoot -Force)
    $manifest = New-TestManifest
    Save-TestManifest -Manifest $manifest

    $state = New-FakeStartupState -Manifest $manifest
    $missing = Invoke-NextStabilStartupPlan -ManifestPath (Join-Path $testRoot 'missing.json') -ExpectedRoot $testRoot -Adapters (New-FakeStartupAdapters $state) -AllowSyntheticRoot
    Assert-Startup ($missing.code -eq 'MANIFEST_MISSING' -and $state.calls.Count -eq 0) 'missing manifest refuses before adapters'

    $outsideState = New-FakeStartupState -Manifest $manifest
    $outside = Invoke-NextStabilStartupPlan -ManifestPath (Join-Path (Split-Path -Parent $testRoot) 'foreign-startup-set.json') -ExpectedRoot $testRoot -Adapters (New-FakeStartupAdapters $outsideState) -AllowSyntheticRoot
    Assert-Startup ($outside.code -eq 'MANIFEST_REFUSED' -and $outsideState.calls.Count -eq 0) 'manifest outside selected root refuses before read or adapters'

    $notApproved = Copy-TestObject $manifest
    $notApproved.approval.status = 'NOT_APPROVED'
    $state = New-FakeStartupState $manifest
    $result = Invoke-TestPlan $notApproved $state
    Assert-Startup ($result.code -eq 'MANIFEST_REFUSED' -and $state.calls.Count -eq 0) 'NOT_APPROVED refuses before adapters'

    $clientNotAvailable = Copy-TestObject $manifest
    $clientNotAvailable.client.policy = 'OPEN_AFTER_BASE_READY'
    $state = New-FakeStartupState $manifest
    $result = Invoke-TestPlan $clientNotAvailable $state
    Assert-Startup ($result.code -eq 'MANIFEST_REFUSED' -and $state.calls.Count -eq 0) 'P1 refuses unsupported client opening before adapters'

    $realAdapterDefinitions = New-RealStartupAdapters -Manifest $manifest
    $realAdapterContract = Test-StartupAdapterContract -Adapters $realAdapterDefinitions
    Assert-Startup $realAdapterContract.valid 'real adapter definitions satisfy the same bounded adapter contract without invocation'

    $state = New-FakeStartupState $manifest
    $result = Invoke-TestPlan $manifest $state
    Assert-Startup ($result.code -eq 'BASE_READY_LIMITED' -and $result.base_ready -and -not $result.all_ready -and -not $result.ai_export_ready) ('valid set is limited base ready; actual=' + ($result | ConvertTo-Json -Depth 8 -Compress))
    Assert-Startup ($result.supervisor_status -eq 'INTENTIONALLY_STOPPED' -and ($state.calls -notcontains 'host.start.supervisor') -and $state.desktop_starts -eq 0) 'ready Engine and stopped Supervisor receive zero starts'
    $engineIndex = $state.calls.IndexOf('engine.observe')
    $containerIndex = $state.calls.IndexOf('container.observe.backend')
    $gatewayIndex = $state.calls.IndexOf('host.observe.public_gateway')
    $readinessIndex = $state.calls.IndexOf('readiness.backend')
    Assert-Startup ($engineIndex -ge 0 -and $engineIndex -lt $containerIndex -and $containerIndex -lt $gatewayIndex -and $gatewayIndex -lt $readinessIndex) 'plan order is Engine then existing containers then gateways then readiness'
    $firstCallCount = $state.calls.Count
    $repeat = Invoke-TestPlan $manifest $state
    Assert-Startup ($repeat.code -eq 'BASE_READY_LIMITED' -and $state.container_starts -eq 0 -and $state.desktop_starts -eq 0) 'repeat start does not duplicate running resources'
    Assert-Startup ($state.calls.Count -gt $firstCallCount) 'repeat performs fresh observations'

    $savedLocation = Get-Location
    try {
        Set-Location $env:SystemRoot
        $state = New-FakeStartupState $manifest
        $otherCwd = Invoke-TestPlan $manifest $state
    }
    finally { Set-Location $savedLocation }
    Assert-Startup ($otherCwd.code -eq 'BASE_READY_LIMITED') 'current working directory does not select another root'

    $state = New-FakeStartupState $manifest
    $state.containers.backend[0].running = $false
    $result = Invoke-TestPlan $manifest $state
    Assert-Startup ($result.code -eq 'BASE_READY_LIMITED' -and $state.container_starts -eq 1 -and $state.container_start_targets[0] -eq ('d' * 64)) 'stopped matching container starts exact observed full ID once'

    $state = New-FakeStartupState $manifest
    $state.containers.backend[0].running = $false
    $state.change_container_id_after_start = $true
    $result = Invoke-TestPlan $manifest $state
    Assert-Startup ($result.code -eq 'CONTAINER_RUNTIME_ID_CHANGED' -and $state.container_starts -eq 1) 'container replacement between verified start and observation is refused'

    foreach ($case in @('missing', 'duplicate', 'image', 'mount', 'port', 'runtime_id')) {
        $state = New-FakeStartupState $manifest
        if ($case -eq 'missing') { $state.containers.backend = @() }
        elseif ($case -eq 'duplicate') { $state.containers.backend = @($state.containers.backend[0], (Copy-TestObject $state.containers.backend[0])) }
        elseif ($case -eq 'image') { $state.containers.backend[0].image_id = 'sha256:' + ('c' * 64) }
        elseif ($case -eq 'mount') { $state.containers.backend[0].mounts[0].source = (Join-Path $testRoot 'foreign') }
        elseif ($case -eq 'port') { $state.containers.backend[0].ports[0].host_port = 19999 }
        elseif ($case -eq 'runtime_id') { $state.containers.backend[0].running = $false; $state.containers.backend[0].full_id = 'not-a-full-id' }
        $result = Invoke-TestPlan $manifest $state
        Assert-Startup (-not $result.base_ready -and $state.container_starts -eq 0) ('container identity refusal: ' + $case)
    }

    $unsupportedProcess = Copy-TestObject $manifest
    $unsupportedProcess.host_services[0].launch_kind = 'PROCESS'
    $state = New-FakeStartupState $manifest
    $result = Invoke-TestPlan $unsupportedProcess $state
    Assert-Startup ($result.code -eq 'MANIFEST_REFUSED' -and $state.calls.Count -eq 0) 'P1 requires exact Task Scheduler identity for host services'

    $state = New-FakeStartupState $manifest
    $state.engine_sequence = @('UNAVAILABLE', 'RESPONDING')
    $result = Invoke-TestPlan $manifest $state
    Assert-Startup ($result.code -eq 'BASE_READY_LIMITED' -and $state.desktop_starts -eq 1) 'missing desktop starts once and engine later responds'

    $state = New-FakeStartupState $manifest
    $state.engine_sequence = @('UNAVAILABLE')
    $state.desktop = @([pscustomobject]@{ identity_valid = $true })
    $result = Invoke-TestPlan $manifest $state
    Assert-Startup ($result.code -eq 'ENGINE_UNAVAILABLE' -and $state.desktop_starts -eq 0) 'existing desktop plus silent engine times out without restart'

    $state = New-FakeStartupState $manifest
    $adapters = New-FakeStartupAdapters $state
    $adapters.GetDockerEnvironment = { [pscustomobject]@{ context = 'desktop-linux-test'; endpoint = 'npipe:////./pipe/nextStabilSynthetic'; docker_host_override = 'tcp://foreign'; docker_context_override = '' } }
    Save-TestManifest $manifest
    $result = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $testRoot -Adapters $adapters -AllowSyntheticRoot
    Assert-Startup ($result.code -eq 'DOCKER_ENV_OVERRIDE_CONFLICT' -and $state.container_starts -eq 0) 'docker override conflict refuses'

    $state = New-FakeStartupState $manifest
    $adapters = New-FakeStartupAdapters $state
    $adapters.GetDockerEnvironment = { [pscustomobject]@{ context = 'foreign-context'; endpoint = 'npipe:////./pipe/nextStabilSynthetic'; docker_host_override = ''; docker_context_override = '' } }
    $result = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $testRoot -Adapters $adapters -AllowSyntheticRoot
    Assert-Startup ($result.code -eq 'DOCKER_CONTEXT_MISMATCH' -and $state.desktop_starts -eq 0) 'different observed Docker context refuses'

    $state = New-FakeStartupState $manifest
    $state.engine_sequence = @('UNAVAILABLE')
    $result = Invoke-TestPlan $manifest $state
    Assert-Startup ($result.code -eq 'ENGINE_UNAVAILABLE' -and $state.desktop_starts -eq 1) 'accepted Desktop start followed by timeout is not retried'

    $state = New-FakeStartupState $manifest
    $supervisorExpected = @($manifest.host_services | Where-Object { $_.name -eq 'supervisor' })[0]
    $supervisorObserved = Copy-TestObject $supervisorExpected
    $supervisorObserved | Add-Member -NotePropertyName listener_ready -NotePropertyValue $true
    $state.hosts.supervisor = @($supervisorObserved)
    $result = Invoke-TestPlan $manifest $state
    Assert-Startup ($result.code -eq 'SUPERVISOR_POLICY_CONFLICT' -and $result.supervisor_status -eq 'POLICY_CONFLICT') 'running supervisor conflicts with stopped policy'

    $state = New-FakeStartupState $manifest
    $state.readiness.public_control_boundary = 200
    $result = Invoke-TestPlan $manifest $state
    Assert-Startup ($result.code -eq 'READINESS_FAILED') 'public control 200 fails boundary'

    foreach ($case in @('executable', 'arguments', 'working_directory', 'task_name')) {
        $state = New-FakeStartupState $manifest
        if ($case -eq 'executable') { $state.hosts.public_gateway[0].executable = Join-Path $testRoot 'foreign-node.exe' }
        elseif ($case -eq 'arguments') { $state.hosts.public_gateway[0].arguments = @('foreign-script.js') }
        elseif ($case -eq 'working_directory') { $state.hosts.public_gateway[0].working_directory = Join-Path $testRoot 'foreign' }
        elseif ($case -eq 'task_name') { $state.hosts.public_gateway[0].task_name = 'foreign-task' }
        $result = Invoke-TestPlan $manifest $state
        Assert-Startup ($result.code -eq 'HOST_SERVICE_IDENTITY_MISMATCH' -and -not $state.host_starts.ContainsKey('public_gateway')) ('wrong task identity refuses before start: ' + $case)
    }

    $state = New-FakeStartupState $manifest
    $state.hosts.public_gateway[0].listener_port = 19998
    $result = Invoke-TestPlan $manifest $state
    Assert-Startup ($result.code -eq 'HOST_SERVICE_IDENTITY_MISMATCH') 'foreign listener owner or port is not accepted'

    $state = New-FakeStartupState $manifest
    $state.hosts.public_gateway[0].listener_ready = $false
    $result = Invoke-TestPlan $manifest $state
    Assert-Startup ($result.code -eq 'HOST_SERVICE_NOT_READY' -and -not $state.host_starts.ContainsKey('public_gateway')) 'existing matching process without listener is not duplicated'

    $state = New-FakeStartupState $manifest
    $state.hosts.public_gateway = @()
    $result = Invoke-TestPlan $manifest $state
    Assert-Startup ($result.code -eq 'HOST_SERVICE_NOT_READY' -and $state.host_starts.public_gateway -eq 1) 'task start is not readiness proof'

    $state = New-FakeStartupState $manifest
    $state.containers.backend[0].running = $false
    $state.container_start_status = 'TIMEOUT'
    $result = Invoke-TestPlan $manifest $state
    Assert-Startup ($result.code -eq 'CONTAINER_START_UNKNOWN' -and $state.container_starts -eq 1) 'timed out start is unknown and not retried'

    $state = New-FakeStartupState $manifest
    $state.throw_engine = 'token=TOPSECRET diagnostic-kept'
    $result = Invoke-TestPlan $manifest $state
    $serialized = $result | ConvertTo-Json -Depth 10 -Compress
    Assert-Startup ($result.code -eq 'ADAPTER_FAILURE' -and $serialized -notmatch 'TOPSECRET' -and $serialized -match 'diagnostic-kept') 'adapter secrets are redacted'

    $badPath = Copy-TestObject $manifest
    $badPath.root = $testRoot + '-other'
    $state = New-FakeStartupState $manifest
    $result = Invoke-TestPlan $badPath $state
    Assert-Startup ($result.code -eq 'MANIFEST_REFUSED' -and $state.calls.Count -eq 0) 'prefix-like foreign root refused'

    $badHash = Copy-TestObject $manifest
    $badHash.files[0].sha256 = 'f' * 64
    $state = New-FakeStartupState $manifest
    $result = Invoke-TestPlan $badHash $state
    Assert-Startup ($result.code -eq 'MANIFEST_REFUSED' -and $state.calls.Count -eq 0) 'hash mismatch refused before adapters'

    Write-TestText -Path $manifestPath -Text '{invalid'
    $state = New-FakeStartupState $manifest
    $result = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $testRoot -Adapters (New-FakeStartupAdapters $state) -AllowSyntheticRoot
    Assert-Startup ($result.code -eq 'MANIFEST_PARSE_FAILED' -and $state.calls.Count -eq 0) 'invalid JSON refused before adapters'

    Save-TestManifest $manifest
    $state = New-FakeStartupState $manifest
    $helperResult = Invoke-ApprovedExistingContainerPhase -ExpectedContainers $manifest.containers -Adapters (New-FakeStartupAdapters $state) -CommandTimeoutMilliseconds 50
    Assert-Startup ($helperResult.success -and $state.container_starts -eq 0) 'compose helper definition uses existing-only phase'

    $formatGood = ConvertFrom-StartupDockerVersionResponse '28.3.3'
    $formatBad = ConvertFrom-StartupDockerVersionResponse '{{.ServerVersion}}'
    Assert-Startup ($formatGood.valid -and -not $formatBad.valid -and $formatBad.code -eq 'INVALID_FORMAT') 'docker version format is distinguished'

    $volumeMount = (@(ConvertFrom-StartupDockerMounts '[{"Type":"volume","Name":"approved-volume","Source":"/var/lib/docker/volumes/approved-volume/_data","Destination":"/var/lib/data","RW":false}]'))[0]
    Assert-Startup ($volumeMount.source -eq 'approved-volume' -and $volumeMount.read_only) ('named volume identity uses Docker volume name instead of engine backing path; actual=' + ($volumeMount | ConvertTo-Json -Compress))

    $timeout = Invoke-BoundedNativeCommand -FilePath $powershellPath -ArgumentList @('-NoProfile', '-Command', 'Start-Sleep -Seconds 3') -TimeoutMilliseconds 150 -MaximumOutputCharacters 2048
    Assert-Startup ($timeout.status -eq 'TIMEOUT' -and -not $timeout.process_left_running -and $timeout.duration_ms -lt 2500) 'native timeout owns and accounts for child'

    $large = Invoke-BoundedNativeCommand -FilePath $powershellPath -ArgumentList @('-NoProfile', '-Command', '$x="x"*50000; [Console]::Out.Write($x); [Console]::Error.Write($x)') -TimeoutMilliseconds 8000 -MaximumOutputCharacters 4096
    Assert-Startup ($large.status -eq 'SUCCESS' -and $large.stdout_truncated -and $large.stderr_truncated -and $large.stdout.Length -le 4110 -and $large.stderr.Length -le 4110) 'large simultaneous output is bounded without deadlock'

    $nonzero = Invoke-BoundedNativeCommand -FilePath $powershellPath -ArgumentList @('-NoProfile', '-Command', '[Console]::Error.Write("failure"); exit 7') -TimeoutMilliseconds 5000 -MaximumOutputCharacters 2048
    Assert-Startup ($nonzero.status -eq 'NONZERO_EXIT' -and $nonzero.exit_code -eq 7) 'nonzero exit distinguished'
    $empty = Invoke-BoundedNativeCommand -FilePath $powershellPath -ArgumentList @('-NoProfile', '-Command', 'exit 0') -TimeoutMilliseconds 5000 -MaximumOutputCharacters 2048
    Assert-Startup ($empty.status -eq 'EMPTY_OUTPUT') 'empty output distinguished'

    $childDirectory = Join-Path $testRoot "child scripts with apostrophe's"
    $childPath = Join-Path $childDirectory 'argument child.ps1'
    Write-TestText -Path $childPath -Text 'param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Values) [Console]::Out.Write(($Values -join "|"))'
    $marshal = Invoke-BoundedNativeCommand -FilePath $powershellPath -ArgumentList @('-NoProfile', '-File', $childPath, 'space value', "apostrophe's", '{{.ServerVersion}}') -TimeoutMilliseconds 5000 -MaximumOutputCharacters 2048
    Assert-Startup ($marshal.status -eq 'SUCCESS' -and $marshal.stdout -eq "space value|apostrophe's|{{.ServerVersion}}") ('PS5 native marshalling preserves special arguments; actual=' + ($marshal | ConvertTo-Json -Compress))

    $parentLock = Enter-StartupMutex -Root $testRoot
    Assert-Startup ($parentLock.acquired) 'parent acquired unique synthetic mutex'
    $mutexChild = Join-Path $testRoot 'mutex-child.ps1'
    $runtimePath = Join-Path $runtimeDirectory 'startup-runtime.ps1'
    Write-TestText -Path $mutexChild -Text ('. "{0}"; $l=Enter-StartupMutex -Root "{1}"; [Console]::Out.Write([string]$l.acquired); Exit-StartupMutex $l' -f $runtimePath.Replace('"','`"'), $testRoot.Replace('"','`"'))
    $childLockResult = Invoke-BoundedNativeCommand -FilePath $powershellPath -ArgumentList @('-NoProfile', '-File', $mutexChild) -TimeoutMilliseconds 5000 -MaximumOutputCharacters 2048
    Exit-StartupMutex -Lock $parentLock
    Assert-Startup ($childLockResult.status -eq 'SUCCESS' -and $childLockResult.stdout -eq 'False') 'concurrent entry has exactly one mutex owner'

    $recoveryRefusal = Invoke-BoundedNativeCommand -FilePath $powershellPath -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $runtimeDirectory 'start-host-services.ps1')) -TimeoutMilliseconds 5000 -MaximumOutputCharacters 4096
    Assert-Startup ($recoveryRefusal.status -eq 'NONZERO_EXIT' -and $recoveryRefusal.exit_code -eq 20 -and $recoveryRefusal.stdout -match 'RUNTIME_SOURCE_REFUSED') 'ordinary execution from recovery refuses before real adapters'

    $composeHelperPath = Join-Path (Split-Path -Parent $runtimeDirectory) 'windows\start-compose-after-docker.ps1'
    $composeRefusal = Invoke-BoundedNativeCommand -FilePath $powershellPath -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $composeHelperPath) -TimeoutMilliseconds 5000 -MaximumOutputCharacters 4096
    Assert-Startup ($composeRefusal.status -eq 'NONZERO_EXIT' -and $composeRefusal.stderr -match 'START_REFUSED') 'legacy helper direct execution refuses without Docker or Compose fallback'
    $composeHelperSource = Get-Content -LiteralPath $composeHelperPath -Raw
    Assert-Startup ($composeHelperSource -notmatch '(?i)docker\s+compose|compose[^\r\n]*\bup\b') 'legacy helper source contains no Compose deployment fallback'

    $actions = @($state.calls) -join ';'
    Assert-Startup ($actions -notmatch '(?i)compose\.up|pull|build|recreate|backup|purge|export') 'planned actions exclude deployment and unrelated projects'

    Write-Output ('D21_P1_TEST_PASS assertions={0}' -f $script:Assertions)
}
finally {
    if (Test-Path -LiteralPath $testRoot) {
        $resolved = [System.IO.Path]::GetFullPath($testRoot)
        $tempRoot = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
        if ($resolved.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and $resolved -match 'NEXT Stabil D21 P1 [0-9a-f]{32}$') {
            Remove-Item -LiteralPath $resolved -Recurse -Force
        }
    }
}
