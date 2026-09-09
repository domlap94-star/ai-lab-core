# R04-A2 isolated real-app smoke

This is a test-only recipe for the authorized R04-A2 run. It does not deploy
or alter production. Stop if the selected root, Docker names, ports, source SHA
or local pinned image identities differ from the recorded checkpoint.

## Isolation contract

- Create a fresh external root and extract the complete source snapshot from
  exact Git object `f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99`.
- Mount that snapshot into the backend read-only. Use a separate mutable copy
  for each Flutter build; generated files do not change code under test.
- Use only the exact-name project/network/containers/volume from the run
  checkpoint. PostgreSQL and backend remain on the internal network and have no
  host ports. A credential-free, fixed-target transport bridge is the only
  container on the separate ingress network and binds API only to
  `127.0.0.1:18004`; Web binds only `127.0.0.1:18005`.
- Use locally present image IDs, `pull_policy: never`, synthetic one-run
  credentials and a synthetic `.invalid` account. Never reuse production env,
  DB, storage, networks, cookies or credentials.
- Keep preparation, Assistant, Vision, Advanced, KB processing/vector writes,
  restore and retention deletion disabled. Unreachable external URLs and the
  internal network are independent barriers.

## Literal PowerShell 5.1 reproduction

Run from a normal PowerShell 5.1 window. The commands intentionally require a
fresh run ID and a non-existing root. They do not read a production `.env`.
Keep the generated values in this process only and do not copy the rendered
Compose configuration into Git.

