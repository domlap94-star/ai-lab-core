[CmdletBinding()]
param(
    [switch]$DefinitionOnly,
    [string]$ManifestPath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$runtimeDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeHelper = Join-Path $runtimeDirectory "startup-runtime.ps1"
. $runtimeHelper

function ConvertFrom-StartupDockerMounts {
    param([AllowNull()][string]$Json)
    if ([string]::IsNullOrWhiteSpace($Json)) { return @() }
    $parsedItems = $Json | ConvertFrom-Json -ErrorAction Stop
    $result = New-Object System.Collections.Generic.List[object]
    foreach ($item in $parsedItems) {
        $type = [string](Get-StartupProperty -InputObject $item -Name 'Type')
        $parsed = [pscustomobject]@{
            source = if ($type -eq 'volume') { [string](Get-StartupProperty -InputObject $item -Name 'Name') } else { [string](Get-StartupProperty -InputObject $item -Name 'Source') }
            destination = [string](Get-StartupProperty -InputObject $item -Name 'Destination')
            type = $type
            read_only = -not [bool](Get-StartupProperty -InputObject $item -Name 'RW')
        }
        $result.Add($parsed)
    }
    return $result.ToArray()
}

function ConvertFrom-StartupDockerPorts {
    param([AllowNull()][string]$Json)
    if ([string]::IsNullOrWhiteSpace($Json) -or $Json -eq 'null') { return @() }
    $result = New-Object System.Collections.Generic.List[object]
    $ports = $Json | ConvertFrom-Json -ErrorAction Stop
    foreach ($property in $ports.PSObject.Properties) {
        $parts = $property.Name -split '/', 2
        foreach ($binding in @($property.Value)) {
            if ($null -eq $binding) { continue }
            $result.Add([pscustomobject]@{
                host_ip = [string](Get-StartupProperty -InputObject $binding -Name 'HostIp')
                host_port = [string](Get-StartupProperty -InputObject $binding -Name 'HostPort')
                container_port = [string]$parts[0]
                protocol = if ($parts.Count -gt 1) { [string]$parts[1] } else { 'tcp' }
            })
        }
    }
    return $result.ToArray()
}

function New-RealStartupAdapters {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)]$Manifest)

    $timeouts = Get-StartupProperty -InputObject $Manifest -Name 'timeouts'
    $commandTimeout = [int](Get-StartupProperty -InputObject $timeouts -Name 'native_command_ms')
    $outputLimit = [int](Get-StartupProperty -InputObject $timeouts -Name 'max_output_chars')
    $dockerDefinition = Get-StartupProperty -InputObject $Manifest -Name 'docker'
    $context = [string](Get-StartupProperty -InputObject $dockerDefinition -Name 'context')
    $tools = @{}
    foreach ($tool in @(Get-StartupProperty -InputObject $Manifest -Name 'external_tools')) { $tools[[string]$tool.name] = $tool }
    $dockerPath = [string](Get-StartupProperty -InputObject $tools['docker_cli'] -Name 'path')
    $desktopPath = [string](Get-StartupProperty -InputObject $tools['docker_desktop'] -Name 'path')

    $invokeDocker = {
        param([string[]]$Arguments)
        Invoke-BoundedNativeCommand -FilePath $dockerPath -ArgumentList $Arguments -TimeoutMilliseconds $commandTimeout -MaximumOutputCharacters $outputLimit
    }.GetNewClosure()

    $getEnvironment = {
        $contextResult = & $invokeDocker @('context', 'show')
        $endpointResult = & $invokeDocker @('context', 'inspect', $context, '--format', '{{.Endpoints.docker.Host}}')
        if ($contextResult.status -ne 'SUCCESS' -or $endpointResult.status -ne 'SUCCESS') { throw 'Docker context metadata could not be read within the approved deadline.' }
        [pscustomobject]@{
            context = $contextResult.stdout.Trim()
            endpoint = $endpointResult.stdout.Trim()
            docker_host_override = if ([string]::IsNullOrWhiteSpace($env:DOCKER_HOST)) { '' } else { 'SET' }
            docker_context_override = if ([string]::IsNullOrWhiteSpace($env:DOCKER_CONTEXT)) { '' } else { 'SET' }
        }
    }.GetNewClosure()

    $observeEngine = {
        $result = & $invokeDocker @('--context', $context, 'version', '--format', '{{.Server.Version}}')
        if ($result.status -ne 'SUCCESS') { return [pscustomobject]@{ status = 'UNAVAILABLE'; command_status = $result.status } }
        $version = ConvertFrom-StartupDockerVersionResponse $result.stdout
        if (-not $version.valid) { return [pscustomobject]@{ status = 'INVALID_FORMAT'; command_status = $version.code } }
        return [pscustomobject]@{ status = 'RESPONDING'; version = $version.version }
    }.GetNewClosure()

    $observeDesktop = {
        param($Definition)
        $name = [string](Get-StartupProperty -InputObject $Definition -Name 'process_name')
        $matches = @(Get-Process -Name $name -ErrorAction SilentlyContinue)
        return @($matches | ForEach-Object {
            $actualPath = ''
            $startTime = ''
            try { $actualPath = $_.MainModule.FileName } catch { }
            try { $startTime = $_.StartTime.ToUniversalTime().ToString('o') } catch { }
            [pscustomobject]@{
                pid = $_.Id
                start_time_utc = $startTime
                identity_valid = (-not [string]::IsNullOrWhiteSpace($actualPath) -and $actualPath.Equals($desktopPath, [System.StringComparison]::OrdinalIgnoreCase))
            }
        })
    }.GetNewClosure()

    $startDesktop = {
        param($Definition)
        try {
            $info = New-Object System.Diagnostics.ProcessStartInfo
            $info.FileName = $desktopPath
            $info.UseShellExecute = $true
            $process = [System.Diagnostics.Process]::Start($info)
            if ($null -eq $process) { return [pscustomobject]@{ status = 'START_FAILED' } }
            return [pscustomobject]@{ status = 'ACCEPTED'; pid = $process.Id }
        }
        catch { return [pscustomobject]@{ status = 'START_FAILED'; detail = ConvertTo-SafeStartupDiagnostic $_.Exception.Message } }
    }.GetNewClosure()

    $observeContainer = {
        param($Expected)
        $project = [string](Get-StartupProperty -InputObject $Expected -Name 'compose_project')
        $service = [string](Get-StartupProperty -InputObject $Expected -Name 'service')
        $ids = & $invokeDocker @('--context', $context, 'ps', '-aq', '--filter', ('label=com.docker.compose.project=' + $project), '--filter', ('label=com.docker.compose.service=' + $service))
        if ($ids.status -eq 'EMPTY_OUTPUT') { return @() }
        if ($ids.status -ne 'SUCCESS') { throw ('Docker container observation failed: ' + $ids.status) }
        $result = New-Object System.Collections.Generic.List[object]
        foreach ($id in @($ids.stdout -split '[\r\n]+' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })) {
            $format = '{{.Id}}|{{.Name}}|{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}|{{.Image}}|{{.State.Running}}|{{json .Mounts}}|{{json .NetworkSettings.Ports}}'
            $inspect = & $invokeDocker @('--context', $context, 'inspect', '--format', $format, $id.Trim())
            if ($inspect.status -ne 'SUCCESS') { throw ('Docker inspect failed: ' + $inspect.status) }
            $parts = $inspect.stdout.Trim() -split '\|', 8
            if ($parts.Count -ne 8) { throw 'Docker inspect returned an invalid format.' }
            $digests = & $invokeDocker @('--context', $context, 'image', 'inspect', '--format', '{{json .RepoDigests}}', $parts[4])
            if ($digests.status -ne 'SUCCESS') { throw ('Docker image identity failed: ' + $digests.status) }
            $parsedDigests = $digests.stdout | ConvertFrom-Json -ErrorAction Stop
            $repoDigests = @()
            foreach ($digest in $parsedDigests) { $repoDigests += [string]$digest }
            $approvedDigest = [string](Get-StartupProperty -InputObject $Expected -Name 'repo_digest')
            $matchedDigest = @($repoDigests | Where-Object { ([string]$_).EndsWith($approvedDigest, [System.StringComparison]::OrdinalIgnoreCase) } | Select-Object -First 1)
            $result.Add([pscustomobject]@{
                full_id = $parts[0]
                container_name = $parts[1].TrimStart('/')
                compose_project = $parts[2]
                service = $parts[3]
                image_id = $parts[4]
                repo_digest = if ($matchedDigest.Count -eq 1) { $approvedDigest } else { '' }
                running = [System.Convert]::ToBoolean($parts[5])
                mounts = @(ConvertFrom-StartupDockerMounts $parts[6])
                ports = @(ConvertFrom-StartupDockerPorts $parts[7])
            })
        }
        return $result.ToArray()
    }.GetNewClosure()

    $startContainer = {
        param($Name, $Timeout)
        $result = Invoke-BoundedNativeCommand -FilePath $dockerPath -ArgumentList @('--context', $context, 'start', $Name) -TimeoutMilliseconds $Timeout -MaximumOutputCharacters $outputLimit
        return [pscustomobject]@{ status = $result.status; process_left_running = $result.process_left_running }
    }.GetNewClosure()

    $observeHost = {
        param($Expected)
        $expectedExecutable = [string](Get-StartupProperty -InputObject $Expected -Name 'executable')
        $expectedArguments = @((Get-StartupProperty -InputObject $Expected -Name 'arguments') | ForEach-Object { [string]$_ })
        $expectedWorkingDirectory = [string](Get-StartupProperty -InputObject $Expected -Name 'working_directory')
        $taskName = [string](Get-StartupProperty -InputObject $Expected -Name 'task_name')
        $taskPath = [string](Get-StartupProperty -InputObject $Expected -Name 'task_path')
        $actualExecutable = $expectedExecutable
        $actualArguments = $expectedArguments
        $actualWorkingDirectory = $expectedWorkingDirectory
        if ((Get-StartupProperty -InputObject $Expected -Name 'launch_kind') -eq 'TASK') {
            $task = Get-ScheduledTask -TaskPath $taskPath -TaskName $taskName -ErrorAction SilentlyContinue
            if ($null -eq $task -or @($task.Actions).Count -ne 1) { return @() }
            $action = @($task.Actions)[0]
            $actualExecutable = [string]$action.Execute
            $actualWorkingDirectory = [string]$action.WorkingDirectory
            $expectedArgumentString = Join-WindowsNativeArguments -ArgumentList $expectedArguments
            $actualArguments = if ([string]$action.Arguments -ceq $expectedArgumentString) { $expectedArguments } else { @([string]$action.Arguments) }
        }
        $listenerPort = [int](Get-StartupProperty -InputObject $Expected -Name 'listener_port')
        $processName = [System.IO.Path]::GetFileNameWithoutExtension($actualExecutable)
        $expectedArgumentString = Join-WindowsNativeArguments -ArgumentList $expectedArguments
        $processes = @(Get-CimInstance Win32_Process -Filter ("Name='{0}.exe'" -f $processName.Replace("'", "''")) -ErrorAction SilentlyContinue | Where-Object {
            ([string]$_.ExecutablePath).Equals($actualExecutable, [System.StringComparison]::OrdinalIgnoreCase) -and
            ($expectedArguments.Count -eq 0 -or ([string]$_.CommandLine).TrimEnd().EndsWith($expectedArgumentString, [System.StringComparison]::Ordinal))
        })
        return @($processes | ForEach-Object {
            $pidValue = [int]$_.ProcessId
            $listener = @(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $listenerPort -OwningProcess $pidValue -ErrorAction SilentlyContinue).Count -eq 1
            [pscustomobject]@{
                name = [string](Get-StartupProperty -InputObject $Expected -Name 'name')
                launch_kind = [string](Get-StartupProperty -InputObject $Expected -Name 'launch_kind')
                task_name = $taskName
                task_path = $taskPath
                executable = $actualExecutable
                arguments = $actualArguments
                working_directory = $actualWorkingDirectory
                listener_host = '127.0.0.1'
                listener_port = $listenerPort
                listener_ready = $listener
                pid = $pidValue
                start_time_utc = if ($null -ne $_.CreationDate) { [System.Management.ManagementDateTimeConverter]::ToDateTime([string]$_.CreationDate).ToUniversalTime().ToString('o') } else { '' }
            }
        })
    }.GetNewClosure()

    $startHost = {
        param($Expected, $Timeout)
        $kind = [string](Get-StartupProperty -InputObject $Expected -Name 'launch_kind')
        try {
            if ($kind -eq 'TASK') {
                $taskName = [string](Get-StartupProperty -InputObject $Expected -Name 'task_name')
                $taskPath = [string](Get-StartupProperty -InputObject $Expected -Name 'task_path')
                $task = Get-ScheduledTask -TaskPath $taskPath -TaskName $taskName -ErrorAction Stop
                if (@($task.Actions).Count -ne 1) { return [pscustomobject]@{ status = 'IDENTITY_MISMATCH' } }
                $action = @($task.Actions)[0]
                $expectedArgumentString = Join-WindowsNativeArguments -ArgumentList @((Get-StartupProperty -InputObject $Expected -Name 'arguments') | ForEach-Object { [string]$_ })
                if (-not ([string]$action.Execute).Equals([string](Get-StartupProperty -InputObject $Expected -Name 'executable'), [System.StringComparison]::OrdinalIgnoreCase) -or
                    -not ([string]$action.WorkingDirectory).Equals([string](Get-StartupProperty -InputObject $Expected -Name 'working_directory'), [System.StringComparison]::OrdinalIgnoreCase) -or
                    -not ([string]$action.Arguments).Equals($expectedArgumentString, [System.StringComparison]::Ordinal)) {
                    return [pscustomobject]@{ status = 'IDENTITY_MISMATCH' }
                }
                Start-ScheduledTask -TaskPath $taskPath -TaskName $taskName -ErrorAction Stop
                return [pscustomobject]@{ status = 'SUCCESS' }
            }
            return [pscustomobject]@{ status = 'UNSUPPORTED_LAUNCH_KIND' }
        }
        catch { return [pscustomobject]@{ status = 'START_FAILED'; detail = ConvertTo-SafeStartupDiagnostic $_.Exception.Message } }
    }.GetNewClosure()

    $checkReadiness = {
        param($Definition)
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri ([string]$Definition.uri) -TimeoutSec ([Math]::Max(1, [Math]::Ceiling($commandTimeout / 1000.0))) -ErrorAction Stop
            return [pscustomobject]@{ status = [int]$response.StatusCode }
        }
        catch {
            if ($null -ne $_.Exception.Response) { return [pscustomobject]@{ status = [int]$_.Exception.Response.StatusCode.value__ } }
            return [pscustomobject]@{ status = 0 }
        }
    }.GetNewClosure()

    return [pscustomobject]@{
        GetDockerEnvironment = $getEnvironment
        ObserveEngine = $observeEngine
        ObserveDockerDesktopProcess = $observeDesktop
        StartDockerDesktop = $startDesktop
        ObserveContainer = $observeContainer
        StartExistingContainer = $startContainer
        ObserveHostService = $observeHost
        StartHostService = $startHost
        CheckReadiness = $checkReadiness
        Sleep = { param($Milliseconds) Start-Sleep -Milliseconds $Milliseconds }
    }
}

