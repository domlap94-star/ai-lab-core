[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$BackupRoot,
  [Parameter(Mandatory=$true)][string]$ArtifactRoot,
  [Parameter(Mandatory=$true)][string[]]$Collections,
  [Parameter(Mandatory=$true)][string]$OperationId,
  [Parameter(Mandatory=$true)][string]$ValidatorPath,
  [int]$HelperPort=16333
)
$ErrorActionPreference='Stop';Set-StrictMode -Version 2.0
function Docker([string[]]$Arguments){$o=@(& docker.exe @Arguments 2>&1);if($LASTEXITCODE-ne0){throw "docker_failed:$($o-join ' ')"};return $o}
function Api([string]$Uri,[string]$Method='Get'){Invoke-RestMethod -Method $Method -Uri $Uri -TimeoutSec 900}
function Snapshot([string]$Collection,[string]$Base){$info=Api "$Base/collections/$Collection";$aliases=Api "$Base/collections/$Collection/aliases";if($info.status-ne'ok'-or$aliases.status-ne'ok'){throw "qdrant_inventory_failed:$Collection"};[ordered]@{collection=$Collection;points_count=[int64]$info.result.points_count;indexed_vectors_count=[int64]$info.result.indexed_vectors_count;segments_count=[int]$info.result.segments_count;config=$info.result.config;aliases=@($aliases.result.aliases|ForEach-Object{[string]$_.alias_name})}}
$backup=[IO.Path]::GetFullPath($BackupRoot).TrimEnd('\');if([IO.Path]::GetPathRoot($backup).TrimEnd('\').ToUpperInvariant()-ne'F:'){throw 'qdrant_staging_not_on_f'}
$rootItem=Get-Item -LiteralPath $backup;if($rootItem.Attributes-band[IO.FileAttributes]::ReparsePoint){throw 'qdrant_backup_root_reparse'}
$safe=($OperationId-replace'[^A-Za-z0-9_.-]','-');$staging=Join-Path $backup ".next-stabil-qdrant-staging\$safe";if(Test-Path -LiteralPath $staging){throw 'qdrant_staging_collision'};New-Item -ItemType Directory -Path $staging -Force|Out-Null
$probe=Join-Path $staging '.probe';[IO.File]::WriteAllText($probe,'probe',[Text.UTF8Encoding]::new($false));Remove-Item $probe -Force
$drive=Get-PSDrive F;if([int64]$drive.Free-lt 5GB){throw 'qdrant_staging_space_low'}
$base='http://127.0.0.1:6333';$helperBase="http://127.0.0.1:$HelperPort";$helper="next-stabil-qdrant-backup-$safe";$baseId=(Docker @('inspect','-f','{{.Id}}','qdrant'))[-1].Trim();$imageId=(Docker @('inspect','-f','{{.Image}}','qdrant'))[-1].Trim();$imageRef=(Docker @('inspect','-f','{{.Config.Image}}','qdrant'))[-1].Trim();$restart=(Docker @('inspect','-f','{{.HostConfig.RestartPolicy.Name}}','qdrant'))[-1].Trim();$volume=(Docker @('inspect','-f','{{range .Mounts}}{{if eq .Destination "/qdrant/storage"}}{{.Name}}{{end}}{{end}}','qdrant'))[-1].Trim();if(-not$volume){throw 'qdrant_named_volume_missing'}
$before=@($Collections|ForEach-Object{Snapshot $_ $base});$records=@();$helperCreated=$false;$primaryStopped=$false
try{
  Docker @('stop','-t','60','qdrant')|Out-Null;$primaryStopped=$true;$running=(Docker @('inspect','-f','{{.State.Running}}','qdrant'))[-1].Trim();if($running-ne'false'){throw 'qdrant_primary_not_stopped'}
  $mount="type=bind,src=$staging,dst=/qdrant/snapshots";Docker @('run','-d','--name',$helper,'--pull','never','--restart','no','-p',"127.0.0.1:$HelperPort`:6333",'--mount',"source=$volume,target=/qdrant/storage",'--mount',$mount,'-e','QDRANT__STORAGE__SNAPSHOTS_PATH=/qdrant/snapshots','-e','QDRANT__STORAGE__TEMP_PATH=/qdrant/snapshots/temp',$imageId)|Out-Null;$helperCreated=$true
  $deadline=(Get-Date).AddMinutes(3);do{Start-Sleep 2;try{$ready=Invoke-WebRequest -UseBasicParsing -Uri "$helperBase/readyz" -TimeoutSec 3}catch{$ready=$null}}while((-not$ready-or$ready.StatusCode-ne200)-and(Get-Date)-lt$deadline);if(-not$ready-or$ready.StatusCode-ne200){throw 'qdrant_helper_not_ready'}
  foreach($collection in $Collections){$baseline=$before|Where-Object{$_.collection-eq$collection};$response=Api "$helperBase/collections/$collection/snapshots" 'Post';if($response.status-ne'ok'-or-not$response.result.name){throw "qdrant_snapshot_create_failed:$collection"};$name=[string]$response.result.name;$source=Join-Path $staging $name;if(-not(Test-Path -LiteralPath $source -PathType Leaf)){throw "qdrant_snapshot_not_on_f:$collection"};$validationJson=@(& node.exe $ValidatorPath $source 2>$null);if($LASTEXITCODE-ne0-or-not$validationJson){throw "qdrant_snapshot_invalid:$collection"};$validation=($validationJson-join'')|ConvertFrom-Json;if($validation.valid-ne$true){throw "qdrant_snapshot_invalid:$collection"};$destination=Join-Path $ArtifactRoot "$collection.snapshot";Move-Item -LiteralPath $source -Destination $destination;$item=Get-Item $destination;$records+=[ordered]@{collection=$collection;artifact=$destination;bytes=[int64]$item.Length;sha256=(Get-FileHash $destination -Algorithm SHA256).Hash.ToLowerInvariant();snapshot_name=$name;points_count=$baseline.points_count;indexed_vectors_count=$baseline.indexed_vectors_count;segments_count=$baseline.segments_count;config=$baseline.config;aliases=$baseline.aliases;structurally_valid=$true;structural_validation_reason=[string]$validation.reason}}
}finally{
  if($helperCreated){& docker.exe stop -t 30 $helper 2>$null|Out-Null;& docker.exe rm -f $helper 2>$null|Out-Null}
  if($primaryStopped){Docker @('start','qdrant')|Out-Null;$deadline=(Get-Date).AddMinutes(3);do{Start-Sleep 2;try{$ready=Invoke-WebRequest -UseBasicParsing -Uri "$base/readyz" -TimeoutSec 3}catch{$ready=$null}}while((-not$ready-or$ready.StatusCode-ne200)-and(Get-Date)-lt$deadline)}
}
$afterId=(Docker @('inspect','-f','{{.Id}}','qdrant'))[-1].Trim();if($afterId-ne$baseId){throw 'qdrant_primary_identity_changed'};$after=@($Collections|ForEach-Object{Snapshot $_ $base});foreach($b in $before){$a=$after|Where-Object{$_.collection-eq$b.collection};if($a.points_count-ne$b.points_count-or$a.indexed_vectors_count-ne$b.indexed_vectors_count-or(($a.aliases-join'|')-ne($b.aliases-join'|'))){throw "qdrant_post_state_mismatch:$($b.collection)"}}
if(@(Docker @('ps','-a','--filter',"name=^/$helper$",'--format','{{.ID}}')).Count-ne0){throw 'qdrant_helper_residue'}
$residue=@(Get-ChildItem -LiteralPath $staging -Recurse -File -Force);if($residue.Count){throw 'qdrant_staging_residue'};Remove-Item -LiteralPath $staging -Recurse -Force
[ordered]@{status='PASS';primary_container_id=$baseId;image_id=$imageId;image_ref=$imageRef;restart_policy=$restart;named_volume=$volume;helper_name=$helper;helper_removed=$true;staging_root=$staging;staging_volume='F:';records=$records;before=$before;after=$after}|ConvertTo-Json -Depth 12 -Compress