```powershell
$ErrorActionPreference = "Stop"
$Recovery = "C:\ai-lab-core-recovery"
$SourceSha = "f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99"
$RunId = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$Root = "C:\ai-lab-core-staging\recovery\R04_A2_REAL_APP_$RunId"
$SourceRoot = Join-Path $Root "source-clean"
$WebRoot = Join-Path $Root "web-source"
$DataRoot = Join-Path $Root "data"
$RawRoot = Join-Path $Root "raw"
$Compose = Join-Path $Recovery "operations\recovery\r04-a2\compose.yaml"
$Fixture = Join-Path $Recovery "operations\recovery\r04-a2\fixtures\synthetic-document.txt"

if ((git -C $Recovery rev-parse $SourceSha) -ne $SourceSha) { throw "source object mismatch" }
if (Test-Path -LiteralPath $Root) { throw "R04-A2 root collision: $Root" }
if (Get-NetTCPConnection -State Listen -LocalPort 18004,18005 -ErrorAction SilentlyContinue) {
    throw "R04-A2 loopback port collision"
}

New-Item -ItemType Directory -Path $SourceRoot,$WebRoot,$DataRoot,$RawRoot | Out-Null
$Archive = Join-Path $Root "source-$($SourceSha.Substring(0,8)).tar"
git -C $Recovery archive --format=tar --output=$Archive $SourceSha
tar.exe -xf $Archive -C $SourceRoot
Copy-Item -Path (Join-Path $SourceRoot "frontend\*") -Destination $WebRoot -Recurse

Add-Type -AssemblyName System.Security
function New-R04Secret([int]$Bytes = 36) {
    $buffer = New-Object byte[] $Bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buffer)
    [Convert]::ToBase64String($buffer)
}

$idLower = $RunId.ToLowerInvariant()
$env:R04_A2_RUN_ID = $RunId
$env:R04_A2_PROJECT = "next-stabil-r04-a2-$idLower"
$env:R04_A2_POSTGRES_CONTAINER = "$($env:R04_A2_PROJECT)-postgres"
$env:R04_A2_BACKEND_CONTAINER = "$($env:R04_A2_PROJECT)-backend"
$env:R04_A2_TRANSPORT_CONTAINER = "$($env:R04_A2_PROJECT)-transport"
$env:R04_A2_POSTGRES_VOLUME = "$($env:R04_A2_PROJECT)-postgres-data"
$env:R04_A2_NETWORK = "$($env:R04_A2_PROJECT)-internal"
$env:R04_A2_INGRESS_NETWORK = "$($env:R04_A2_PROJECT)-ingress"
$env:R04_A2_DATABASE_NAME = "ai_lab_r04_a2_$($RunId.Substring(0,15).ToLowerInvariant())"
$env:R04_A2_DATABASE_USER = "r04_a2_owner"
$env:R04_A2_DATABASE_PASSWORD = New-R04Secret
$env:R04_A2_SECRET_KEY = New-R04Secret 48
$env:R04_A2_ADMIN_USERNAME = "r04_a2_admin"
$env:R04_A2_ADMIN_EMAIL = "r04-a2-$idLower@example.invalid"
$env:R04_A2_ADMIN_PASSWORD = New-R04Secret
$env:R04_A2_N8N_INGEST_API_KEY = New-R04Secret
$env:R04_A2_SOURCE_ROOT = $SourceRoot
$env:R04_A2_DATA_ROOT = $DataRoot
$env:R04_A2_TRANSPORT_SCRIPT = Join-Path $Recovery "operations\recovery\r04-a2\loopback_proxy.py"
$env:R04_A2_POSTGRES_IMAGE = "sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685"
$env:R04_A2_BACKEND_IMAGE = "sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651"
$env:R04_A2_BACKEND_IMAGE_ID = $env:R04_A2_BACKEND_IMAGE

docker image inspect $env:R04_A2_POSTGRES_IMAGE --format '{{.Id}}'
docker image inspect $env:R04_A2_BACKEND_IMAGE --format '{{.Id}}'
docker compose -f $Compose config | Out-File -LiteralPath (Join-Path $RawRoot "compose-config.local.txt") -Encoding utf8
docker compose -f $Compose up -d --no-build postgres
docker exec $env:R04_A2_POSTGRES_CONTAINER psql -U $env:R04_A2_DATABASE_USER -d $env:R04_A2_DATABASE_NAME -Atc "select current_database();"
docker inspect --format '{{.Name}}|{{.Config.Image}}|{{json .NetworkSettings.Ports}}|{{json .Mounts}}|{{json .HostConfig.SecurityOpt}}|{{.HostConfig.Privileged}}|{{.HostConfig.PidMode}}' $env:R04_A2_POSTGRES_CONTAINER
docker compose -f $Compose run --rm --no-deps `
    --name "$($env:R04_A2_PROJECT)-migrate" --entrypoint python `
    backend -m alembic -c alembic.ini upgrade head
docker exec $env:R04_A2_POSTGRES_CONTAINER psql -U $env:R04_A2_DATABASE_USER -d $env:R04_A2_DATABASE_NAME -Atc "select version_num from alembic_version;"
docker compose -f $Compose up -d --no-build backend transport
docker inspect --format '{{.Name}}|{{.Config.Image}}|{{json .NetworkSettings.Ports}}|{{json .Mounts}}|{{json .HostConfig.SecurityOpt}}|{{.HostConfig.Privileged}}|{{.HostConfig.PidMode}}' $env:R04_A2_BACKEND_CONTAINER $env:R04_A2_TRANSPORT_CONTAINER
docker network inspect $env:R04_A2_NETWORK --format '{{.Name}}|internal={{.Internal}}|{{json .Labels}}'
docker network inspect $env:R04_A2_INGRESS_NETWORK --format '{{.Name}}|internal={{.Internal}}|{{json .Labels}}'

Invoke-WebRequest -UseBasicParsing http://127.0.0.1:18004/health
$version = Invoke-RestMethod -UseBasicParsing http://127.0.0.1:18004/version
function Assert-R04A2SourceRevision {
    param([Parameter(Mandatory=$true)][object]$Version,
          [Parameter(Mandatory=$true)][string]$Expected)
    $identity = $Version.PSObject.Properties['component_identity']
    if ($null -eq $identity -or $null -eq $identity.Value) { throw "component_identity missing" }
    $backend = $identity.Value.PSObject.Properties['backend']
    if ($null -eq $backend -or $null -eq $backend.Value) { throw "component_identity.backend missing" }
    $source = $backend.Value.PSObject.Properties['source_revision']
    if ($null -eq $source) { throw "component_identity.backend.source_revision missing" }
    $observed = [string]$source.Value
    if ([string]::IsNullOrWhiteSpace($observed) -or $observed -eq 'UNKNOWN') {
        throw "backend source revision is not verified"
    }
    if ($observed -notmatch '^[0-9a-f]{40}$' -or $observed -ne $Expected) {
        throw "runtime source mismatch"
    }
    $observed
}
Assert-R04A2SourceRevision -Version $version -Expected $SourceSha | Out-Null
```