function New-StartupResult {
    param(
        [Parameter(Mandatory = $true)][string]$Code,
        [bool]$BaseReady = $false,
        [string]$SupervisorStatus = 'NOT_OBSERVED',
        [object[]]$Events = @(),
        [object[]]$Details = @()
    )
    return [pscustomobject][ordered]@{
        schema = 'NEXT_STABIL_STARTUP_RESULT_V1'
        code = $Code
        base_ready = $BaseReady
        supervisor_status = $SupervisorStatus
        ai_export_ready = $false
        all_ready = $false
        events = @($Events)
        details = @(ConvertTo-SafeStartupDiagnostic -Value ($Details -join ';'))
    }
}

function Test-StartupAdapterContract {
    param([Parameter(Mandatory = $true)]$Adapters)
    $missing = New-Object System.Collections.Generic.List[string]
    foreach ($name in @(
        'GetDockerEnvironment', 'ObserveEngine', 'ObserveDockerDesktopProcess',
        'StartDockerDesktop', 'ObserveContainer', 'StartExistingContainer',
        'ObserveHostService', 'StartHostService', 'CheckReadiness', 'Sleep'
    )) {
        $value = Get-StartupProperty -InputObject $Adapters -Name $name
        if (-not ($value -is [scriptblock])) { $missing.Add($name) }
    }
    return [pscustomobject]@{ valid = ($missing.Count -eq 0); missing = $missing.ToArray() }
}

