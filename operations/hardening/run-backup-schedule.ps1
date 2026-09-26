[CmdletBinding()]
param([Parameter(Mandatory=$true)][ValidateRange(1,9223372036854775807)][long]$ScheduleId,[string]$RepositoryRoot='C:\ai-lab-core')
$ErrorActionPreference='Stop'; Set-StrictMode -Version 2.0
function Invoke-BackendScheduleCli { param([string[]]$Arguments) $output=@(& docker.exe exec ai-lab-backend python -m app.scripts.run_backup_schedule @Arguments 2>&1); if($LASTEXITCODE -ne 0){throw "backup_schedule_state_failed:$($output -join ' ')"}; return $output }
function Test-Checkpoint { param([string]$Checkpoint,[long]$ExpectedRunId,[long]$ExpectedScheduleId)
  $root=[IO.Path]::GetFullPath($Checkpoint).TrimEnd('\'); $manifestPath=Join-Path $root 'backup-manifest.json'
  if(-not(Test-Path -LiteralPath $manifestPath -PathType Leaf)){throw 'backup_manifest_missing'}
  if(Get-ChildItem -LiteralPath $root -Recurse -File|Where-Object{$_.Name -match '\.partial($|\.)|\.tmp$'}){throw 'backup_partial_artifact_present'}
  $manifest=Get-Content -LiteralPath $manifestPath -Raw|ConvertFrom-Json
  if([string]$manifest.schema_version -ne 'NEXT_STABIL_BACKUP_V1'){throw 'backup_manifest_schema_invalid'}
  if([long]$manifest.run_id -ne $ExpectedRunId -or [long]$manifest.schedule_id -ne $ExpectedScheduleId -or [string]$manifest.trigger -ne 'scheduled'){throw 'backup_manifest_run_binding_invalid'}
  $count=0;[int64]$total=0
  foreach($artifact in @($manifest.artifacts)){ $relative=([string]$artifact.file).Replace('/','\');$absolute=[IO.Path]::GetFullPath((Join-Path $root $relative));if(-not $absolute.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'backup_artifact_path_escape'};$item=Get-Item -LiteralPath $absolute;if([int64]$item.Length -ne [int64]$artifact.bytes){throw 'backup_artifact_size_mismatch'};if((Get-FileHash -LiteralPath $absolute -Algorithm SHA256).Hash.ToLowerInvariant() -ne [string]$artifact.sha256){throw 'backup_artifact_hash_mismatch'};$count++;$total+=[int64]$item.Length }
  if($count -lt 1){throw 'backup_artifact_missing'}
  return [ordered]@{checkpoint_path=$root;manifest_path=$manifestPath;artifact_count=$count;total_bytes=$total;manifest_schema=[string]$manifest.schema_version;manifest_sha256=(Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant();app_version=[string]$manifest.app_version;source_head=[string]$manifest.source_head;db_revision=[string]$manifest.db_revision;created_at=[string]$manifest.created_at}
}
$repo=(Resolve-Path -LiteralPath $RepositoryRoot).Path
$prepare=Invoke-BackendScheduleCli @('--schedule-id',[string]$ScheduleId,'--phase','host-prepare');$operation=$prepare[-1]|ConvertFrom-Json
$destination=[IO.Path]::GetFullPath([string]$operation.destination).TrimEnd('\');$volume=[IO.Path]::GetPathRoot($destination).TrimEnd('\').ToUpperInvariant()
if($volume -in @('C:','D:')){throw 'backup_destination_system_or_data_volume_forbidden'}
if(-not(Test-Path -LiteralPath $destination -PathType Container)){throw 'backup_destination_unavailable'}
$probe=Join-Path $destination ('.next-stabil-schedule-probe-{0}.tmp' -f $operation.run_id);$logRoot=Join-Path $repo 'data\logs\backup-schedule';New-Item -ItemType Directory -Path $logRoot -Force|Out-Null;$logPath=Join-Path $logRoot ('run-{0}.log' -f $operation.run_id)
try{
  [IO.File]::WriteAllText($probe,'probe',[Text.UTF8Encoding]::new($false));if([IO.File]::ReadAllText($probe)-ne'probe'){throw 'backup_destination_not_writable'};Remove-Item -LiteralPath $probe -Force
  $lines=@(& (Join-Path $repo 'operations\hardening\backup-production.ps1') -RepositoryRoot $repo -BackupRoot $destination -Release ([string]$operation.release) -Scope ([string]$operation.scope) -RunId ([long]$operation.run_id) -Trigger 'scheduled' -ScheduleId $ScheduleId 2>&1)
  $lines|ForEach-Object{[string]$_}|Set-Content -LiteralPath $logPath -Encoding UTF8;$complete=@($lines|ForEach-Object{[string]$_}|Where-Object{$_ -like 'BACKUP_COMPLETE=*'});if($complete.Count-ne 1){throw 'backup_checkpoint_missing'};$checkpoint=$complete[0].Substring('BACKUP_COMPLETE='.Length)
  $evidence=Test-Checkpoint -Checkpoint $checkpoint -ExpectedRunId ([long]$operation.run_id) -ExpectedScheduleId $ScheduleId;$encoded=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(($evidence|ConvertTo-Json -Compress)))
  Invoke-BackendScheduleCli @('--schedule-id',[string]$ScheduleId,'--phase','host-complete','--run-id',[string]$operation.run_id,'--evidence-base64',$encoded)|ForEach-Object{Write-Output $_};Write-Output ('SCHEDULE_PROOF_LOG={0}' -f $logPath)
}catch{
  if(Test-Path -LiteralPath $probe){Remove-Item -LiteralPath $probe -Force};$code=if($_.Exception.Message){[string]$_.Exception.Message}else{'backup_runner_failed'};$safeCode=($code -replace '[^A-Za-z0-9_.:-]','_');if($safeCode.Length-gt 100){$safeCode=$safeCode.Substring(0,100)};try{Invoke-BackendScheduleCli @('--schedule-id',[string]$ScheduleId,'--phase','host-fail','--run-id',[string]$operation.run_id,'--error-code',$safeCode)|Out-Null}catch{};Add-Content -LiteralPath $logPath -Value ('ERROR={0}' -f $code);throw
}