## Resume the preserved 20260909T131617Z run

`RESUME` is different from `FRESH RUN`: do not create the root again, extract
Git, migrate, seed, or use values remembered by an old shell. Start from the
published resource manifest and the protected local synthetic credential file.
The manifest records historical running state; resume compares immutable IDs,
images, labels, mounts and networks, then requires the current state to be
stopped before it starts anything.

```powershell
$ErrorActionPreference = "Stop"
$ExpectedSource = "f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99"
$Root = "C:\ai-lab-core-staging\recovery\R04_A2_REAL_APP_20260909T131617Z"
$ContinuationRoot = Join-Path $Root "continuation-<actual-UTC>"
$ResourceManifestPath = Join-Path $Root "raw\resource-manifest.json"
$CredentialsPath = Join-Path $Root "raw\ui-credentials.local.json"
$SourceArchive = Join-Path $Root "source-f4ea20c.tar"
$SourceRoot = Join-Path $Root "source-clean"
$WebRoot = Join-Path $Root "web-source"
$expectedArchiveHash = "B93DF8FE6F2D86EE32394D7DE08EF45DB44E99A97C9A38F6231A44200400F391"
$expectedDocumentHash = "C0EBC642C0AE14C7A3D8D4A4A6B5F9178E0370CDC3241E3155E710D88E7EB0F2"

foreach ($required in $Root,$ContinuationRoot,$ResourceManifestPath,$CredentialsPath,$SourceArchive,$SourceRoot,$WebRoot) {
    if (-not (Test-Path -LiteralPath $required)) { throw "required preserved path missing" }
}
if ((Get-FileHash -LiteralPath $SourceArchive -Algorithm SHA256).Hash -ne $expectedArchiveHash) {
    throw "preserved source archive mismatch"
}
if (Get-NetTCPConnection -State Listen -LocalPort 18004,18005 -ErrorAction SilentlyContinue) {
    throw "R04-A2 loopback port collision"
}

$resourceManifest = Get-Content -LiteralPath $ResourceManifestPath -Raw | ConvertFrom-Json
if ($resourceManifest.run_id -ne '20260909T131617Z') { throw "resource manifest run mismatch" }

function Invoke-R04DockerValue {
    param([Parameter(Mandatory=$true)][string[]]$Arguments)
    $value = & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw "docker command failed" }
    (($value | ForEach-Object { [string]$_ }) -join "`n").Trim()
}

foreach ($expected in $resourceManifest.docker_resources) {
    $actualId = Invoke-R04DockerValue @('inspect','--format','{{.Id}}',$expected.name)
    $actualImage = Invoke-R04DockerValue @('inspect','--format','{{.Image}}',$expected.name)
    $actualState = Invoke-R04DockerValue @('inspect','--format','{{.State.Status}}',$expected.name)
    $actualOwner = Invoke-R04DockerValue @('inspect','--format','{{index .Config.Labels "next-stabil.owner"}}',$expected.name)
    $actualRun = Invoke-R04DockerValue @('inspect','--format','{{index .Config.Labels "next-stabil.run-id"}}',$expected.name)
    if ($actualId -ne $expected.id -or $actualImage -ne $expected.image_id) { throw "container identity mismatch" }
    if ($actualOwner -ne 'R04-A2' -or $actualRun -ne '20260909T131617Z') { throw "container ownership mismatch" }
    if ($actualState -ne 'exited') { throw "preserved container is not stopped" }
}