function Test-StartupHostServiceIdentity {
    param([Parameter(Mandatory = $true)]$Expected, [Parameter(Mandatory = $true)]$Observed)
    $errors = New-Object System.Collections.Generic.List[string]
    foreach ($field in @('name', 'launch_kind', 'task_name', 'task_path', 'executable', 'working_directory', 'listener_host', 'listener_port')) {
        $left = [string](Get-StartupProperty -InputObject $Expected -Name $field)
        $right = [string](Get-StartupProperty -InputObject $Observed -Name $field)
        if (-not $left.Equals($right, [System.StringComparison]::OrdinalIgnoreCase)) { $errors.Add(('HOST_SERVICE_IDENTITY_MISMATCH:{0}' -f $field)) }
    }
    $expectedArguments = @((Get-StartupProperty -InputObject $Expected -Name 'arguments') | ForEach-Object { [string]$_ })
    $observedArguments = @((Get-StartupProperty -InputObject $Observed -Name 'arguments') | ForEach-Object { [string]$_ })
    if ($expectedArguments.Count -ne $observedArguments.Count) {
        $errors.Add('HOST_SERVICE_IDENTITY_MISMATCH:arguments')
    }
    else {
        for ($index = 0; $index -lt $expectedArguments.Count; $index++) {
            if (-not $expectedArguments[$index].Equals($observedArguments[$index], [System.StringComparison]::Ordinal)) {
                $errors.Add('HOST_SERVICE_IDENTITY_MISMATCH:arguments')
                break
            }
        }
    }
    return [pscustomobject]@{ valid = ($errors.Count -eq 0); errors = $errors.ToArray() }
}

