[CmdletBinding()]
param([string]$SourceRoot='C:\ai-lab-core-recovery',[string]$InstallRoot='C:\ai-lab-core',[string]$OutputRoot='C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-R04-COMPLETION-20260926')
$ErrorActionPreference='Stop';Set-StrictMode -Version 2.0
$pre=Join-Path $OutputRoot 'preimages';New-Item -ItemType Directory -Path $pre -Force|Out-Null
$expected=@{
 'operations\supervisor\server.js'='4CFB7F9E3D97521D8D0F6D588BB119AB34C9D52FAD498AA520368CD13B170701'
 'operations\supervisor\analysis_queue.js'='F26E521CB50B76FB35BB28A09C0919167164F1E11131FD7E7CE39FBA4EF05CAA'
 'operations\supervisor\vision_queue.js'='37B0AFFDB2D3C355E4377BE4EF905CC1A8EFCCE635089B8E002D5445C8505F33'
 'operations\vision-worker\vision-job.js'='A059A64B1BD7658990A8A14ACD03D433697792FBCC6C231D18319AB48EFCFB9A'
 'operations\vision-worker\analysis-job.js'='2D9E4B0B639D052611F57C5A17AF7DAD415E5D7BAA78349C420BF3E13B2C971C'
 'backend\app\scripts\run_backup_schedule.py'='A9065CDE2FB69DFE18F7B760FEBBFD6EDBEE68D3C16C9EDF7DD1A796CA47A614'
 'operations\hardening\run-backup-schedule.ps1'='83717D1178F4BCD45727E3665C97FD81A9BDB94CD43AE3C45ABF19006A69C56B'
 'operations\runtime\startup-set.json'='53CA6E98F81915D62C7695D8F077FACC95E394D897BD2E9D12000143B6972EC9'
}
foreach($rel in $expected.Keys){$target=Join-Path $InstallRoot $rel;if((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash-ne$expected[$rel]){throw "PREIMAGE_MISMATCH:$rel"};$copy=Join-Path $pre $rel;New-Item -ItemType Directory -Path (Split-Path -Parent $copy)-Force|Out-Null;Copy-Item -LiteralPath $target -Destination $copy}
$active=Get-CimInstance Win32_Process|Where-Object{$_.CommandLine -match '(?i)(vision-job|analysis-job|ChatGPT-Vision-Worker)'}
if($active){throw 'WORKER_PROCESS_ACTIVE'}
$reparse=Get-ChildItem -LiteralPath 'C:\ChatGPT-Vision-Worker' -Recurse -Force|Where-Object{$_.Attributes-band[IO.FileAttributes]::ReparsePoint}
if($reparse){throw 'WORKER_SOURCE_REPARSE_POINT'}
$state=Join-Path $InstallRoot 'data\workers\chatgpt-vision';New-Item -ItemType Directory -Path $state -Force|Out-Null
foreach($name in @('edge-profile','input','logs','output','rollback')){$src=Join-Path 'C:\ChatGPT-Vision-Worker' $name;$dst=Join-Path $state $name;if(Test-Path -LiteralPath $src){& robocopy.exe $src $dst /E /COPY:DATS /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP|Out-Null;if($LASTEXITCODE-ge 8){throw "WORKER_STATE_COPY_FAILED:$name"}}}
$modulesSource='C:\ChatGPT-Vision-Worker\worker\node_modules';$modulesTarget=Join-Path $InstallRoot 'operations\vision-worker\node_modules';New-Item -ItemType Directory -Path $modulesTarget -Force|Out-Null;& robocopy.exe $modulesSource $modulesTarget /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP|Out-Null;if($LASTEXITCODE-ge 8){throw 'WORKER_MODULES_COPY_FAILED'}
$files=@('operations\supervisor\server.js','operations\supervisor\analysis_queue.js','operations\supervisor\vision_queue.js','operations\vision-worker\vision-job.js','operations\vision-worker\analysis-job.js','operations\vision-worker\package.json','operations\vision-worker\package-lock.json','backend\app\scripts\run_backup_schedule.py','operations\hardening\run-backup-schedule.ps1')
foreach($rel in $files){Copy-Item -LiteralPath (Join-Path $SourceRoot $rel)-Destination (Join-Path $InstallRoot $rel)-Force}
Copy-Item -LiteralPath (Join-Path $SourceRoot 'docs\recovery\R04_DATA_BACKUP_STARTUP_SET_CANDIDATE.json')-Destination (Join-Path $InstallRoot 'operations\runtime\startup-set.json')-Force
foreach($rel in $files){if((Get-FileHash -LiteralPath (Join-Path $SourceRoot $rel)-Algorithm SHA256).Hash-ne(Get-FileHash -LiteralPath (Join-Path $InstallRoot $rel)-Algorithm SHA256).Hash){throw "POSTIMAGE_MISMATCH:$rel"}}
function Inventory([string]$Path){$items=@(Get-ChildItem -LiteralPath $Path -Recurse -File);[pscustomobject]@{files=$items.Count;bytes=[int64](($items|Measure-Object Length -Sum).Sum);aggregate_sha256=(($items|Sort-Object FullName|ForEach-Object{"$($_.FullName.Substring($Path.Length).ToLowerInvariant())|$($_.Length)|$((Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant())"})-join "`n"|ForEach-Object{$b=[Text.Encoding]::UTF8.GetBytes($_);$s=[Security.Cryptography.SHA256]::Create();([BitConverter]::ToString($s.ComputeHash($b))).Replace('-','').ToLowerInvariant()})}}
$stateChecks=@();foreach($name in @('edge-profile','input','logs','output','rollback')){$src=Join-Path 'C:\ChatGPT-Vision-Worker' $name;if(Test-Path -LiteralPath $src){$a=Inventory $src;$b=Inventory (Join-Path $state $name);if($a.files-ne$b.files-or$a.bytes-ne$b.bytes-or$a.aggregate_sha256-ne$b.aggregate_sha256){throw "WORKER_STATE_VERIFY_FAILED:$name"};$stateChecks+=[pscustomobject]@{name=$name;files=$a.files;bytes=$a.bytes;sha256=$a.aggregate_sha256;acl_preserved=((Get-Acl -LiteralPath $src).Sddl-eq(Get-Acl -LiteralPath (Join-Path $state $name)).Sddl)}}}
$moduleSource=Inventory $modulesSource;$moduleTarget=Inventory $modulesTarget;if($moduleSource.files-ne$moduleTarget.files-or$moduleSource.bytes-ne$moduleTarget.bytes-or$moduleSource.aggregate_sha256-ne$moduleTarget.aggregate_sha256){throw 'WORKER_MODULES_VERIFY_FAILED'}
$result=[ordered]@{status='INSTALLED';state_checks=$stateChecks;state_root=$state;modules_root=$modulesTarget;modules=$moduleTarget;old_source_preserved=$true;preimages=$pre;installed_files=$files}
$result|ConvertTo-Json -Depth 6|Set-Content -LiteralPath (Join-Path $OutputRoot 'install-result.json')-Encoding UTF8
$result|ConvertTo-Json -Compress -Depth 6
