param(
    [string]$TaskName = "NEXT Stabil - Public Ingress Reconcile"
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "PUBLIC_INGRESS_TASK_REGISTRATION_REQUIRES_ADMINISTRATOR"
}

$scriptPath = Join-Path $PSScriptRoot "reconcile-public-ingress.ps1"
$powerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$arguments = '-NoProfile -NonInteractive -File "{0}"' -f $scriptPath
$currentTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($null -ne $currentTask) {
    $action = @($currentTask.Actions)[0]
    if (
        $action.Execute -ne $powerShell -or
        $action.Arguments -ne $arguments -or
        $currentTask.Principal.RunLevel -ne "Highest"
    ) {
        throw "PUBLIC_INGRESS_TASK_CONFLICT_REQUIRES_OPERATOR_REVIEW"
    }
    Write-Output "PUBLIC_INGRESS_TASK_NOOP exact task already registered"
    return
}

$action = New-ScheduledTaskAction `
    -Execute $powerShell `
    -Argument $arguments `
    -WorkingDirectory (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity.Name
$trigger.Delay = "PT45S"
$taskPrincipal = New-ScheduledTaskPrincipal `
    -UserId $identity.Name `
    -LogonType Interactive `
    -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Principal $taskPrincipal `
    -Settings $settings `
    -Description "Fail-closed reconciliation of public HTTPS 443 to the NEXT Stabil loopback public gateway only."

Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
Write-Output "PUBLIC_INGRESS_TASK_REGISTERED"