$postgres = 'next-stabil-r04-a2-20260909t131617z-postgres'
$backend = 'next-stabil-r04-a2-20260909t131617z-backend'
$transport = 'next-stabil-r04-a2-20260909t131617z-transport'
$database = 'ai_lab_r04_a2_20260909'
$databaseUser = 'r04_a2_owner'

$postgresMounts = (Invoke-R04DockerValue @('inspect','--format','{{json .Mounts}}',$postgres)) | ConvertFrom-Json
$backendMounts = (Invoke-R04DockerValue @('inspect','--format','{{json .Mounts}}',$backend)) | ConvertFrom-Json
$transportMounts = (Invoke-R04DockerValue @('inspect','--format','{{json .Mounts}}',$transport)) | ConvertFrom-Json
if (@($postgresMounts | Where-Object { $_.Name -eq 'next-stabil-r04-a2-20260909t131617z-postgres-data' -and $_.Destination -eq '/var/lib/postgresql/data' }).Count -ne 1) { throw "postgres mount mismatch" }
if (@($backendMounts | Where-Object { $_.Source -eq $SourceRoot -and $_.Destination -eq '/workspace' -and -not $_.RW }).Count -ne 1) { throw "backend source mount mismatch" }
if (@($backendMounts | Where-Object { $_.Source -eq (Join-Path $Root 'data') -and $_.Destination -eq '/r04-data' -and $_.RW }).Count -ne 1) { throw "backend data mount mismatch" }
if (@($transportMounts | Where-Object { $_.Destination -eq '/transport/loopback_proxy.py' -and -not $_.RW }).Count -ne 1) { throw "transport mount mismatch" }

Invoke-R04DockerValue @('start',$postgres) | Out-Null
$deadline=[DateTime]::UtcNow.AddSeconds(90)
do {
    $health=Invoke-R04DockerValue @('inspect','--format','{{.State.Health.Status}}',$postgres)
    if ($health -eq 'healthy') { break }
    Start-Sleep -Seconds 2
} while ([DateTime]::UtcNow -lt $deadline)
if ($health -ne 'healthy') { throw "postgres health timeout" }

$currentDatabase=Invoke-R04DockerValue @('exec',$postgres,'psql','-U',$databaseUser,'-d',$database,'-Atc','select current_database();')
$dbHead=Invoke-R04DockerValue @('exec',$postgres,'psql','-U',$databaseUser,'-d',$database,'-Atc','select version_num from alembic_version;')
if ($currentDatabase -ne $database) { throw "database identity mismatch" }
if ($dbHead -ne 'followup_assistant_chat_history_20260829') { throw "database head mismatch" }

Invoke-R04DockerValue @('start',$backend) | Out-Null
$deadline=[DateTime]::UtcNow.AddSeconds(90)
do {
    $health=Invoke-R04DockerValue @('inspect','--format','{{.State.Health.Status}}',$backend)
    if ($health -eq 'healthy') { break }
    Start-Sleep -Seconds 2
} while ([DateTime]::UtcNow -lt $deadline)
if ($health -ne 'healthy') { throw "backend health timeout" }
Invoke-R04DockerValue @('start',$transport) | Out-Null

function Assert-R04A2SourceRevision {
    param([Parameter(Mandatory=$true)][object]$Version,
          [Parameter(Mandatory=$true)][string]$Expected)
    $identity = $Version.PSObject.Properties['component_identity']
    if ($null -eq $identity -or $null -eq $identity.Value) { throw "component_identity missing" }
    $backendIdentity = $identity.Value.PSObject.Properties['backend']
    if ($null -eq $backendIdentity -or $null -eq $backendIdentity.Value) { throw "component_identity.backend missing" }
    $source = $backendIdentity.Value.PSObject.Properties['source_revision']
    if ($null -eq $source) { throw "component_identity.backend.source_revision missing" }
    $observed = [string]$source.Value
    if ([string]::IsNullOrWhiteSpace($observed) -or $observed -eq 'UNKNOWN') { throw "backend source revision is not verified" }
    if ($observed -notmatch '^[0-9a-f]{40}$' -or $observed -ne $Expected) { throw "runtime source mismatch" }
    $observed
}