function Wait-StartupEngine {
    param(
        [Parameter(Mandatory = $true)]$Adapters,
        [Parameter(Mandatory = $true)][int]$StageTimeoutMilliseconds,
        [Parameter(Mandatory = $true)][int]$PollMilliseconds
    )
    $deadline = (Get-MonotonicMilliseconds) + $StageTimeoutMilliseconds
    do {
        $observed = & $Adapters.ObserveEngine
        if ((Get-StartupProperty -InputObject $observed -Name 'status') -eq 'RESPONDING') { return $observed }
        $remaining = $deadline - (Get-MonotonicMilliseconds)
        if ($remaining -le 0) { break }
        & $Adapters.Sleep ([int][Math]::Min($PollMilliseconds, $remaining))
    } while ((Get-MonotonicMilliseconds) -lt $deadline)
    return [pscustomobject]@{ status = 'ENGINE_UNAVAILABLE' }
}

function Wait-StartupHostServiceReady {
    param(
        [Parameter(Mandatory = $true)]$Expected,
        [Parameter(Mandatory = $true)]$Adapters,
        [Parameter(Mandatory = $true)][int]$StageTimeoutMilliseconds,
        [Parameter(Mandatory = $true)][int]$PollMilliseconds
    )
    $deadline = (Get-MonotonicMilliseconds) + $StageTimeoutMilliseconds
    do {
        $matches = @(& $Adapters.ObserveHostService $Expected)
        if ($matches.Count -gt 1) { return [pscustomobject]@{ ready = $false; code = 'HOST_SERVICE_AMBIGUOUS' } }
        if ($matches.Count -eq 1) {
            $identity = Test-StartupHostServiceIdentity -Expected $Expected -Observed $matches[0]
            if (-not $identity.valid) { return [pscustomobject]@{ ready = $false; code = 'HOST_SERVICE_IDENTITY_MISMATCH'; detail = @($identity.errors) } }
            if ([bool](Get-StartupProperty -InputObject $matches[0] -Name 'listener_ready')) { return [pscustomobject]@{ ready = $true; code = 'READY'; observed = $matches[0] } }
        }
        $remaining = $deadline - (Get-MonotonicMilliseconds)
        if ($remaining -le 0) { break }
        & $Adapters.Sleep ([int][Math]::Min($PollMilliseconds, $remaining))
    } while ((Get-MonotonicMilliseconds) -lt $deadline)
    return [pscustomobject]@{ ready = $false; code = 'HOST_SERVICE_NOT_READY' }
}

