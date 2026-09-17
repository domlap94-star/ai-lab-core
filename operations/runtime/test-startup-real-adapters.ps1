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
        repo_digests = @('repo@sha256:' + ('b' * 64))
        image_identity_status = 'SUCCESS'
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

function New-SharedProcessRecord {
    param($Service, [int]$ProcessId, [string[]]$AdditionalArguments)
    $arguments = @([string]$Service.executable) + @($Service.arguments | ForEach-Object { [string]$_ }) + @($AdditionalArguments)
    return [pscustomobject]@{
        ProcessId = $ProcessId
        ExecutablePath = [string]$Service.executable
        CommandLine = Join-WindowsNativeArguments -ArgumentList $arguments
        CreationDate = [datetime]'2026-09-15T12:34:56Z'
    }
}

function New-SharedListenerRecord {
    param($Service, [int]$ProcessId, [string]$Address = '127.0.0.1')
    return [pscustomobject]@{
        LocalAddress = $Address
        LocalPort = [int]$Service.listener_port
        OwningProcess = $ProcessId
    }
}

function New-HostCommandBoundary {
    param([hashtable]$State)

    $getTask = {
        param($Expected, $BoundaryState)
        $mode = if ($BoundaryState.task_modes.ContainsKey([string]$Expected.name)) { [string]$BoundaryState.task_modes[[string]$Expected.name] } else { 'READY' }
        if ($mode -eq 'MISSING') { return $null }
        if ($mode -eq 'MISSING_ERROR') {
            $exception = New-Object System.Management.Automation.ItemNotFoundException 'synthetic task query found no match'
            $record = New-Object System.Management.Automation.ErrorRecord(
                $exception,
                'CmdletizationQuery_NotFound_TaskName,Get-ScheduledTask',
                [System.Management.Automation.ErrorCategory]::ObjectNotFound,
                ([string]$Expected.task_name)
            )
            throw $record
        }
        if ($mode -eq 'ACCESS_DENIED') { throw [System.UnauthorizedAccessException]::new('synthetic task access denied') }
        return [pscustomobject]@{ Actions = @([pscustomobject]@{
            Execute = [string]$Expected.executable
            Arguments = [string]$Expected.argument_string
            WorkingDirectory = [string]$Expected.working_directory
        }) }
    }
    $getProcesses = {
        param($Expected, $BoundaryState)
        if ([string]$BoundaryState.process_mode -eq 'ACCESS_DENIED') { throw [System.UnauthorizedAccessException]::new('synthetic CIM access denied') }
        if ([string]$BoundaryState.process_mode -eq 'MISSING_MODULE') { throw [System.Management.Automation.CommandNotFoundException]::new('synthetic CIM command unavailable') }
        return @($BoundaryState.shared_processes)
    }
    $getListeners = {
        param($Expected, $BoundaryState)
        $mode = if ($BoundaryState.listener_modes.ContainsKey([string]$Expected.name)) { [string]$BoundaryState.listener_modes[[string]$Expected.name] } else { 'RETURN' }
        if ($mode -eq 'NOT_FOUND') {
            $exception = New-Object System.Management.Automation.ItemNotFoundException 'synthetic listener query found no match'
            $record = New-Object System.Management.Automation.ErrorRecord(
                $exception,
                'CmdletizationQuery_NotFound_LocalPort,Get-NetTCPConnection',
                [System.Management.Automation.ErrorCategory]::ObjectNotFound,
                ([int]$Expected.listener_port)
            )
            throw $record
        }
        if ($mode -eq 'ACCESS_DENIED') { throw [System.UnauthorizedAccessException]::new('synthetic TCP access denied') }
        if ($mode -eq 'PROVIDER_ERROR') { throw [System.InvalidOperationException]::new('synthetic TCP provider error') }
        $matches = New-Object System.Collections.Generic.List[object]
        foreach ($listener in @($BoundaryState.shared_listeners)) {
            if ([int]$listener.LocalPort -eq [int]$Expected.listener_port) { $matches.Add($listener) }
        }
        return $matches.ToArray()
    }
    $startTask = {
        param($Expected, $BoundaryState)
        if ([string]$BoundaryState.start_mode -eq 'ERROR') { throw [System.InvalidOperationException]::new('synthetic start failure') }
        return [pscustomobject]@{ accepted = $true }
    }
    return [pscustomobject]@{
        State = $State
        GetTask = $getTask
        GetProcesses = $getProcesses
        GetListeners = $getListeners
        StartTask = $startTask
    }
}

