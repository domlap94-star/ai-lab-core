[CmdletBinding()]
param(
    [string]$RepositoryRoot = "C:\ai-lab-core",
    [string]$TaskName = "NEXT Stabil - Trash Purge",
    [ValidateRange(1, 100)]
    [int]$BatchLimit = 100
)

$ErrorActionPreference = "Stop"

$resolvedRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path
$runner = Join-Path $resolvedRoot "operations\hardening\run-trash-purge.ps1"
if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
    throw "Trash purge runner was not found."
}

$arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -RepositoryRoot "{1}" -BatchLimit {2}' -f $runner, $resolvedRoot, $BatchLimit
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments
$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).Date.AddHours(1) `
    -RepetitionInterval (New-TimeSpan -Hours 4) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType S4U `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Bounded NEXT Stabil Trash purge; no secrets in command line." `
    -Force | Out-Null

$task = Get-ScheduledTask -TaskName $TaskName
if ($task.State -eq "Disabled") {
    throw "Trash purge scheduled task is disabled."
}

[pscustomobject]@{
    TaskName = $task.TaskName
    State = $task.State
    BatchLimit = $BatchLimit
    CadenceHours = 4
    Runner = $runner
}
