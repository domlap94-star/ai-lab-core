[CmdletBinding()]
param(
    [string]$RepositoryRoot = "C:\ai-lab-core",
    [ValidateRange(1, 100)]
    [int]$BatchLimit = 100
)

$ErrorActionPreference = "Stop"

$resolvedRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path
$composeFile = Join-Path $resolvedRoot "compose.yaml"
if (-not (Test-Path -LiteralPath $composeFile -PathType Leaf)) {
    throw "Canonical compose file was not found."
}

Push-Location $resolvedRoot
try {
    $output = @(& docker compose exec -T backend python -m app.commands.purge_trash --limit $BatchLimit 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "Trash purge runner failed with exit code $LASTEXITCODE."
    }
    $summary = $output[-1] | ConvertFrom-Json
    $logDirectory = Join-Path $resolvedRoot "data\operations"
    New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
    $logPath = Join-Path $logDirectory "trash-purge.log"
    $line = "{0} eligible={1} processed={2} purged={3} blocked={4} failed={5} singleton={6}" -f `
        (Get-Date).ToUniversalTime().ToString("o"), `
        $summary.eligible, $summary.processed, $summary.purged, `
        $summary.blocked, $summary.failed, $summary.singleton_acquired
    Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8
    if ((Get-Item -LiteralPath $logPath).Length -gt 1MB) {
        $tail = @(Get-Content -LiteralPath $logPath -Tail 200)
        Set-Content -LiteralPath $logPath -Value $tail -Encoding UTF8
    }
    Write-Output $line
}
finally {
    Pop-Location
}
