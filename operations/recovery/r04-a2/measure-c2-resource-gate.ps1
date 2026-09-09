[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ExpectedContainerId,

    [Parameter(Mandatory = $true)]
    [string]$OutputCsv,

    [Parameter(Mandatory = $true)]
    [string]$StopFile,

    [string]$ExpectedContainerName = "next-stabil-r04-a2-c2--telemetry",

    [string]$ExpectedOwner = "R04-A2-C2",

    [string]$ExpectedRunId = "20260909T184535Z",

    [ValidateRange(5, 10)]
    [int]$IntervalSeconds = 5,

    [ValidateRange(1, 1080)]
    [int]$MaxSamples = 600
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$container = $ExpectedContainerName
$gib = [double](1024 * 1024 * 1024)
$mib = [double](1024 * 1024)
$minimumReserveGiB = 4.0
$maximumSwapGrowthMiB = 256.0
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Invoke-DockerValue {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $lines = & docker.exe @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "DOCKER_READ_FAILED"
    }
    (($lines | ForEach-Object { [string]$_ }) -join "`n").Trim()
}

function Read-PoolMemInfo {
    $raw = Invoke-DockerValue @(
        "exec", $container, "python", "-c",
        "__import__('builtins').print(__import__('pathlib').Path('/proc/meminfo').read_text())"
    )
    $values = @{}
    foreach ($line in ($raw -split "`r?`n")) {
        if ($line -match '^([A-Za-z_()]+):\s+(\d+)\s+kB$') {
            $values[$matches[1]] = [int64]$matches[2] * 1KB
        }
    }
    foreach ($field in @("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")) {
        if (-not $values.ContainsKey($field)) {
            throw "POOL_FIELD_MISSING_$field"
        }
    }
    $values
}

$parent = Split-Path -Parent $OutputCsv
if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
    throw "OUTPUT_PARENT_MISSING"
}
if ((Split-Path -Parent $StopFile) -ne $parent) {
    throw "STOP_FILE_OUTSIDE_OUTPUT_PARENT"
}

$actualId = Invoke-DockerValue @("inspect", "--format", "{{.Id}}", $container)
$owner = Invoke-DockerValue @("inspect", "--format", '{{index .Config.Labels \"next.stabil.owner\"}}', $container)
$run = Invoke-DockerValue @("inspect", "--format", '{{index .Config.Labels \"next.stabil.run-id\"}}', $container)
$state = Invoke-DockerValue @("inspect", "--format", "{{.State.Status}}", $container)
if ($actualId -ne $ExpectedContainerId -or $owner -ne $ExpectedOwner -or
    $run -ne $ExpectedRunId -or $state -ne "running") {
    throw "TELEMETRY_IDENTITY_MISMATCH"
}

$initialPool = Read-PoolMemInfo
$baselineSwapUsed = [int64]$initialPool.SwapTotal - [int64]$initialPool.SwapFree
$header = "utc,windows_available_gib,commit_used_gib,commit_limit_gib,commit_reserve_gib,pool_total_gib,pool_available_gib,pool_swap_total_gib,pool_swap_used_mib,status`r`n"
[System.IO.File]::WriteAllText($OutputCsv, $header, $utf8NoBom)

for ($index = 0; $index -lt $MaxSamples; $index++) {
    if (Test-Path -LiteralPath $StopFile) {
        exit 0
    }

    try {
        $os = Get-CimInstance Win32_OperatingSystem
        $memory = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
        $pool = Read-PoolMemInfo
        $windowsAvailable = [double]$os.FreePhysicalMemory * 1KB
        $commitUsed = [double]$memory.CommittedBytes
        $commitLimit = [double]$memory.CommitLimit
        $commitReserve = $commitLimit - $commitUsed
        $swapUsed = [int64]$pool.SwapTotal - [int64]$pool.SwapFree
        $swapGrowth = $swapUsed - $baselineSwapUsed
        $status = "PASS"
        if ($windowsAvailable -lt ($minimumReserveGiB * $gib)) { $status = "RAM_GATE_BLOCKED" }
        elseif ($commitReserve -lt ($minimumReserveGiB * $gib)) { $status = "COMMIT_GATE_BLOCKED" }
        elseif ([double]$pool.MemAvailable -lt ($minimumReserveGiB * $gib)) { $status = "POOL_RESERVE_BLOCKED" }
        elseif ($swapGrowth -gt ($maximumSwapGrowthMiB * $mib)) { $status = "POOL_SWAP_GROWTH_BLOCKED" }

        $line = [string]::Format(
            [System.Globalization.CultureInfo]::InvariantCulture,
            "{0},{1:F3},{2:F3},{3:F3},{4:F3},{5:F3},{6:F3},{7:F3},{8:F1},{9}`r`n",
            ([DateTime]::UtcNow.ToString("o")), ($windowsAvailable / $gib),
            ($commitUsed / $gib), ($commitLimit / $gib), ($commitReserve / $gib),
            ([double]$pool.MemTotal / $gib), ([double]$pool.MemAvailable / $gib),
            ([double]$pool.SwapTotal / $gib), ($swapUsed / $mib), $status
        )
        [System.IO.File]::AppendAllText($OutputCsv, $line, $utf8NoBom)
        Write-Output $line.Trim()
        if ($status -ne "PASS") {
            exit 20
        }
    }
    catch {
        $safeCode = if ([string]::IsNullOrWhiteSpace($_.Exception.Message)) {
            "RESOURCE_OBSERVABILITY_BLOCKED"
        } else {
            ($_.Exception.Message -replace '[^A-Za-z0-9_]', '_')
        }
        $line = "{0},,,,,,,,,$safeCode`r`n" -f ([DateTime]::UtcNow.ToString("o"))
        [System.IO.File]::AppendAllText($OutputCsv, $line, $utf8NoBom)
        Write-Error $safeCode
        exit 21
    }

    Start-Sleep -Seconds $IntervalSeconds
}

exit 0