$version=Invoke-RestMethod -UseBasicParsing http://127.0.0.1:18004/version
Assert-R04A2SourceRevision -Version $version -Expected $ExpectedSource | Out-Null
$credential=Get-Content -LiteralPath $CredentialsPath -Raw | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace([string]$credential.username) -or [string]::IsNullOrWhiteSpace([string]$credential.password)) { throw "synthetic credentials unavailable" }
$api='http://127.0.0.1:18004/api/v1'
$login=Invoke-RestMethod -UseBasicParsing -Method Post -Uri "$api/auth/login" -ContentType 'application/x-www-form-urlencoded' -Body @{username=$credential.username;password=$credential.password}
$headers=@{Authorization="Bearer $($login.access_token)"}
$clientsResponse=Invoke-RestMethod -UseBasicParsing -Headers $headers -Uri "$api/clients?limit=100"
$clients=if ($clientsResponse -is [System.Array]) { [object[]]$clientsResponse } else { @($clientsResponse) }
$primary=@($clients | Where-Object name -eq 'R04 A2 Primary Case')
$other=@($clients | Where-Object name -eq 'R04 A2 Distinguishing Record')
if ($primary.Count -ne 1 -or $other.Count -ne 1 -or $primary[0].id -eq $other[0].id) { throw "synthetic client identity mismatch" }
$documents=Invoke-RestMethod -UseBasicParsing -Headers $headers -Uri "$api/documents?client_id=$($primary[0].id)&limit=100"
$document=@($documents.items | Where-Object original_filename -eq 'synthetic-document.txt')
if ($document.Count -ne 1 -or $document[0].client_id -ne $primary[0].id -or $document[0].file_size -ne 204) { throw "synthetic document identity mismatch" }
```

Run the guard contract without a backend by using synthetic response objects.
Every negative case below must throw; a missing field or `UNKNOWN` is never a
default to the expected SHA:

```powershell
$expected='f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99'
$positive=[pscustomobject]@{component_identity=[pscustomobject]@{backend=[pscustomobject]@{source_revision=$expected}}}
Assert-R04A2SourceRevision -Version $positive -Expected $expected | Out-Null
$negative=@(
    [pscustomobject]@{component_identity=[pscustomobject]@{backend=[pscustomobject]@{}}},
    [pscustomobject]@{component_identity=[pscustomobject]@{backend=[pscustomobject]@{source_revision='UNKNOWN'}}},
    [pscustomobject]@{component_identity=[pscustomobject]@{backend=[pscustomobject]@{source_revision=('0' * 40)}}}
)
foreach($case in $negative) {
    $stopped=$false
    try { Assert-R04A2SourceRevision -Version $case -Expected $expected | Out-Null }
    catch { $stopped=$true }
    if (-not $stopped) { throw "negative source identity case did not stop" }
}
```

Before seeding, inspect the exact containers with allowlisted fields and require
the recorded names, owner labels, no PostgreSQL/backend host ports, the internal
network, the read-only source mount, and no Docker socket/production mount. Then
seed only through authenticated HTTP:

```powershell
$Api = "http://127.0.0.1:18004/api/v1"
$login = Invoke-RestMethod -UseBasicParsing -Method Post -Uri "$Api/auth/login" `
    -ContentType "application/x-www-form-urlencoded" `
    -Body @{ username = $env:R04_A2_ADMIN_USERNAME; password = $env:R04_A2_ADMIN_PASSWORD }
$headers = @{ Authorization = "Bearer $($login.access_token)" }

$primary = Invoke-RestMethod -UseBasicParsing -Method Post -Uri "$Api/clients" `
    -Headers $headers -ContentType "application/json" `
    -Body (@{ client_type = "company"; name = "R04 A2 Primary Case" } | ConvertTo-Json -Compress)
$other = Invoke-RestMethod -UseBasicParsing -Method Post -Uri "$Api/clients" `
    -Headers $headers -ContentType "application/json" `
    -Body (@{ client_type = "company"; name = "R04 A2 Distinguishing Record" } | ConvertTo-Json -Compress)