function Invoke-NextStabilStartupPlan {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$ManifestPath,
        [Parameter(Mandatory = $true)][string]$ExpectedRoot,
        [Parameter(Mandatory = $true)]$Adapters,
        [switch]$AllowSyntheticRoot
    )

    $events = New-Object System.Collections.Generic.List[object]
    if (-not (Test-StartupPathWithinRoot -Root $ExpectedRoot -Candidate $ManifestPath)) {
        return New-StartupResult -Code 'MANIFEST_REFUSED' -Details @('MANIFEST_OUTSIDE_ROOT')
    }
    if ((Test-Path -LiteralPath $ManifestPath) -and (Test-StartupPathHasReparsePoint -Root $ExpectedRoot -Candidate $ManifestPath)) {
        return New-StartupResult -Code 'MANIFEST_REFUSED' -Details @('MANIFEST_REPARSE_POINT')
    }
    $read = Read-StartupSetManifest -ManifestPath $ManifestPath
    if (-not $read.success) { return New-StartupResult -Code $read.code -Details @($read.detail) }
    $validation = Test-StartupSetManifest -Manifest $read.manifest -ManifestPath $ManifestPath -ExpectedRoot $ExpectedRoot -AllowSyntheticRoot:$AllowSyntheticRoot
    if (-not $validation.valid) { return New-StartupResult -Code 'MANIFEST_REFUSED' -Details $validation.errors }
    $adapterContract = Test-StartupAdapterContract -Adapters $Adapters
    if (-not $adapterContract.valid) { return New-StartupResult -Code 'ADAPTER_CONTRACT_INVALID' -Details $adapterContract.missing }

    $lock = Enter-StartupMutex -Root $validation.normalized_root
    if (-not $lock.acquired) {
        Exit-StartupMutex -Lock $lock
        return New-StartupResult -Code 'START_ALREADY_IN_PROGRESS'
    }
    try {
        $manifest = $read.manifest
        $timeouts = Get-StartupProperty -InputObject $manifest -Name 'timeouts'
        $nativeTimeout = [int](Get-StartupProperty -InputObject $timeouts -Name 'native_command_ms')
        $engineTimeout = [int](Get-StartupProperty -InputObject $timeouts -Name 'engine_stage_ms')
        $serviceTimeout = [int](Get-StartupProperty -InputObject $timeouts -Name 'service_stage_ms')
        $poll = [int](Get-StartupProperty -InputObject $timeouts -Name 'poll_ms')

        $dockerDefinition = Get-StartupProperty -InputObject $manifest -Name 'docker'
        $environment = & $Adapters.GetDockerEnvironment
        if (-not [string]::IsNullOrWhiteSpace([string](Get-StartupProperty -InputObject $environment -Name 'docker_host_override')) -or
            -not [string]::IsNullOrWhiteSpace([string](Get-StartupProperty -InputObject $environment -Name 'docker_context_override'))) {
            return New-StartupResult -Code 'DOCKER_ENV_OVERRIDE_CONFLICT'
        }
        foreach ($field in @('context', 'endpoint')) {
            $expectedValue = [string](Get-StartupProperty -InputObject $dockerDefinition -Name $field)
            $observedValue = [string](Get-StartupProperty -InputObject $environment -Name $field)
            if (-not $expectedValue.Equals($observedValue, [System.StringComparison]::OrdinalIgnoreCase)) { return New-StartupResult -Code 'DOCKER_CONTEXT_MISMATCH' -Details @($field) }
        }

        $engine = & $Adapters.ObserveEngine
        if ((Get-StartupProperty -InputObject $engine -Name 'status') -ne 'RESPONDING') {
            $desktop = @(& $Adapters.ObserveDockerDesktopProcess $dockerDefinition)
            if ($desktop.Count -gt 1) { return New-StartupResult -Code 'DOCKER_DESKTOP_AMBIGUOUS' }
            if ($desktop.Count -eq 0) {
                $start = & $Adapters.StartDockerDesktop $dockerDefinition
                $events.Add([pscustomobject]@{ component = 'docker_desktop'; action = 'START_ONCE'; result = [string](Get-StartupProperty -InputObject $start -Name 'status') })
                if ((Get-StartupProperty -InputObject $start -Name 'status') -ne 'ACCEPTED') { return New-StartupResult -Code 'DOCKER_DESKTOP_START_FAILED' -Events $events }
            }
            else {
                if (-not [bool](Get-StartupProperty -InputObject $desktop[0] -Name 'identity_valid')) { return New-StartupResult -Code 'DOCKER_DESKTOP_IDENTITY_MISMATCH' }
                $events.Add([pscustomobject]@{ component = 'docker_desktop'; action = 'PRESERVE_EXISTING' })
            }
            $engine = Wait-StartupEngine -Adapters $Adapters -StageTimeoutMilliseconds $engineTimeout -PollMilliseconds $poll
        }
        if ((Get-StartupProperty -InputObject $engine -Name 'status') -ne 'RESPONDING') { return New-StartupResult -Code 'ENGINE_UNAVAILABLE' -Events $events }
        $events.Add([pscustomobject]@{ component = 'docker_engine'; action = 'OBSERVED_READY' })

        $expectedContainers = @(Get-StartupProperty -InputObject $manifest -Name 'containers')
        $containerPhase = Invoke-StartupExistingContainerPhase `
            -ExpectedContainers $expectedContainers `
            -Adapters $Adapters `
            -CommandTimeoutMilliseconds $nativeTimeout
        foreach ($event in @($containerPhase.events)) { $events.Add($event) }
        if (-not $containerPhase.success) {
            return New-StartupResult -Code $containerPhase.code -Events $events -Details @(
                (Get-StartupProperty -InputObject $containerPhase -Name 'component'),
                (Get-StartupProperty -InputObject $containerPhase -Name 'detail')
            )
        }

        $hostServices = @(Get-StartupProperty -InputObject $manifest -Name 'host_services')
        $supervisor = @($hostServices | Where-Object { (Get-StartupProperty -InputObject $_ -Name 'name') -eq 'supervisor' })[0]
        $supervisorObserved = @(& $Adapters.ObserveHostService $supervisor)
        if ($supervisorObserved.Count -gt 0) { return New-StartupResult -Code 'SUPERVISOR_POLICY_CONFLICT' -SupervisorStatus 'POLICY_CONFLICT' -Events $events }
        $events.Add([pscustomobject]@{ component = 'supervisor'; action = 'INTENTIONALLY_STOPPED' })

        foreach ($service in @($hostServices | Where-Object { (Get-StartupProperty -InputObject $_ -Name 'policy') -eq 'REQUIRED' })) {
            $name = [string](Get-StartupProperty -InputObject $service -Name 'name')
            $observed = @(& $Adapters.ObserveHostService $service)
            if ($observed.Count -gt 1) { return New-StartupResult -Code 'HOST_SERVICE_AMBIGUOUS' -SupervisorStatus 'INTENTIONALLY_STOPPED' -Events $events -Details @($name) }
            $needsStart = ($observed.Count -eq 0)
            if ($observed.Count -eq 1) {
                $identity = Test-StartupHostServiceIdentity -Expected $service -Observed $observed[0]
                if (-not $identity.valid) { return New-StartupResult -Code 'HOST_SERVICE_IDENTITY_MISMATCH' -SupervisorStatus 'INTENTIONALLY_STOPPED' -Events $events -Details @($name) }
                if ([bool](Get-StartupProperty -InputObject $observed[0] -Name 'listener_ready')) {
                    $events.Add([pscustomobject]@{ component = $name; action = 'PRESERVE_RUNNING' })
                    continue
                }
            }
            if ($needsStart) {
                $started = & $Adapters.StartHostService $service $nativeTimeout
                $events.Add([pscustomobject]@{ component = $name; action = 'START_ONCE'; result = [string](Get-StartupProperty -InputObject $started -Name 'status') })
                if ((Get-StartupProperty -InputObject $started -Name 'status') -ne 'SUCCESS') { return New-StartupResult -Code 'HOST_SERVICE_START_FAILED' -SupervisorStatus 'INTENTIONALLY_STOPPED' -Events $events -Details @($name) }
            }
            $ready = Wait-StartupHostServiceReady -Expected $service -Adapters $Adapters -StageTimeoutMilliseconds $serviceTimeout -PollMilliseconds $poll
            if (-not $ready.ready) { return New-StartupResult -Code $ready.code -SupervisorStatus 'INTENTIONALLY_STOPPED' -Events $events -Details @($name) }
        }

        foreach ($check in @(Get-StartupProperty -InputObject $manifest -Name 'readiness')) {
            $actual = & $Adapters.CheckReadiness $check
            $expectedCode = [int](Get-StartupProperty -InputObject $check -Name 'expected_status')
            if ([int](Get-StartupProperty -InputObject $actual -Name 'status') -ne $expectedCode) {
                return New-StartupResult -Code 'READINESS_FAILED' -SupervisorStatus 'INTENTIONALLY_STOPPED' -Events $events -Details @((Get-StartupProperty -InputObject $check -Name 'name'))
            }
        }
        return New-StartupResult -Code 'BASE_READY_LIMITED' -BaseReady $true -SupervisorStatus 'INTENTIONALLY_STOPPED' -Events $events
    }
    catch {
        return New-StartupResult -Code 'ADAPTER_FAILURE' -Events $events -Details @(
            ('{0} [stage line {1}]' -f $_.Exception.Message, $_.InvocationInfo.ScriptLineNumber)
        )
    }
    finally {
        Exit-StartupMutex -Lock $lock
    }
}

if (-not $DefinitionOnly) {
    $canonicalRuntimeDirectory = 'C:\ai-lab-core\operations\runtime'
    if (-not (Get-CanonicalStartupPath -Path $runtimeDirectory).Equals($canonicalRuntimeDirectory, [System.StringComparison]::OrdinalIgnoreCase) -or
        (Test-StartupPathHasReparsePoint -Root 'C:\ai-lab-core' -Candidate $runtimeDirectory)) {
        $result = New-StartupResult -Code 'RUNTIME_SOURCE_REFUSED' -Details @('The launcher is not installed under the canonical root.')
        $result | ConvertTo-Json -Depth 8
        exit 20
    }
    if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
        $result = New-StartupResult -Code 'MANIFEST_MISSING'
        $result | ConvertTo-Json -Depth 8
        exit 21
    }
    if (-not (Test-StartupPathWithinRoot -Root 'C:\ai-lab-core' -Candidate $ManifestPath) -or
        ((Test-Path -LiteralPath $ManifestPath) -and (Test-StartupPathHasReparsePoint -Root 'C:\ai-lab-core' -Candidate $ManifestPath))) {
        $result = New-StartupResult -Code 'MANIFEST_REFUSED' -Details @('Manifest path is outside the canonical root or traverses a reparse point.')
        $result | ConvertTo-Json -Depth 8
        exit 22
    }

    $read = Read-StartupSetManifest -ManifestPath $ManifestPath
    if (-not $read.success) {
        $result = New-StartupResult -Code $read.code -Details @($read.detail)
        $result | ConvertTo-Json -Depth 8
        exit 22
    }
    $preflight = Test-StartupSetManifest `
        -Manifest $read.manifest `
        -ManifestPath $ManifestPath `
        -ExpectedRoot 'C:\ai-lab-core'
    if (-not $preflight.valid) {
        $result = New-StartupResult -Code 'MANIFEST_REFUSED' -Details @($preflight.errors)
        $result | ConvertTo-Json -Depth 8
        exit 22
    }

    $adapters = New-RealStartupAdapters -Manifest $read.manifest
    $result = Invoke-NextStabilStartupPlan `
        -ManifestPath $ManifestPath `
        -ExpectedRoot 'C:\ai-lab-core' `
        -Adapters $adapters
    $result | ConvertTo-Json -Depth 8
    if ($result.code -eq 'BASE_READY_LIMITED') { exit 0 }
    exit 22
}
