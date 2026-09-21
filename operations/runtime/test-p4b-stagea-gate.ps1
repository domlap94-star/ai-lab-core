[CmdletBinding()]
param(
    [string]$CollectorPath = 'C:\Users\domai\AppData\Local\Temp\P4B-NUP-EXEC-01\n1\capture-four-tasks.ps1',
    [string]$BaselineDirectory = 'C:\ai-lab-core-staging\recovery\P4B-FIN-01\out\run01\after-tasks',
    [string]$TestRoot = 'C:\Users\domai\AppData\Local\Temp\P4B-NUP-EXEC-01\n1\tests\stagea-fixtures-01'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$script:Assertions = 0
$script:ChildProcesses = 0
$utf8 = New-Object Text.UTF8Encoding($false)

function Assert-True {
    param([bool]$Condition,[string]$Message)
    $script:Assertions++
    if (-not $Condition) { throw ('ASSERT_TRUE_FAILED:' + $Message) }
}

function Assert-Equal {
    param($Expected,$Actual,[string]$Message)
    $script:Assertions++
    if ([string]$Expected -cne [string]$Actual) {
        throw ('ASSERT_EQUAL_FAILED:{0}:expected={1}:actual={2}' -f $Message,$Expected,$Actual)
    }
}

function Write-TestJson {
    param([string]$Path,$Value)
    [IO.File]::WriteAllText($Path,(($Value | ConvertTo-Json -Depth 30) + "`n"),$utf8)
}

function New-ObservedResponse {
    param([string]$Name,[string]$Xml,[switch]$Incomplete)
    $payload = if ($Incomplete) {
        [ordered]@{task_name=$Name;task_path='\';state='Ready';enabled=$true;xml=$null}
    }
    else {
        [ordered]@{task_name=$Name;task_path='\';state='Ready';enabled=$true;xml=$Xml;xml_text_encoding='TEST_UTF8'}
    }
    return [ordered]@{schema='NEXT_STABIL_P4B_STAGEA_TASK_CAPTURE_BOUNDARY_V1';operation='READ_EXACT_TASK_DEFINITION';selector=$Name;started_utc='2026-09-21T10:00:00.0000000Z';finished_utc='2026-09-21T10:00:00.0100000Z';read_status='OBSERVED';payload=$payload;error_id=$null;error_type=$null}
}

function New-ErrorResponse {
    param([string]$Name,[string]$Status,[string]$ErrorId)
    return [ordered]@{schema='NEXT_STABIL_P4B_STAGEA_TASK_CAPTURE_BOUNDARY_V1';operation='READ_EXACT_TASK_DEFINITION';selector=$Name;started_utc='2026-09-21T10:00:00.0000000Z';finished_utc='2026-09-21T10:00:00.0100000Z';read_status=$Status;payload=$null;error_id=$ErrorId;error_type='System.UnauthorizedAccessException'}
}

function ConvertTo-XmlEscaped {
    param([AllowEmptyString()][string]$Value)
    return [Security.SecurityElement]::Escape($Value)
}

function New-TestTaskXml {
    param([string]$Arguments,[string]$TriggersXml='')
    $escapedArguments = ConvertTo-XmlEscaped $Arguments
    return @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Principals><Principal id="Author"><UserId>S-1-5-21-1</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Triggers>$TriggersXml</Triggers>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><Enabled>true</Enabled><ExecutionTimeLimit>PT15M</ExecutionTimeLimit></Settings>
  <Actions Context="Author"><Exec><Command>C:\Program Files\nodejs\node.exe</Command><Arguments>$escapedArguments</Arguments><WorkingDirectory>C:\ai-lab-core\gateway</WorkingDirectory></Exec></Actions>
</Task>
"@
}

function Initialize-Case {
    param([string]$Name)
    $caseRoot = Join-Path $TestRoot $Name
    if (Test-Path -LiteralPath $caseRoot) { throw ('CASE_COLLISION:' + $Name) }
    $fixture = Join-Path $caseRoot 'fixture'
    $output = Join-Path $caseRoot 'output'
    [void](New-Item -ItemType Directory -Path $fixture)
    [void](New-Item -ItemType Directory -Path $output)
    return [pscustomobject]@{Root=$caseRoot;Fixture=$fixture;Output=$output}
}

function Invoke-FixtureCase {
    param($Case)
    $powershell = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
    $captured = @(& $powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $CollectorPath -Mode Fixture -OutputDirectory $Case.Output -FixtureDirectory $Case.Fixture -BaselineDirectory $BaselineDirectory -TimeoutSeconds 2 2>&1)
    $script:ChildProcesses++
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { throw ('COLLECTOR_FAILED:{0}:{1}' -f $exitCode,($captured -join '|')) }
    $resultPath = Join-Path $Case.Output 'result.json'
    Assert-True (Test-Path -LiteralPath $resultPath -PathType Leaf) 'result file exists'
    return (Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json)
}

$definitions = @(
    [pscustomobject]@{name='NEXT Stabil - Docker Desktop';stem='d01';baseline='NEXT_Stabil_-_Docker_Desktop.xml'},
    [pscustomobject]@{name='NEXT Stabil - Public Gateway';stem='d03';baseline='NEXT_Stabil_-_Public_Gateway.xml'},
    [pscustomobject]@{name='NEXT Stabil - Private Gateway';stem='d04';baseline='NEXT_Stabil_-_Private_Gateway.xml'},
    [pscustomobject]@{name='NEXT Stabil - Supervisor';stem='d05';baseline='NEXT_Stabil_-_Supervisor.xml'}
)

if (-not (Test-Path -LiteralPath $CollectorPath -PathType Leaf)) { throw 'COLLECTOR_MISSING' }
if (-not (Test-Path -LiteralPath $BaselineDirectory -PathType Container)) { throw 'BASELINE_DIRECTORY_MISSING' }
if (Test-Path -LiteralPath $TestRoot) { throw 'TEST_ROOT_COLLISION' }
[void](New-Item -ItemType Directory -Path $TestRoot)
Assert-Equal 4 $definitions.Count 'definition count'

$complete = Initialize-Case 'complete'
foreach ($definition in $definitions) {
    $xml = [IO.File]::ReadAllText((Join-Path $BaselineDirectory $definition.baseline),$utf8)
    Write-TestJson (Join-Path $complete.Fixture ($definition.stem + '.response.json')) (New-ObservedResponse -Name $definition.name -Xml $xml)
}
$completeResult = Invoke-FixtureCase $complete
Assert-Equal 'COMPLETE' $completeResult.status 'complete status'
Assert-Equal 4 $completeResult.observed_count 'complete observed count'
Assert-Equal 4 $completeResult.normalized_match_count 'complete normalized count'
Assert-True ([bool]$completeResult.all_workers_accounted) 'complete workers accounted'

$projection = Initialize-Case 'projection'
$projectionXml = @{
    d01 = New-TestTaskXml -Arguments 'desktop'
    d03 = New-TestTaskXml -Arguments '"C:\ai-lab-core\gateway\public_gateway.js"' -TriggersXml '<LogonTrigger><Enabled>true</Enabled><UserId>domai</UserId></LogonTrigger>'
    d04 = New-TestTaskXml -Arguments '"C:\ai-lab-core\gateway\private_gateway.js"'
    d05 = New-TestTaskXml -Arguments 'C:\ai-lab-core\gateway\supervisor.js'
}
foreach ($definition in $definitions) {
    Write-TestJson (Join-Path $projection.Fixture ($definition.stem + '.response.json')) (New-ObservedResponse -Name $definition.name -Xml ([string]$projectionXml[$definition.stem]))
}
$projectionResult = Invoke-FixtureCase $projection
$projectionByName = @{}; foreach ($item in @($projectionResult.items)) { $projectionByName[[string]$item.task_name] = $item }
Assert-Equal 0 $projectionByName['NEXT Stabil - Docker Desktop'].trigger_count 'empty triggers are empty'
Assert-Equal 1 $projectionByName['NEXT Stabil - Public Gateway'].trigger_count 'logon trigger count'
Assert-Equal 'LogonTrigger' $projectionByName['NEXT Stabil - Public Gateway'].triggers[0].type 'logon trigger type'
Assert-Equal '"C:\ai-lab-core\gateway\private_gateway.js"' $projectionByName['NEXT Stabil - Private Gateway'].actions[0].arguments 'quoted args preserved'
Assert-Equal 'C:\ai-lab-core\gateway\supervisor.js' $projectionByName['NEXT Stabil - Supervisor'].actions[0].arguments 'unquoted args preserved'

$lineEndings = Initialize-Case 'line-endings'
foreach ($definition in $definitions) {
    $baseline = [IO.File]::ReadAllText((Join-Path $BaselineDirectory $definition.baseline),$utf8)
    $xml = $baseline.Replace("`r`n","`n").Replace("`r","`n") + "`n`n"
    Write-TestJson (Join-Path $lineEndings.Fixture ($definition.stem + '.response.json')) (New-ObservedResponse -Name $definition.name -Xml $xml)
}
$lineResult = Invoke-FixtureCase $lineEndings
Assert-Equal 4 $lineResult.normalized_match_count 'line ending normalized count'
Assert-Equal 0 @($lineResult.items | Where-Object raw_match).Count 'raw differs after trailing newlines'

$partial = Initialize-Case 'partial'
foreach ($definition in $definitions) {
    $fixturePath = Join-Path $partial.Fixture ($definition.stem + '.response.json')
    if ($definition.stem -eq 'd01') {
        Write-TestJson $fixturePath (New-ErrorResponse -Name $definition.name -Status 'ACCESS_DENIED' -ErrorId 'AccessDenied')
    }
    elseif ($definition.stem -eq 'd03') {
        Write-TestJson $fixturePath (New-ObservedResponse -Name $definition.name -Incomplete)
    }
    else {
        $xml = [IO.File]::ReadAllText((Join-Path $BaselineDirectory $definition.baseline),$utf8)
        Write-TestJson $fixturePath (New-ObservedResponse -Name $definition.name -Xml $xml)
    }
}
$partialResult = Invoke-FixtureCase $partial
$partialByName = @{}; foreach ($item in @($partialResult.items)) { $partialByName[[string]$item.task_name] = $item }
Assert-Equal 'PARTIAL' $partialResult.status 'partial status'
Assert-Equal 2 $partialResult.observed_count 'partial observed count'
Assert-Equal 'ACCESS_DENIED' $partialByName['NEXT Stabil - Docker Desktop'].read_status 'access denied preserved'
Assert-Equal 'INVALID_PAYLOAD' $partialByName['NEXT Stabil - Public Gateway'].read_status 'incomplete payload rejected'
Assert-Equal 'NOT_AVAILABLE' $partialByName['NEXT Stabil - Public Gateway'].projection_status 'no invented projection'
Assert-True (-not (Test-Path -LiteralPath (Join-Path $partial.Output 'd01.xml'))) 'no XML for access denied'
Assert-True (-not (Test-Path -LiteralPath (Join-Path $partial.Output 'd03.xml'))) 'no XML for incomplete payload'
Assert-True ([bool]$partialResult.all_workers_accounted) 'partial workers accounted'

. (Join-Path $PSScriptRoot 'startup-runtime.ps1')
$expectedMounts = @(
    [pscustomobject]@{source='C:\ai-lab-core\backend';destination='/app';type='bind';read_only=$true},
    [pscustomobject]@{source='C:\ai-lab-core\data';destination='/data';type='bind';read_only=$false}
)
$expectedContainer = [pscustomobject]@{container_name='ai-lab-backend';compose_project='ai-lab-core';service='backend';container_id=('a'*64);image_id='sha256:image';image_identity_mode='REPO_DIGEST';repo_digest='repo@sha256:digest';mounts=$expectedMounts;ports=@()}
function New-ObservedBackend {
    param([object[]]$Mounts)
    return [pscustomobject]@{container_name='ai-lab-backend';compose_project='ai-lab-core';service='backend';full_id=('a'*64);image_id='sha256:image';repo_digest='repo@sha256:digest';mounts=$Mounts;configured_ports=@();active_ports=@();running=$false;state_status='exited'}
}
$slashMounts = @(
    [pscustomobject]@{source='C:/ai-lab-core/backend';destination='/app';type='bind';read_only=$true},
    [pscustomobject]@{source='C:/ai-lab-core/data';destination='/data';type='bind';read_only=$false}
)
Assert-True (Test-ApprovedContainerIdentity -Expected $expectedContainer -Observed (New-ObservedBackend $slashMounts)).valid 'Windows bind slash representation accepted'
$wrongSource = @($slashMounts | ForEach-Object { $_.PSObject.Copy() }); $wrongSource[0].source='C:/ai-lab-core/backend-other'
Assert-True (-not (Test-ApprovedContainerIdentity -Expected $expectedContainer -Observed (New-ObservedBackend $wrongSource)).valid) 'different bind source refused'
$wrongDestination = @($slashMounts | ForEach-Object { $_.PSObject.Copy() }); $wrongDestination[0].destination='/app2'
Assert-True (-not (Test-ApprovedContainerIdentity -Expected $expectedContainer -Observed (New-ObservedBackend $wrongDestination)).valid) 'different Linux destination refused'
$wrongMode = @($slashMounts | ForEach-Object { $_.PSObject.Copy() }); $wrongMode[1].read_only=$true
Assert-True (-not (Test-ApprovedContainerIdentity -Expected $expectedContainer -Observed (New-ObservedBackend $wrongMode)).valid) 'different mount mode refused'
Assert-True ((ConvertTo-StartupComparableMount ([pscustomobject]@{source='qdrant_storage';destination='/qdrant/storage';type='volume';read_only=$false})) -cne (ConvertTo-StartupComparableMount ([pscustomobject]@{source='qdrant/storage';destination='/qdrant/storage';type='volume';read_only=$false}))) 'volume source is not slash-normalized'

. (Join-Path $PSScriptRoot 'start-host-services.ps1') -DefinitionOnly
$expectedHost = [pscustomobject]@{
    name='public_gateway';launch_kind='TASK';task_name='NEXT Stabil - Public Gateway';task_path='\'
    executable='C:\Program Files\nodejs\node.exe';arguments=@('operations/gateway/public_web_server.cjs')
    working_directory='C:\ai-lab-core';listener_host='127.0.0.1';listener_port=8789
}
$argumentParser = ${function:ConvertFrom-StartupWindowsCommandLine}
Assert-True (Test-StartupTaskActionIdentity -ExpectedExecutable $expectedHost.executable -ExpectedArguments $expectedHost.arguments -ExpectedWorkingDirectory $expectedHost.working_directory -ObservedExecutable $expectedHost.executable -ObservedArgumentString 'operations/gateway/public_web_server.cjs' -ObservedWorkingDirectory $expectedHost.working_directory -ApprovedRoot 'C:\ai-lab-core' -ArgumentParser $argumentParser) 'relative script accepted'
Assert-True (Test-StartupTaskActionIdentity -ExpectedExecutable $expectedHost.executable -ExpectedArguments $expectedHost.arguments -ExpectedWorkingDirectory $expectedHost.working_directory -ObservedExecutable $expectedHost.executable -ObservedArgumentString '"C:\ai-lab-core\operations\gateway\public_web_server.cjs"' -ObservedWorkingDirectory $expectedHost.working_directory -ApprovedRoot 'C:\ai-lab-core' -ArgumentParser $argumentParser) 'absolute quoted same script accepted'
Assert-True (-not (Test-StartupTaskActionIdentity -ExpectedExecutable $expectedHost.executable -ExpectedArguments $expectedHost.arguments -ExpectedWorkingDirectory $expectedHost.working_directory -ObservedExecutable $expectedHost.executable -ObservedArgumentString '"C:\ai-lab-core\operations\gateway\other.cjs"' -ObservedWorkingDirectory $expectedHost.working_directory -ApprovedRoot 'C:\ai-lab-core' -ArgumentParser $argumentParser)) 'different script refused'
Assert-True (-not (Test-StartupTaskActionIdentity -ExpectedExecutable $expectedHost.executable -ExpectedArguments $expectedHost.arguments -ExpectedWorkingDirectory $expectedHost.working_directory -ObservedExecutable $expectedHost.executable -ObservedArgumentString '"C:\ai-lab-core\operations\gateway\public_web_server.cjs" --extra' -ObservedWorkingDirectory $expectedHost.working_directory -ApprovedRoot 'C:\ai-lab-core' -ArgumentParser $argumentParser)) 'extra argument refused'
Assert-True (-not (Test-StartupTaskActionIdentity -ExpectedExecutable $expectedHost.executable -ExpectedArguments $expectedHost.arguments -ExpectedWorkingDirectory $expectedHost.working_directory -ObservedExecutable $expectedHost.executable -ObservedArgumentString '"C:\ai-lab-core\operations\gateway\public_web_server.cjs"' -ObservedWorkingDirectory 'C:\ai-lab-core\other' -ApprovedRoot 'C:\ai-lab-core' -ArgumentParser $argumentParser)) 'different CWD refused'
Assert-True (-not (Test-StartupTaskActionIdentity -ExpectedExecutable $expectedHost.executable -ExpectedArguments $expectedHost.arguments -ExpectedWorkingDirectory $expectedHost.working_directory -ObservedExecutable $expectedHost.executable -ObservedArgumentString '"C:\ai-lab-core-recovery\operations\gateway\public_web_server.cjs"' -ObservedWorkingDirectory $expectedHost.working_directory -ApprovedRoot 'C:\ai-lab-core' -ArgumentParser $argumentParser)) 'external root refused'

function New-TestHostBoundary {
    param([string]$Arguments)
    $state = [pscustomobject]@{task=[pscustomobject]@{Actions=@([pscustomobject]@{Execute='C:\Program Files\nodejs\node.exe';Arguments=$Arguments;WorkingDirectory='C:\ai-lab-core'})}}
    return [pscustomobject]@{
        State=$state
        GetTask={param($Expected,$State) $State.task}
        GetProcesses={param($Expected,$State) @()}
        GetListeners={param($Expected,$State) @()}
        StartTask={param($Expected,$State) throw 'START_NOT_ALLOWED_IN_OBSERVE_TEST'}
    }
}
$realWorkerMatch = Invoke-BoundedStartupHostOperation -Operation OBSERVE -Expected $expectedHost -TimeoutMilliseconds 2000 -MaximumOutputCharacters 16384 -SyntheticCommandBoundary (New-TestHostBoundary '"C:\ai-lab-core\operations\gateway\public_web_server.cjs"')
Assert-Equal 'SUCCESS' $realWorkerMatch.status 'real worker envelope'
Assert-Equal 'SUCCESS' $realWorkerMatch.result.status 'real worker accepts exact absolute script'
Assert-Equal 'GET_TASK,GET_PROCESSES,GET_LISTENERS' (@($realWorkerMatch.result.lower_boundary_calls) -join ',') 'real worker exercised lower boundaries'
$realWorkerMismatch = Invoke-BoundedStartupHostOperation -Operation OBSERVE -Expected $expectedHost -TimeoutMilliseconds 2000 -MaximumOutputCharacters 16384 -SyntheticCommandBoundary (New-TestHostBoundary '"C:\ai-lab-core\operations\gateway\public_web_server.cjs" --extra')
Assert-Equal 'SUCCESS' $realWorkerMismatch.status 'real worker mismatch envelope'
Assert-Equal 'IDENTITY_MISMATCH' $realWorkerMismatch.result.status 'real worker refuses extra argument'
Assert-Equal 'GET_TASK' (@($realWorkerMismatch.result.lower_boundary_calls) -join ',') 'real worker stops before other boundaries on mismatch'

[pscustomobject][ordered]@{
    status='PASS'
    assertions=$script:Assertions
    collector_fixture_cases=4
    child_processes=$script:ChildProcesses
    all_child_processes_accounted=$true
    production_boundaries=0
    mount_normalization='PASS'
    task_action_normalization='PASS'
} | ConvertTo-Json -Compress
