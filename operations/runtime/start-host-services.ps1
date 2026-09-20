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
        if ($null -eq $item) { continue }
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

function Test-StartupDockerContainerNotFoundResult {
    param([Parameter(Mandatory = $true)]$Result)

    if ([string](Get-StartupProperty -InputObject $Result -Name 'status') -notin @('ERROR', 'NONZERO_EXIT')) { return $false }
    if ([bool](Get-StartupProperty -InputObject $Result -Name 'stderr_truncated')) { return $false }
    $stderr = [string](Get-StartupProperty -InputObject $Result -Name 'stderr')
    return $stderr -match '(?i)(no such (container|object)|container .* not found)'
}

function ConvertFrom-StartupDockerContainerProjection {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$Json)

    if ([string]::IsNullOrWhiteSpace($Json)) { throw 'Docker inspect projection was empty.' }
    try { $projection = $Json | ConvertFrom-Json -ErrorAction Stop }
    catch { throw 'Docker inspect projection was not valid JSON.' }
    if (@($projection).Count -ne 1 -or $null -eq $projection) { throw 'Docker inspect projection did not contain exactly one object.' }

    foreach ($required in @('id', 'name', 'image_id', 'compose_project', 'compose_service', 'state', 'mounts', 'configured_ports', 'active_ports')) {
        if (-not (Test-StartupProperty -InputObject $projection -Name $required)) { throw ('Docker inspect projection field missing: ' + $required) }
    }
    $state = Get-StartupProperty -InputObject $projection -Name 'state'
    if ($null -eq $state) { throw 'Docker inspect projection State was missing.' }
    foreach ($requiredState in @('status', 'running', 'health')) {
        if (-not (Test-StartupProperty -InputObject $state -Name $requiredState)) { throw ('Docker inspect projection State field missing: ' + $requiredState) }
    }
    $stateStatus = Get-StartupProperty -InputObject $state -Name 'status'
    $running = Get-StartupProperty -InputObject $state -Name 'running'
    if (-not ($stateStatus -is [string]) -or [string]::IsNullOrWhiteSpace([string]$stateStatus)) { throw 'Docker inspect projection State.Status was invalid.' }
    if (-not ($running -is [bool])) { throw 'Docker inspect projection State.Running was invalid.' }
    if ([string]$stateStatus -notin @('created', 'running', 'paused', 'restarting', 'removing', 'exited', 'dead')) { throw 'Docker inspect projection State.Status was unknown.' }
    if (([string]$stateStatus -eq 'running' -and -not [bool]$running) -or ([string]$stateStatus -in @('created', 'exited', 'dead') -and [bool]$running)) {
        throw 'Docker inspect projection State fields were inconsistent.'
    }

    $healthValue = Get-StartupProperty -InputObject $state -Name 'health'
    if ($null -eq $healthValue) {
        $healthStatus = 'NOT_CONFIGURED'
        $healthObservation = 'NOT_CONFIGURED'
    }
    elseif ($healthValue -is [string] -and ([string]$healthValue) -in @('healthy', 'starting', 'unhealthy')) {
        $healthStatus = [string]$healthValue
        $healthObservation = 'OBSERVED'
    }
    else {
        $healthStatus = 'UNKNOWN'
        $healthObservation = 'UNKNOWN'
    }

    $mountValue = Get-StartupProperty -InputObject $projection -Name 'mounts'
    $configuredPortValue = Get-StartupProperty -InputObject $projection -Name 'configured_ports'
    $activePortValue = Get-StartupProperty -InputObject $projection -Name 'active_ports'
    $mountJson = if ($null -eq $mountValue) {
        if ($Json -notmatch '"mounts"\s*:\s*\[\s*\]') { throw 'Docker inspect projection mounts were null or invalid.' }
        '[]'
    }
    else { $mountValue | ConvertTo-Json -Depth 8 -Compress }
    $configuredPortJson = if ($null -eq $configuredPortValue) {
        if ($Json -notmatch '"configured_ports"\s*:\s*\{\s*\}') { throw 'Docker inspect projection configured ports were null or invalid.' }
        '{}'
    }
    else { $configuredPortValue | ConvertTo-Json -Depth 8 -Compress }
    $activePortJson = if ($null -eq $activePortValue) {
        if ($Json -notmatch '"active_ports"\s*:\s*\{\s*\}') { throw 'Docker inspect projection active ports were null or invalid.' }
        '{}'
    }
    else { $activePortValue | ConvertTo-Json -Depth 8 -Compress }
    return [pscustomobject]@{
        full_id = [string](Get-StartupProperty -InputObject $projection -Name 'id')
        container_name = ([string](Get-StartupProperty -InputObject $projection -Name 'name')).TrimStart('/')
        compose_project = [string](Get-StartupProperty -InputObject $projection -Name 'compose_project')
        service = [string](Get-StartupProperty -InputObject $projection -Name 'compose_service')
        image_id = [string](Get-StartupProperty -InputObject $projection -Name 'image_id')
        running = [bool]$running
        state_status = ([string]$stateStatus).ToLowerInvariant()
        health_status = $healthStatus
        health_observation = $healthObservation
        mounts = @(ConvertFrom-StartupDockerMounts $mountJson)
        configured_ports = @(ConvertFrom-StartupDockerPorts $configuredPortJson)
        active_ports = @(ConvertFrom-StartupDockerPorts $activePortJson)
    }
}

