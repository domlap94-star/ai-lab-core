[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$script:Assertions = 0
function Assert-TransportTest {
    param([bool]$Condition, [string]$Message)
    $script:Assertions++
    if (-not $Condition) { throw "ASSERTION_FAILED:$Message" }
}

$runner = Join-Path $PSScriptRoot 'backup-production.ps1'
$tokens = $null
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($runner, [ref]$tokens, [ref]$errors)
Assert-TransportTest (@($errors).Count -eq 0) 'runner parses in Windows PowerShell 5.1'
$requiredFunctions = @(
    'ConvertTo-NativeArgumentString',
    'Get-PipeTransportDisposition',
    'Write-BinaryTransportEvidence',
    'Invoke-CheckedBinaryCapture',
    'Invoke-CheckedFileInput'
)
foreach ($name in $requiredFunctions) {
    $definition = @($ast.FindAll({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name
    }, $true))
    Assert-TransportTest ($definition.Count -eq 1) "one definition for $name"
    Invoke-Expression $definition[0].Extent.Text
}

$root = Join-Path $env:LOCALAPPDATA ('Temp\NEXT-STABIL-BINARY-TRANSPORT-' + [Guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $input = Join-Path $root 'input.bin'
    $stream = [IO.File]::Open($input, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $block = New-Object byte[] (1MB)
        for ($index = 0; $index -lt $block.Length; $index++) { $block[$index] = [byte]($index % 251) }
        for ($iteration = 0; $iteration -lt 16; $iteration++) { $stream.Write($block, 0, $block.Length) }
    }
    finally { $stream.Dispose() }
    $inputHash = (Get-FileHash -LiteralPath $input -Algorithm SHA256).Hash

    $producer = Join-Path $root 'producer.ps1'
    [IO.File]::WriteAllText($producer, @'
$source=[IO.File]::OpenRead($args[0]);$stdout=[Console]::OpenStandardOutput()
try{$source.CopyTo($stdout);$stdout.Flush()}finally{$source.Dispose();$stdout.Dispose()}
'@, (New-Object Text.UTF8Encoding($false)))
    $producerFail = Join-Path $root 'producer-fail.ps1'
    [IO.File]::WriteAllText($producerFail, @'
$source=[IO.File]::OpenRead($args[0]);$stdout=[Console]::OpenStandardOutput();$buffer=New-Object byte[] (1MB)
try{$read=$source.Read($buffer,0,$buffer.Length);$stdout.Write($buffer,0,$read);$stdout.Flush();[Console]::Error.WriteLine('synthetic producer failure')}finally{$source.Dispose();$stdout.Dispose()};exit 7
'@, (New-Object Text.UTF8Encoding($false)))
    $consumer = Join-Path $root 'consumer.ps1'
    [IO.File]::WriteAllText($consumer, @'
$stdin=[Console]::OpenStandardInput();$target=[IO.File]::Open($args[0],[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
try{$stdin.CopyTo($target);$target.Flush()}finally{$stdin.Dispose();$target.Dispose()}
'@, (New-Object Text.UTF8Encoding($false)))
    $consumerFail = Join-Path $root 'consumer-fail.ps1'
    [IO.File]::WriteAllText($consumerFail, @'
$stdin=[Console]::OpenStandardInput();$null=$stdin.ReadByte();$stdin.Dispose();[Console]::Error.WriteLine('synthetic consumer failure');exit 9
'@, (New-Object Text.UTF8Encoding($false)))

    $powershell = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
    $capture = Join-Path $root 'capture.bin'
    $captureEvidence = Join-Path $root 'capture.json'
    $captureResult = Invoke-CheckedBinaryCapture $powershell @('-NoLogo','-NoProfile','-NonInteractive','-File',$producer,$input) $capture 120 $captureEvidence
    Assert-TransportTest ($captureResult.exit_code -eq 0) 'producer exit zero'
    Assert-TransportTest ($captureResult.bytes_written -eq 16MB) 'producer byte count'
    Assert-TransportTest ((Get-FileHash -LiteralPath $capture -Algorithm SHA256).Hash -eq $inputHash) 'producer binary hash exact'

    $partial = Join-Path $root 'producer-nonzero.partial'
    $nonzeroEvidence = Join-Path $root 'producer-nonzero.json'
    $nonzeroFailed = $false
    try {
        [void](Invoke-CheckedBinaryCapture $powershell @('-NoLogo','-NoProfile','-NonInteractive','-File',$producerFail,$input) $partial 120 $nonzeroEvidence)
    }
    catch { $nonzeroFailed = $true }
    $nonzeroRecord = Get-Content -LiteralPath $nonzeroEvidence -Raw | ConvertFrom-Json
    Assert-TransportTest $nonzeroFailed 'nonzero producer fails'
    Assert-TransportTest ($nonzeroRecord.exit_code -eq 7 -and $nonzeroRecord.stderr -match 'synthetic producer failure') 'nonzero producer evidence'
    Assert-TransportTest (-not (Test-Path -LiteralPath $partial)) 'nonzero producer partial removed'

    $pipe109 = Get-PipeTransportDisposition (New-Object IO.IOException('broken pipe', -2147024787))
    $pipe232 = Get-PipeTransportDisposition (New-Object IO.IOException('no data', -2147024664))
    $pipeOther = Get-PipeTransportDisposition (New-Object IO.IOException('access denied', -2147024891))
    Assert-TransportTest ($pipe109.disposition -eq 'PIPE_EOF_CANDIDATE' -and $pipe109.hresult_low_word -eq 109) '109 is EOF candidate'
    Assert-TransportTest ($pipe232.disposition -eq 'PIPE_EOF_CANDIDATE' -and $pipe232.hresult_low_word -eq 232) '232 is EOF candidate'
    Assert-TransportTest ($pipeOther.disposition -eq 'FAIL' -and $pipeOther.hresult_low_word -eq 5) 'other IOException fails'

    $consumerOutput = Join-Path $root 'consumer-output.bin'
    $inputEvidence = Join-Path $root 'input-success.json'
    $inputResult = Invoke-CheckedFileInput $powershell @('-NoLogo','-NoProfile','-NonInteractive','-File',$consumer,$consumerOutput) $input 120 $inputEvidence
    Assert-TransportTest ($inputResult.exit_code -eq 0 -and $inputResult.bytes_read -eq 16MB) 'input success count and exit'
    Assert-TransportTest ((Get-FileHash -LiteralPath $consumerOutput -Algorithm SHA256).Hash -eq $inputHash) 'input success hash exact'

    $earlyEvidence = Join-Path $root 'input-early-failure.json'
    $earlyFailed = $false
    try {
        [void](Invoke-CheckedFileInput $powershell @('-NoLogo','-NoProfile','-NonInteractive','-File',$consumerFail) $input 120 $earlyEvidence)
    }
    catch { $earlyFailed = $true }
    $earlyRecord = Get-Content -LiteralPath $earlyEvidence -Raw | ConvertFrom-Json
    Assert-TransportTest $earlyFailed 'early consumer failure is not accepted'
    Assert-TransportTest ($earlyRecord.exit_code -eq 9 -and $earlyRecord.stderr -match 'synthetic consumer failure') 'early consumer exit and stderr preserved'
    Assert-TransportTest ($earlyRecord.pipe_disposition -eq 'PIPE_EOF_CANDIDATE' -and [int]$earlyRecord.pipe_hresult_low_word -in @(109, 232)) 'EOF candidate plus nonzero exit still fails'

    $final = Join-Path $root 'postgres.dump'
    $validationPartial = Join-Path $root 'postgres.dump.partial'
    Copy-Item -LiteralPath $capture -Destination $validationPartial
    $firstValidator = $true
    $secondValidator = $false
    if ($firstValidator -and $secondValidator) { Move-Item -LiteralPath $validationPartial -Destination $final }
    else { Remove-Item -LiteralPath $validationPartial -Force }
    Assert-TransportTest (-not (Test-Path -LiteralPath $final) -and -not (Test-Path -LiteralPath $validationPartial)) 'validator failure leaves no final or partial'
    Copy-Item -LiteralPath $capture -Destination $validationPartial
    $firstValidator = $true
    $secondValidator = $true
    if ($firstValidator -and $secondValidator) { Move-Item -LiteralPath $validationPartial -Destination $final }
    Assert-TransportTest ((Test-Path -LiteralPath $final) -and -not (Test-Path -LiteralPath $validationPartial)) 'both validators finalize atomically'
    Assert-TransportTest ((Get-FileHash -LiteralPath $final -Algorithm SHA256).Hash -eq $inputHash) 'finalized hash exact'

    $runnerText = Get-Content -LiteralPath $runner -Raw
    $partialPosition = $runnerText.IndexOf('$dbDumpPartial = $dbDump + ".partial"')
    $listPosition = $runnerText.IndexOf('"pg_restore", "--list"')
    $fullPosition = $runnerText.IndexOf('"--file=/dev/null"')
    $movePosition = $runnerText.IndexOf('Move-Item -LiteralPath $dbDumpPartial -Destination $dbDump')
    Assert-TransportTest ($partialPosition -ge 0 -and $partialPosition -lt $listPosition -and $listPosition -lt $fullPosition -and $fullPosition -lt $movePosition) 'production partial validation ordering'

    Write-Output ("BACKUP_BINARY_TRANSPORT_PS51_PASS assertions={0}" -f $script:Assertions)
}
finally {
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
}
