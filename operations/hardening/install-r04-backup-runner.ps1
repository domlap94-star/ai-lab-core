[CmdletBinding()]
param([string]$SourceRoot='C:\ai-lab-core-recovery',[string]$InstallRoot='C:\ai-lab-core',[string]$OutputRoot='C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-R04-BACKUP-RUNNER-20260926')
$ErrorActionPreference='Stop';Set-StrictMode -Version 2.0
$items=@(
  [pscustomobject]@{relative='backend\app\scripts\run_backup_schedule.py';pre='A9065CDE2FB69DFE18F7B760FEBBFD6EDBEE68D3C16C9EDF7DD1A796CA47A614'},
  [pscustomobject]@{relative='operations\hardening\run-backup-schedule.ps1';pre='83717D1178F4BCD45727E3665C97FD81A9BDB94CD43AE3C45ABF19006A69C56B'}
)
$preimages=Join-Path $OutputRoot 'preimages';New-Item -ItemType Directory -Path $preimages -Force|Out-Null
foreach($item in $items){$target=Join-Path $InstallRoot $item.relative;if((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash-ne$item.pre){throw "PREIMAGE_MISMATCH:$($item.relative)"};$saved=Join-Path $preimages $item.relative;New-Item -ItemType Directory -Path (Split-Path -Parent $saved)-Force|Out-Null;Copy-Item -LiteralPath $target -Destination $saved;Copy-Item -LiteralPath (Join-Path $SourceRoot $item.relative)-Destination $target -Force;if((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash-ne(Get-FileHash -LiteralPath (Join-Path $SourceRoot $item.relative)-Algorithm SHA256).Hash){throw "POSTIMAGE_MISMATCH:$($item.relative)"}}
$result=[ordered]@{status='INSTALLED';files=@($items.relative);preimages=$preimages};$result|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $OutputRoot 'result.json')-Encoding UTF8;$result|ConvertTo-Json -Compress