Invoke-RestMethod -UseBasicParsing -Method Post -Uri "$Api/inspections" `
    -Headers $headers -ContentType "application/json" `
    -Body (@{ client_id = $primary.id; status = "planned"; notes = "R04-A2 synthetic inspection" } | ConvertTo-Json -Compress)
curl.exe -fS -H "Authorization: Bearer $($login.access_token)" `
    -F "file=@$Fixture;type=text/plain" "$Api/clients/$($primary.id)/documents/upload"
```

In a second PowerShell 5.1 window, copy the already extracted frontend into a
mutable build root if it was not copied above, then run the exact Web command:

```powershell
Set-Location -LiteralPath "<R04-A2-ROOT>\web-source"
& "C:\FlutterSDK-New\flutter\bin\flutter.bat" pub get --offline
& "C:\FlutterSDK-New\flutter\bin\flutter.bat" run -d web-server `
    --web-hostname 127.0.0.1 --web-port 18005 `
    --dart-define=API_BASE_URL=http://127.0.0.1:18004 `
    --dart-define=ANDROID_AUTH_DIAGNOSTICS=false
```

Use a separate browser profile and perform UI-01 through UI-06 in order:
wrong-password and correct login; distinguish and open the primary client;
open its document and verify the returned bytes; edit the synthetic registration
number and verify it after reopening; correlate `/version`; stop only the exact
test backend, observe the error, start the same backend and retry. Do not seed or
migrate again during UI-06.

```powershell
docker stop $env:R04_A2_BACKEND_CONTAINER
docker start $env:R04_A2_BACKEND_CONTAINER
```

Android is a separate result. Before starting `Pixel_8`, require the existing
resource reserve and a reviewed build-only overlay using package
`pl.ailab.app.r04test` and `API_BASE_URL=http://10.0.2.2:18004`. Never replace
or uninstall `pl.ailab.app`. In the recorded run the projected Windows reserve
was below 4 GiB, so Android correctly stopped at `BLOCKED_RESOURCE_GATE` and no
overlay/build/install was performed.

## C2 resource observation and interrupted Android build

C2 established that the earlier Docker denial occurred at the Codex execution
sandbox boundary to `npipe:////./pipe/dockerDesktopLinuxEngine`. The same
normal user, session, `docker.exe` and `desktop-linux` context reached engine
`78446bed-994a-42ea-ad86-46f8232848a8` only through the narrow command approval;
no administrator role, Docker context change, pipe ACL change or restart was
used. Direct WSL CLI remained unavailable, while the verified Docker engine
provided the same WSL2 pool telemetry.

The bounded session helper is `measure-c2-resource-gate.ps1`. It requires the
full ID of the exact C2 telemetry container, verifies its owner/run labels,
samples Windows physical RAM/commit and Linux `/proc/meminfo` every 5–10
seconds, and stops on a missing field, read failure, a reserve below 4 GiB or
swap growth above the existing 256 MiB bound. Its CSV uses invariant decimal
format and was parsed under Windows PowerShell 5.1. It is not a persistent
monitor and must not be pointed at an application or production container.

The recorded C2 container was created from the already local image
`sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651`
as `next-stabil-r04-a2-c2--telemetry`, with `--network none`, read-only root,
all capabilities dropped, no-new-privileges, 64 MiB memory, 32 PIDs, no mounts,
no host PID/socket and no restart policy. It was removed after the run by exact
ID/owner/run verification.

For the Android candidate, apply the reviewed build-only overlay to the
preserved external `android-source`; it changes only
`android/app/build.gradle.kts`, sets `pl.ailab.app.r04test`, and lets a debug
build use the normal local debug signing path without reading production
`key.properties`:

