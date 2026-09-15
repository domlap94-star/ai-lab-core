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

function Invoke-BoundedStartupHostOperation {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][ValidateSet('OBSERVE', 'START')][string]$Operation,
        [Parameter(Mandatory = $true)]$Expected,
        [Parameter(Mandatory = $true)][ValidateRange(25, 300000)][int]$TimeoutMilliseconds,
        [Parameter(Mandatory = $true)][ValidateRange(1024, 1048576)][int]$MaximumOutputCharacters,
        [AllowNull()]$SyntheticFixture
    )

    # This is a closed launcher boundary, not a command runner. The worker accepts
    # only the two fixed operations above and structured identity data selected
    # from an already validated manifest by New-RealStartupAdapters. The optional
    # fixture is an in-process test seam and is never populated from JSON.
    if ([string](Get-StartupProperty -InputObject $Expected -Name 'launch_kind') -cne 'TASK') {
        return [pscustomobject]@{ status = 'REFUSED'; result = $null; duration_ms = 0; job_left_running = $false; operation_may_have_started = $false }
    }
    foreach ($required in @('name', 'task_name', 'task_path', 'executable', 'working_directory', 'listener_port')) {
        if ([string]::IsNullOrWhiteSpace([string](Get-StartupProperty -InputObject $Expected -Name $required))) {
            return [pscustomobject]@{ status = 'REFUSED'; result = $null; duration_ms = 0; job_left_running = $false; operation_may_have_started = $false }
        }
    }

    $expectedArguments = @((Get-StartupProperty -InputObject $Expected -Name 'arguments') | ForEach-Object { [string]$_ })
    $expectedData = [pscustomobject]@{
        name = [string](Get-StartupProperty -InputObject $Expected -Name 'name')
        task_name = [string](Get-StartupProperty -InputObject $Expected -Name 'task_name')
        task_path = [string](Get-StartupProperty -InputObject $Expected -Name 'task_path')
        executable = [string](Get-StartupProperty -InputObject $Expected -Name 'executable')
        argument_string = Join-WindowsNativeArguments -ArgumentList $expectedArguments
        working_directory = [string](Get-StartupProperty -InputObject $Expected -Name 'working_directory')
        process_name = [System.IO.Path]::GetFileName([string](Get-StartupProperty -InputObject $Expected -Name 'executable'))
        listener_port = [int](Get-StartupProperty -InputObject $Expected -Name 'listener_port')
    }

    $worker = {
        param($SelectedOperation, $SelectedExpected, $TestFixture)
        $ErrorActionPreference = 'Stop'
        Set-StrictMode -Version 2.0

        if ($null -ne $TestFixture) {
            $delay = 0
            if ($null -ne $TestFixture.PSObject.Properties['delay_ms']) { $delay = [int]$TestFixture.delay_ms }
            if ($delay -gt 0) { Start-Sleep -Milliseconds $delay }
            if ($null -eq $TestFixture.PSObject.Properties['result']) { throw 'SYNTHETIC_FIXTURE_RESULT_MISSING' }
            return $TestFixture.result
        }

        $task = Get-ScheduledTask -TaskPath $SelectedExpected.task_path -TaskName $SelectedExpected.task_name -ErrorAction Stop
        if ($null -eq $task -or @($task.Actions).Count -ne 1) {
            return [pscustomobject]@{ status = 'IDENTITY_MISMATCH'; task = $null; processes = @(); listeners = @() }
        }
        $action = @($task.Actions)[0]
        $taskData = [pscustomobject]@{
            execute = [string]$action.Execute
            arguments = [string]$action.Arguments
            working_directory = [string]$action.WorkingDirectory
        }
        $taskMatches =
            $taskData.execute.Equals([string]$SelectedExpected.executable, [System.StringComparison]::OrdinalIgnoreCase) -and
            $taskData.arguments.Equals([string]$SelectedExpected.argument_string, [System.StringComparison]::Ordinal) -and
            $taskData.working_directory.Equals([string]$SelectedExpected.working_directory, [System.StringComparison]::OrdinalIgnoreCase)
        if (-not $taskMatches) {
            return [pscustomobject]@{ status = 'IDENTITY_MISMATCH'; task = $taskData; processes = @(); listeners = @() }
        }

        if ($SelectedOperation -ceq 'START') {
            Start-ScheduledTask -TaskPath $SelectedExpected.task_path -TaskName $SelectedExpected.task_name -ErrorAction Stop
            return [pscustomobject]@{ status = 'SUCCESS'; task = $taskData; processes = @(); listeners = @() }
        }

        $escapedName = ([string]$SelectedExpected.process_name).Replace("'", "''")
        $processes = @(Get-CimInstance Win32_Process -Filter ("Name='{0}'" -f $escapedName) -ErrorAction Stop | ForEach-Object {
            [pscustomobject]@{
                process_id = [int]$_.ProcessId
                executable_path = [string]$_.ExecutablePath
                command_line = [string]$_.CommandLine
                creation_date = $_.CreationDate
            }
        })
        $listeners = @(Get-NetTCPConnection -State Listen -LocalPort ([int]$SelectedExpected.listener_port) -ErrorAction Stop | ForEach-Object {
            [pscustomobject]@{
                local_address = [string]$_.LocalAddress
                local_port = [int]$_.LocalPort
                owning_process = [int]$_.OwningProcess
            }
        })
        return [pscustomobject]@{ status = 'SUCCESS'; task = $taskData; processes = $processes; listeners = $listeners }
    }

    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $powerShell = [System.Management.Automation.PowerShell]::Create()
    $async = $null
    $pipelineSettled = $false
    try {
        [void]$powerShell.AddScript($worker.ToString())
        [void]$powerShell.AddArgument($Operation)
        [void]$powerShell.AddArgument($expectedData)
        [void]$powerShell.AddArgument($SyntheticFixture)
        $async = $powerShell.BeginInvoke()

        $cleanupReserve = [Math]::Min(250, [Math]::Max(25, [int][Math]::Floor($TimeoutMilliseconds / 4.0)))
        $executionBudget = [Math]::Max(0, $TimeoutMilliseconds - [int]$watch.ElapsedMilliseconds - $cleanupReserve)
        $completed = if ($executionBudget -gt 0) { $async.AsyncWaitHandle.WaitOne($executionBudget) } else { $async.IsCompleted }
        if ($completed) {
            $items = @($powerShell.EndInvoke($async))
            $pipelineSettled = $true
            if ($watch.ElapsedMilliseconds -ge $TimeoutMilliseconds) {
                $watch.Stop()
                return [pscustomobject]@{ status = 'TIMEOUT'; result = $null; duration_ms = $watch.ElapsedMilliseconds; job_left_running = $false; operation_may_have_started = ($Operation -ceq 'START') }
            }
            if ($powerShell.HadErrors -or $items.Count -ne 1) {
                $watch.Stop()
                return [pscustomobject]@{ status = 'ERROR'; result = $null; duration_ms = $watch.ElapsedMilliseconds; job_left_running = $false; operation_may_have_started = ($Operation -ceq 'START') }
            }
            $serialized = $items[0] | ConvertTo-Json -Depth 12 -Compress
            if ($watch.ElapsedMilliseconds -ge $TimeoutMilliseconds) {
                $watch.Stop()
                return [pscustomobject]@{ status = 'TIMEOUT'; result = $null; duration_ms = $watch.ElapsedMilliseconds; job_left_running = $false; operation_may_have_started = ($Operation -ceq 'START') }
            }
            if ($serialized.Length -gt $MaximumOutputCharacters) {
                $watch.Stop()
                return [pscustomobject]@{ status = 'OUTPUT_LIMIT'; result = $null; duration_ms = $watch.ElapsedMilliseconds; job_left_running = $false; operation_may_have_started = ($Operation -ceq 'START') }
            }
            $watch.Stop()
            return [pscustomobject]@{ status = 'SUCCESS'; result = $items[0]; duration_ms = $watch.ElapsedMilliseconds; job_left_running = $false; operation_may_have_started = $false }
        }

        $remaining = [Math]::Max(0, $TimeoutMilliseconds - [int]$watch.ElapsedMilliseconds)
        $stopAsync = $null
        try {
            $stopAsync = $powerShell.BeginStop($null, $null)
            if ($remaining -gt 0 -and $stopAsync.AsyncWaitHandle.WaitOne($remaining)) {
                $powerShell.EndStop($stopAsync)
                $pipelineSettled = $true
            }
        }
        catch {
        }
        finally {
            if ($null -ne $stopAsync) { try { $stopAsync.AsyncWaitHandle.Close() } catch { } }
        }
        $watch.Stop()
        return [pscustomobject]@{
            status = 'TIMEOUT'
            result = $null
            duration_ms = $watch.ElapsedMilliseconds
            job_left_running = (-not $pipelineSettled)
            operation_may_have_started = ($Operation -ceq 'START')
        }
    }
    catch {
        $watch.Stop()
        return [pscustomobject]@{
            status = 'ERROR'
            result = $null
            duration_ms = $watch.ElapsedMilliseconds
            job_left_running = (-not $pipelineSettled)
            operation_may_have_started = ($Operation -ceq 'START')
            detail = ConvertTo-SafeStartupDiagnostic -Value $_.Exception.Message
        }
    }
    finally {
        if ($null -ne $async) { try { $async.AsyncWaitHandle.Close() } catch { } }
        if ($pipelineSettled) { $powerShell.Dispose() }
    }
}

