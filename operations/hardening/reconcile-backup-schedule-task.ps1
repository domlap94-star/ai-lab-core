[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Preview", "Apply", "Remove", "Prune")]
    [string]$Mode,
    [ValidateRange(1, 9223372036854775807)]
    [long]$ScheduleId = 1,
    [ValidateRange(1, 2147483647)]
    [int]$PlanRevision = 1,
    [ValidateSet("true", "false")]
    [string]$Enabled = "false",
    [ValidateSet("daily", "weekly", "monthly")]
    [string]$Cadence = "daily",
    [ValidatePattern('^([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$')]
    [string]$LocalTime = "03:00:00",
    [ValidateRange(0, 7)]
    [int]$Weekday = 0,
    [ValidateRange(0, 28)]
    [int]$MonthDay = 0,
    [ValidatePattern('^[0-9]+(,[0-9]+)*$|^$')]
    [string]$ExpectedScheduleIds = "",
    [string]$RepositoryRoot = "C:\ai-lab-core"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$managedPrefix = "NEXT Stabil - Backup - "
$managedMarker = "NEXT_STABIL_MANAGED_BACKUP_V2"
$legacyManagedMarker = "NEXT_STABIL_MANAGED_BACKUP_V1"
$repo = (Resolve-Path -LiteralPath $RepositoryRoot).Path.TrimEnd('\')
$runner = Join-Path $repo "operations\hardening\run-backup-schedule.ps1"
$powerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) { throw "backup_schedule_runner_missing" }

function ConvertTo-SafeXml([string]$Value) {
    return [System.Security.SecurityElement]::Escape($Value)
}

function Get-ExpectedDescription {
    return "$managedMarker schedule_id=$ScheduleId revision=$PlanRevision cadence=$Cadence time=$LocalTime weekday=$Weekday month_day=$MonthDay"
}

function Get-ExpectedArguments {
    return "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$runner`" -ScheduleId $ScheduleId -RepositoryRoot `"$repo`""
}

function Get-OwnedTask([string]$TaskName) {
    $task = Get-ScheduledTask -TaskName $TaskName -TaskPath "\" -ErrorAction SilentlyContinue
    if ($null -eq $task) { return $null }
    $action = @($task.Actions) | Select-Object -First 1
    $description = [string]$task.Description
    $owned = ($description -like "$managedMarker*" -or $description -like "$legacyManagedMarker*") -and
        [string]$action.Execute -ieq $powerShell -and
        [string]$action.Arguments -like "*-File `"$runner`" -ScheduleId *"
    if (-not $owned) { throw "backup_scheduler_unmanaged_task_collision" }
    return $task
}

function Get-TaskSnapshot([string]$TaskName) {
    $task = Get-ScheduledTask -TaskName $TaskName -TaskPath "\" -ErrorAction SilentlyContinue
    if ($null -eq $task) { return $null }
    $action = @($task.Actions) | Select-Object -First 1
    $info = Get-ScheduledTaskInfo -TaskName $TaskName -TaskPath "\"
    [xml]$xml = Export-ScheduledTask -TaskName $TaskName -TaskPath "\"
    $ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
    $ns.AddNamespace("t", $xml.DocumentElement.NamespaceURI)
    $calendar = $xml.SelectSingleNode("//t:CalendarTrigger", $ns)
    $actualCadence = $null
    $actualWeekday = 0
    $actualMonthDay = 0
    if ($null -ne $calendar.SelectSingleNode("t:ScheduleByDay", $ns)) {
        $actualCadence = "daily"
    } elseif ($null -ne $calendar.SelectSingleNode("t:ScheduleByWeek", $ns)) {
        $actualCadence = "weekly"
        $dayNode = $calendar.SelectSingleNode("t:ScheduleByWeek/t:DaysOfWeek/*", $ns)
        $names = @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
        $actualWeekday = [array]::IndexOf($names, $dayNode.LocalName) + 1
    } elseif ($null -ne $calendar.SelectSingleNode("t:ScheduleByMonth", $ns)) {
        $actualCadence = "monthly"
        $actualMonthDay = [int]$calendar.SelectSingleNode("t:ScheduleByMonth/t:DaysOfMonth/t:Day", $ns).InnerText
    }
    $actualTime = ([datetime]$calendar.StartBoundary).ToString("HH:mm:ss")
    return [ordered]@{
        task_name = $TaskName
        state = [string]$task.State
        enabled = [string]$task.State -ne "Disabled"
        description = [string]$task.Description
        execute = [string]$action.Execute
        arguments = [string]$action.Arguments
        working_directory = [string]$action.WorkingDirectory
        cadence = $actualCadence
        local_time = $actualTime
        weekday = $actualWeekday
        month_day = $actualMonthDay
        last_run_at = if ($info.LastRunTime.Year -gt 2000) { $info.LastRunTime.ToString("o") } else { $null }
        last_result = [int64]$info.LastTaskResult
        next_run_at = if ($info.NextRunTime.Year -gt 2000) { $info.NextRunTime.ToString("o") } else { $null }
    }
}

function Test-SnapshotMatches($Snapshot) {
    if ($null -eq $Snapshot) { return $false }
    return $Snapshot.description -eq (Get-ExpectedDescription) -and
        $Snapshot.execute -ieq $powerShell -and
        $Snapshot.arguments -eq (Get-ExpectedArguments) -and
        $Snapshot.working_directory -ieq $repo -and
        $Snapshot.cadence -eq $Cadence -and
        $Snapshot.local_time -eq $LocalTime -and
        [int]$Snapshot.weekday -eq $Weekday -and
        [int]$Snapshot.month_day -eq $MonthDay -and
        $Snapshot.enabled -eq $true
}

function New-TaskXml([string]$PrincipalUser) {
    $dayNames = @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
    $scheduleXml = if ($Cadence -eq "daily") {
        "<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>"
    } elseif ($Cadence -eq "weekly") {
        if ($Weekday -lt 1 -or $Weekday -gt 7 -or $MonthDay -ne 0) { throw "backup_schedule_cadence_fields_invalid" }
        "<ScheduleByWeek><WeeksInterval>1</WeeksInterval><DaysOfWeek><$($dayNames[$Weekday - 1]) /></DaysOfWeek></ScheduleByWeek>"
    } else {
        if ($MonthDay -lt 1 -or $MonthDay -gt 28 -or $Weekday -ne 0) { throw "backup_schedule_cadence_fields_invalid" }
        $months = "<January/><February/><March/><April/><May/><June/><July/><August/><September/><October/><November/><December/>"
        "<ScheduleByMonth><DaysOfMonth><Day>$MonthDay</Day></DaysOfMonth><Months>$months</Months></ScheduleByMonth>"
    }
    if ($Cadence -eq "daily" -and ($Weekday -ne 0 -or $MonthDay -ne 0)) { throw "backup_schedule_cadence_fields_invalid" }
    $startDate = (Get-Date).Date.ToString("yyyy-MM-dd")
    $description = ConvertTo-SafeXml (Get-ExpectedDescription)
    $command = ConvertTo-SafeXml $powerShell
    $arguments = ConvertTo-SafeXml (Get-ExpectedArguments)
    $workDir = ConvertTo-SafeXml $repo
    $user = ConvertTo-SafeXml $PrincipalUser
    return @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>$description</Description></RegistrationInfo>
  <Triggers><CalendarTrigger><StartBoundary>${startDate}T$LocalTime</StartBoundary><Enabled>true</Enabled>$scheduleXml</CalendarTrigger></Triggers>
  <Principals><Principal id="Author"><UserId>$user</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><AllowHardTerminate>true</AllowHardTerminate><StartWhenAvailable>true</StartWhenAvailable><RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable><IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings><AllowStartOnDemand>true</AllowStartOnDemand><Enabled>true</Enabled><Hidden>false</Hidden><RunOnlyIfIdle>false</RunOnlyIfIdle><DisallowStartOnRemoteAppSession>false</DisallowStartOnRemoteAppSession><UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine><WakeToRun>false</WakeToRun><ExecutionTimeLimit>PT6H</ExecutionTimeLimit><Priority>7</Priority></Settings>
  <Actions Context="Author"><Exec><Command>$command</Command><Arguments>$arguments</Arguments><WorkingDirectory>$workDir</WorkingDirectory></Exec></Actions>
</Task>
"@
}

if ($Mode -eq "Prune") {
    $expected = @{}
    foreach ($part in @($ExpectedScheduleIds -split ',' | Where-Object { $_ })) {
        $id = [long]$part
        if ($id -le 0) { throw "backup_schedule_id_invalid" }
        $expected[$id] = $true
    }
    $removed = @()
    $unmanaged = @()
    foreach ($task in @(Get-ScheduledTask -TaskName "$managedPrefix*" -TaskPath "\" -ErrorAction SilentlyContinue)) {
        if ($task.TaskName -notmatch '^NEXT Stabil - Backup - ([0-9]+)$') { $unmanaged += $task.TaskName; continue }
        $id = [long]$Matches[1]
        if ($expected.ContainsKey($id)) { continue }
        try { [void](Get-OwnedTask $task.TaskName) } catch { $unmanaged += $task.TaskName; continue }
        Unregister-ScheduledTask -TaskName $task.TaskName -TaskPath "\" -Confirm:$false
        $removed += $task.TaskName
    }
    [ordered]@{ mode="Prune"; removed=$removed; unmanaged=$unmanaged } | ConvertTo-Json -Compress
    return
}

$taskName = "$managedPrefix$ScheduleId"
$requestedEnabled = $Enabled -eq "true"
$existing = Get-ScheduledTask -TaskName $taskName -TaskPath "\" -ErrorAction SilentlyContinue
if ($null -ne $existing) {
    [void](Get-OwnedTask $taskName)
}
$before = Get-TaskSnapshot $taskName
if ($Mode -eq "Preview") {
    $matches = if ($requestedEnabled) { Test-SnapshotMatches $before } else { $null -eq $before }
    $mutation = if ($matches) { "none" } elseif ($requestedEnabled -and $null -eq $before) { "create" } elseif ($requestedEnabled) { "update" } else { "remove" }
    [ordered]@{ task_name=$taskName; sync_status=if($matches){"synced"}else{"pending_sync"}; mutation=$mutation; actual=$before } | ConvertTo-Json -Depth 6 -Compress
    return
}

if ($Mode -eq "Remove" -or -not $requestedEnabled) {
    if ($null -ne $before) {
        [void](Get-OwnedTask $taskName)
        Unregister-ScheduledTask -TaskName $taskName -TaskPath "\" -Confirm:$false
    }
    [ordered]@{ task_name=$taskName; sync_status="synced"; mutation=if($null -eq $before){"none"}else{"remove"}; enabled=$false; actual=$null } | ConvertTo-Json -Depth 6 -Compress
    return
}

$principalUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
if ($principalUser -notmatch '^S-1-[0-9-]+$') { throw "backup_scheduler_principal_invalid" }
$xml = New-TaskXml $principalUser
Register-ScheduledTask -TaskName $taskName -TaskPath "\" -Xml $xml -Force | Out-Null
$after = Get-TaskSnapshot $taskName
if (-not (Test-SnapshotMatches $after)) { throw "backup_scheduler_postcondition_failed" }
[ordered]@{ task_name=$taskName; sync_status="synced"; mutation=if($null -eq $before){"create"}else{"update"}; enabled=$true; actual=$after } | ConvertTo-Json -Depth 6 -Compress