```powershell
$AndroidRoot = "<preserved-R04-A2-root>\android-source"
$Overlay = "C:\ai-lab-core-recovery\operations\recovery\r04-a2\android-r04test-build-only.patch"
git -C $AndroidRoot apply --check $Overlay
if ($LASTEXITCODE -ne 0) { throw "Android overlay does not apply" }
git -C $AndroidRoot apply $Overlay
if ($LASTEXITCODE -ne 0) { throw "Android overlay apply failed" }
& "C:\FlutterSDK-New\flutter\bin\flutter.bat" pub get --offline
if ($LASTEXITCODE -ne 0) { throw "offline dependency resolution failed" }
$env:GRADLE_OPTS = "-Dorg.gradle.offline=true"
& "C:\FlutterSDK-New\flutter\bin\flutter.bat" build apk --debug --no-pub `
    --dart-define=API_BASE_URL=http://10.0.2.2:18004 `
    --dart-define=ANDROID_AUTH_DIAGNOSTICS=false
if ($LASTEXITCODE -ne 0) { throw "Android debug build failed or was stopped" }
```

C2 did not complete that command: the live monitor observed Windows available
RAM fall from `7.757 GiB` to `3.889 GiB` while commit reserve stayed
`34.636 GiB` and the WSL/Docker pool stayed near `13.852 GiB`. The build was
interrupted during `assembleDebug`, no APK was created, no retry was made, and
`Pixel_8` was not started. A later execution requires a new explicit scope and
a resource gate; this recipe is evidence, not standing authorization.

Web UI-03 does not require another Web run. The retained clicked download is:

```text
C:\ai-lab-core-staging\recovery\R04_A2_REAL_APP_20260909T131617Z\continuation-20260909T162252Z\web-ui03-download-1.txt
```

It is 204 B with SHA-256
`C0EBC642C0AE14C7A3D8D4A4A6B5F9178E0370CDC3241E3155E710D88E7EB0F2`.
Because this Codex session had no supported desktop-window capture tool, the
only remaining owner action is to open that exact file in a local viewer and
capture only that viewer window. Until such evidence is supplied, visible
content remains `WAITING_OWNER_VISUAL_EVIDENCE`, not PASS or product FAIL.

At handoff stop only the exact-name test services and the Web process from this
run. Preserve the volume, data root and evidence pending owner review:

```powershell
docker compose -f $Compose stop transport backend postgres
Get-NetTCPConnection -State Listen -LocalPort 18004,18005 -ErrorAction SilentlyContinue
```

The real smoke must correlate visible UI state with HTTP and the synthetic DB.
API-only calls, parser tests and screenshots of an empty/start screen are not a
substitute. Qwen, embedding, Qdrant, Gmail, Temporary Chat and AI acceptance are
not part of this run.

## C3 low-memory Android build

C3 reuses the preserved `android-source`; it does not recreate, clean or seed
the A2 environment. The source archive remains
`f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99`. The published package/signing
overlay has SHA-256 `1956D912C97F95B0B0BE3367EC580D6AA52C645B31444E129BC8FE6F92DC8DA8`.
The additional build-only overlay is `android-c3-low-memory-build.patch`,
SHA-256 `199415DAE534690CC251707732C71C81BFF061257430AB17E38E2D75C1667666`.
Its resulting `android/gradle.properties` SHA-256 is
`E323EA871057548A1798B9BFF94BCE1B5774C492E92F22F62CB4D26922165D88`.

Do not run `git -C` against the ordinary extracted copy. First confirm that it
has no Git parent, then enter the exact directory and use apply/reverse checks
to distinguish a fresh source from the already-applied C3 state:

```powershell
$AndroidRoot = "C:\ai-lab-core-staging\recovery\R04_A2_REAL_APP_20260909T131617Z\android-source"
$PackagePatch = "C:\ai-lab-core-recovery\operations\recovery\r04-a2\android-r04test-build-only.patch"
$MemoryPatch = "C:\ai-lab-core-recovery\operations\recovery\r04-a2\android-c3-low-memory-build.patch"
if (Test-Path -LiteralPath (Join-Path $AndroidRoot '.git')) { throw 'unexpected Git metadata' }
Push-Location -LiteralPath $AndroidRoot
try {
    git apply --reverse --check $PackagePatch
    if ($LASTEXITCODE -ne 0) { throw 'package/signing overlay is not applied' }
    git apply --reverse --check $MemoryPatch
    if ($LASTEXITCODE -ne 0) { throw 'low-memory overlay is not applied' }
} finally { Pop-Location }
```

The effective profile is checked by the real Gradle 9.1.0 wrapper, offline and
without compiling. `JAVA_HOME` is process-local and points at the already
installed Android Studio JBR; no global Gradle/Java settings are changed:

```powershell
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'
$AndroidGradle = Join-Path $AndroidRoot 'android'
$Guard = 'C:\ai-lab-core-recovery\operations\recovery\r04-a2\verify-c3-gradle-profile.init.gradle'
Push-Location -LiteralPath $AndroidGradle
try {
    & .\gradlew.bat --offline --max-workers=1 --no-parallel --no-daemon `
        -I $Guard r04C3ResourceGuard
    if ($LASTEXITCODE -ne 0) { throw 'BUILD_PROFILE_NOT_APPLIED' }
} finally { Pop-Location }
```

The guard requires the actual JVM input arguments `-Xmx2048m`, metaspace
`768m`, code cache `256m`, one worker, `parallel=false`, Gradle offline and
Kotlin `in-process`. The C3 build uses the same flags in one direct wrapper
invocation. It passes only the Flutter properties reconstructed from the
checked Flutter 3.44.8 tool path and the two explicit test Dart defines:

```powershell
$defines = @(
    'API_BASE_URL=http://10.0.2.2:18004',
    'ANDROID_AUTH_DIAGNOSTICS=false'
) | ForEach-Object { [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($_)) }
$dartDefines = $defines -join ','
Push-Location -LiteralPath $AndroidGradle
try {
    & .\gradlew.bat --offline --max-workers=1 --no-parallel --no-daemon `
        -I $Guard -q `
        '-Ptarget-platform=android-arm,android-arm64,android-x64' `
        '-Ptarget=lib/main.dart' `
        '-Pbase-application-name=android.app.Application' `
        "-Pdart-defines=$dartDefines" `
        '-Pdart-obfuscation=false' '-Ptrack-widget-creation=true' `
        '-Ptree-shake-icons=false' r04C3ResourceGuard assembleDebug
    if ($LASTEXITCODE -ne 0) { throw 'Android C3 build failed or was stopped' }
} finally { Pop-Location }
```

Both commands must run under the session-bounded resource monitor with explicit
C3 `ExpectedContainerName`, `ExpectedOwner` and `ExpectedRunId`; the helper's
C2 defaults remain backward compatible. C3 completed exactly one assemble in
about 3 minutes 15 seconds. The build gate stayed PASS with minimum Windows
available `5.602 GiB`, commit reserve `36.065 GiB`, pool available
`14.135 GiB` and unchanged swap use. The new APK is `166479535` bytes with
SHA-256 `FAF545C0F6E6DD55DC48898A10714AA099FF3EBE78B648EADAC2B036C7AE325E`,
package `pl.ailab.app.r04test`, Android debug certificate and the test API URL
inside `kernel_blob.bin`.

After the build, the preserved A2 stack passed identity/DB/fixture checks. The
verified `Pixel_8` appeared as `emulator-5554`, but before boot completed the
active monitor recorded Windows available `3.900 GiB`. C3 therefore stopped
that exact emulator and classified Android runtime `RAM_GATE_BLOCKED`; APK
install and UI-01–UI-06 were not run. Do not retry automatically. The bounded
next proposal is a separately approved AVD-only window that begins with at
least `8.5 GiB` Windows available while the A2 stack is running, retaining all
existing 4 GiB/commit/pool/swap gates and the same already-built APK.

Web UI-03 remains independent and `WAITING_OWNER_VISUAL_EVIDENCE`. Open the
retained clicked download in a local viewer and capture only that viewer window;
do not rerun Web or fetch the file again. `R04-A2-UI06` remains
`KNOWN_DEFECT_OPEN_R16`.
