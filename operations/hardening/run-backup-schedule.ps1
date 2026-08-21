[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 9223372036854775807)]
    [long]$ScheduleId,
    [string]$RepositoryRoot = "C:\ai-lab-core"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$repo = (Resolve-Path -LiteralPath $RepositoryRoot).Path
& docker.exe compose --project-directory $repo exec -T -e PYTHONPATH=/app backend `
    python /app/app/scripts/run_backup_schedule.py --schedule-id $ScheduleId
if ($LASTEXITCODE -ne 0) {
    throw "Scheduled backup runner failed for schedule $ScheduleId with exit code $LASTEXITCODE."
}
