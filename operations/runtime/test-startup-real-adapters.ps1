$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$script:Assertions = 0
function Assert-Adapter {
    param([bool]$Condition, [string]$Name)
    $script:Assertions++
    if (-not $Condition) { throw ('ASSERT_FAILED: ' + $Name) }
}

$runtimeDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $runtimeDirectory 'start-host-services.ps1') -DefinitionOnly

$testRoot = Join-Path $env:TEMP ('NEXT Stabil D21 P1 raw adapters {0}' -f ([guid]::NewGuid().ToString('N')))
$manifestPath = Join-Path $testRoot 'operations\runtime\startup-set.json'

function Write-AdapterFixture {
    param([string]$Path, [string]$Text)
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) { [void](New-Item -ItemType Directory -Path $parent -Force) }
    [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
}

function Copy-AdapterFixture {
    param($Value)
    return ($Value | ConvertTo-Json -Depth 20 | ConvertFrom-Json)
}

function New-AdapterManifest {
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
        Write-AdapterFixture -Path $path -Text ('fixture-' + $role)
        $files += [pscustomobject]@{ role = $role; path = $relativeFiles[$role]; sha256 = Get-StartupSha256 -Path $path }
    }
    $toolDirectory = Join-Path $testRoot 'external tools'
    $tools = @()
    foreach ($name in @('docker_cli', 'docker_desktop', 'node')) {
        $path = Join-Path $toolDirectory ($name + '.exe')
        Write-AdapterFixture -Path $path -Text ('fixture-tool-' + $name)
        $tools += [pscustomobject]@{ name = $name; path = $path; sha256 = Get-StartupSha256 -Path $path }
    }
    $nodePath = [string](@($tools | Where-Object { $_.name -eq 'node' })[0].path)
    $public = [pscustomobject]@{ name = 'public_gateway'; policy = 'REQUIRED'; launch_kind = 'TASK'; task_name = 'D21 P1 public'; task_path = '\'; executable = $nodePath; arguments = @('operations/gateway/public_web_server.cjs'); working_directory = $testRoot; listener_host = '127.0.0.1'; listener_port = 18789; script_ref = 'public_gateway_script'; tool_ref = 'node' }
    $private = [pscustomobject]@{ name = 'private_gateway'; policy = 'REQUIRED'; launch_kind = 'TASK'; task_name = 'D21 P1 private'; task_path = '\'; executable = $nodePath; arguments = @('operations/gateway/web_server.cjs'); working_directory = $testRoot; listener_host = '127.0.0.1'; listener_port = 18788; script_ref = 'private_gateway_script'; tool_ref = 'node' }
    $supervisor = [pscustomobject]@{ name = 'supervisor'; policy = 'INTENTIONALLY_STOPPED'; launch_kind = 'TASK'; task_name = 'D21 P1 supervisor'; task_path = '\'; executable = $nodePath; arguments = @('operations/supervisor/server.js'); working_directory = $testRoot; listener_host = '127.0.0.1'; listener_port = 18787; script_ref = 'supervisor_script'; tool_ref = 'node' }
    return [pscustomobject][ordered]@{
        schema = 'NEXT_STABIL_STARTUP_SET_V1'
        component_identity_schema = 'NEXT_STABIL_COMPONENT_COMPATIBILITY_V1'
        set_id = 'D21-P1-RAW-ADAPTERS'
        root = $testRoot
        approval = [pscustomobject]@{ status = 'APPROVED_FOR_START'; set_id = 'D21-P1-RAW-ADAPTERS'; decision_id = 'TEST_ONLY' }
        timeouts = [pscustomobject]@{ native_command_ms = 150; engine_stage_ms = 150; service_stage_ms = 300; poll_ms = 1; max_output_chars = 4096 }
        files = $files
        external_tools = $tools
        docker = [pscustomobject]@{ context = 'desktop-linux-test'; endpoint = 'npipe:////./pipe/nextStabilSynthetic'; process_name = 'Docker Desktop Synthetic'; cli_tool = 'docker_cli'; desktop_tool = 'docker_desktop' }
        containers = @([pscustomobject]@{
            service = 'backend'; container_name = 'd21-p1-backend'; compose_project = 'd21-p1'
            image_id = 'sha256:' + ('a' * 64); repo_digest = 'sha256:' + ('b' * 64)
            mounts = @([pscustomobject]@{ source = (Join-Path $testRoot 'backend'); destination = '/app'; type = 'bind'; read_only = $true })
            ports = @([pscustomobject]@{ host_ip = '127.0.0.1'; host_port = 18000; container_port = 8000; protocol = 'tcp' })
        })
        host_services = @($public, $private, $supervisor)
        readiness = @(
            [pscustomobject]@{ name = 'backend'; uri = 'http://127.0.0.1:18000/health'; expected_status = 200 },
            [pscustomobject]@{ name = 'web'; uri = 'http://127.0.0.1:18789/'; expected_status = 200 },
            [pscustomobject]@{ name = 'public_control_boundary'; uri = 'http://127.0.0.1:18789/control'; expected_status = 404 }
        )
        client = [pscustomobject]@{ policy = 'DISABLED' }
    }
}

function Save-AdapterManifest {
    param($Manifest)
    Write-AdapterFixture -Path $manifestPath -Text ($Manifest | ConvertTo-Json -Depth 20)
}

function New-RawAdapterState {
    param($Manifest)
    return [hashtable]@{
        calls = New-Object System.Collections.Generic.List[string]
        container_running = $true
        container_id = 'd' * 64
        container_start_count = 0
        change_container_id_on_start = $false
        configured_ports = @([pscustomobject]@{ HostIp = '127.0.0.1'; HostPort = '18000'; key = '8000/tcp' })
        active_ports = @([pscustomobject]@{ HostIp = '127.0.0.1'; HostPort = '18000'; key = '8000/tcp' })
        host_modes = @{ public_gateway = 'READY'; private_gateway = 'READY'; supervisor = 'ABSENT' }
        host_observe_count = @{}
        host_start_count = @{}
        creation_date = [datetime]'2026-09-15T12:34:56Z'
        start_status = 'SUCCESS'
        host_delay_ms = 0
    }
}

function ConvertTo-PortJson {
    param([object[]]$Bindings)
    if (@($Bindings).Count -eq 0) { return '{}' }
    $map = [ordered]@{}
    foreach ($binding in $Bindings) {
        $map[[string]$binding.key] = @([ordered]@{ HostIp = [string]$binding.HostIp; HostPort = [string]$binding.HostPort })
    }
    return ($map | ConvertTo-Json -Depth 5 -Compress)
}

function New-HostPayload {
    param($Expected, [hashtable]$State, [string]$Mode)
    $task = [pscustomobject]@{
        execute = [string]$Expected.executable
        arguments = Join-WindowsNativeArguments -ArgumentList @($Expected.arguments | ForEach-Object { [string]$_ })
        working_directory = [string]$Expected.working_directory
    }
    if ($Mode -eq 'ABSENT') { return [pscustomobject]@{ status = 'SUCCESS'; task = $task; processes = @(); listeners = @() } }
    $command = Join-WindowsNativeArguments -ArgumentList (@([string]$Expected.executable) + @($Expected.arguments | ForEach-Object { [string]$_ }))
    if ($Mode -eq 'EXTRA_ARGUMENT') { $command = $command + ' --foreign' }
    $process = [pscustomobject]@{ process_id = 4242; executable_path = [string]$Expected.executable; command_line = $command; creation_date = $State.creation_date }
    $listeners = if ($Mode -eq 'NO_LISTENER' -or $Mode -eq 'EXTRA_ARGUMENT') { @() } elseif ($Mode -eq 'FOREIGN_WILDCARD') {
        @([pscustomobject]@{ local_address = '0.0.0.0'; local_port = [int]$Expected.listener_port; owning_process = 9999 })
    } else {
        @([pscustomobject]@{ local_address = '127.0.0.1'; local_port = [int]$Expected.listener_port; owning_process = 4242 })
    }
    return [pscustomobject]@{ status = 'SUCCESS'; task = $task; processes = @($process); listeners = $listeners }
}

function New-RawSystemBoundary {
    param([hashtable]$State)
    $invokeNative = {
        param($FilePath, $Arguments, $Timeout, $MaximumOutput)
        $joined = @($Arguments) -join ' '
        $State.calls.Add('native:' + $joined)
        if ($joined -eq 'context show') { return [pscustomobject]@{ status = 'SUCCESS'; stdout = 'desktop-linux-test'; stderr = ''; process_left_running = $false } }
        if ($joined -like 'context inspect*') { return [pscustomobject]@{ status = 'SUCCESS'; stdout = 'npipe:////./pipe/nextStabilSynthetic'; stderr = ''; process_left_running = $false } }
        if ($joined -like '--context desktop-linux-test version*') { return [pscustomobject]@{ status = 'SUCCESS'; stdout = '28.3.3'; stderr = ''; process_left_running = $false } }
        if ($joined -like '--context desktop-linux-test ps -aq*') { return [pscustomobject]@{ status = 'SUCCESS'; stdout = $State.container_id; stderr = ''; process_left_running = $false } }
        if ($joined -like '--context desktop-linux-test inspect --format*') {
            $mountJson = @([ordered]@{ Type = 'bind'; Name = ''; Source = (Join-Path $testRoot 'backend'); Destination = '/app'; RW = $false }) | ConvertTo-Json -Depth 5 -Compress
            $configured = ConvertTo-PortJson $State.configured_ports
            $active = ConvertTo-PortJson $State.active_ports
            $line = @($State.container_id, '/d21-p1-backend', 'd21-p1', 'backend', ('sha256:' + ('a' * 64)), ([string]$State.container_running), $mountJson, $configured, $active) -join '|'
            return [pscustomobject]@{ status = 'SUCCESS'; stdout = $line; stderr = ''; process_left_running = $false }
        }
        if ($joined -like '--context desktop-linux-test image inspect*') { return [pscustomobject]@{ status = 'SUCCESS'; stdout = ('["repo@sha256:' + ('b' * 64) + '"]'); stderr = ''; process_left_running = $false } }
        if ($joined -like '--context desktop-linux-test start*') {
            $State.container_start_count++
            $State.container_running = $true
            if ($State.change_container_id_on_start) { $State.container_id = 'e' * 64 }
            $State.active_ports = @([pscustomobject]@{ HostIp = '127.0.0.1'; HostPort = '18000'; key = '8000/tcp' })
            return [pscustomobject]@{ status = 'SUCCESS'; stdout = 'd21-p1-backend'; stderr = ''; process_left_running = $false }
        }
        throw ('UNEXPECTED_NATIVE_BOUNDARY:' + $joined)
    }.GetNewClosure()
    $hostOperation = {
        param($Operation, $Expected, $Timeout, $MaximumOutput)
        $name = [string]$Expected.name
        $State.calls.Add(('host:{0}:{1}' -f $Operation, $name))
        if ($State.host_delay_ms -gt 0) {
            $payload = New-HostPayload -Expected $Expected -State $State -Mode 'ABSENT'
            return Invoke-BoundedStartupHostOperation -Operation $Operation -Expected $Expected -TimeoutMilliseconds $Timeout -MaximumOutputCharacters $MaximumOutput -SyntheticFixture ([pscustomobject]@{ delay_ms = $State.host_delay_ms; result = $payload })
        }
        if ($Operation -eq 'START') {
            if (-not $State.host_start_count.ContainsKey($name)) { $State.host_start_count[$name] = 0 }
            $State.host_start_count[$name]++
            if ($State.start_status -eq 'SUCCESS') { $State.host_modes[$name] = 'READY' }
            return [pscustomobject]@{ status = 'SUCCESS'; result = [pscustomobject]@{ status = $State.start_status }; duration_ms = 1; job_left_running = $false; operation_may_have_started = $false }
        }
        if (-not $State.host_observe_count.ContainsKey($name)) { $State.host_observe_count[$name] = 0 }
        $State.host_observe_count[$name]++
        $mode = [string]$State.host_modes[$name]
        if ($mode -eq 'ACCESS_DENIED') { return [pscustomobject]@{ status = 'ERROR'; result = $null; duration_ms = 1; job_left_running = $false; operation_may_have_started = $false } }
        return [pscustomobject]@{ status = 'SUCCESS'; result = (New-HostPayload -Expected $Expected -State $State -Mode $mode); duration_ms = 1; job_left_running = $false; operation_may_have_started = $false }
    }.GetNewClosure()
    $http = {
        param($Uri, $Timeout)
        $State.calls.Add('http:' + $Uri)
        [pscustomobject]@{ status = if ($Uri -like '*/control') { 404 } else { 200 } }
    }.GetNewClosure()
    return [pscustomobject]@{
        InvokeNative = $invokeNative
        GetEnvironmentState = { [pscustomobject]@{ docker_host_override = ''; docker_context_override = '' } }
        ObserveDesktop = { param($ProcessName, $ExpectedPath) throw 'UNEXPECTED_DESKTOP_OBSERVE' }
        StartDesktop = { param($ExpectedPath) throw 'UNEXPECTED_DESKTOP_START' }
        InvokeHostOperation = $hostOperation
        InvokeHttp = $http
        Sleep = { param($Milliseconds) }
    }
}

function Invoke-RawPlan {
    param($Manifest, [hashtable]$State)
    Save-AdapterManifest $Manifest
    $boundary = New-RawSystemBoundary $State
    $adapters = New-RealStartupAdapters -Manifest $Manifest -SystemBoundary $boundary
    return Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $testRoot -Adapters $adapters -AllowSyntheticRoot
}

try {
    [void](New-Item -ItemType Directory -Path $testRoot -Force)
    $manifest = New-AdapterManifest
    Save-AdapterManifest $manifest

    $incompleteBoundary = New-RawSystemBoundary (New-RawAdapterState $manifest)
    $incompleteBoundary.PSObject.Properties.Remove('InvokeHostOperation')
    $contractRefused = $false
    try { [void](New-RealStartupAdapters -Manifest $manifest -SystemBoundary $incompleteBoundary) } catch { $contractRefused = $_.Exception.Message -match 'SYSTEM_BOUNDARY_CONTRACT_INVALID' }
    Assert-Adapter $contractRefused 'missing low-level fake refuses instead of falling back to host operations'

    $state = New-RawAdapterState $manifest
    $result = Invoke-RawPlan $manifest $state
    Assert-Adapter ($result.code -eq 'BASE_READY_LIMITED') ('raw-boundary positive plan succeeds; actual=' + ($result | ConvertTo-Json -Depth 8 -Compress))
    Assert-Adapter ($state.container_start_count -eq 0 -and $state.host_start_count.Count -eq 0) 'ready synthetic set is preserved without starts'
    Assert-Adapter (@($state.calls | Where-Object { $_ -notmatch '^(native:|host:|http:)' }).Count -eq 0) 'raw fixture campaign records only complete fake-boundary calls'

    $public = @($manifest.host_services | Where-Object { $_.name -eq 'public_gateway' })[0]
    $state = New-RawAdapterState $manifest
    $adapters = New-RealStartupAdapters -Manifest $manifest -SystemBoundary (New-RawSystemBoundary $state)
    $dateObservation = ConvertTo-StartupHostObservation (& $adapters.ObserveHostService $public 100)
    Assert-Adapter ($dateObservation.status -eq 'PRESENT' -and $dateObservation.matches[0].start_time_utc -eq '2026-09-15T12:34:56.0000000Z') 'RV01 DateTime maps to invariant UTC through the real adapter'
    $state.creation_date = '20260915123456.000000+000'
    $dmtfObservation = ConvertTo-StartupHostObservation (& $adapters.ObserveHostService $public 100)
    Assert-Adapter ($dmtfObservation.status -eq 'PRESENT' -and $dmtfObservation.matches[0].start_time_utc -match '^2026-09-15T') 'RV01 DMTF remains explicitly supported'
    $state.creation_date = 'not-a-date'
    $badDate = ConvertTo-StartupHostObservation (& $adapters.ObserveHostService $public 100)
    Assert-Adapter ($badDate.status -eq 'UNKNOWN') 'RV01 invalid creation date is UNKNOWN, never invented readiness'

    $state = New-RawAdapterState $manifest
    $state.container_running = $false
    $state.active_ports = @()
    $result = Invoke-RawPlan $manifest $state
    Assert-Adapter ($result.code -eq 'BASE_READY_LIMITED' -and $state.container_start_count -eq 1) 'RV02 stopped container uses configured bindings, starts exact ID once, then checks active bindings'
    $state = New-RawAdapterState $manifest
    $state.container_running = $false
    $state.active_ports = @()
    $state.configured_ports = @([pscustomobject]@{ HostIp = '0.0.0.0'; HostPort = '18000'; key = '8000/tcp' })
    $result = Invoke-RawPlan $manifest $state
    Assert-Adapter ($result.code -eq 'IDENTITY_MISMATCH' -and $state.container_start_count -eq 0) 'RV02 incorrect configured binding blocks before start'
    $state = New-RawAdapterState $manifest
    $state.container_running = $false
    $state.active_ports = @()
    $state.configured_ports += [pscustomobject]@{ HostIp = '127.0.0.1'; HostPort = '18001'; key = '8001/tcp' }
    $result = Invoke-RawPlan $manifest $state
    Assert-Adapter ($result.code -eq 'IDENTITY_MISMATCH' -and $state.container_start_count -eq 0) 'RV02 additional unapproved configured binding blocks before start'
    $state = New-RawAdapterState $manifest
    $state.container_running = $false
    $state.active_ports = @()
    $state.change_container_id_on_start = $true
    $result = Invoke-RawPlan $manifest $state
    Assert-Adapter ($result.code -eq 'CONTAINER_RUNTIME_ID_CHANGED' -and $state.container_start_count -eq 1) 'RV02 changed full ID after the one start is refused by the real observation path'

    foreach ($case in @('FOREIGN_WILDCARD', 'EXTRA_ARGUMENT', 'ACCESS_DENIED')) {
        $state = New-RawAdapterState $manifest
        $state.host_modes.public_gateway = $case
        $result = Invoke-RawPlan $manifest $state
        $expectedCode = if ($case -eq 'ACCESS_DENIED') { 'HOST_SERVICE_OBSERVATION_UNKNOWN' } else { 'HOST_SERVICE_IDENTITY_MISMATCH' }
        Assert-Adapter ($result.code -eq $expectedCode -and -not $state.host_start_count.ContainsKey('public_gateway')) ('RV03 refuses without start: ' + $case)
    }
    $state = New-RawAdapterState $manifest
    $state.host_modes.public_gateway = 'ABSENT'
    $result = Invoke-RawPlan $manifest $state
    Assert-Adapter ($result.code -eq 'BASE_READY_LIMITED' -and $state.host_start_count.public_gateway -eq 1) 'RV03 true absence plus free port allows one synthetic exact-task start'

    $wrongScript = Copy-AdapterFixture $manifest
    $wrongScript.host_services[0].arguments = @('operations/gateway/web_server.cjs')
    $state = New-RawAdapterState $manifest
    $result = Invoke-RawPlan $wrongScript $state
    Assert-Adapter ($result.code -eq 'MANIFEST_REFUSED' -and $state.calls.Count -eq 0 -and ($result.details -join ';') -match 'HOST_SERVICE_SCRIPT_BINDING_MISMATCH') 'RV04 internally inconsistent script_ref is refused before adapters'
    $outsideScript = Copy-AdapterFixture $manifest
    $outsideScript.host_services[0].arguments = @((Join-Path (Split-Path -Parent $testRoot) 'recovery\public_web_server.cjs'))
    $state = New-RawAdapterState $manifest
    $result = Invoke-RawPlan $outsideScript $state
    Assert-Adapter ($result.code -eq 'MANIFEST_REFUSED' -and $state.calls.Count -eq 0) 'RV04 adjacent recovery script cannot be the executed manifest argument'

    $syntheticSuccess = Invoke-BoundedStartupHostOperation -Operation OBSERVE -Expected $public -TimeoutMilliseconds 250 -MaximumOutputCharacters 4096 -SyntheticFixture ([pscustomobject]@{ delay_ms = 0; result = (New-HostPayload $public (New-RawAdapterState $manifest) 'ABSENT') })
    Assert-Adapter ($syntheticSuccess.status -eq 'SUCCESS' -and -not $syntheticSuccess.job_left_running) 'RV05 bounded host job returns one controlled synthetic result'
    $syntheticTimeout = Invoke-BoundedStartupHostOperation -Operation OBSERVE -Expected $public -TimeoutMilliseconds 100 -MaximumOutputCharacters 4096 -SyntheticFixture ([pscustomobject]@{ delay_ms = 500; result = (New-HostPayload $public (New-RawAdapterState $manifest) 'ABSENT') })
    Assert-Adapter ($syntheticTimeout.status -eq 'TIMEOUT' -and -not $syntheticTimeout.job_left_running -and $syntheticTimeout.duration_ms -lt 750) ('RV05 deadline includes bounded cleanup; actual=' + ($syntheticTimeout | ConvertTo-Json -Compress))
    $state = New-RawAdapterState $manifest
    $state.host_delay_ms = 500
    $result = Invoke-RawPlan $manifest $state
    Assert-Adapter ($result.code -eq 'SUPERVISOR_STATE_UNKNOWN' -and $state.host_start_count.Count -eq 0) 'RV05 observation timeout is UNKNOWN and starts no service'
    $state = New-RawAdapterState $manifest
    $state.host_delay_ms = 500
    $adapters = New-RealStartupAdapters -Manifest $manifest -SystemBoundary (New-RawSystemBoundary $state)
    $adapterWatch = [System.Diagnostics.Stopwatch]::StartNew()
    $adapterObservation = ConvertTo-StartupHostObservation (& $adapters.ObserveHostService $public 100)
    $adapterWatch.Stop()
    Assert-Adapter ($adapterObservation.status -eq 'UNKNOWN' -and $adapterWatch.ElapsedMilliseconds -lt 750) ('RV05 whole ObserveHostService adapter call is bounded; elapsed_ms=' + $adapterWatch.ElapsedMilliseconds)
    $startTimeout = Invoke-BoundedStartupHostOperation -Operation START -Expected $public -TimeoutMilliseconds 100 -MaximumOutputCharacters 4096 -SyntheticFixture ([pscustomobject]@{ delay_ms = 500; result = [pscustomobject]@{ status = 'SUCCESS' } })
    Assert-Adapter ($startTimeout.status -eq 'TIMEOUT' -and $startTimeout.operation_may_have_started -and -not $startTimeout.job_left_running) 'RV05 start timeout is possible-contact UNKNOWN, not rollback or success'
    $adapterStart = & $adapters.StartHostService $public 100
    Assert-Adapter ($adapterStart.status -eq 'TIMEOUT' -and $adapterStart.operation_may_have_started -and -not $adapterStart.job_left_running) 'RV05 whole StartHostService adapter preserves possible-start UNKNOWN without retry'

    Write-Output ('D21_P1_RAW_ADAPTER_TEST_PASS assertions={0}' -f $script:Assertions)
}
finally {
    if (Test-Path -LiteralPath $testRoot) {
        $resolved = [System.IO.Path]::GetFullPath($testRoot)
        $tempRoot = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
        if ($resolved.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and $resolved -match 'NEXT Stabil D21 P1 raw adapters [0-9a-f]{32}$') {
            Remove-Item -LiteralPath $resolved -Recurse -Force
        }
    }
}
