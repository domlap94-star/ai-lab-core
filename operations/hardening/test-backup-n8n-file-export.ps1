[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$script:Assertions = 0
function Assert-N8nExportTest {
    param([bool]$Condition, [string]$Message)
    $script:Assertions++
    if (-not $Condition) { throw "ASSERTION_FAILED:$Message" }
}

$runner = Join-Path $PSScriptRoot 'backup-production.ps1'
$tokens = $null
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($runner, [ref]$tokens, [ref]$errors)
Assert-N8nExportTest (@($errors).Count -eq 0) 'runner parses in Windows PowerShell 5.1'
$requiredFunctions = @(
    'ConvertTo-NativeArgumentString', 'Get-BoundedQdrantDiagnosticText', 'Write-BinaryTransportEvidence',
    'Get-TextSha256', 'Invoke-NsR26NativeProcessCapture', 'Test-NsR26N8nExportDocument',
    'Invoke-NsR26N8nExportToArtifact'
)
foreach ($name in $requiredFunctions) {
    $definition = @($ast.FindAll({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name
    }, $true))
    Assert-N8nExportTest ($definition.Count -eq 1) "one definition for $name"
    Invoke-Expression $definition[0].Extent.Text
}

$root = Join-Path $env:LOCALAPPDATA ('Temp\NEXT-STABIL-N8N-FILE-EXPORT-' + [Guid]::NewGuid().ToString('N'))
$fakeRoot = Join-Path $root 'container'
$fakeDocker = Join-Path $root 'fake-docker.ps1'
$powershell51 = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
try {
    New-Item -ItemType Directory -Path $fakeRoot -Force | Out-Null
    [IO.File]::WriteAllText($fakeDocker, @'
$ErrorActionPreference='Stop'
$items=@($args)
$root=$env:NS_R26_N8N_TEST_ROOT
$mode=$env:NS_R26_N8N_TEST_MODE
function HostPath([string]$containerPath){Join-Path $root ([IO.Path]::GetFileName($containerPath))}
if($items[0]-eq'exec' -and $items[2]-eq'test'){
    $path=HostPath $items[5]
    if(Test-Path -LiteralPath $path){exit 1}else{exit 0}
}
if($items[0]-eq'exec' -and $items[2]-eq'rm'){
    $path=HostPath $items[5]
    if($mode-eq'cleanup_fail'){[Console]::Error.WriteLine('synthetic cleanup failure');exit 9}
    Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    exit 0
}
if($items[0]-eq'exec' -and $items[2]-eq'n8n'){
    if($mode-eq'timeout'){Start-Sleep -Seconds 4;exit 0}
    if($mode-eq'nonzero'){[Console]::Error.WriteLine('synthetic process failure');exit 7}
    $exportType=if($items[3]-eq'export:workflow'){'workflow'}else{'credentials'}
    $outputArg=@($items|Where-Object{$_-like'--output=*'})[0]
    if([string]::IsNullOrWhiteSpace($outputArg)){[Console]::WriteLine('INFO '+ '[{"id":"old"}]');exit 0}
    $containerPath=$outputArg.Substring(9)
    $path=HostPath $containerPath
    if($mode-ne'missing'){
        $json=if($exportType-eq'workflow'){
            switch($mode){
                'invalid' {'[not-json'}
                'object' {'{"id":"wf-1","name":"Hidden","nodes":[],"connections":{}}'}
                'missing_nodes' {'[{"id":"wf-1","name":"Hidden","connections":{}}]'}
                'duplicate' {'[{"id":"wf-1","name":"Hidden","nodes":[],"connections":{}},{"id":"wf-1","name":"Hidden2","nodes":[],"connections":{}}]'}
                'empty' {''}
                'oversized' {'[' + (' ' * 512) + ']'}
                default {'[{"id":"wf-1","name":"Hidden","nodes":[],"connections":{}}]'}
            }
        }else{
            switch($mode){
                'invalid' {'[not-json'}
                'object' {'{"id":"cred-1","name":"Hidden","type":"test","data":"encrypted-value"}'}
                'plaintext' {'[{"id":"cred-1","name":"Hidden","type":"test","data":{"token":"not-allowed"}}]'}
                'duplicate' {'[{"id":"cred-1","name":"Hidden","type":"test","data":"encrypted-one"},{"id":"cred-1","name":"Hidden2","type":"test","data":"encrypted-two"}]'}
                'empty' {''}
                'oversized' {'[' + (' ' * 512) + ']'}
                default {'[{"id":"cred-1","name":"Hidden","type":"test","data":"encrypted-value"}]'}
            }
        }
        [IO.File]::WriteAllText($path,$json,(New-Object Text.UTF8Encoding($false)))
    }
    [Console]::WriteLine('INFO noisy logger prefix: Successfully exported to '+$containerPath)
    exit 0
}
if($items[0]-eq'cp'){
    $containerPath=($items[1]-split':',2)[1]
    $source=HostPath $containerPath
    if(-not(Test-Path -LiteralPath $source)){[Console]::Error.WriteLine('missing output');exit 2}
    Copy-Item -LiteralPath $source -Destination $items[2]
    exit 0
}
[Console]::Error.WriteLine('unexpected fake docker argv: '+[string]::Join(' ',[string[]]$items));exit 99
'@, (New-Object Text.UTF8Encoding($false)))

    $env:NS_R26_N8N_TEST_ROOT = $fakeRoot
    $prefix = @('-NoLogo','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$fakeDocker)

    $oldStdout = 'INFO logger prefix ' + '[{"id":"wf-1","name":"Hidden","nodes":[],"connections":{}}]'
    $failBefore = $false
    try { $null = $oldStdout | ConvertFrom-Json } catch { $failBefore = $true }
    Assert-N8nExportTest $failBefore 'old stdout-as-json contract fails with logger prefix'

    function Invoke-TestExport {
        param([string]$Name,[string]$Type,[string]$Mode='success',[int]$Timeout=30,[int64]$MaximumBytes=128MB)
        $env:NS_R26_N8N_TEST_MODE=$Mode
        $final=Join-Path $root "$Name.json"
        $diagnostic=Join-Path $root "$Name-diagnostic.json"
        $container="/tmp/next-stabil-$Name.json"
        $result=Invoke-NsR26N8nExportToArtifact -ExportType $Type -HostPartialPath ($final+'.partial') `
            -HostFinalPath $final -ContainerTemporaryPath $container -DiagnosticPath $diagnostic `
            -TimeoutSeconds $Timeout -MaximumBytes $MaximumBytes -DockerExecutable $powershell51 -DockerPrefixArguments $prefix
        return [pscustomobject]@{result=$result;final=$final;partial=$final+'.partial';diagnostic=$diagnostic;container=Join-Path $fakeRoot ([IO.Path]::GetFileName($container))}
    }

    try { $workflow=Invoke-TestExport -Name 'workflow-success' -Type workflow }
    catch {
        $diagnosticPath=Join-Path $root 'workflow-success-diagnostic.json'
        $diagnosticText=if(Test-Path $diagnosticPath){Get-Content $diagnosticPath -Raw}else{'DIAGNOSTIC_MISSING'}
        throw "WORKFLOW_SUCCESS_FAILED:$($_.Exception.Message):$diagnosticText"
    }
    Assert-N8nExportTest (Test-Path $workflow.final) 'workflow final exists'
    Assert-N8nExportTest (-not(Test-Path $workflow.partial)) 'workflow partial promoted'
    Assert-N8nExportTest (-not(Test-Path $workflow.container)) 'workflow container temp cleaned'
    Assert-N8nExportTest ($workflow.result.count-eq1 -and $workflow.result.command_exit-eq0) 'workflow result count and exit'
    Assert-N8nExportTest ($workflow.result.sha256-eq(Get-FileHash $workflow.final).Hash.ToLowerInvariant()) 'workflow hash exact'
    $workflowDiagnostic=Get-Content $workflow.diagnostic -Raw|ConvertFrom-Json
    Assert-N8nExportTest ($workflowDiagnostic.command.stdout-match'Successfully exported') 'noisy stdout retained as diagnostic'
    Assert-N8nExportTest ($workflowDiagnostic.first_non_whitespace-eq'[') 'workflow first character'

    try { $credential=Invoke-TestExport -Name 'credential-success' -Type credentials }
    catch {
        $diagnosticPath=Join-Path $root 'credential-success-diagnostic.json'
        $diagnosticText=if(Test-Path $diagnosticPath){Get-Content $diagnosticPath -Raw}else{'DIAGNOSTIC_MISSING'}
        throw "CREDENTIAL_SUCCESS_FAILED:$($_.Exception.Message):$diagnosticText"
    }
    Assert-N8nExportTest ($credential.result.count-eq1 -and $credential.result.credential_data_encrypted-eq$true) 'credential encrypted contract'
    Assert-N8nExportTest (-not(Test-Path $credential.container)) 'credential container temp cleaned'
    $credentialDiagnostic=Get-Content $credential.diagnostic -Raw|ConvertFrom-Json
    Assert-N8nExportTest (@($credentialDiagnostic.command.arguments|Where-Object{$_-eq'--decrypted'}).Count-eq0) 'decrypted flag absent'

    $collisionContainer=Join-Path $fakeRoot 'next-stabil-preexisting-collision.json'
    [IO.File]::WriteAllText($collisionContainer,'owner-data',(New-Object Text.UTF8Encoding($false)))
    $collisionFailed=$false;$collisionMessage=''
    try{$null=Invoke-TestExport -Name 'preexisting-collision' -Type workflow}catch{$collisionFailed=$true;$collisionMessage=$_.Exception.Message}
    Assert-N8nExportTest $collisionFailed 'preexisting collision fails'
    Assert-N8nExportTest ($collisionMessage-eq'N8N_CONTAINER_TEMP_COLLISION') 'preexisting collision exact code'
    Assert-N8nExportTest ((Get-Content $collisionContainer -Raw)-eq'owner-data') 'preexisting collision is not deleted'
    Remove-Item -LiteralPath $collisionContainer -Force

    foreach($case in @(
        @{name='workflow-invalid';type='workflow';mode='invalid';code='N8N_EXPORT_JSON_INVALID'},
        @{name='workflow-object';type='workflow';mode='object';code='N8N_EXPORT_TOP_LEVEL_NOT_ARRAY'},
        @{name='workflow-schema';type='workflow';mode='missing_nodes';code='N8N_WORKFLOW_EXPORT_SCHEMA_INVALID'},
        @{name='workflow-duplicate';type='workflow';mode='duplicate';code='N8N_WORKFLOW_EXPORT_SCHEMA_INVALID'},
        @{name='credential-plaintext';type='credentials';mode='plaintext';code='N8N_CREDENTIAL_EXPORT_NOT_ENCRYPTED'},
        @{name='credential-duplicate';type='credentials';mode='duplicate';code='N8N_CREDENTIAL_EXPORT_SCHEMA_INVALID'},
        @{name='process-nonzero';type='workflow';mode='nonzero';code='N8N_EXPORT_PROCESS_FAILED'},
        @{name='file-missing';type='workflow';mode='missing';code='N8N_EXPORT_FILE_MISSING'},
        @{name='file-empty';type='workflow';mode='empty';code='N8N_EXPORT_FILE_EMPTY'},
        @{name='file-oversized';type='workflow';mode='oversized';code='N8N_EXPORT_FILE_TOO_LARGE';max=128}
    )){
        $failed=$false;$message=''
        $caseMaximum=if($case.ContainsKey('max')){[int64]$case.max}else{128MB}
        try{$null=Invoke-TestExport -Name $case.name -Type $case.type -Mode $case.mode -MaximumBytes $caseMaximum}
        catch{$failed=$true;$message=$_.Exception.Message}
        Assert-N8nExportTest $failed "$($case.name) fails"
        Assert-N8nExportTest ($message-eq$case.code) "$($case.name) exact code"
        Assert-N8nExportTest (-not(Test-Path (Join-Path $root "$($case.name).json.partial"))) "$($case.name) partial removed"
        Assert-N8nExportTest (-not(Test-Path (Join-Path $fakeRoot "$($case.name).json"))) "$($case.name) container temp cleaned"
    }

    $timeoutFailed=$false;$timeoutMessage=''
    try{$null=Invoke-TestExport -Name 'process-timeout' -Type workflow -Mode timeout -Timeout 1}catch{$timeoutFailed=$true;$timeoutMessage=$_.Exception.Message}
    Assert-N8nExportTest $timeoutFailed 'timeout fails'
    Assert-N8nExportTest ($timeoutMessage-eq'N8N_EXPORT_TIMEOUT') 'timeout exact code'
    Assert-N8nExportTest (-not(Test-Path (Join-Path $fakeRoot 'process-timeout.json'))) 'timeout temp cleaned'

    $cleanupFailed=$false;$cleanupMessage=''
    try{$null=Invoke-TestExport -Name 'cleanup-failure' -Type workflow -Mode cleanup_fail}catch{$cleanupFailed=$true;$cleanupMessage=$_.Exception.Message}
    Assert-N8nExportTest $cleanupFailed 'cleanup failure fails'
    Assert-N8nExportTest ($cleanupMessage-eq'N8N_CONTAINER_TEMP_RESIDUE') 'cleanup failure exact code'
    Assert-N8nExportTest (-not(Test-Path (Join-Path $root 'cleanup-failure.json'))) 'cleanup failure removes final'
    Remove-Item -LiteralPath (Join-Path $fakeRoot 'cleanup-failure.json') -Force -ErrorAction SilentlyContinue

    $runnerText=Get-Content -LiteralPath $runner -Raw
    Assert-N8nExportTest ($runnerText-match 'export:workflow.+--all.+--output=' -or $runnerText-match '"--output=\{0\}"') 'production output argument present'
    Assert-N8nExportTest ($runnerText-notmatch 'export:credentials.+--decrypted') 'production decrypted flag absent'
    Assert-N8nExportTest ($runnerText-match '-HostPartialPath \(\$n8nWorkflows \+ ''\.partial''\)') 'workflow partial contract wired'
    Assert-N8nExportTest ($runnerText-match '-HostPartialPath \(\$n8nCredentials \+ ''\.partial''\)') 'credential partial contract wired'
    Write-Output ("PASS_N8N_FILE_EXPORT_PS51 assertions={0}" -f $script:Assertions)
}
finally {
    Remove-Item Env:NS_R26_N8N_TEST_ROOT -ErrorAction SilentlyContinue
    Remove-Item Env:NS_R26_N8N_TEST_MODE -ErrorAction SilentlyContinue
    if(Test-Path -LiteralPath $root){Remove-Item -LiteralPath $root -Recurse -Force}
}
