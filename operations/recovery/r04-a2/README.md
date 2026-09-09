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
if ($version.component_identity.source_revision -ne $SourceSha) { throw "runtime source mismatch" }
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