function Test-RealStartupBoundaryContract {
    param([Parameter(Mandatory = $true)]$SystemBoundary)

    $missing = New-Object System.Collections.Generic.List[string]
    foreach ($name in @('InvokeNative', 'GetEnvironmentState', 'ObserveDesktop', 'StartDesktop', 'InvokeHostOperation', 'InvokeHttp', 'Sleep')) {
        if (-not ((Get-StartupProperty -InputObject $SystemBoundary -Name $name) -is [scriptblock])) { $missing.Add($name) }
    }
    return [pscustomobject]@{ valid = ($missing.Count -eq 0); missing = $missing.ToArray() }
}

function New-RealStartupAdapters {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [AllowNull()]$SystemBoundary
    )

    $timeouts = Get-StartupProperty -InputObject $Manifest -Name 'timeouts'
    $commandTimeout = [int](Get-StartupProperty -InputObject $timeouts -Name 'native_command_ms')
    $outputLimit = [int](Get-StartupProperty -InputObject $timeouts -Name 'max_output_chars')
    $dockerDefinition = Get-StartupProperty -InputObject $Manifest -Name 'docker'
    $context = [string](Get-StartupProperty -InputObject $dockerDefinition -Name 'context')
    $tools = @{}
    foreach ($tool in @(Get-StartupProperty -InputObject $Manifest -Name 'external_tools')) { $tools[[string]$tool.name] = $tool }
    $dockerPath = [string](Get-StartupProperty -InputObject $tools['docker_cli'] -Name 'path')
    $desktopPath = [string](Get-StartupProperty -InputObject $tools['docker_desktop'] -Name 'path')

    if ($null -eq $SystemBoundary) {
        $nativeBoundary = {
            param($FilePath, $Arguments, $Timeout, $MaximumOutput)
            Invoke-BoundedNativeCommand -FilePath $FilePath -ArgumentList $Arguments -TimeoutMilliseconds $Timeout -MaximumOutputCharacters $MaximumOutput
        }
        $environmentBoundary = {
            [pscustomobject]@{
                docker_host_override = if ([string]::IsNullOrWhiteSpace($env:DOCKER_HOST)) { '' } else { 'SET' }
                docker_context_override = if ([string]::IsNullOrWhiteSpace($env:DOCKER_CONTEXT)) { '' } else { 'SET' }
            }
        }
        $observeDesktopBoundary = {
            param($ProcessName, $ExpectedPath)
            $matches = @(Get-Process -Name $ProcessName -ErrorAction Stop)
            return @($matches | ForEach-Object {
                $actualPath = ''
                $startTime = ''
                try { $actualPath = $_.MainModule.FileName } catch { }
                try { $startTime = $_.StartTime.ToUniversalTime().ToString('o') } catch { }
                [pscustomobject]@{
                    pid = $_.Id
                    start_time_utc = $startTime
                    identity_valid = (-not [string]::IsNullOrWhiteSpace($actualPath) -and $actualPath.Equals($ExpectedPath, [System.StringComparison]::OrdinalIgnoreCase))
                }
            })
        }
        $startDesktopBoundary = {
            param($ExpectedPath)
            $info = New-Object System.Diagnostics.ProcessStartInfo
            $info.FileName = $ExpectedPath
            $info.UseShellExecute = $true
            $process = [System.Diagnostics.Process]::Start($info)
            if ($null -eq $process) { return [pscustomobject]@{ status = 'START_FAILED' } }
            return [pscustomobject]@{ status = 'ACCEPTED'; pid = $process.Id }
        }
        $hostBoundary = {
            param($Operation, $Expected, $Timeout, $MaximumOutput)
            Invoke-BoundedStartupHostOperation -Operation $Operation -Expected $Expected -TimeoutMilliseconds $Timeout -MaximumOutputCharacters $MaximumOutput
        }
        $httpBoundary = {
            param($Uri, $Timeout)
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec ([Math]::Max(1, [Math]::Ceiling($Timeout / 1000.0))) -ErrorAction Stop
            [pscustomobject]@{ status = [int]$response.StatusCode }
        }
        $SystemBoundary = [pscustomobject]@{
            InvokeNative = $nativeBoundary
            GetEnvironmentState = $environmentBoundary
            ObserveDesktop = $observeDesktopBoundary
            StartDesktop = $startDesktopBoundary
            InvokeHostOperation = $hostBoundary
            InvokeHttp = $httpBoundary
            Sleep = { param($Milliseconds) Start-Sleep -Milliseconds $Milliseconds }
        }
    }
    $boundaryContract = Test-RealStartupBoundaryContract -SystemBoundary $SystemBoundary
    if (-not $boundaryContract.valid) {
        throw ('SYSTEM_BOUNDARY_CONTRACT_INVALID:' + (@($boundaryContract.missing) -join ','))
    }

    $invokeDocker = {
        param([string[]]$Arguments)
        & $SystemBoundary.InvokeNative $dockerPath $Arguments $commandTimeout $outputLimit
    }.GetNewClosure()

    $getEnvironment = {
        $contextResult = & $invokeDocker @('context', 'show')
        $endpointResult = & $invokeDocker @('context', 'inspect', $context, '--format', '{{.Endpoints.docker.Host}}')
        if ($contextResult.status -ne 'SUCCESS' -or $endpointResult.status -ne 'SUCCESS') { throw 'Docker context metadata could not be read within the approved deadline.' }
        $overrides = & $SystemBoundary.GetEnvironmentState
        [pscustomobject]@{
            context = $contextResult.stdout.Trim()
            endpoint = $endpointResult.stdout.Trim()
            docker_host_override = [string](Get-StartupProperty -InputObject $overrides -Name 'docker_host_override')
            docker_context_override = [string](Get-StartupProperty -InputObject $overrides -Name 'docker_context_override')
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
        try { return @(& $SystemBoundary.ObserveDesktop $name $desktopPath) }
        catch { return @([pscustomobject]@{ observation_status = 'UNKNOWN'; detail = ConvertTo-SafeStartupDiagnostic $_.Exception.Message }) }
    }.GetNewClosure()

    $startDesktop = {
        param($Definition)
        try {
            return & $SystemBoundary.StartDesktop $desktopPath
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
            $format = '{{.Id}}|{{.Name}}|{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}|{{.Image}}|{{.State.Running}}|{{json .Mounts}}|{{json .HostConfig.PortBindings}}|{{json .NetworkSettings.Ports}}'
            $inspect = & $invokeDocker @('--context', $context, 'inspect', '--format', $format, $id.Trim())
            if ($inspect.status -ne 'SUCCESS') { throw ('Docker inspect failed: ' + $inspect.status) }
            $parts = $inspect.stdout.Trim() -split '\|', 9
            if ($parts.Count -ne 9) { throw 'Docker inspect returned an invalid format.' }
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
                configured_ports = @(ConvertFrom-StartupDockerPorts $parts[7])
                active_ports = @(ConvertFrom-StartupDockerPorts $parts[8])
            })
        }
        return $result.ToArray()
    }.GetNewClosure()

    $startContainer = {
        param($Name, $Timeout)
        $result = & $SystemBoundary.InvokeNative $dockerPath @('--context', $context, 'start', $Name) $Timeout $outputLimit
        return [pscustomobject]@{ status = $result.status; process_left_running = $result.process_left_running }
    }.GetNewClosure()

    $observeHost = {
        param($Expected, $Timeout)
        $operation = & $SystemBoundary.InvokeHostOperation 'OBSERVE' $Expected $Timeout $outputLimit
        if ((Get-StartupProperty -InputObject $operation -Name 'status') -ne 'SUCCESS') {
            return [pscustomobject]@{ observation_status = 'UNKNOWN'; matches = @(); detail = [string](Get-StartupProperty -InputObject $operation -Name 'status') }
        }
        $payload = Get-StartupProperty -InputObject $operation -Name 'result'
        if ((Get-StartupProperty -InputObject $payload -Name 'status') -ne 'SUCCESS') {
            return [pscustomobject]@{ observation_status = 'CONFLICT'; matches = @(); detail = [string](Get-StartupProperty -InputObject $payload -Name 'status') }
        }

        $expectedExecutable = [string](Get-StartupProperty -InputObject $Expected -Name 'executable')
        $expectedArguments = @((Get-StartupProperty -InputObject $Expected -Name 'arguments') | ForEach-Object { [string]$_ })
        $expectedArgumentString = Join-WindowsNativeArguments -ArgumentList $expectedArguments
        $expectedCommandLine = Join-WindowsNativeArguments -ArgumentList (@($expectedExecutable) + $expectedArguments)
        $expectedWorkingDirectory = [string](Get-StartupProperty -InputObject $Expected -Name 'working_directory')
        $task = Get-StartupProperty -InputObject $payload -Name 'task'
        if ($null -eq $task -or
            -not ([string](Get-StartupProperty -InputObject $task -Name 'execute')).Equals($expectedExecutable, [System.StringComparison]::OrdinalIgnoreCase) -or
            -not ([string](Get-StartupProperty -InputObject $task -Name 'arguments')).Equals($expectedArgumentString, [System.StringComparison]::Ordinal) -or
            -not ([string](Get-StartupProperty -InputObject $task -Name 'working_directory')).Equals($expectedWorkingDirectory, [System.StringComparison]::OrdinalIgnoreCase)) {
            return [pscustomobject]@{ observation_status = 'CONFLICT'; matches = @(); detail = 'TASK_IDENTITY_MISMATCH' }
        }

        $processes = @((Get-StartupProperty -InputObject $payload -Name 'processes'))
        $listeners = @((Get-StartupProperty -InputObject $payload -Name 'listeners'))
        $exactProcesses = New-Object System.Collections.Generic.List[object]
        $conflictingProcess = $false
        foreach ($process in $processes) {
            $actualExecutable = [string](Get-StartupProperty -InputObject $process -Name 'executable_path')
            $actualCommandLine = ([string](Get-StartupProperty -InputObject $process -Name 'command_line')).Trim()
            if ($actualExecutable.Equals($expectedExecutable, [System.StringComparison]::OrdinalIgnoreCase)) {
                if (-not $actualCommandLine.Equals($expectedCommandLine, [System.StringComparison]::Ordinal)) {
                    $conflictingProcess = $true
                    continue
                }
                $convertedDate = ConvertTo-StartupUtcTimestamp (Get-StartupProperty -InputObject $process -Name 'creation_date')
                if (-not $convertedDate.valid) {
                    return [pscustomobject]@{ observation_status = 'UNKNOWN'; matches = @(); detail = 'PROCESS_CREATION_DATE_UNKNOWN' }
                }
                $exactProcesses.Add([pscustomobject]@{
                    source = $process
                    pid = [int](Get-StartupProperty -InputObject $process -Name 'process_id')
                    start_time_utc = $convertedDate.value
                })
            }
        }

        if ($exactProcesses.Count -gt 1) {
            return [pscustomobject]@{ observation_status = 'AMBIGUOUS'; matches = @(); detail = 'MULTIPLE_MATCHING_PROCESSES' }
        }
        $expectedHost = [string](Get-StartupProperty -InputObject $Expected -Name 'listener_host')
        $expectedPort = [int](Get-StartupProperty -InputObject $Expected -Name 'listener_port')
        $expectedPid = if ($exactProcesses.Count -eq 1) { [int]$exactProcesses[0].pid } else { -1 }
        $expectedListenerCount = 0
        $foreignListener = $false
        foreach ($listener in $listeners) {
            $listenerAddress = [string](Get-StartupProperty -InputObject $listener -Name 'local_address')
            $listenerPort = [int](Get-StartupProperty -InputObject $listener -Name 'local_port')
            $listenerPid = [int](Get-StartupProperty -InputObject $listener -Name 'owning_process')
            if ($listenerPort -ne $expectedPort) { continue }
            if ($listenerPid -eq $expectedPid -and $listenerAddress.Equals($expectedHost, [System.StringComparison]::OrdinalIgnoreCase)) {
                $expectedListenerCount++
            }
            else {
                $foreignListener = $true
            }
        }
        if ($foreignListener -or $conflictingProcess) {
            return [pscustomobject]@{ observation_status = 'CONFLICT'; matches = @(); detail = if ($foreignListener) { 'PORT_OWNERSHIP_CONFLICT' } else { 'PROCESS_ARGUMENT_CONFLICT' } }
        }
        if ($exactProcesses.Count -eq 0) {
            return [pscustomobject]@{ observation_status = 'ABSENT'; matches = @(); detail = '' }
        }

        $match = [pscustomobject]@{
            name = [string](Get-StartupProperty -InputObject $Expected -Name 'name')
            launch_kind = [string](Get-StartupProperty -InputObject $Expected -Name 'launch_kind')
            task_name = [string](Get-StartupProperty -InputObject $Expected -Name 'task_name')
            task_path = [string](Get-StartupProperty -InputObject $Expected -Name 'task_path')
            executable = $expectedExecutable
            arguments = $expectedArguments
            working_directory = $expectedWorkingDirectory
            working_directory_source = 'TASK_CONFIGURATION'
            listener_host = $expectedHost
            listener_port = $expectedPort
            listener_ready = ($expectedListenerCount -eq 1)
            pid = $expectedPid
            start_time_utc = $exactProcesses[0].start_time_utc
        }
        return [pscustomobject]@{ observation_status = 'PRESENT'; matches = @($match); detail = '' }
    }.GetNewClosure()

    $startHost = {
        param($Expected, $Timeout)
        $operation = & $SystemBoundary.InvokeHostOperation 'START' $Expected $Timeout $outputLimit
        $operationStatus = [string](Get-StartupProperty -InputObject $operation -Name 'status')
        if ($operationStatus -eq 'TIMEOUT') {
            return [pscustomobject]@{ status = 'TIMEOUT'; operation_may_have_started = $true; job_left_running = [bool](Get-StartupProperty -InputObject $operation -Name 'job_left_running') }
        }
        if ($operationStatus -ne 'SUCCESS') { return [pscustomobject]@{ status = 'START_FAILED' } }
        $payload = Get-StartupProperty -InputObject $operation -Name 'result'
        return [pscustomobject]@{ status = [string](Get-StartupProperty -InputObject $payload -Name 'status'); operation_may_have_started = $false; job_left_running = $false }
    }.GetNewClosure()

    $checkReadiness = {
        param($Definition)
        try {
            return & $SystemBoundary.InvokeHttp ([string]$Definition.uri) $commandTimeout
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
        Sleep = $SystemBoundary.Sleep
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
        [Parameter(Mandatory = $true)][int64]$Deadline,
        [Parameter(Mandatory = $true)][int]$MaximumObservationMilliseconds,
        [Parameter(Mandatory = $true)][int]$PollMilliseconds
    )
    do {
        $remaining = Get-StartupRemainingMilliseconds -Deadline $Deadline -MaximumMilliseconds $MaximumObservationMilliseconds
        if ($remaining -le 0) { break }
        $observation = ConvertTo-StartupHostObservation (& $Adapters.ObserveHostService $Expected $remaining)
        if ($observation.status -eq 'UNKNOWN') { return [pscustomobject]@{ ready = $false; code = 'HOST_SERVICE_OBSERVATION_UNKNOWN'; detail = $observation.detail } }
        if ($observation.status -eq 'CONFLICT') { return [pscustomobject]@{ ready = $false; code = 'HOST_SERVICE_IDENTITY_MISMATCH'; detail = $observation.detail } }
        if ($observation.status -eq 'AMBIGUOUS') { return [pscustomobject]@{ ready = $false; code = 'HOST_SERVICE_AMBIGUOUS' } }
        if ($observation.status -eq 'PRESENT') {
            $identity = Test-StartupHostServiceIdentity -Expected $Expected -Observed $observation.matches[0]
            if (-not $identity.valid) { return [pscustomobject]@{ ready = $false; code = 'HOST_SERVICE_IDENTITY_MISMATCH'; detail = @($identity.errors) } }
            if ([bool](Get-StartupProperty -InputObject $observation.matches[0] -Name 'listener_ready')) { return [pscustomobject]@{ ready = $true; code = 'READY'; observed = $observation.matches[0] } }
        }
        $remaining = $Deadline - (Get-MonotonicMilliseconds)
        if ($remaining -le 0) { break }
        & $Adapters.Sleep ([int][Math]::Min($PollMilliseconds, $remaining))
    } while ((Get-MonotonicMilliseconds) -lt $Deadline)
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
        $supervisorObservation = ConvertTo-StartupHostObservation (& $Adapters.ObserveHostService $supervisor $nativeTimeout)
        if ($supervisorObservation.status -eq 'PRESENT' -or $supervisorObservation.status -eq 'CONFLICT' -or $supervisorObservation.status -eq 'AMBIGUOUS') {
            return New-StartupResult -Code 'SUPERVISOR_POLICY_CONFLICT' -SupervisorStatus 'POLICY_CONFLICT' -Events $events
        }
        if ($supervisorObservation.status -eq 'UNKNOWN') {
            return New-StartupResult -Code 'SUPERVISOR_STATE_UNKNOWN' -SupervisorStatus 'UNKNOWN' -Events $events
        }
        $events.Add([pscustomobject]@{ component = 'supervisor'; action = 'INTENTIONALLY_STOPPED' })

        foreach ($service in @($hostServices | Where-Object { (Get-StartupProperty -InputObject $_ -Name 'policy') -eq 'REQUIRED' })) {
            $name = [string](Get-StartupProperty -InputObject $service -Name 'name')
            $serviceDeadline = (Get-MonotonicMilliseconds) + $serviceTimeout
            $firstBudget = Get-StartupRemainingMilliseconds -Deadline $serviceDeadline -MaximumMilliseconds $nativeTimeout
            if ($firstBudget -le 0) { return New-StartupResult -Code 'HOST_SERVICE_OBSERVATION_UNKNOWN' -SupervisorStatus 'INTENTIONALLY_STOPPED' -Events $events -Details @($name) }
            $observation = ConvertTo-StartupHostObservation (& $Adapters.ObserveHostService $service $firstBudget)
            if ($observation.status -eq 'UNKNOWN') { return New-StartupResult -Code 'HOST_SERVICE_OBSERVATION_UNKNOWN' -SupervisorStatus 'INTENTIONALLY_STOPPED' -Events $events -Details @($name, $observation.detail) }
            if ($observation.status -eq 'AMBIGUOUS') { return New-StartupResult -Code 'HOST_SERVICE_AMBIGUOUS' -SupervisorStatus 'INTENTIONALLY_STOPPED' -Events $events -Details @($name) }
            if ($observation.status -eq 'CONFLICT') { return New-StartupResult -Code 'HOST_SERVICE_IDENTITY_MISMATCH' -SupervisorStatus 'INTENTIONALLY_STOPPED' -Events $events -Details @($name, $observation.detail) }
            $needsStart = ($observation.status -eq 'ABSENT')
            if ($observation.status -eq 'PRESENT') {
                $identity = Test-StartupHostServiceIdentity -Expected $service -Observed $observation.matches[0]
                if (-not $identity.valid) { return New-StartupResult -Code 'HOST_SERVICE_IDENTITY_MISMATCH' -SupervisorStatus 'INTENTIONALLY_STOPPED' -Events $events -Details @($name) }
                if ([bool](Get-StartupProperty -InputObject $observation.matches[0] -Name 'listener_ready')) {
                    $events.Add([pscustomobject]@{ component = $name; action = 'PRESERVE_RUNNING' })
                    continue
                }
            }
            if ($needsStart) {
                $startBudget = Get-StartupRemainingMilliseconds -Deadline $serviceDeadline -MaximumMilliseconds $nativeTimeout
                if ($startBudget -le 0) { return New-StartupResult -Code 'HOST_SERVICE_START_UNKNOWN' -SupervisorStatus 'INTENTIONALLY_STOPPED' -Events $events -Details @($name) }
                $started = & $Adapters.StartHostService $service $startBudget
                $events.Add([pscustomobject]@{ component = $name; action = 'START_ONCE'; result = [string](Get-StartupProperty -InputObject $started -Name 'status') })
                if ((Get-StartupProperty -InputObject $started -Name 'status') -eq 'TIMEOUT') { return New-StartupResult -Code 'HOST_SERVICE_START_UNKNOWN' -SupervisorStatus 'INTENTIONALLY_STOPPED' -Events $events -Details @($name) }
                if ((Get-StartupProperty -InputObject $started -Name 'status') -ne 'SUCCESS') { return New-StartupResult -Code 'HOST_SERVICE_START_FAILED' -SupervisorStatus 'INTENTIONALLY_STOPPED' -Events $events -Details @($name) }
            }
            $ready = Wait-StartupHostServiceReady -Expected $service -Adapters $Adapters -Deadline $serviceDeadline -MaximumObservationMilliseconds $nativeTimeout -PollMilliseconds $poll
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
