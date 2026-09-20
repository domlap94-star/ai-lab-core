[CmdletBinding()]
param(
    [switch]$PreimageEvidence,
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
        starts = New-Object System.Collections.Generic.List[string]
        captured_template = ''
        repo_digests = @('repo@sha256:' + ('b' * 64))
    }
}

function New-Host22SystemBoundary {
    param([hashtable]$State)
    $invokeNative = {
        param($FilePath, $Arguments, $Timeout, $MaximumOutput)
        $joined = @($Arguments) -join ' '
        $State.calls.Add($joined)
        if ($joined -like '--context desktop-linux-test inspect --type container --format*') {
            $id = [string]$Arguments[-1]
            $State.captured_template = [string]$Arguments[-2]
            $mode = if ($State.inspect_modes.ContainsKey($id)) { [string]$State.inspect_modes[$id] } else { 'SUCCESS' }
            if ($mode -eq 'TIMEOUT') { return [pscustomobject]@{ status = 'TIMEOUT'; stdout = ''; stderr = ''; process_left_running = $false } }
            if ($mode -eq 'NOT_FOUND') { return [pscustomobject]@{ status = 'ERROR'; stdout = ''; stderr = 'Error: No such container: synthetic'; process_left_running = $false } }
            if ($mode -eq 'NOT_FOUND_NONZERO') { return [pscustomobject]@{ status = 'NONZERO_EXIT'; stdout = ''; stderr = 'Error response from daemon: No such container: synthetic'; process_left_running = $false } }
            if ($mode -eq 'ERROR') { return [pscustomobject]@{ status = 'ERROR'; stdout = ''; stderr = 'synthetic access denied'; process_left_running = $false } }
            if ($mode -eq 'TRUNCATED') { return [pscustomobject]@{ status = 'SUCCESS'; stdout = '{"id":'; stderr = ''; process_left_running = $false } }
            if (-not $State.projections.ContainsKey($id)) { return [pscustomobject]@{ status = 'ERROR'; stdout = ''; stderr = 'Error: No such container: synthetic'; process_left_running = $false } }
            return [pscustomobject]@{ status = 'SUCCESS'; stdout = ($State.projections[$id] | ConvertTo-Json -Depth 10 -Compress); stderr = ''; process_left_running = $false }
        }
        if ($joined -like '--context desktop-linux-test container ls --all --no-trunc*') {
            return [pscustomobject]@{ status = 'SUCCESS'; stdout = (@($State.selector_ids) -join "`r`n"); stderr = ''; process_left_running = $false }
        }
        if ($joined -like '--context desktop-linux-test image inspect*') {
            return [pscustomobject]@{ status = 'SUCCESS'; stdout = (@($State.repo_digests) | ConvertTo-Json -Compress); stderr = ''; process_left_running = $false }
        }
        if ($joined -like '--context desktop-linux-test start*') {
            $id = [string]$Arguments[-1]
            $State.starts.Add($id)
            if ($State.projections.ContainsKey($id)) {
                $State.projections[$id].state.running = $true
                $State.projections[$id].state.status = 'running'
                $State.projections[$id].active_ports = [ordered]@{ '8000/tcp' = @([ordered]@{ HostIp = '127.0.0.1'; HostPort = '18000' }) }
            }
            return [pscustomobject]@{ status = 'SUCCESS'; stdout = $id; stderr = ''; process_left_running = $false }
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
    param([hashtable]$State)
    $adapters = New-RealStartupAdapters -Manifest (New-Host22AdapterManifest) -SystemBoundary (New-Host22SystemBoundary $State)
    foreach ($adapterName in @('ObserveContainer', 'StartExistingContainer', 'Sleep')) {
        if (-not ((Get-StartupProperty -InputObject $adapters -Name $adapterName) -is [scriptblock])) {
            throw ('HOST22_ADAPTER_NOT_SCRIPTBLOCK:' + $adapterName + ':' + (Get-StartupProperty -InputObject $adapters -Name $adapterName).GetType().FullName)
        }
    }
    try {
        return Invoke-StartupExistingContainerPhase -ExpectedContainers @($State.expected) -Adapters $adapters -CommandTimeoutMilliseconds 100 -StageTimeoutMilliseconds 20 -PollMilliseconds 1
    }
    catch {
        throw ('HOST22_PHASE_EXCEPTION:' + $_.Exception.Message + ';STACK=' + $_.ScriptStackTrace)
    }
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
$probeObservations = @(& $probeAdapters.ObserveContainer $probeState.expected)
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
try { [void](Invoke-Host22AdapterPhase $timeout) } catch { $timeoutRefused = $_.Exception.Message -match 'inspect failed: TIMEOUT' }
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
$postgresResult = Invoke-StartupExistingContainerPhase -ExpectedContainers @($postgres) -Adapters $postgresAdapters -CommandTimeoutMilliseconds 20 -StageTimeoutMilliseconds 2 -PollMilliseconds 1
Assert-Host22 ($postgresResult.code -eq 'CONTAINER_HEALTH_UNKNOWN') 'PostgreSQL without configured/healthy status never becomes healthy'
foreach ($healthCase in @('healthy', 'starting', 'unhealthy', 'UNKNOWN')) {
    $postgresObserved.health_status = $healthCase
    $healthResult = Invoke-StartupExistingContainerPhase -ExpectedContainers @($postgres) -Adapters $postgresAdapters -CommandTimeoutMilliseconds 20 -StageTimeoutMilliseconds 2 -PollMilliseconds 1
    if ($healthCase -eq 'healthy') {
        Assert-Host22 ($healthResult.code -eq 'CONTAINERS_READY') 'PostgreSQL HEALTHY accepts only an observed healthy state'
    }
    else {
        Assert-Host22 ($healthResult.code -eq 'CONTAINER_HEALTH_UNKNOWN') ('PostgreSQL health never degrades to RUNNING: ' + $healthCase)
    }
}

Write-Output ('HOST22_CONTAINER_OBSERVATION_TEST_PASS assertions={0} production_boundary_calls=0' -f $script:Assertions)