function Test-StartupExpectedEmptyResultError {
    param(
        [Parameter(Mandatory = $true)]$ErrorRecord,
        [Parameter(Mandatory = $true)][ValidateSet('GET_PROCESS', 'GET_NET_TCP_LISTENER')][string]$Query,
        [AllowNull()]$ExpectedTarget
    )

    if ([string]$ErrorRecord.CategoryInfo.Category -cne 'ObjectNotFound') { return $false }
    $errorId = [string]$ErrorRecord.FullyQualifiedErrorId
    if ($Query -ceq 'GET_PROCESS') {
        if ($errorId -cne 'NoProcessFoundForGivenName,Microsoft.PowerShell.Commands.GetProcessCommand') { return $false }
        $target = [string]$ErrorRecord.TargetObject
        return [string]::IsNullOrWhiteSpace($target) -or $target.Equals([string]$ExpectedTarget, [System.StringComparison]::OrdinalIgnoreCase)
    }
    return $errorId -match '^CmdletizationQuery_NotFound(?:_[A-Za-z0-9]+)*,Get-NetTCPConnection$'
}

function Invoke-StartupDesktopProcessObservation {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$ProcessName,
        [Parameter(Mandatory = $true)][string]$ExpectedPath,
        [AllowNull()][scriptblock]$GetProcessBoundary
    )

    if ($null -eq $GetProcessBoundary) {
        $GetProcessBoundary = { param($Name) @(Get-Process -Name $Name -ErrorAction Stop) }
    }
    try {
        $matches = @(& $GetProcessBoundary $ProcessName)
    }
    catch {
        if (Test-StartupExpectedEmptyResultError -ErrorRecord $_ -Query GET_PROCESS -ExpectedTarget $ProcessName) { return @() }
        throw
    }
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

