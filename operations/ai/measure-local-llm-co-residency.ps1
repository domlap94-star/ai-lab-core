param(
    [ValidateSet('phi-qwen7-embedding')]
    [string]$Combination = 'phi-qwen7-embedding',
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$OllamaBase = 'http://127.0.0.1:11434'
$Models = @('phi4-mini:latest', 'qwen2.5:7b-instruct')
$EmbeddingModel = 'qwen3-embedding:0.6b'

function Get-WslState {
    $Raw = & wsl.exe -d docker-desktop sh -lc "cat /proc/meminfo | grep -E '^(MemAvailable|SwapTotal|SwapFree):'"
    if ($LASTEXITCODE -ne 0) { throw 'wsl_probe_failed' }
    $Values = @{}
    foreach ($Line in $Raw) {
        if ($Line -match '^([^:]+):\s+(\d+)\s+kB$') { $Values[$Matches[1]] = [double]$Matches[2] }
    }
    return [ordered]@{
        available_gib = [math]::Round($Values.MemAvailable / 1MB, 3)
        swap_used_gib = [math]::Round(($Values.SwapTotal - $Values.SwapFree) / 1MB, 3)
    }
}

function Get-Snapshot([string]$Phase) {
    $Os = Get-CimInstance Win32_OperatingSystem
    $Memory = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
    $Wsl = Get-WslState
    $Resident = (Invoke-RestMethod "$OllamaBase/api/ps" -TimeoutSec 10).models
    $Value = [ordered]@{
        utc = [DateTime]::UtcNow.ToString('o')
        phase = $Phase
        windows_available_gib = [math]::Round($Os.FreePhysicalMemory / 1MB, 3)
        committed_gib = [math]::Round($Memory.CommittedBytes / 1GB, 3)
        pagefile_current_mib = [double]((Get-CimInstance Win32_PageFileUsage | Measure-Object CurrentUsage -Sum).Sum)
        pages_input_sec = [double]$Memory.PagesInputPerSec
        wsl = $Wsl
        resident = @($Resident | ForEach-Object { [ordered]@{ name = $_.name; size_gib = [math]::Round($_.size / 1GB, 3); vram_gib = [math]::Round($_.size_vram / 1GB, 3) } })
    }
    if ($Value.windows_available_gib -lt 3.0) { throw 'safety_abort_windows_available' }
    if ($Value.wsl.available_gib -lt 2.0) { throw 'safety_abort_wsl_available' }
    if ($Value.wsl.swap_used_gib -gt 2.0) { throw 'safety_abort_wsl_swap' }
    return $Value
}

function Invoke-Generate([string]$Model, [string]$KeepAlive) {
    $Body = @{ model = $Model; prompt = 'Reply with one word: test.'; stream = $false; keep_alive = $KeepAlive; options = @{ num_ctx = 4096; temperature = 0.1; num_predict = 8 } } | ConvertTo-Json -Depth 5 -Compress
    Invoke-RestMethod -Method Post -Uri "$OllamaBase/api/generate" -ContentType 'application/json' -Body $Body -TimeoutSec 300 | Out-Null
}

function Invoke-Unload([string]$Model, [bool]$Embedding) {
    $Uri = if ($Embedding) { "$OllamaBase/api/embed" } else { "$OllamaBase/api/generate" }
    $Body = if ($Embedding) { @{ model = $Model; input = ''; keep_alive = 0 } } else { @{ model = $Model; prompt = ''; stream = $false; keep_alive = 0 } }
    try { Invoke-RestMethod -Method Post -Uri $Uri -ContentType 'application/json' -Body ($Body | ConvertTo-Json -Compress) -TimeoutSec 60 | Out-Null } catch {}
}

$Result = [ordered]@{ schema = 'NEXT_STABIL_LLM_CORESIDENCY_V1'; combination = $Combination; source_head = (& git.exe rev-parse HEAD).Trim(); samples = @() }
foreach ($Model in $Models) { Invoke-Unload $Model $false }
Invoke-Unload $EmbeddingModel $true
$Result.samples += Get-Snapshot 'idle'

$Embed = @{ model = $EmbeddingModel; input = 'synthetic coexistence probe'; keep_alive = '5m'; options = @{ num_ctx = 4096 } } | ConvertTo-Json -Depth 5 -Compress
Invoke-RestMethod -Method Post -Uri "$OllamaBase/api/embed" -ContentType 'application/json' -Body $Embed -TimeoutSec 180 | Out-Null
$Result.samples += Get-Snapshot 'embedding'
foreach ($Model in $Models) {
    Invoke-Generate $Model '5m'
    $Result.samples += Get-Snapshot ("loaded_" + $Model)
}
$Result.health = [ordered]@{
    backend = (Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 5).status
    qdrant = (Invoke-RestMethod 'http://127.0.0.1:6333/collections' -TimeoutSec 5).status
    supervisor = [bool](Invoke-RestMethod 'http://127.0.0.1:8787/health' -TimeoutSec 5).supervisor_online
}

foreach ($Model in $Models) { Invoke-Unload $Model $false }
Invoke-Unload $EmbeddingModel $true
Start-Sleep -Seconds 5
$Result.samples += Get-Snapshot 'unloaded'
$Parent = Split-Path -Parent $OutputPath
if ($Parent -and -not (Test-Path $Parent)) { New-Item -ItemType Directory -Path $Parent -Force | Out-Null }
$Result | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Output 'CORESIDENCY_PROBE=PASS'
Write-Output "MIN_WINDOWS_AVAILABLE_GIB=$([math]::Round(($Result.samples.windows_available_gib | Measure-Object -Minimum).Minimum,3))"
Write-Output "MIN_WSL_AVAILABLE_GIB=$([math]::Round(($Result.samples.wsl.available_gib | Measure-Object -Minimum).Minimum,3))"
Write-Output "MAX_WSL_SWAP_GIB=$([math]::Round(($Result.samples.wsl.swap_used_gib | Measure-Object -Maximum).Maximum,3))"
