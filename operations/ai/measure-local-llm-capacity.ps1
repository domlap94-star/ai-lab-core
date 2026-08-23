param(
    [ValidateSet(4096, 8192)]
    [int]$Context = 4096,
    [switch]$WithEmbedding,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
trap {
    Write-Error ("capacity_probe_failed line={0} error={1}" -f $_.InvocationInfo.ScriptLineNumber, $_.Exception.Message)
    exit 1
}
$OllamaBase = 'http://127.0.0.1:11434'
$Model = 'qwen3.5:9b'
$EmbeddingModel = 'qwen3-embedding:0.6b'
$StartedAt = [DateTime]::UtcNow
$Samples = New-Object System.Collections.Generic.List[object]
$Queries = @(
    'Give three short steps for safely verifying inconsistent technical data.',
    'Briefly distinguish a fact, an estimate, and a hypothesis.',
    'For F = 10 kN and A = 0.005 m2 calculate pressure and give MPa.',
    'List the main checks before combining evidence from two documents.',
    'Answer briefly: when should missing data block an estimate?'
)

function Convert-KiBToGiB([double]$Value) {
    return [math]::Round($Value / 1MB, 3)
}

function Get-WslMemory {
    $Raw = & wsl.exe -d docker-desktop sh -lc "cat /proc/meminfo | grep -E '^(MemTotal|MemAvailable|Cached|SwapTotal|SwapFree):'"
    if ($LASTEXITCODE -ne 0) { throw 'wsl_memory_probe_failed' }
    $Values = @{}
    foreach ($Line in $Raw) {
        if ($Line -match '^([^:]+):\s+(\d+)\s+kB$') {
            $Values[$Matches[1]] = [double]$Matches[2]
        }
    }
    return [ordered]@{
        mem_total_gib = Convert-KiBToGiB $Values.MemTotal
        mem_available_gib = Convert-KiBToGiB $Values.MemAvailable
        cached_gib = Convert-KiBToGiB $Values.Cached
        swap_total_gib = Convert-KiBToGiB $Values.SwapTotal
        swap_used_gib = Convert-KiBToGiB ($Values.SwapTotal - $Values.SwapFree)
    }
}

function Get-OllamaResident {
    try {
        $Response = Invoke-RestMethod -Method Get -Uri "$OllamaBase/api/ps" -TimeoutSec 10
        return @($Response.models | ForEach-Object {
            [ordered]@{
                name = $_.name
                size_gib = [math]::Round([double]$_.size / 1GB, 3)
                size_vram_gib = [math]::Round([double]$_.size_vram / 1GB, 3)
                context = $_.context_length
                expires_at = $_.expires_at
            }
        })
    } catch {
        return @()
    }
}

function Get-Snapshot([string]$Phase) {
    $Memory = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
    $Cpu = Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor |
        Where-Object { $_.Name -eq '_Total' } |
        Select-Object -First 1
    $PageFiles = @(Get-CimInstance Win32_PageFileUsage)
    $GpuRows = @(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory)
    $Wsl = Get-WslMemory
    $Docker = @(& docker.exe stats --no-stream --format '{{json .}}' | ForEach-Object {
        $Item = $_ | ConvertFrom-Json
        [ordered]@{
            name = $Item.Name
            memory = $Item.MemUsage
            memory_percent = $Item.MemPerc
            cpu_percent = $Item.CPUPerc
        }
    })
    $Snapshot = [ordered]@{
        utc = [DateTime]::UtcNow.ToString('o')
        phase = $Phase
        windows = [ordered]@{
            available_gib = [math]::Round([double]$Memory.AvailableBytes / 1GB, 3)
            cached_gib = [math]::Round([double]$Memory.CacheBytes / 1GB, 3)
            committed_gib = [math]::Round([double]$Memory.CommittedBytes / 1GB, 3)
            commit_limit_gib = [math]::Round([double]$Memory.CommitLimit / 1GB, 3)
            commit_percent = [int]$Memory.PercentCommittedBytesInUse
            pages_input_sec = [double]$Memory.PagesInputPerSec
            page_reads_sec = [double]$Memory.PageReadsPerSec
            page_faults_sec = [double]$Memory.PageFaultsPerSec
            pagefile_current_mib = [double](($PageFiles | Measure-Object CurrentUsage -Sum).Sum)
            pagefile_peak_mib = [double](($PageFiles | Measure-Object PeakUsage -Sum).Sum)
            cpu_percent = [double]$Cpu.PercentProcessorTime
        }
        wsl = $Wsl
        gpu = [ordered]@{
            dedicated_gib = [math]::Round([double](($GpuRows | Measure-Object DedicatedUsage -Sum).Sum) / 1GB, 3)
            shared_gib = [math]::Round([double](($GpuRows | Measure-Object SharedUsage -Sum).Sum) / 1GB, 3)
        }
        docker = $Docker
        ollama = @(Get-OllamaResident)
    }
    $Samples.Add([pscustomobject]$Snapshot)
    if ($Snapshot.windows.available_gib -lt 3.0) { throw 'safety_abort_windows_available' }
    if ($Snapshot.wsl.mem_available_gib -lt 2.0) { throw 'safety_abort_wsl_available' }
    if ($Snapshot.wsl.swap_used_gib -gt 2.0) { throw 'safety_abort_wsl_swap' }
    return $Snapshot
}

function Invoke-Unload([string]$Name, [bool]$Embedding) {
    try {
        if ($Embedding) {
            $Body = @{ model = $Name; input = ''; keep_alive = 0 } | ConvertTo-Json -Compress
            Invoke-RestMethod -Method Post -Uri "$OllamaBase/api/embed" -ContentType 'application/json' -Body $Body -TimeoutSec 60 | Out-Null
        } else {
            $Body = @{ model = $Name; prompt = ''; stream = $false; keep_alive = 0 } | ConvertTo-Json -Compress
            Invoke-RestMethod -Method Post -Uri "$OllamaBase/api/generate" -ContentType 'application/json' -Body $Body -TimeoutSec 60 | Out-Null
        }
    } catch {
        # A model already absent from memory is an acceptable unload state.
    }
}

function Wait-ModelAbsent([string]$Name, [int]$TimeoutSeconds = 90) {
    $Watch = [Diagnostics.Stopwatch]::StartNew()
    do {
        $Found = @(Get-OllamaResident | Where-Object { $_.name -eq $Name }).Count -gt 0
        if (-not $Found) { return [math]::Round($Watch.Elapsed.TotalSeconds, 2) }
        Start-Sleep -Milliseconds 500
    } while ($Watch.Elapsed.TotalSeconds -lt $TimeoutSeconds)
    throw "model_unload_timeout:$Name"
}

function Invoke-Health {
    $Backend = $false
    $Supervisor = $false
    $Qdrant = $false
    $Postgres = $false
    try { $Backend = (Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 5).status -eq 'ok' } catch {}
    try { $Supervisor = (Invoke-RestMethod 'http://127.0.0.1:8787/health' -TimeoutSec 5).supervisor_online -eq $true } catch {}
    try { $Qdrant = (Invoke-RestMethod 'http://127.0.0.1:6333/collections' -TimeoutSec 5).status -eq 'ok' } catch {}
    try {
        & docker.exe compose exec -T postgres pg_isready -U postgres 2>&1 | Out-Null
        $Postgres = $LASTEXITCODE -eq 0
    } catch {}
    return [ordered]@{ backend = $Backend; supervisor = $Supervisor; qdrant = $Qdrant; postgres = $Postgres }
}

function Invoke-Query([string]$Prompt, [int]$Index) {
    $Payload = [ordered]@{
        model = $Model
        prompt = $Prompt
        stream = $false
        think = $false
        keep_alive = '10m'
        options = [ordered]@{ num_ctx = $Context; temperature = 0.1; num_predict = 120 }
    }
    $Body = $Payload | ConvertTo-Json -Depth 5 -Compress
    $Job = Start-Job -ScriptBlock {
        param($Uri, $Json)
        Invoke-RestMethod -Method Post -Uri $Uri -ContentType 'application/json' -Body $Json -TimeoutSec 300
    } -ArgumentList "$OllamaBase/api/generate", $Body
    $Watch = [Diagnostics.Stopwatch]::StartNew()
    while ($Job.State -eq 'Running') {
        Get-Snapshot "query_$Index" | Out-Null
        Start-Sleep -Seconds 1
        $Job = Get-Job -Id $Job.Id
    }
    $Response = Receive-Job -Job $Job -ErrorAction Stop
    Remove-Job -Job $Job -Force
    return [ordered]@{
        query = $Index
        wall_seconds = [math]::Round($Watch.Elapsed.TotalSeconds, 2)
        load_seconds = [math]::Round([double]$Response.load_duration / 1e9, 3)
        prompt_tokens = [int]$Response.prompt_eval_count
        prompt_tokens_per_second = if ($Response.prompt_eval_duration -gt 0) { [math]::Round([double]$Response.prompt_eval_count / ([double]$Response.prompt_eval_duration / 1e9), 2) } else { 0 }
        response_tokens = [int]$Response.eval_count
        response_tokens_per_second = if ($Response.eval_duration -gt 0) { [math]::Round([double]$Response.eval_count / ([double]$Response.eval_duration / 1e9), 2) } else { 0 }
    }
}

$Result = [ordered]@{
    schema = 'NEXT_STABIL_LLM_CAPACITY_V1'
    source_head = (& git.exe rev-parse HEAD).Trim()
    model = $Model
    context = $Context
    embedding_coexistence = [bool]$WithEmbedding
    started_at = $StartedAt.ToString('o')
    health_before = $null
    health_after = $null
    queries = @()
    model_unload_seconds = $null
    embedding_unload_seconds = $null
    completed_at = $null
    samples = @()
}

Invoke-Unload $Model $false
Invoke-Unload $EmbeddingModel $true
Wait-ModelAbsent $Model | Out-Null
Wait-ModelAbsent $EmbeddingModel | Out-Null
$Result.health_before = Invoke-Health
Get-Snapshot 'idle_before_load' | Out-Null

if ($WithEmbedding) {
    $EmbedBody = @{ model = $EmbeddingModel; input = 'synthetic capacity probe'; keep_alive = '10m'; options = @{ num_ctx = 4096 } } | ConvertTo-Json -Depth 5 -Compress
    Invoke-RestMethod -Method Post -Uri "$OllamaBase/api/embed" -ContentType 'application/json' -Body $EmbedBody -TimeoutSec 180 | Out-Null
    Get-Snapshot 'embedding_loaded' | Out-Null
}

$QueryResults = @()
for ($Index = 0; $Index -lt $Queries.Count; $Index++) {
    $QueryResults += [pscustomobject](Invoke-Query $Queries[$Index] ($Index + 1))
}
$Result.queries = $QueryResults
Get-Snapshot 'steady_after_queries' | Out-Null
$Result.health_after = Invoke-Health
if ($Result.health_after.Values -contains $false) { throw 'service_health_degraded' }

Get-Snapshot 'before_model_unload' | Out-Null
Invoke-Unload $Model $false
$Result.model_unload_seconds = Wait-ModelAbsent $Model
Start-Sleep -Seconds 5
Get-Snapshot 'after_model_unload' | Out-Null

if ($WithEmbedding) {
    Invoke-Unload $EmbeddingModel $true
    $Result.embedding_unload_seconds = Wait-ModelAbsent $EmbeddingModel
    Start-Sleep -Seconds 5
    Get-Snapshot 'after_embedding_unload' | Out-Null
}

$Result.completed_at = [DateTime]::UtcNow.ToString('o')
$Result.samples = $Samples.ToArray()
$Parent = Split-Path -Parent $OutputPath
if ($Parent -and -not (Test-Path $Parent)) { New-Item -ItemType Directory -Path $Parent -Force | Out-Null }
$Result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Output 'CAPACITY_PROBE=PASS'
Write-Output "OUTPUT=$OutputPath"
Write-Output "MODEL_UNLOAD_SECONDS=$($Result.model_unload_seconds)"
Write-Output "EMBEDDING_UNLOAD_SECONDS=$($Result.embedding_unload_seconds)"
Write-Output "MIN_WINDOWS_AVAILABLE_GIB=$([math]::Round(($Samples.windows.available_gib | Measure-Object -Minimum).Minimum,3))"
Write-Output "MIN_WSL_AVAILABLE_GIB=$([math]::Round(($Samples.wsl.mem_available_gib | Measure-Object -Minimum).Minimum,3))"
Write-Output "MAX_WSL_SWAP_GIB=$([math]::Round(($Samples.wsl.swap_used_gib | Measure-Object -Maximum).Maximum,3))"
Write-Output "MAX_PAGEFILE_CURRENT_MIB=$([math]::Round(($Samples.windows.pagefile_current_mib | Measure-Object -Maximum).Maximum,1))"
Write-Output "MAX_COMMIT_GIB=$([math]::Round(($Samples.windows.committed_gib | Measure-Object -Maximum).Maximum,3))"
Write-Output "MEDIAN_TOKENS_PER_SEC=$([math]::Round(($QueryResults.response_tokens_per_second | Sort-Object)[[math]::Floor($QueryResults.Count/2)],2))"