function ConvertFrom-StartupWindowsCommandLine {
    param([AllowNull()][string]$CommandLine)

    if ([string]::IsNullOrWhiteSpace($CommandLine)) {
        return [pscustomobject]@{ valid = $false; arguments = @() }
    }
    $arguments = New-Object System.Collections.Generic.List[string]
    $length = $CommandLine.Length
    $index = 0
    while ($index -lt $length) {
        while ($index -lt $length -and [char]::IsWhiteSpace($CommandLine[$index])) { $index++ }
        if ($index -ge $length) { break }
        $builder = New-Object System.Text.StringBuilder
        $inQuotes = $false
        while ($index -lt $length) {
            if (-not $inQuotes -and [char]::IsWhiteSpace($CommandLine[$index])) { break }
            $backslashes = 0
            while ($index -lt $length -and $CommandLine[$index] -eq '\') { $backslashes++; $index++ }
            if ($index -lt $length -and $CommandLine[$index] -eq '"') {
                [void]$builder.Append(('\' * [int][Math]::Floor($backslashes / 2.0)))
                if (($backslashes % 2) -eq 1) { [void]$builder.Append('"') }
                else { $inQuotes = -not $inQuotes }
                $index++
                continue
            }
            if ($backslashes -gt 0) { [void]$builder.Append(('\' * $backslashes)) }
            if ($index -lt $length) { [void]$builder.Append($CommandLine[$index]); $index++ }
        }
        if ($inQuotes) { return [pscustomobject]@{ valid = $false; arguments = @() } }
        $arguments.Add($builder.ToString())
        while ($index -lt $length -and [char]::IsWhiteSpace($CommandLine[$index])) { $index++ }
    }
    return [pscustomobject]@{ valid = ($arguments.Count -gt 0); arguments = $arguments.ToArray() }
}

function Invoke-BoundedStartupHostOperation {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][ValidateSet('OBSERVE', 'START')][string]$Operation,
        [Parameter(Mandatory = $true)]$Expected,
        [Parameter(Mandatory = $true)][ValidateRange(25, 300000)][int]$TimeoutMilliseconds,
        [Parameter(Mandatory = $true)][ValidateRange(1024, 1048576)][int]$MaximumOutputCharacters,
        [AllowNull()]$SyntheticFixture,
        [AllowNull()]$SyntheticCommandBoundary
    )

    # This is a closed launcher boundary, not a command runner. The worker accepts
    # only the two fixed operations above and structured identity data selected
    # from an already validated manifest by New-RealStartupAdapters. The optional
    # fixture is an in-process test seam and is never populated from JSON. The
    # command-boundary seam is likewise test-only, must be complete, and still
    # executes the worker's real collection and error-normalization branches.
    if ([string](Get-StartupProperty -InputObject $Expected -Name 'launch_kind') -cne 'TASK') {
        return [pscustomobject]@{ status = 'REFUSED'; result = $null; duration_ms = 0; job_left_running = $false; operation_may_have_started = $false }
    }
    foreach ($required in @('name', 'task_name', 'task_path', 'executable', 'working_directory', 'listener_port')) {
        if ([string]::IsNullOrWhiteSpace([string](Get-StartupProperty -InputObject $Expected -Name $required))) {
            return [pscustomobject]@{ status = 'REFUSED'; result = $null; duration_ms = 0; job_left_running = $false; operation_may_have_started = $false }
        }
    }
    if ($null -ne $SyntheticFixture -and $null -ne $SyntheticCommandBoundary) {
        return [pscustomobject]@{ status = 'REFUSED'; result = $null; duration_ms = 0; job_left_running = $false; operation_may_have_started = $false }
    }
    if ($null -ne $SyntheticCommandBoundary) {
        foreach ($commandName in @('GetTask', 'GetProcesses', 'GetListeners', 'StartTask')) {
            $property = $SyntheticCommandBoundary.PSObject.Properties[$commandName]
            if ($null -eq $property -or -not ($property.Value -is [scriptblock])) {
                return [pscustomobject]@{ status = 'REFUSED'; result = $null; duration_ms = 0; job_left_running = $false; operation_may_have_started = $false }
            }
        }
        if ($null -eq $SyntheticCommandBoundary.PSObject.Properties['State']) {
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
        param($SelectedOperation, $SelectedExpected, $TestFixture, $TestCommands)
        $ErrorActionPreference = 'Stop'
        Set-StrictMode -Version 2.0

        function Test-ExpectedEmptyResultError {
            param($ErrorRecord, [string]$Query, $ExpectedTarget)
            if ([string]$ErrorRecord.CategoryInfo.Category -cne 'ObjectNotFound') { return $false }
            $errorId = [string]$ErrorRecord.FullyQualifiedErrorId
            $target = [string]$ErrorRecord.TargetObject
            $targetMatches = [string]::IsNullOrWhiteSpace($target) -or $target.Equals([string]$ExpectedTarget, [System.StringComparison]::OrdinalIgnoreCase)
            if ($Query -ceq 'GET_SCHEDULED_TASK') {
                return $targetMatches -and $errorId -match '^CmdletizationQuery_NotFound(?:_[A-Za-z0-9]+)*,Get-ScheduledTask$'
            }
            if ($Query -ceq 'GET_NET_TCP_LISTENER') {
                return $targetMatches -and $errorId -match '^CmdletizationQuery_NotFound(?:_[A-Za-z0-9]+)*,Get-NetTCPConnection$'
            }
            return $false
        }

        $testCalls = New-Object System.Collections.Generic.List[string]
        $normalizedEmptyResult = ''

        if ($null -ne $TestFixture) {
            $delay = 0
            if ($null -ne $TestFixture.PSObject.Properties['delay_ms']) { $delay = [int]$TestFixture.delay_ms }
            if ($delay -gt 0) { Start-Sleep -Milliseconds $delay }
            if ($null -eq $TestFixture.PSObject.Properties['result']) { throw 'SYNTHETIC_FIXTURE_RESULT_MISSING' }
            return $TestFixture.result
        }

        try {
            if ($null -ne $TestCommands) {
                $testCalls.Add('GET_TASK')
                $taskCommand = $TestCommands.PSObject.Properties['GetTask'].Value
                $task = & $taskCommand $SelectedExpected $TestCommands.PSObject.Properties['State'].Value
            }
            else {
                $task = Get-ScheduledTask -TaskPath $SelectedExpected.task_path -TaskName $SelectedExpected.task_name -ErrorAction Stop
            }
        }
        catch {
            if (Test-ExpectedEmptyResultError -ErrorRecord $_ -Query 'GET_SCHEDULED_TASK' -ExpectedTarget $SelectedExpected.task_name) {
                return [pscustomobject]@{ status = 'CONTROLLED_DEPLOY_REQUIRED'; task = $null; processes = @(); listeners = @(); lower_boundary_calls = $testCalls.ToArray(); normalized_empty_result = 'GET_SCHEDULED_TASK' }
            }
            return [pscustomobject]@{ status = 'OBSERVATION_UNKNOWN'; task = $null; processes = @(); listeners = @(); lower_boundary_calls = $testCalls.ToArray() }
        }
        if ($null -eq $task) {
            return [pscustomobject]@{ status = 'CONTROLLED_DEPLOY_REQUIRED'; task = $null; processes = @(); listeners = @(); lower_boundary_calls = $testCalls.ToArray() }
        }
        if (@($task.Actions).Count -ne 1) {
            return [pscustomobject]@{ status = 'IDENTITY_MISMATCH'; task = $null; processes = @(); listeners = @(); lower_boundary_calls = $testCalls.ToArray() }
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
            return [pscustomobject]@{ status = 'IDENTITY_MISMATCH'; task = $taskData; processes = @(); listeners = @(); lower_boundary_calls = $testCalls.ToArray() }
        }

        if ($SelectedOperation -ceq 'START') {
            try {
                if ($null -ne $TestCommands) {
                    $testCalls.Add('START_TASK')
                    $startTaskCommand = $TestCommands.PSObject.Properties['StartTask'].Value
                    [void](& $startTaskCommand $SelectedExpected $TestCommands.PSObject.Properties['State'].Value)
                }
                else {
                    Start-ScheduledTask -TaskPath $SelectedExpected.task_path -TaskName $SelectedExpected.task_name -ErrorAction Stop
                }
            }
            catch {
                return [pscustomobject]@{ status = 'START_UNKNOWN'; task = $taskData; processes = @(); listeners = @(); lower_boundary_calls = $testCalls.ToArray() }
            }
            return [pscustomobject]@{ status = 'SUCCESS'; task = $taskData; processes = @(); listeners = @(); lower_boundary_calls = $testCalls.ToArray() }
        }

        try {
            if ($null -ne $TestCommands) {
                $testCalls.Add('GET_PROCESSES')
                $processCommand = $TestCommands.PSObject.Properties['GetProcesses'].Value
                $rawProcesses = @(& $processCommand $SelectedExpected $TestCommands.PSObject.Properties['State'].Value)
            }
            else {
                $escapedName = ([string]$SelectedExpected.process_name).Replace("'", "''")
                $rawProcesses = @(Get-CimInstance Win32_Process -Filter ("Name='{0}'" -f $escapedName) -ErrorAction Stop)
            }
            $processes = @($rawProcesses | ForEach-Object {
                [pscustomobject]@{
                    process_id = [int]$_.ProcessId
                    executable_path = [string]$_.ExecutablePath
                    command_line = [string]$_.CommandLine
                    creation_date = $_.CreationDate
                }
            })
        }
        catch {
            return [pscustomobject]@{ status = 'OBSERVATION_UNKNOWN'; task = $taskData; processes = @(); listeners = @(); lower_boundary_calls = $testCalls.ToArray() }
        }
        try {
            if ($null -ne $TestCommands) {
                $testCalls.Add('GET_LISTENERS')
                $listenerCommand = $TestCommands.PSObject.Properties['GetListeners'].Value
                $rawListeners = @(& $listenerCommand $SelectedExpected $TestCommands.PSObject.Properties['State'].Value)
            }
            else {
                $rawListeners = @(Get-NetTCPConnection -State Listen -LocalPort ([int]$SelectedExpected.listener_port) -ErrorAction Stop)
            }
        }
        catch {
            if (Test-ExpectedEmptyResultError -ErrorRecord $_ -Query 'GET_NET_TCP_LISTENER' -ExpectedTarget $SelectedExpected.listener_port) {
                $rawListeners = @()
                $normalizedEmptyResult = 'GET_NET_TCP_LISTENER'
            }
            else {
                return [pscustomobject]@{ status = 'OBSERVATION_UNKNOWN'; task = $taskData; processes = $processes; listeners = @(); lower_boundary_calls = $testCalls.ToArray() }
            }
        }
        $listeners = @($rawListeners | ForEach-Object {
            [pscustomobject]@{
                local_address = [string]$_.LocalAddress
                local_port = [int]$_.LocalPort
                owning_process = [int]$_.OwningProcess
            }
        })
        return [pscustomobject]@{ status = 'SUCCESS'; task = $taskData; processes = $processes; listeners = $listeners; lower_boundary_calls = $testCalls.ToArray(); normalized_empty_result = $normalizedEmptyResult }
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
        [void]$powerShell.AddArgument($SyntheticCommandBoundary)
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
            $caughtErrorWasFailClosed = $false
            if ($items.Count -eq 1) {
                $workerStatus = [string](Get-StartupProperty -InputObject $items[0] -Name 'status')
                $normalizedEmptyResult = [string](Get-StartupProperty -InputObject $items[0] -Name 'normalized_empty_result')
                $caughtErrorWasFailClosed = ($workerStatus -eq 'OBSERVATION_UNKNOWN' -or $workerStatus -eq 'START_UNKNOWN' -or
                    ($workerStatus -eq 'SUCCESS' -and $normalizedEmptyResult -eq 'GET_NET_TCP_LISTENER') -or
                    ($workerStatus -eq 'CONTROLLED_DEPLOY_REQUIRED' -and $normalizedEmptyResult -eq 'GET_SCHEDULED_TASK'))
            }
            if ($items.Count -ne 1 -or ($powerShell.HadErrors -and -not $caughtErrorWasFailClosed)) {
                $watch.Stop()
                return [pscustomobject]@{
                    status = 'ERROR'
                    result = $null
                    duration_ms = $watch.ElapsedMilliseconds
                    job_left_running = $false
                    operation_may_have_started = ($Operation -ceq 'START')
                }
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
            Invoke-StartupDesktopProcessObservation -ProcessName $ProcessName -ExpectedPath $ExpectedPath
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
        $expectedId = [string](Get-StartupProperty -InputObject $Expected -Name 'container_id')
        $format = '{"id":{{json .Id}},"name":{{json .Name}},"image_id":{{json .Image}},"compose_project":{{json (index .Config.Labels "com.docker.compose.project")}},"compose_service":{{json (index .Config.Labels "com.docker.compose.service")}},"state":{"status":{{json .State.Status}},"running":{{json .State.Running}},"health":{{with (index .State "Health")}}{{with (index . "Status")}}{{json .}}{{else}}""{{end}}{{else}}null{{end}}},"mounts":[{{- $first := true -}}{{range .Mounts}}{{if not $first}},{{end}}{"Type":{{json .Type}},"Name":{{json (index . "Name")}},"Source":{{json .Source}},"Destination":{{json .Destination}},"RW":{{json .RW}}}{{$first = false}}{{end}}],"configured_ports":{{json .HostConfig.PortBindings}},"active_ports":{{json .NetworkSettings.Ports}}}'
        $result = New-Object System.Collections.Generic.List[object]
        $imageIdentityCache = @{}
        $invokeDockerForContainer = $invokeDocker
        $containerContext = [string]$context
        $containerExpected = $Expected
        $containerFormat = [string]$format
        $containerImageIdentityCache = $imageIdentityCache
        $readContainer = {
            param([string]$Id, [bool]$AllowNotFound)
            $inspect = & $invokeDockerForContainer @('--context', $containerContext, 'inspect', '--type', 'container', '--format', $containerFormat, $Id)
            if ($inspect.status -ne 'SUCCESS') {
                if ($AllowNotFound -and (Test-StartupDockerContainerNotFoundResult -Result $inspect)) { return $null }
                throw ('Docker container inspect failed: ' + $inspect.status)
            }
            $observed = ConvertFrom-StartupDockerContainerProjection -Json $inspect.stdout
            $observedImageId = [string](Get-StartupProperty -InputObject $observed -Name 'image_id')
            if (-not $containerImageIdentityCache.ContainsKey($observedImageId)) {
                $digests = & $invokeDockerForContainer @('--context', $containerContext, 'image', 'inspect', '--format', '{{json .RepoDigests}}', $observedImageId)
                if ($digests.status -ne 'SUCCESS') { throw ('Docker image identity failed: ' + $digests.status) }
                $parsedDigests = @($digests.stdout | ConvertFrom-Json -ErrorAction Stop | Where-Object { $null -ne $_ -and -not [string]::IsNullOrWhiteSpace([string]$_) })
                $containerImageIdentityCache[$observedImageId] = @($parsedDigests | ForEach-Object { [string]$_ })
            }
            $repoDigests = @($containerImageIdentityCache[$observedImageId])
            $approvedDigest = [string](Get-StartupProperty -InputObject $containerExpected -Name 'repo_digest')
            $identityMode = [string](Get-StartupProperty -InputObject $containerExpected -Name 'image_identity_mode')
            if ([string]::IsNullOrWhiteSpace($identityMode)) { $identityMode = 'REPO_DIGEST' }
            $matchedDigest = if ($identityMode -eq 'REPO_DIGEST') {
                @($repoDigests | Where-Object { ([string]$_).EndsWith($approvedDigest, [System.StringComparison]::OrdinalIgnoreCase) } | Select-Object -First 1)
            }
            else { @() }
            $observed | Add-Member -NotePropertyName repo_digest -NotePropertyValue $(if (@($matchedDigest).Count -eq 1) { $approvedDigest } else { '' })
            $observed | Add-Member -NotePropertyName repo_digest_state -NotePropertyValue $(if ($repoDigests.Count -eq 0) { 'CONFIRMED_ABSENT' } else { 'OBSERVED' })
            return $observed
        }.GetNewClosure()

        $pinned = $null
        if (-not [string]::IsNullOrWhiteSpace($expectedId)) {
            $pinned = & $readContainer $expectedId $true
            if ($null -ne $pinned) { $result.Add($pinned) }
        }

        $ids = & $invokeDocker @('--context', $context, 'container', 'ls', '--all', '--no-trunc', '--filter', ('label=com.docker.compose.project=' + $project), '--filter', ('label=com.docker.compose.service=' + $service), '--format', '{{.ID}}')
        if ($ids.status -notin @('SUCCESS', 'EMPTY_OUTPUT')) { throw ('Docker container conflict observation failed: ' + $ids.status) }
        $selectorIds = @($ids.stdout -split '[\r\n]+' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object { $_.Trim() })
        if (@($selectorIds | Where-Object { $_ -notmatch '^[a-fA-F0-9]{64}$' }).Count -gt 0) { throw 'Docker container conflict selector returned an invalid or truncated ID.' }
        $selectorIds = @($selectorIds | Select-Object -Unique)
        if ($null -ne $pinned -and
            ([string](Get-StartupProperty -InputObject $pinned -Name 'compose_project')).Equals($project, [System.StringComparison]::OrdinalIgnoreCase) -and
            ([string](Get-StartupProperty -InputObject $pinned -Name 'service')).Equals($service, [System.StringComparison]::OrdinalIgnoreCase) -and
            -not @($selectorIds | Where-Object { $_.Equals($expectedId, [System.StringComparison]::OrdinalIgnoreCase) }).Count) {
            throw 'Docker container conflict selector omitted the pinned container.'
        }
        foreach ($id in $selectorIds) {
            if ($null -ne $pinned -and $id.Equals($expectedId, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
            $observed = & $readContainer $id $false
            if ($null -ne $observed) { $result.Add($observed) }
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
        if ([int]$Timeout -lt 25) {
            return [pscustomobject]@{ observation_status = 'UNKNOWN'; matches = @(); detail = 'DEADLINE_EXHAUSTED' }
        }
        $operation = & $SystemBoundary.InvokeHostOperation 'OBSERVE' $Expected $Timeout $outputLimit
        if ((Get-StartupProperty -InputObject $operation -Name 'status') -ne 'SUCCESS') {
            return [pscustomobject]@{ observation_status = 'UNKNOWN'; matches = @(); detail = [string](Get-StartupProperty -InputObject $operation -Name 'status') }
        }
        $payload = Get-StartupProperty -InputObject $operation -Name 'result'
        $payloadStatus = [string](Get-StartupProperty -InputObject $payload -Name 'status')
        if ($payloadStatus -eq 'OBSERVATION_UNKNOWN') {
            return [pscustomobject]@{ observation_status = 'UNKNOWN'; matches = @(); detail = $payloadStatus }
        }
        if ($payloadStatus -eq 'CONTROLLED_DEPLOY_REQUIRED') {
            return [pscustomobject]@{ observation_status = 'CONTROLLED_DEPLOY_REQUIRED'; matches = @(); detail = 'TASK_NOT_FOUND' }
        }
        if ($payloadStatus -ne 'SUCCESS') {
            return [pscustomobject]@{ observation_status = 'CONFLICT'; matches = @(); detail = $payloadStatus }
        }

        $expectedExecutable = [string](Get-StartupProperty -InputObject $Expected -Name 'executable')
        $expectedArguments = @((Get-StartupProperty -InputObject $Expected -Name 'arguments') | ForEach-Object { [string]$_ })
        $expectedArgumentString = Join-WindowsNativeArguments -ArgumentList $expectedArguments
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
        $unknownProcessEvidence = $false
        $codeArgumentIndexes = New-Object System.Collections.Generic.List[int]
        for ($argumentIndex = 0; $argumentIndex -lt $expectedArguments.Count; $argumentIndex++) {
            if ($expectedArguments[$argumentIndex] -match '(?i)\.(c?js|mjs|ps1|py)$') { $codeArgumentIndexes.Add($argumentIndex) }
        }
        if ($codeArgumentIndexes.Count -ne 1) {
            return [pscustomobject]@{ observation_status = 'UNKNOWN'; matches = @(); detail = 'EXPECTED_CODE_ARGUMENT_UNKNOWN' }
        }
        $codeArgumentIndex = $codeArgumentIndexes[0]
        $expectedTokens = @($expectedExecutable) + $expectedArguments
        $expectedCodePath = try {
            $codeArgument = $expectedArguments[$codeArgumentIndex]
            if ([System.IO.Path]::IsPathRooted($codeArgument)) { [System.IO.Path]::GetFullPath($codeArgument) }
            else { [System.IO.Path]::GetFullPath((Join-Path $expectedWorkingDirectory $codeArgument)) }
        }
        catch { return [pscustomobject]@{ observation_status = 'UNKNOWN'; matches = @(); detail = 'EXPECTED_CODE_ARGUMENT_INVALID' } }
        foreach ($process in $processes) {
            $actualExecutable = [string](Get-StartupProperty -InputObject $process -Name 'executable_path')
            $actualCommandLine = ([string](Get-StartupProperty -InputObject $process -Name 'command_line')).Trim()
            if ([string]::IsNullOrWhiteSpace($actualExecutable)) { $unknownProcessEvidence = $true; continue }
            if (-not $actualExecutable.Equals($expectedExecutable, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
            $parsedCommand = ConvertFrom-StartupWindowsCommandLine $actualCommandLine
            if (-not $parsedCommand.valid) { $unknownProcessEvidence = $true; continue }
            $actualTokens = @($parsedCommand.arguments | ForEach-Object { [string]$_ })
            if ($actualTokens.Count -le (1 + $codeArgumentIndex) -or
                -not $actualTokens[0].Equals($expectedExecutable, [System.StringComparison]::OrdinalIgnoreCase)) {
                $unknownProcessEvidence = $true
                continue
            }
            $actualCodePath = try {
                $actualCodeArgument = $actualTokens[1 + $codeArgumentIndex]
                if ([System.IO.Path]::IsPathRooted($actualCodeArgument)) { [System.IO.Path]::GetFullPath($actualCodeArgument) }
                else { [System.IO.Path]::GetFullPath((Join-Path $expectedWorkingDirectory $actualCodeArgument)) }
            }
            catch { $null }
            if ($null -eq $actualCodePath) { $unknownProcessEvidence = $true; continue }
            $referencesExpectedCode = $actualCodePath.Equals($expectedCodePath, [System.StringComparison]::OrdinalIgnoreCase)
            if (-not $referencesExpectedCode) {
                for ($actualTokenIndex = 1; $actualTokenIndex -lt $actualTokens.Count; $actualTokenIndex++) {
                    $candidatePath = try {
                        if ([System.IO.Path]::IsPathRooted($actualTokens[$actualTokenIndex])) { [System.IO.Path]::GetFullPath($actualTokens[$actualTokenIndex]) }
                        else { [System.IO.Path]::GetFullPath((Join-Path $expectedWorkingDirectory $actualTokens[$actualTokenIndex])) }
                    }
                    catch { $null }
                    if ($null -ne $candidatePath -and $candidatePath.Equals($expectedCodePath, [System.StringComparison]::OrdinalIgnoreCase)) {
                        $referencesExpectedCode = $true
                        break
                    }
                }
            }
            $allTokensMatch = ($actualTokens.Count -eq $expectedTokens.Count)
            if ($allTokensMatch) {
                for ($tokenIndex = 0; $tokenIndex -lt $expectedTokens.Count; $tokenIndex++) {
                    $comparison = if ($tokenIndex -eq 0 -or $tokenIndex -eq (1 + $codeArgumentIndex)) { [System.StringComparison]::OrdinalIgnoreCase } else { [System.StringComparison]::Ordinal }
                    if (-not $actualTokens[$tokenIndex].Equals([string]$expectedTokens[$tokenIndex], $comparison)) { $allTokensMatch = $false; break }
                }
            }
            if (-not $allTokensMatch) {
                if ($referencesExpectedCode) { $conflictingProcess = $true }
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
        if ($unknownProcessEvidence) {
            return [pscustomobject]@{ observation_status = 'UNKNOWN'; matches = @(); detail = 'PROCESS_IDENTITY_UNKNOWN' }
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
        if ([int]$Timeout -lt 25) {
            return [pscustomobject]@{ status = 'TIMEOUT'; operation_may_have_started = $false; job_left_running = $false }
        }
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
        if ($observation.status -eq 'CONTROLLED_DEPLOY_REQUIRED') { return [pscustomobject]@{ ready = $false; code = 'CONTROLLED_DEPLOY_REQUIRED'; detail = $observation.detail } }
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
            if ($desktop.Count -eq 1 -and [string](Get-StartupProperty -InputObject $desktop[0] -Name 'observation_status') -eq 'UNKNOWN') {
                return New-StartupResult -Code 'DOCKER_DESKTOP_STATE_UNKNOWN' -Events $events
            }
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
            -CommandTimeoutMilliseconds $nativeTimeout `
            -StageTimeoutMilliseconds $serviceTimeout `
            -PollMilliseconds $poll
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
        if ($supervisorObservation.status -eq 'CONTROLLED_DEPLOY_REQUIRED') {
            return New-StartupResult -Code 'CONTROLLED_DEPLOY_REQUIRED' -SupervisorStatus 'UNKNOWN' -Events $events -Details @('supervisor', $supervisorObservation.detail)
        }
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
            if ($observation.status -eq 'CONTROLLED_DEPLOY_REQUIRED') { return New-StartupResult -Code 'CONTROLLED_DEPLOY_REQUIRED' -SupervisorStatus 'INTENTIONALLY_STOPPED' -Events $events -Details @($name, $observation.detail) }
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