function New-CommandPipelineState {
    param($Manifest)
    $base = New-RawAdapterState $Manifest
    $base.shared_processes = @()
    $base.shared_listeners = @()
    $base.task_modes = @{}
    $base.listener_modes = @{}
    $base.process_mode = 'RETURN'
    $base.start_mode = 'SUCCESS'
    $base.lower_boundary_calls = New-Object System.Collections.Generic.List[string]
    $base.next_process_id = 5100
    return $base
}

function New-CommandPipelineSystemBoundary {
    param([hashtable]$State)

    $boundary = New-RawSystemBoundary $State
    $hostOperation = {
        param($Operation, $Expected, $Timeout, $MaximumOutput)
        $name = [string]$Expected.name
        $State.calls.Add(('command-host:{0}:{1}' -f $Operation, $name))
        $operationResult = Invoke-BoundedStartupHostOperation `
            -Operation $Operation `
            -Expected $Expected `
            -TimeoutMilliseconds $Timeout `
            -MaximumOutputCharacters $MaximumOutput `
            -SyntheticCommandBoundary (New-HostCommandBoundary $State)
        $State.calls.Add(('command-result:{0}:{1}:{2}' -f $Operation, $name, [string]$operationResult.status))
        if ($operationResult.status -eq 'SUCCESS' -and $null -ne $operationResult.result) {
            foreach ($call in @($operationResult.result.lower_boundary_calls)) { $State.lower_boundary_calls.Add(('{0}:{1}:{2}' -f $Operation, $name, $call)) }
        }
        if ($Operation -eq 'START' -and $operationResult.status -eq 'SUCCESS' -and [string]$operationResult.result.status -eq 'SUCCESS') {
            if (-not $State.host_start_count.ContainsKey($name)) { $State.host_start_count[$name] = 0 }
            $State.host_start_count[$name]++
            $State.next_process_id++
            $newProcessId = [int]$State.next_process_id
            $State.shared_processes += New-SharedProcessRecord -Service $Expected -ProcessId $newProcessId -AdditionalArguments @()
            $State.shared_listeners += New-SharedListenerRecord -Service $Expected -ProcessId $newProcessId
            $State.listener_modes[$name] = 'RETURN'
        }
        return $operationResult
    }.GetNewClosure()
    $boundary.InvokeHostOperation = $hostOperation
    return $boundary
}

function Invoke-CommandPipelinePlan {
    param($Manifest, [hashtable]$State)
    Save-AdapterManifest $Manifest
    $adapters = New-RealStartupAdapters -Manifest $Manifest -SystemBoundary (New-CommandPipelineSystemBoundary $State)
    return Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $testRoot -Adapters $adapters -AllowSyntheticRoot
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
            $line = @($State.container_id, '/d21-p1-backend', 'd21-p1', 'backend', ('sha256:' + ('a' * 64)), ([string]$State.container_running), 'NONE', $mountJson, $configured, $active) -join '|'
            return [pscustomobject]@{ status = 'SUCCESS'; stdout = $line; stderr = ''; process_left_running = $false }
        }
        if ($joined -like '--context desktop-linux-test image inspect*') {
            if ($State.image_identity_status -ne 'SUCCESS') { return [pscustomobject]@{ status = $State.image_identity_status; stdout = ''; stderr = 'synthetic image identity failure'; process_left_running = $false } }
            return [pscustomobject]@{ status = 'SUCCESS'; stdout = (ConvertTo-Json -InputObject @($State.repo_digests) -Compress); stderr = ''; process_left_running = $false }
        }
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

    $localImageManifest = Copy-AdapterFixture $manifest
    $localImageManifest.containers[0] | Add-Member -NotePropertyName image_identity_mode -NotePropertyValue 'LOCAL_IMAGE_ID_CONFIRMED_NO_REPO_DIGEST'
    $localImageManifest.containers[0].repo_digest = 'CONFIRMED_ABSENT'
    $state = New-RawAdapterState $localImageManifest
    $state.repo_digests = @()
    $localImageResult = Invoke-RawPlan $localImageManifest $state
    Assert-Adapter ($localImageResult.code -eq 'BASE_READY_LIMITED' -and $state.container_start_count -eq 0) ('explicit backend local-image mode passes only after the real adapter confirms empty RepoDigests; actual=' + ($localImageResult | ConvertTo-Json -Depth 8 -Compress))

    $state = New-RawAdapterState $manifest
    $state.repo_digests = @('repo@sha256:' + ('c' * 64))
    $wrongDigestResult = Invoke-RawPlan $manifest $state
    Assert-Adapter ($wrongDigestResult.code -eq 'IDENTITY_MISMATCH' -and $state.container_start_count -eq 0) 'nonmatching observed repository digest blocks before start'

    $state = New-RawAdapterState $localImageManifest
    $state.repo_digests = @()
    $state.image_identity_status = 'TIMEOUT'
    $unknownDigestResult = Invoke-RawPlan $localImageManifest $state
    Assert-Adapter ($unknownDigestResult.code -eq 'ADAPTER_FAILURE' -and $state.container_start_count -eq 0) 'image identity timeout remains unknown and never falls back to local-image mode'

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

    $commandManifest = Copy-AdapterFixture $manifest
    $commandManifest.timeouts.native_command_ms = 1000
    $commandManifest.timeouts.engine_stage_ms = 1000
    $commandManifest.timeouts.service_stage_ms = 2500
    $public = @($commandManifest.host_services | Where-Object { $_.name -eq 'public_gateway' })[0]
    $private = @($commandManifest.host_services | Where-Object { $_.name -eq 'private_gateway' })[0]
    $supervisor = @($commandManifest.host_services | Where-Object { $_.name -eq 'supervisor' })[0]
    $otherService = [pscustomobject]@{
        executable = [string]$public.executable
        arguments = @('operations/other/unrelated-tool.js')
        working_directory = $testRoot
    }

    $state = New-CommandPipelineState $commandManifest
    $state.shared_processes = @(
        (New-SharedProcessRecord -Service $public -ProcessId 4101 -AdditionalArguments @()),
        (New-SharedProcessRecord -Service $private -ProcessId 4102 -AdditionalArguments @()),
        (New-SharedProcessRecord -Service $otherService -ProcessId 4103 -AdditionalArguments @())
    )
    $state.shared_listeners = @(
        (New-SharedListenerRecord -Service $public -ProcessId 4101),
        (New-SharedListenerRecord -Service $private -ProcessId 4102)
    )
    $state.listener_modes.supervisor = 'NOT_FOUND'
    $result = Invoke-CommandPipelinePlan $commandManifest $state
    Assert-Adapter ($result.code -eq 'BASE_READY_LIMITED' -and $result.supervisor_status -eq 'INTENTIONALLY_STOPPED') ('RV03-POSITIVE-01 shared node process image is classified by exact script and port ownership; actual=' + ($result | ConvertTo-Json -Depth 8 -Compress) + '; calls=' + (@($state.calls) -join ',') + '; lower=' + (@($state.lower_boundary_calls) -join ','))
    Assert-Adapter ($state.host_start_count.Count -eq 0) 'RV03-POSITIVE-01 public/private coexistence preserves both services and starts nothing'
    Assert-Adapter (@($state.lower_boundary_calls | Where-Object { $_ -match '^OBSERVE:(public_gateway|private_gateway|supervisor):GET_PROCESSES$' }).Count -eq 3) 'RV03-POSITIVE-01 every service observes the same untrimmed global process set through the worker branch'
    Assert-Adapter (@($state.lower_boundary_calls | Where-Object { $_ -eq 'OBSERVE:supervisor:GET_LISTENERS' }).Count -eq 1) 'RV03-POSITIVE-02 structured no-listener result executes and normalizes in the worker branch'

    $state = New-CommandPipelineState $commandManifest
    $state.shared_processes = @(
        (New-SharedProcessRecord -Service $private -ProcessId 4202 -AdditionalArguments @()),
        (New-SharedProcessRecord -Service $otherService -ProcessId 4203 -AdditionalArguments @())
    )
    $state.shared_listeners = @((New-SharedListenerRecord -Service $private -ProcessId 4202))
    $state.listener_modes.public_gateway = 'NOT_FOUND'
    $state.listener_modes.supervisor = 'NOT_FOUND'
    $firstMissingPublic = Invoke-CommandPipelinePlan $commandManifest $state
    $secondMissingPublic = Invoke-CommandPipelinePlan $commandManifest $state
    Assert-Adapter ($firstMissingPublic.code -eq 'BASE_READY_LIMITED' -and $secondMissingPublic.code -eq 'BASE_READY_LIMITED') 'RV03-POSITIVE-01 missing public gateway reaches START_ONCE/readiness and remains ready on the next plan'
    Assert-Adapter ($state.host_start_count.public_gateway -eq 1 -and $state.host_start_count.Count -eq 1) 'RV03-POSITIVE-01 exactly one fake public task start occurs across two plans'
    Assert-Adapter (@($state.lower_boundary_calls | Where-Object { $_ -eq 'START:public_gateway:START_TASK' }).Count -eq 1) 'RV03-POSITIVE-01 the one start passes through the real internal START command branch'

    $state = New-CommandPipelineState $commandManifest
    $state.shared_processes = @((New-SharedProcessRecord -Service $public -ProcessId 4301 -AdditionalArguments @('--foreign')))
    $state.shared_listeners = @()
    $state.listener_modes.supervisor = 'NOT_FOUND'
    $result = Invoke-CommandPipelinePlan $commandManifest $state
    Assert-Adapter ($result.code -eq 'HOST_SERVICE_IDENTITY_MISMATCH' -and $state.host_start_count.Count -eq 0) 'RV03 same approved script with additional argument remains a conflict'

    $state = New-CommandPipelineState $commandManifest
    $prefixedProcess = New-SharedProcessRecord -Service $public -ProcessId 4302 -AdditionalArguments @()
    $prefixedProcess.CommandLine = Join-WindowsNativeArguments -ArgumentList @([string]$public.executable, '--foreign', [string]$public.arguments[0])
    $state.shared_processes = @($prefixedProcess)
    $state.shared_listeners = @()
    $state.listener_modes.supervisor = 'NOT_FOUND'
    $result = Invoke-CommandPipelinePlan $commandManifest $state
    Assert-Adapter ($result.code -eq 'HOST_SERVICE_IDENTITY_MISMATCH' -and $state.host_start_count.Count -eq 0) 'RV03 same approved script with an unapproved prefix argument remains a conflict'

    $state = New-CommandPipelineState $commandManifest
    $state.shared_processes = @(
        (New-SharedProcessRecord -Service $public -ProcessId 4401 -AdditionalArguments @()),
        (New-SharedProcessRecord -Service $public -ProcessId 4402 -AdditionalArguments @())
    )
    $state.shared_listeners = @((New-SharedListenerRecord -Service $public -ProcessId 4401))
    $state.listener_modes.supervisor = 'NOT_FOUND'
    $result = Invoke-CommandPipelinePlan $commandManifest $state
    Assert-Adapter ($result.code -eq 'HOST_SERVICE_AMBIGUOUS' -and $state.host_start_count.Count -eq 0) 'RV03 duplicate exact processes remain ambiguous and cannot be started'

    $state = New-CommandPipelineState $commandManifest
    $state.shared_processes = @((New-SharedProcessRecord -Service $public -ProcessId 4501 -AdditionalArguments @()))
    $state.shared_listeners = @()
    $state.listener_modes.supervisor = 'NOT_FOUND'
    $state.listener_modes.public_gateway = 'NOT_FOUND'
    $presentWithoutListenerAdapters = New-RealStartupAdapters -Manifest $commandManifest -SystemBoundary (New-CommandPipelineSystemBoundary $state)
    $presentWithoutListener = ConvertTo-StartupHostObservation (& $presentWithoutListenerAdapters.ObserveHostService $public 1000)
    Assert-Adapter ($presentWithoutListener.status -eq 'PRESENT' -and -not $presentWithoutListener.matches[0].listener_ready) 'RV03-POSITIVE-02 exact process with confirmed absent listener remains PRESENT/not-ready'
    $result = Invoke-CommandPipelinePlan $commandManifest $state
    Assert-Adapter ($result.code -in @('HOST_SERVICE_NOT_READY', 'HOST_SERVICE_OBSERVATION_UNKNOWN') -and $state.host_start_count.Count -eq 0) ('RV03-POSITIVE-02 bounded wait for an existing not-ready process never starts a duplicate; actual=' + ($result | ConvertTo-Json -Depth 8 -Compress))

    $state = New-CommandPipelineState $commandManifest
    $state.task_modes.supervisor = 'MISSING'
    $result = Invoke-CommandPipelinePlan $commandManifest $state
    Assert-Adapter ($result.code -eq 'CONTROLLED_DEPLOY_REQUIRED' -and $state.host_start_count.Count -eq 0) 'RV03-POSITIVE-02 missing approved task requires controlled install and starts nothing'

    $state = New-CommandPipelineState $commandManifest
    $state.task_modes.supervisor = 'MISSING_ERROR'
    $result = Invoke-CommandPipelinePlan $commandManifest $state
    Assert-Adapter ($result.code -eq 'CONTROLLED_DEPLOY_REQUIRED' -and $state.host_start_count.Count -eq 0) 'RV03-POSITIVE-02 structural scheduled-task no-match requires controlled install and starts nothing'

    $state = New-CommandPipelineState $commandManifest
    $state.listener_modes.supervisor = 'ACCESS_DENIED'
    $result = Invoke-CommandPipelinePlan $commandManifest $state
    Assert-Adapter ($result.code -eq 'SUPERVISOR_STATE_UNKNOWN' -and $state.host_start_count.Count -eq 0) 'RV03-POSITIVE-02 listener access denial remains UNKNOWN and starts nothing'

    $state = New-CommandPipelineState $commandManifest
    $state.task_modes.supervisor = 'ACCESS_DENIED'
    $result = Invoke-CommandPipelinePlan $commandManifest $state
    Assert-Adapter ($result.code -eq 'SUPERVISOR_STATE_UNKNOWN' -and $state.host_start_count.Count -eq 0) 'RV03-POSITIVE-02 task access denial remains UNKNOWN and starts nothing'

    foreach ($processFailure in @('ACCESS_DENIED', 'MISSING_MODULE')) {
        $state = New-CommandPipelineState $commandManifest
        $state.process_mode = $processFailure
        $result = Invoke-CommandPipelinePlan $commandManifest $state
        Assert-Adapter ($result.code -eq 'SUPERVISOR_STATE_UNKNOWN' -and $state.host_start_count.Count -eq 0) ('RV03-POSITIVE-02 process collection failure remains UNKNOWN: ' + $processFailure)
    }

    $state = New-CommandPipelineState $commandManifest
    $state.listener_modes.supervisor = 'PROVIDER_ERROR'
    $result = Invoke-CommandPipelinePlan $commandManifest $state
    Assert-Adapter ($result.code -eq 'SUPERVISOR_STATE_UNKNOWN' -and $state.host_start_count.Count -eq 0) 'RV03-POSITIVE-02 listener provider error remains UNKNOWN and starts nothing'

    $state = New-CommandPipelineState $commandManifest
    $state.shared_processes = @([pscustomobject]@{ ProcessId = 4601; ExecutablePath = ''; CommandLine = ''; CreationDate = [datetime]'2026-09-15T12:34:56Z' })
    $state.listener_modes.supervisor = 'NOT_FOUND'
    $result = Invoke-CommandPipelinePlan $commandManifest $state
    Assert-Adapter ($result.code -eq 'SUPERVISOR_STATE_UNKNOWN' -and $state.host_start_count.Count -eq 0) 'RV03-POSITIVE-02 incomplete process identity remains UNKNOWN and starts nothing'

    $desktopNoMatch = {
        param($Name)
        $exception = New-Object System.Management.Automation.ItemNotFoundException 'synthetic process query found no match'
        $record = New-Object System.Management.Automation.ErrorRecord(
            $exception,
            'NoProcessFoundForGivenName,Microsoft.PowerShell.Commands.GetProcessCommand',
            [System.Management.Automation.ErrorCategory]::ObjectNotFound,
            $Name
        )
        throw $record
    }
    $desktopAbsent = @(Invoke-StartupDesktopProcessObservation -ProcessName 'Docker Desktop Synthetic' -ExpectedPath 'C:\synthetic\Docker Desktop.exe' -GetProcessBoundary $desktopNoMatch)
    Assert-Adapter ($desktopAbsent.Count -eq 0) 'RV03-POSITIVE-02 exact Get-Process no-match is normalized to confirmed absence'

    $state = New-RawAdapterState $commandManifest
    $desktopBoundary = New-RawSystemBoundary $state
    $baseNative = $desktopBoundary.InvokeNative
    $script:DesktopEngineObservations = 0
    $script:DesktopStarts = 0
    $desktopBoundary.InvokeNative = {
        param($FilePath, $Arguments, $Timeout, $MaximumOutput)
        if ((@($Arguments) -join ' ') -like '--context desktop-linux-test version*') {
            $script:DesktopEngineObservations++
            if ($script:DesktopEngineObservations -eq 1) { return [pscustomobject]@{ status = 'NONZERO_EXIT'; stdout = ''; stderr = ''; process_left_running = $false } }
        }
        return & $baseNative $FilePath $Arguments $Timeout $MaximumOutput
    }.GetNewClosure()
    $desktopBoundary.ObserveDesktop = {
        param($ProcessName, $ExpectedPath)
        return @(Invoke-StartupDesktopProcessObservation -ProcessName $ProcessName -ExpectedPath $ExpectedPath -GetProcessBoundary $desktopNoMatch)
    }.GetNewClosure()
    $desktopBoundary.StartDesktop = {
        param($ExpectedPath)
        $script:DesktopStarts++
        return [pscustomobject]@{ status = 'ACCEPTED'; pid = 9991 }
    }
    Save-AdapterManifest $commandManifest
    $desktopAdapters = New-RealStartupAdapters -Manifest $commandManifest -SystemBoundary $desktopBoundary
    $desktopStartResult = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $testRoot -Adapters $desktopAdapters -AllowSyntheticRoot
    Assert-Adapter ($desktopStartResult.code -eq 'BASE_READY_LIMITED' -and $script:DesktopStarts -eq 1) 'RV03-POSITIVE-02 confirmed desktop absence permits one fake desktop start and bounded engine recheck'

    $desktopUnknownBoundary = { param($Name) throw [System.UnauthorizedAccessException]::new('synthetic process access denied') }
    $desktopUnknown = $false
    try { [void](Invoke-StartupDesktopProcessObservation -ProcessName 'Docker Desktop Synthetic' -ExpectedPath 'C:\synthetic\Docker Desktop.exe' -GetProcessBoundary $desktopUnknownBoundary) } catch { $desktopUnknown = $true }
    Assert-Adapter $desktopUnknown 'RV03-POSITIVE-02 process access denial is not normalized to absence'

    $state = New-RawAdapterState $commandManifest
    $desktopUnknownSystemBoundary = New-RawSystemBoundary $state
    $unknownBaseNative = $desktopUnknownSystemBoundary.InvokeNative
    $script:DesktopUnknownStarts = 0
    $desktopUnknownSystemBoundary.InvokeNative = {
        param($FilePath, $Arguments, $Timeout, $MaximumOutput)
        if ((@($Arguments) -join ' ') -like '--context desktop-linux-test version*') { return [pscustomobject]@{ status = 'NONZERO_EXIT'; stdout = ''; stderr = ''; process_left_running = $false } }
        return & $unknownBaseNative $FilePath $Arguments $Timeout $MaximumOutput
    }.GetNewClosure()
    $desktopUnknownSystemBoundary.ObserveDesktop = {
        param($ProcessName, $ExpectedPath)
        return @(Invoke-StartupDesktopProcessObservation -ProcessName $ProcessName -ExpectedPath $ExpectedPath -GetProcessBoundary $desktopUnknownBoundary)
    }.GetNewClosure()
    $desktopUnknownSystemBoundary.StartDesktop = { param($ExpectedPath) $script:DesktopUnknownStarts++; return [pscustomobject]@{ status = 'ACCEPTED' } }
    Save-AdapterManifest $commandManifest
    $desktopUnknownAdapters = New-RealStartupAdapters -Manifest $commandManifest -SystemBoundary $desktopUnknownSystemBoundary
    $desktopUnknownResult = Invoke-NextStabilStartupPlan -ManifestPath $manifestPath -ExpectedRoot $testRoot -Adapters $desktopUnknownAdapters -AllowSyntheticRoot
    Assert-Adapter ($desktopUnknownResult.code -eq 'DOCKER_DESKTOP_STATE_UNKNOWN' -and $script:DesktopUnknownStarts -eq 0) 'RV03-POSITIVE-02 desktop access denial remains UNKNOWN and never starts Desktop'

    $incompleteCommandBoundary = New-HostCommandBoundary (New-CommandPipelineState $commandManifest)
    $incompleteCommandBoundary.PSObject.Properties.Remove('GetListeners')
    $incompleteCommandResult = Invoke-BoundedStartupHostOperation -Operation OBSERVE -Expected $public -TimeoutMilliseconds 100 -MaximumOutputCharacters 4096 -SyntheticCommandBoundary $incompleteCommandBoundary
    Assert-Adapter ($incompleteCommandResult.status -eq 'REFUSED') 'incomplete command-level fixture refuses before any real command fallback'

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
