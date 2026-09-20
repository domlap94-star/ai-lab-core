[CmdletBinding()]
param(
    [switch]$PreimageEvidence,
    [switch]$ObservationReviewPreimage,
    [string]$PreimageRuntimePath = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($PreimageEvidence) {
    if ([string]::IsNullOrWhiteSpace($PreimageRuntimePath)) {
        throw 'PREIMAGE_RUNTIME_PATH_REQUIRED'
    }
    $resolvedPreimageRuntime = (Resolve-Path -LiteralPath $PreimageRuntimePath -ErrorAction Stop).Path
    . $resolvedPreimageRuntime
}
else {
    . (Join-Path $PSScriptRoot 'start-host-services.ps1') -DefinitionOnly
}

$script:Assertions = 0
function Assert-Host22 {
    param([bool]$Condition, [string]$Name)
    $script:Assertions++
    if (-not $Condition) { throw ('ASSERT_FAILED: ' + $Name) }
}

function New-Host22NativeEnvelope {
    param(
        [string]$Status,
        [string]$Stdout = '',
        [string]$Stderr = '',
        [bool]$Started = $true,
        [bool]$TimedOut = $false,
        $ExitCode = 0,
        [bool]$ProcessLeftRunning = $false,
        [bool]$StdoutTruncated = $false,
        [bool]$StderrTruncated = $false
    )
    return [pscustomobject]@{
        status = $Status
        started = $Started
        timed_out = $TimedOut
        exit_code = $ExitCode
        pid = 4242
        process_left_running = $ProcessLeftRunning
        duration_ms = 1
        stdout = $Stdout
        stderr = $Stderr
        stdout_truncated = $StdoutTruncated
        stderr_truncated = $StderrTruncated
    }
}

function New-Host22PreimageExpected {
    return [pscustomobject]@{
        service = 'backend'
        container_name = 'ai-lab-backend'
        compose_project = 'ai-lab-core'
        container_id = '6' * 64
        image_id = 'sha256:' + ('a' * 64)
        image_identity_mode = 'REPO_DIGEST'
        repo_digest = 'sha256:' + ('b' * 64)
        startup_order = 10
        health_requirement = 'RUNNING'
        depends_on_healthy = @()
        mounts = @([pscustomobject]@{ source = 'C:\synthetic\backend'; destination = '/app'; type = 'bind'; read_only = $true })
        ports = @([pscustomobject]@{ host_ip = '127.0.0.1'; host_port = '18000'; container_port = '8000'; protocol = 'tcp' })
    }
}

function New-Host22PreimageObservation {
    param([string]$Id, [string]$Name, [bool]$Running, [string]$StateStatus, [bool]$Drill)
    $expected = New-Host22PreimageExpected
    return [pscustomobject]@{
        full_id = $Id
        container_name = $Name
        compose_project = 'ai-lab-core'
        service = 'backend'
        image_id = $expected.image_id
        repo_digest = $expected.repo_digest
        repo_digest_state = 'OBSERVED'
        running = $Running
        state_status = $StateStatus
        health_status = 'NOT_CONFIGURED'
        mounts = $(if ($Drill) { @() } else { @($expected.mounts) })
        configured_ports = $(if ($Drill) { @() } else { @($expected.ports) })
        active_ports = $(if ($Running) { @($expected.ports) } else { @() })
    }
}

if ($PreimageEvidence) {
    $expected = New-Host22PreimageExpected
    $observations = @(
        (New-Host22PreimageObservation -Id $expected.container_id -Name $expected.container_name -Running $true -StateStatus 'running' -Drill $false),
        (New-Host22PreimageObservation -Id ('1' * 64) -Name 'next-stabil-r03-a1-drill-20260908-a4-qdrant-2-client' -Running $false -StateStatus 'exited' -Drill $true),
        (New-Host22PreimageObservation -Id ('2' * 64) -Name 'next-stabil-r03-a1-drill-20260908-a4-qdrant-1-client' -Running $false -StateStatus 'exited' -Drill $true),
        (New-Host22PreimageObservation -Id ('3' * 64) -Name 'next-stabil-r03-a1-drill-20260908-a1-qdrant-2-client' -Running $false -StateStatus 'exited' -Drill $true),
        (New-Host22PreimageObservation -Id ('4' * 64) -Name 'next-stabil-r03-a1-drill-20260908-a1-qdrant-1-client' -Running $false -StateStatus 'exited' -Drill $true)
    )
    $startCalls = New-Object System.Collections.Generic.List[string]
    $adapters = [pscustomobject]@{
        ObserveContainer = { param($Definition) return @($observations) }.GetNewClosure()
        StartExistingContainer = { param($FullId, $Timeout) $startCalls.Add([string]$FullId); [pscustomobject]@{ status = 'SUCCESS' } }.GetNewClosure()
        Sleep = { param($Milliseconds) }
    }
    $result = Invoke-StartupExistingContainerPhase -ExpectedContainers @($expected) -Adapters $adapters -CommandTimeoutMilliseconds 50 -StageTimeoutMilliseconds 20 -PollMilliseconds 1
    [pscustomobject]@{
        schema = 'NEXT_STABIL_HOST22_FAIL_BEFORE_V1'
        code = [string]$result.code
        component = [string]$result.component
        observation_count = $observations.Count
        start_calls = $startCalls.Count
    } | ConvertTo-Json -Depth 5
    if ($result.code -ne 'CONTAINER_IDENTITY_AMBIGUOUS' -or $startCalls.Count -ne 0) {
        throw 'HOST22_PREIMAGE_FAIL_BEFORE_NOT_REPRODUCED'
    }
    exit 0
}

function Copy-Host22Object {
    param($Value)
    return ($Value | ConvertTo-Json -Depth 20 | ConvertFrom-Json)
}

function New-Host22Projection {
    param(
        [string]$Id,
        [string]$Name,
        [bool]$Running,
        [string]$StateStatus,
        [AllowNull()]$Health,
        [bool]$Drill = $false
    )
    $expected = New-Host22PreimageExpected
    $configured = [ordered]@{}
    $active = [ordered]@{}
    $mounts = New-Object System.Collections.ArrayList
    if (-not $Drill) {
        [void]$mounts.Add([ordered]@{ Type = 'bind'; Name = ''; Source = 'C:\synthetic\backend'; Destination = '/app'; RW = $false })
        $configured['8000/tcp'] = @([ordered]@{ HostIp = '127.0.0.1'; HostPort = '18000' })
        if ($Running) { $active['8000/tcp'] = @([ordered]@{ HostIp = '127.0.0.1'; HostPort = '18000' }) }
    }
    return [ordered]@{
        id = $Id
        name = '/' + $Name
        image_id = $expected.image_id
        compose_project = $expected.compose_project
        compose_service = $expected.service
        state = [ordered]@{ status = $StateStatus; running = $Running; health = $Health }
        mounts = $mounts
        configured_ports = $configured
        active_ports = $active
    }
}

function New-Host22AdapterState {
    $expected = New-Host22PreimageExpected
    $projections = @{}
    $projections[$expected.container_id] = New-Host22Projection -Id $expected.container_id -Name $expected.container_name -Running $true -StateStatus 'running' -Health $null
    $drills = @(
        [pscustomobject]@{ id = ('1' * 64); name = 'next-stabil-r03-a1-drill-20260908-a4-qdrant-2-client' },
        [pscustomobject]@{ id = ('2' * 64); name = 'next-stabil-r03-a1-drill-20260908-a4-qdrant-1-client' },
        [pscustomobject]@{ id = ('3' * 64); name = 'next-stabil-r03-a1-drill-20260908-a1-qdrant-2-client' },
        [pscustomobject]@{ id = ('4' * 64); name = 'next-stabil-r03-a1-drill-20260908-a1-qdrant-1-client' }
    )
    foreach ($drill in $drills) { $projections[$drill.id] = New-Host22Projection -Id $drill.id -Name $drill.name -Running $false -StateStatus 'exited' -Health $null -Drill $true }
    return [hashtable]@{
        expected = $expected
        projections = $projections
        selector_ids = @($expected.container_id) + @($drills.id)
        inspect_modes = @{}
        calls = New-Object System.Collections.Generic.List[string]
        native_timeouts = New-Object System.Collections.Generic.List[int]
        starts = New-Object System.Collections.Generic.List[string]
        captured_template = ''
        repo_digests = @('repo@sha256:' + ('b' * 64))
        selector_override = $null
        selector_stdout_truncated = $false
        selector_stderr_truncated = $false
        selector_metadata_missing = $false
        image_stdout_truncated = $false
        read_delay_ms = 0
    }
}

function New-Host22SystemBoundary {
    param([hashtable]$State)
    $invokeNative = {
        param($FilePath, $Arguments, $Timeout, $MaximumOutput)
        $joined = @($Arguments) -join ' '
        $State.calls.Add($joined)
        $State.native_timeouts.Add([int]$Timeout)
        if ([int]$State.read_delay_ms -gt 0 -and $joined -notlike '--context desktop-linux-test start*') {
            Start-Sleep -Milliseconds ([int]$State.read_delay_ms)
        }
        if ($joined -like '--context desktop-linux-test inspect --type container --format*') {
            $id = [string]$Arguments[-1]
            $State.captured_template = [string]$Arguments[-2]
            $mode = if ($State.inspect_modes.ContainsKey($id)) { [string]$State.inspect_modes[$id] } else { 'SUCCESS' }
            if ($mode -eq 'TIMEOUT') { return New-Host22NativeEnvelope -Status 'TIMEOUT' -TimedOut $true -ExitCode $null }
            if ($mode -eq 'NOT_FOUND') { return New-Host22NativeEnvelope -Status 'ERROR' -Stderr 'Error: No such container: synthetic' -ExitCode 1 }
            if ($mode -eq 'NOT_FOUND_NONZERO') { return New-Host22NativeEnvelope -Status 'NONZERO_EXIT' -Stderr 'Error response from daemon: No such container: synthetic' -ExitCode 1 }
            if ($mode -eq 'ERROR') { return New-Host22NativeEnvelope -Status 'ERROR' -Stderr 'synthetic access denied' -ExitCode 1 }
            if ($mode -eq 'TRUNCATED') { return New-Host22NativeEnvelope -Status 'SUCCESS' -Stdout '{"id":' }
            if (-not $State.projections.ContainsKey($id)) { return New-Host22NativeEnvelope -Status 'ERROR' -Stderr 'Error: No such container: synthetic' -ExitCode 1 }
            $json = $State.projections[$id] | ConvertTo-Json -Depth 10 -Compress
            return New-Host22NativeEnvelope -Status 'SUCCESS' -Stdout $json -StdoutTruncated ($mode -eq 'TRUNCATED_METADATA')
        }
        if ($joined -like '--context desktop-linux-test container ls --all --no-trunc*') {
            $selectorText = if ($null -ne $State.selector_override) { [string]$State.selector_override } else { @($State.selector_ids) -join "`r`n" }
            if ([bool]$State.selector_metadata_missing) {
                return [pscustomobject]@{ status = 'SUCCESS'; started = $true; timed_out = $false; exit_code = 0; process_left_running = $false; stdout = $selectorText; stderr = ''; stderr_truncated = $false }
            }
            return New-Host22NativeEnvelope -Status 'SUCCESS' -Stdout $selectorText -StdoutTruncated ([bool]$State.selector_stdout_truncated) -StderrTruncated ([bool]$State.selector_stderr_truncated)
        }
        if ($joined -like '--context desktop-linux-test image inspect*') {
            return New-Host22NativeEnvelope -Status 'SUCCESS' -Stdout (@($State.repo_digests) | ConvertTo-Json -Compress) -StdoutTruncated ([bool]$State.image_stdout_truncated)
        }
        if ($joined -like '--context desktop-linux-test start*') {
            $id = [string]$Arguments[-1]
            $State.starts.Add($id)
            if ($State.projections.ContainsKey($id)) {
                $State.projections[$id].state.running = $true
                $State.projections[$id].state.status = 'running'
                $State.projections[$id].active_ports = [ordered]@{ '8000/tcp' = @([ordered]@{ HostIp = '127.0.0.1'; HostPort = '18000' }) }
            }
            return New-Host22NativeEnvelope -Status 'SUCCESS' -Stdout $id
        }
        throw ('UNEXPECTED_NATIVE_CALL:' + $joined)
    }.GetNewClosure()
    return [pscustomobject]@{
        InvokeNative = $invokeNative
        GetEnvironmentState = { throw 'UNEXPECTED_ENVIRONMENT_CALL' }
        ObserveDesktop = { param($ProcessName, $ExpectedPath) throw 'UNEXPECTED_DESKTOP_OBSERVE' }
        StartDesktop = { param($ExpectedPath) throw 'UNEXPECTED_DESKTOP_START' }
        InvokeHostOperation = { param($Operation, $Expected, $Timeout, $MaximumOutput) throw 'UNEXPECTED_HOST_OPERATION' }
        InvokeHttp = { param($Uri, $Timeout) throw 'UNEXPECTED_HTTP_CALL' }
        Sleep = { param($Milliseconds) }
    }
}

function New-Host22AdapterManifest {
    return [pscustomobject]@{
        timeouts = [pscustomobject]@{ native_command_ms = 100; max_output_chars = 16384 }
        docker = [pscustomobject]@{ context = 'desktop-linux-test' }
        external_tools = @(
            [pscustomobject]@{ name = 'docker_cli'; path = 'C:\synthetic\docker.exe' },
            [pscustomobject]@{ name = 'docker_desktop'; path = 'C:\synthetic\Docker Desktop.exe' }
        )
    }
}

function Invoke-Host22AdapterPhase {
    param(
        [hashtable]$State,
        [int]$CommandTimeoutMilliseconds = 100,
        [int]$StageTimeoutMilliseconds = 5000
    )
    $adapters = New-RealStartupAdapters -Manifest (New-Host22AdapterManifest) -SystemBoundary (New-Host22SystemBoundary $State)
    foreach ($adapterName in @('ObserveContainer', 'StartExistingContainer', 'Sleep')) {
        if (-not ((Get-StartupProperty -InputObject $adapters -Name $adapterName) -is [scriptblock])) {
            throw ('HOST22_ADAPTER_NOT_SCRIPTBLOCK:' + $adapterName + ':' + (Get-StartupProperty -InputObject $adapters -Name $adapterName).GetType().FullName)
        }
    }
    try {
        return Invoke-StartupExistingContainerPhase -ExpectedContainers @($State.expected) -Adapters $adapters -CommandTimeoutMilliseconds $CommandTimeoutMilliseconds -StageTimeoutMilliseconds $StageTimeoutMilliseconds -PollMilliseconds 1
    }
    catch {
        throw ('HOST22_PHASE_EXCEPTION:' + $_.Exception.Message + ';STACK=' + $_.ScriptStackTrace)
    }
}

if ($ObservationReviewPreimage) {
    $reviewResults = New-Object System.Collections.Generic.List[object]
    foreach ($case in @('A_SELECTOR_TRUNCATED', 'B_INSPECT_TRUNCATED', 'C_EMPTY_SELECTOR_TRUNCATED', 'D_COMPLETE_CONTROL')) {
        $caseState = New-Host22AdapterState
        $caseState.selector_ids = @($caseState.expected.container_id)
        $caseState.projections[$caseState.expected.container_id].state.running = $false
        $caseState.projections[$caseState.expected.container_id].state.status = 'exited'
        $caseState.projections[$caseState.expected.container_id].active_ports = [ordered]@{}
        switch ($case) {
            'A_SELECTOR_TRUNCATED' { $caseState.selector_stdout_truncated = $true; $caseState.selector_override = $caseState.expected.container_id }
            'B_INSPECT_TRUNCATED' { $caseState.inspect_modes[$caseState.expected.container_id] = 'TRUNCATED_METADATA' }
            'C_EMPTY_SELECTOR_TRUNCATED' { $caseState.selector_stdout_truncated = $true; $caseState.selector_override = '' }
        }
        $caseResult = $null
        $caseError = ''
        try {
            $caseResult = Invoke-Host22AdapterPhase -State $caseState -CommandTimeoutMilliseconds 200 -StageTimeoutMilliseconds 1000
        }
        catch { $caseError = $_.Exception.Message }
        $reviewResults.Add([pscustomobject]@{
            finding = 'RV-H22-OBS-01'
            case = $case
            code = $(if ($null -ne $caseResult) { [string]$caseResult.code } else { 'EXCEPTION' })
            detail = $caseError
            starts = $caseState.starts.Count
            calls = $caseState.calls.Count
        })
        if ($case -eq 'C_EMPTY_SELECTOR_TRUNCATED') {
            if ($caseState.starts.Count -ne 0 -or $caseError -notmatch 'selector omitted the pinned container') {
                throw ('HOST22_OBS01_PREIMAGE_C_EXISTING_GUARD_NOT_REPRODUCED:' + $caseError)
            }
        }
        elseif ($null -eq $caseResult -or $caseResult.code -ne 'CONTAINERS_READY' -or $caseState.starts.Count -ne 1) {
            throw ('HOST22_OBS01_PREIMAGE_NOT_REPRODUCED:' + $case + ':' + $caseError)
        }
    }

    $deadlineState = New-Host22AdapterState
    $deadlineState.read_delay_ms = 60
    $deadlineWatch = [System.Diagnostics.Stopwatch]::StartNew()
    $deadlineResult = Invoke-Host22AdapterPhase -State $deadlineState -CommandTimeoutMilliseconds 200 -StageTimeoutMilliseconds 250
    $deadlineWatch.Stop()
    $reviewResults.Add([pscustomobject]@{
        finding = 'RV-H22-OBS-02'
        case = 'CUMULATIVE_READS_EXCEED_STAGE'
        code = [string]$deadlineResult.code
        starts = $deadlineState.starts.Count
        calls = $deadlineState.calls.Count
        elapsed_ms = $deadlineWatch.ElapsedMilliseconds
        native_timeouts = @($deadlineState.native_timeouts)
    })
    if ($deadlineResult.code -ne 'CONTAINERS_READY' -or $deadlineState.starts.Count -ne 0 -or $deadlineWatch.ElapsedMilliseconds -lt 250) {
        throw 'HOST22_OBS02_PREIMAGE_NOT_REPRODUCED'
    }

    foreach ($stateStatus in @('paused', 'restarting')) {
        $stateCase = New-Host22AdapterState
        $stateCase.projections[$stateCase.expected.container_id].state.status = $stateStatus
        $stateCase.projections[$stateCase.expected.container_id].state.running = $true
        $stateResult = Invoke-Host22AdapterPhase -State $stateCase -CommandTimeoutMilliseconds 200 -StageTimeoutMilliseconds 1000
        $reviewResults.Add([pscustomobject]@{
            finding = 'RV-H22-OBS-03'
            case = ('PINNED_' + $stateStatus.ToUpperInvariant())
            code = [string]$stateResult.code
            starts = $stateCase.starts.Count
        })
        if ($stateResult.code -ne 'CONTAINERS_READY' -or $stateCase.starts.Count -ne 0) {
            throw ('HOST22_OBS03_PREIMAGE_NOT_REPRODUCED:' + $stateStatus)
        }
    }

    $postgresExpected = New-Host22PreimageExpected
    $postgresExpected.service = 'postgres'
    $postgresExpected.container_name = 'postgres'
    $postgresExpected.container_id = 'f' * 64
    $postgresExpected.health_requirement = 'HEALTHY'
    foreach ($stateStatus in @('paused', 'restarting')) {
        $postgresObservation = New-Host22PreimageObservation -Id $postgresExpected.container_id -Name $postgresExpected.container_name -Running $true -StateStatus $stateStatus -Drill $false
        $postgresObservation.service = 'postgres'
        $postgresObservation.health_status = 'healthy'
        $postgresAdapters = [pscustomobject]@{
            ObserveContainer = { param($Definition, $Timeout) @($postgresObservation) }.GetNewClosure()
            StartExistingContainer = { param($FullId, $Timeout) throw 'UNEXPECTED_POSTGRES_START' }
            Sleep = { param($Milliseconds) }
        }
        $postgresResult = Invoke-StartupExistingContainerPhase -ExpectedContainers @($postgresExpected) -Adapters $postgresAdapters -CommandTimeoutMilliseconds 200 -StageTimeoutMilliseconds 1000 -PollMilliseconds 1
        $reviewResults.Add([pscustomobject]@{
            finding = 'RV-H22-OBS-03'
            case = ('POSTGRES_PINNED_' + $stateStatus.ToUpperInvariant() + '_STALE_HEALTHY')
            code = [string]$postgresResult.code
            starts = 0
        })
        if ($postgresResult.code -ne 'CONTAINERS_READY') {
            throw ('HOST22_OBS03_POSTGRES_PREIMAGE_NOT_REPRODUCED:' + $stateStatus)
        }
    }

    [pscustomobject]@{
        schema = 'NEXT_STABIL_HOST22_OBSERVATION_REVIEW_FAIL_BEFORE_V1'
        source = 'ed961d6980ebebe2e4d351319e2aa909437bc1ec'
        results = $reviewResults.ToArray()
        production_boundary_calls = 0
    } | ConvertTo-Json -Depth 8
    exit 0
}

# Parser matrix: the safe projection turns an absent Docker Health key into
# JSON null; null is not healthy, but it is valid for a RUNNING-only service.
$baseProjection = New-Host22Projection -Id ('6' * 64) -Name 'ai-lab-backend' -Running $true -StateStatus 'running' -Health $null
$parsed = ConvertFrom-StartupDockerContainerProjection -Json ($baseProjection | ConvertTo-Json -Depth 10 -Compress)
Assert-Host22 ($parsed.health_status -eq 'NOT_CONFIGURED' -and $parsed.running) 'missing/null Health is a valid NOT_CONFIGURED observation'
foreach ($health in @('healthy', 'starting', 'unhealthy')) {
    $projection = Copy-Host22Object $baseProjection
    $projection.state.health = $health
    $value = ConvertFrom-StartupDockerContainerProjection -Json ($projection | ConvertTo-Json -Depth 10 -Compress)
    Assert-Host22 ($value.health_status -eq $health) ('health status is preserved: ' + $health)
}
$projection = Copy-Host22Object $baseProjection
$projection.state.health = ''
Assert-Host22 ((ConvertFrom-StartupDockerContainerProjection -Json ($projection | ConvertTo-Json -Depth 10 -Compress)).health_status -eq 'UNKNOWN') 'missing Health.Status is UNKNOWN'
$projection.state.health = [pscustomobject]@{ unexpected = $true }
Assert-Host22 ((ConvertFrom-StartupDockerContainerProjection -Json ($projection | ConvertTo-Json -Depth 10 -Compress)).health_status -eq 'UNKNOWN') 'invalid Health type is UNKNOWN'
$projection = Copy-Host22Object $baseProjection
$projection.state = $null
$missingStateRefused = $false
try { [void](ConvertFrom-StartupDockerContainerProjection -Json ($projection | ConvertTo-Json -Depth 10 -Compress)) } catch { $missingStateRefused = $_.Exception.Message -match 'State was missing' }
Assert-Host22 $missingStateRefused 'missing State is refused'
$truncatedRefused = $false
try { [void](ConvertFrom-StartupDockerContainerProjection -Json '{"id":') } catch { $truncatedRefused = $_.Exception.Message -match 'not valid JSON' }
Assert-Host22 $truncatedRefused 'truncated JSON is refused'

# Real adapter path: exact inspect first, bounded same-role conflict scan, safe
# projection parser, common selection and identity validation.
$probeState = New-Host22AdapterState
$probeAdapters = New-RealStartupAdapters -Manifest (New-Host22AdapterManifest) -SystemBoundary (New-Host22SystemBoundary $probeState)
$probeObservations = @(& $probeAdapters.ObserveContainer $probeState.expected 5000)
$probeSelection = Select-StartupApprovedContainerObservation -Expected $probeState.expected -Observations $probeObservations
Assert-Host22 ($probeSelection.success -and @($probeSelection.ignored).Count -eq 4) ('real adapter classifies the four synthetic retained drills; actual=' + ($probeObservations | ConvertTo-Json -Depth 8 -Compress))

$state = New-Host22AdapterState
$result = Invoke-Host22AdapterPhase $state
Assert-Host22 ($result.code -eq 'CONTAINERS_READY' -and $state.starts.Count -eq 0) ('exact backend plus four retained stopped drills reaches readiness without starts; actual=' + ($result | ConvertTo-Json -Depth 8 -Compress) + ';starts=' + $state.starts.Count)
Assert-Host22 (@($result.events | Where-Object { $_.action -eq 'IGNORE_RETAINED_INACTIVE_DRILL' }).Count -eq 4) 'all four retained drills are accounted for'
Assert-Host22 ($state.calls[0] -like '--context desktop-linux-test inspect --type container*' -and $state.calls[0] -like ('*' + $state.expected.container_id)) 'adapter inspects the pinned full ID before conflict discovery'
Assert-Host22 ($state.captured_template -notmatch '\.State\.Health' -and $state.captured_template -match 'index \.State "Health"') 'adapter template does not dereference optional State.Health'

$state.selector_ids = @($state.selector_ids[4], $state.selector_ids[2], $state.selector_ids[0], $state.selector_ids[1], $state.selector_ids[3])
$reordered = Invoke-Host22AdapterPhase $state
Assert-Host22 ($reordered.code -eq 'CONTAINERS_READY' -and $state.starts.Count -eq 0) 'selector order never changes pinned selection'

foreach ($identityCase in @('name', 'project', 'service', 'image', 'digest', 'mount', 'port')) {
    $mismatch = New-Host22AdapterState
    $exactProjection = $mismatch.projections[$mismatch.expected.container_id]
    switch ($identityCase) {
        'name' { $exactProjection.name = '/foreign-backend' }
        'project' { $exactProjection.compose_project = 'foreign-project' }
        'service' { $exactProjection.compose_service = 'foreign-service' }
        'image' { $exactProjection.image_id = 'sha256:' + ('c' * 64) }
        'digest' { $mismatch.repo_digests = @('repo@sha256:' + ('c' * 64)) }
        'mount' { $exactProjection.mounts[0].Source = 'C:\synthetic\foreign' }
        'port' { $exactProjection.configured_ports['8000/tcp'][0].HostPort = '18001'; $exactProjection.active_ports['8000/tcp'][0].HostPort = '18001' }
    }
    $mismatchResult = Invoke-Host22AdapterPhase $mismatch
    Assert-Host22 ($mismatchResult.code -eq 'IDENTITY_MISMATCH' -and $mismatch.starts.Count -eq 0) ('identity mismatch blocks before start: ' + $identityCase)
}

$missing = New-Host22AdapterState
$missing.inspect_modes[$missing.expected.container_id] = 'NOT_FOUND'
$missing.selector_ids = @($missing.selector_ids | Where-Object { $_ -ne $missing.expected.container_id })
$missingResult = Invoke-Host22AdapterPhase $missing
Assert-Host22 ($missingResult.code -eq 'CONTROLLED_DEPLOY_REQUIRED' -and $missing.starts.Count -eq 0) 'missing pinned ID never adopts a same-role container'

$missingNonzero = New-Host22AdapterState
$missingNonzero.inspect_modes[$missingNonzero.expected.container_id] = 'NOT_FOUND_NONZERO'
$missingNonzero.selector_ids = @($missingNonzero.selector_ids | Where-Object { $_ -ne $missingNonzero.expected.container_id })
$missingNonzeroResult = Invoke-Host22AdapterPhase $missingNonzero
Assert-Host22 ($missingNonzeroResult.code -eq 'CONTROLLED_DEPLOY_REQUIRED' -and $missingNonzero.starts.Count -eq 0) 'native nonzero missing pinned ID is classified without adoption'

$timeout = New-Host22AdapterState
$timeout.inspect_modes[$timeout.expected.container_id] = 'TIMEOUT'
$timeoutRefused = $false
try { [void](Invoke-Host22AdapterPhase $timeout) } catch { $timeoutRefused = $_.Exception.Message -match 'NATIVE_READ_TIMED_OUT' }
Assert-Host22 ($timeoutRefused -and $timeout.starts.Count -eq 0) 'timeout remains unknown and does not start a container'

$nonzero = New-Host22AdapterState
$nonzero.inspect_modes[$nonzero.expected.container_id] = 'ERROR'
$nonzeroRefused = $false
try { [void](Invoke-Host22AdapterPhase $nonzero) } catch { $nonzeroRefused = $_.Exception.Message -match 'inspect failed: ERROR' }
Assert-Host22 ($nonzeroRefused -and $nonzero.starts.Count -eq 0) 'nonzero inspect remains an adapter error'

$truncated = New-Host22AdapterState
$truncated.inspect_modes[$truncated.expected.container_id] = 'TRUNCATED'
$truncatedAdapterRefused = $false
try { [void](Invoke-Host22AdapterPhase $truncated) } catch { $truncatedAdapterRefused = $_.Exception.Message -match 'not valid JSON' }
Assert-Host22 ($truncatedAdapterRefused -and $truncated.starts.Count -eq 0) 'truncated adapter stdout remains invalid'

foreach ($case in @('SELECTOR_STDOUT_TRUNCATED', 'INSPECT_STDOUT_TRUNCATED', 'EMPTY_SELECTOR_TRUNCATED', 'SELECTOR_STDERR_TRUNCATED', 'SELECTOR_METADATA_MISSING')) {
    $incomplete = New-Host22AdapterState
    $incomplete.selector_ids = @($incomplete.expected.container_id)
    $incomplete.projections[$incomplete.expected.container_id].state.running = $false
    $incomplete.projections[$incomplete.expected.container_id].state.status = 'exited'
    $incomplete.projections[$incomplete.expected.container_id].active_ports = [ordered]@{}
    switch ($case) {
        'SELECTOR_STDOUT_TRUNCATED' { $incomplete.selector_stdout_truncated = $true; $incomplete.selector_override = $incomplete.expected.container_id }
        'INSPECT_STDOUT_TRUNCATED' { $incomplete.inspect_modes[$incomplete.expected.container_id] = 'TRUNCATED_METADATA' }
        'EMPTY_SELECTOR_TRUNCATED' { $incomplete.selector_stdout_truncated = $true; $incomplete.selector_override = '' }
        'SELECTOR_STDERR_TRUNCATED' { $incomplete.selector_stderr_truncated = $true }
        'SELECTOR_METADATA_MISSING' { $incomplete.selector_metadata_missing = $true }
    }
    $incompleteRefused = $false
    try { [void](Invoke-Host22AdapterPhase -State $incomplete -CommandTimeoutMilliseconds 200 -StageTimeoutMilliseconds 5000) }
    catch {
        $incompleteRefused = if ($case -eq 'SELECTOR_METADATA_MISSING') {
            $_.Exception.Message -match 'NATIVE_READ_METADATA_MISSING'
        }
        else { $_.Exception.Message -match 'NATIVE_READ_OUTPUT_TRUNCATED' }
    }
    Assert-Host22 ($incompleteRefused -and $incomplete.starts.Count -eq 0) ('incomplete native read blocks before start: ' + $case)
}

$deadline = New-Host22AdapterState
$deadline.read_delay_ms = 60
$deadlineWatch = [System.Diagnostics.Stopwatch]::StartNew()
$deadlineResult = Invoke-Host22AdapterPhase -State $deadline -CommandTimeoutMilliseconds 200 -StageTimeoutMilliseconds 250
$deadlineWatch.Stop()
$deadlineBudgets = @($deadline.native_timeouts)
$strictlyDecreased = $false
for ($budgetIndex = 1; $budgetIndex -lt $deadlineBudgets.Count; $budgetIndex++) {
    if ($deadlineBudgets[$budgetIndex] -lt $deadlineBudgets[$budgetIndex - 1]) { $strictlyDecreased = $true; break }
}
Assert-Host22 ($deadlineResult.code -eq 'CONTAINER_OBSERVATION_DEADLINE_EXCEEDED' -and $deadline.starts.Count -eq 0) 'cumulative observation deadline blocks without start'
Assert-Host22 ($deadline.calls.Count -lt 7 -and $strictlyDecreased) ('remaining native budgets stop further reads; calls=' + $deadline.calls.Count + ';budgets=' + ($deadlineBudgets -join ','))

foreach ($stateStatus in @('paused', 'restarting', 'removing', 'dead')) {
    $pinnedState = New-Host22AdapterState
    $pinnedState.projections[$pinnedState.expected.container_id].state.status = $stateStatus
    $pinnedState.projections[$pinnedState.expected.container_id].state.running = ($stateStatus -ne 'dead')
    $pinnedStateResult = Invoke-Host22AdapterPhase -State $pinnedState -CommandTimeoutMilliseconds 200 -StageTimeoutMilliseconds 5000
    Assert-Host22 ($pinnedStateResult.code -eq 'CONTAINER_STATE_NOT_READY' -and $pinnedState.starts.Count -eq 0) ('pinned non-running state never becomes ready: ' + $stateStatus)
}
$unknownPinned = New-Host22AdapterState
$unknownPinned.projections[$unknownPinned.expected.container_id].state.status = 'unknown'
$unknownPinned.projections[$unknownPinned.expected.container_id].state.running = $true
$unknownPinnedRefused = $false
try { [void](Invoke-Host22AdapterPhase -State $unknownPinned -CommandTimeoutMilliseconds 200 -StageTimeoutMilliseconds 5000) }
catch { $unknownPinnedRefused = $_.Exception.Message -match 'State.Status was unknown' }
Assert-Host22 ($unknownPinnedRefused -and $unknownPinned.starts.Count -eq 0) 'unknown pinned state is refused before start'

foreach ($status in @('running', 'paused', 'restarting')) {
    $conflict = New-Host22AdapterState
    $foreignId = '8' * 64
    $foreign = New-Host22Projection -Id $foreignId -Name 'foreign-backend' -Running ($status -ne 'restarting') -StateStatus $status -Health $null
    if ($status -eq 'restarting') { $foreign.state.running = $true }
    $conflict.projections[$foreignId] = $foreign
    $conflict.selector_ids += $foreignId
    $conflictResult = Invoke-Host22AdapterPhase $conflict
    Assert-Host22 ($conflictResult.code -eq 'CONTAINER_ROLE_CONFLICT' -and $conflict.starts.Count -eq 0) ('same-role ' + $status + ' competitor blocks')
}

$unknown = New-Host22AdapterState
$unknownId = '9' * 64
$unknownProjection = New-Host22Projection -Id $unknownId -Name 'foreign-backend' -Running $false -StateStatus 'exited' -Health $null -Drill $true
[void]$unknownProjection.state.Remove('status')
$unknown.projections[$unknownId] = $unknownProjection
$unknown.selector_ids += $unknownId
$unknownRefused = $false
try { [void](Invoke-Host22AdapterPhase $unknown) } catch { $unknownRefused = $_.Exception.Message -match 'State field missing' }
Assert-Host22 ($unknownRefused -and $unknown.starts.Count -eq 0) 'unreadable competitor is UNKNOWN and blocks'

$arbitraryStopped = New-Host22AdapterState
$stoppedId = 'a' * 64
$arbitraryStopped.projections[$stoppedId] = New-Host22Projection -Id $stoppedId -Name 'arbitrary-stopped-backend' -Running $false -StateStatus 'exited' -Health $null -Drill $true
$arbitraryStopped.selector_ids += $stoppedId
$arbitraryResult = Invoke-Host22AdapterPhase $arbitraryStopped
Assert-Host22 ($arbitraryResult.code -eq 'CONTAINER_ROLE_CONFLICT' -and $arbitraryStopped.starts.Count -eq 0) 'arbitrary stopped same-role container is not silently ignored'

$stoppedPinned = New-Host22AdapterState
$stoppedPinned.projections[$stoppedPinned.expected.container_id].state.running = $false
$stoppedPinned.projections[$stoppedPinned.expected.container_id].state.status = 'exited'
$stoppedPinned.projections[$stoppedPinned.expected.container_id].active_ports = [ordered]@{}
$stoppedResult = Invoke-Host22AdapterPhase $stoppedPinned
Assert-Host22 ($stoppedResult.code -eq 'CONTAINERS_READY' -and $stoppedPinned.starts.Count -eq 1 -and $stoppedPinned.starts[0] -eq $stoppedPinned.expected.container_id) 'cold synthetic start targets only the pinned full ID and rechecks the same selection'

$postgres = New-Host22PreimageExpected
$postgres.service = 'postgres'
$postgres.container_name = 'postgres'
$postgres.container_id = 'f' * 64
$postgres.health_requirement = 'HEALTHY'
$postgresObserved = New-Host22PreimageObservation -Id $postgres.container_id -Name $postgres.container_name -Running $true -StateStatus 'running' -Drill $false
$postgresObserved.service = 'postgres'
$postgresObserved.health_status = 'NOT_CONFIGURED'
$postgresAdapters = [pscustomobject]@{
    ObserveContainer = { param($Definition) @($postgresObserved) }.GetNewClosure()
    StartExistingContainer = { param($FullId, $Timeout) throw 'UNEXPECTED_POSTGRES_START' }
    Sleep = { param($Milliseconds) }
}
$postgresResult = Invoke-StartupExistingContainerPhase -ExpectedContainers @($postgres) -Adapters $postgresAdapters -CommandTimeoutMilliseconds 20 -StageTimeoutMilliseconds 50 -PollMilliseconds 1
Assert-Host22 ($postgresResult.code -eq 'CONTAINER_HEALTH_UNKNOWN') 'PostgreSQL without configured/healthy status never becomes healthy'
foreach ($healthCase in @('healthy', 'starting', 'unhealthy', 'UNKNOWN')) {
    $postgresObserved.health_status = $healthCase
    $healthResult = Invoke-StartupExistingContainerPhase -ExpectedContainers @($postgres) -Adapters $postgresAdapters -CommandTimeoutMilliseconds 20 -StageTimeoutMilliseconds 50 -PollMilliseconds 1
    if ($healthCase -eq 'healthy') {
        Assert-Host22 ($healthResult.code -eq 'CONTAINERS_READY') 'PostgreSQL HEALTHY accepts only an observed healthy state'
    }
    else {
        Assert-Host22 ($healthResult.code -eq 'CONTAINER_HEALTH_UNKNOWN') ('PostgreSQL health never degrades to RUNNING: ' + $healthCase)
    }
}

foreach ($stateStatus in @('paused', 'restarting')) {
    $postgresObserved.state_status = $stateStatus
    $postgresObserved.running = $true
    $postgresObserved.health_status = 'healthy'
    $staleHealthResult = Invoke-StartupExistingContainerPhase -ExpectedContainers @($postgres) -Adapters $postgresAdapters -CommandTimeoutMilliseconds 20 -StageTimeoutMilliseconds 50 -PollMilliseconds 1
    Assert-Host22 ($staleHealthResult.code -eq 'CONTAINER_STATE_NOT_READY') ('PostgreSQL stale healthy never overrides pinned state: ' + $stateStatus)
}

Write-Output ('HOST22_CONTAINER_OBSERVATION_TEST_PASS assertions={0} production_boundary_calls=0' -f $script:Assertions)
