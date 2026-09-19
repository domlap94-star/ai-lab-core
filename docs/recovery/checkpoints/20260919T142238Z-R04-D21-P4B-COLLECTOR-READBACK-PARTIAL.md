# R04 / D-21 / P4-B — collector correction and readback partial

UTC: `2026-09-19T14:22:38Z`

## Tożsamość

- entry HEAD: `14bb1c4ff25a0ae027aedd85862401a622587587`
- exact recipe: `F6D3A8CC7AA57ED50244D773076700BCBE5771609762947B230E344C5C883F0E`
- package index: `FDF9FE7AF55A8285FB51506E3CBFA5368F366353748DC68BBCCBBC37164A977F`
- review ZIP: `D2B3263BE6ECB20E139CF63E7559C0E53605CE8827183989E37979247965DA1C`
- LOCAL_ONLY evidence: `C:\ai-lab-core-staging\recovery\P4B-PF-01\c2`
- final projection: `6D18493AFACBF19BFDA5D0607910572101AC5D27A36665AAE596727F8B159B74`
- c2 index: `A3FB97D5F46713753CBEC8A509D518D2DBFAE96EFAB7ABE44B8624F266FF52F8`

## Poprawka kolektora

Historyczny kolektor i dowody zachowano. Nowa LOCAL_ONLY wersja ma SHA-256
`B78AC996CC180D0137454447EFC4C64007E83BFFC712D8960341BCFFF98850A3`.
Windows PowerShell `5.1.26100.8894`: `13` przypadków, `61` asercji, exit `0`,
własne procesy `3/3` rozliczone, real Task/Docker/HTTP/CIM/TCP calls `0`.
Ponowne przetworzenie sześciu wcześniej zapisanych XML-i: `PASS`.

## Bieżący odczyt

- Task State `6/6`: Docker Desktop `Ready`, Docker Compose `Ready`, Public
  Gateway `Running`, Private Gateway `Ready`, Supervisor `Ready`, Host
  `Disabled`.
- TaskInfo `0/6`: sześć zapisanych błędów mapowania
  `CommandNotFoundException,Invoke-ClosedWorkerOperation`; bez ponowienia.
  `LastRunTime` i `LastTaskResult` pozostają `NOT_VERIFIED`.
- listenery: `8000` Docker proxy i `8789` Public Gateway; brak `8787/8788` w
  tym ograniczonym snapshotcie.
- HTTP: backend health/version `200`, public root/gateway-health `200`, public
  `/control` i `/control/health` `404`.
- Windows/disk gates: PASS (`6.557 GiB` available, `35.493 GiB` commit reserve,
  C `575.323 GiB` free, D `854.573 GiB` free). Docker/WSL available pool i
  swap-used: `UNKNOWN`.
- Docker: wszystkie 6 exact kontenerów running, restart count `0`, zgodne
  ID/image/mounty/porty/sieć, PostgreSQL `healthy`; 6 image records, Qdrant
  volume i info zapisane. Błąd końcowego formattera wystąpił po exit-zero
  odczytach; bezpieczną projekcję zbudowano z rekordów bez kolejnego Engine
  read.

## Skutki i status

UAC `0`, Install `0`, warm runs `0`, rollback `0`, task/service/container
mutations `0`, business-data mutations `0`. Wszystkie własne procesy zostały
rozliczone. Exact recipe nie zmieniła się. Reserved installer output nie był
dotykany; zgodność ścieżek `252/275` pozostaje `NOT_VERIFIED_NO_IO`.

`P4B PREFLIGHT_EVIDENCE_PARTIAL / TASK_INFO_MAPPING_ERROR_NO_REREAD / NO_UAC /
NOT_INSTALLED`

Globalny manifest pozostaje `NOT_APPROVED_FOR_START`. Supervisor pozostaje
`INTENTIONALLY_STOPPED` na podstawie braku listenera w ograniczonym snapshotcie
oraz zachowanej polityki; task w stanie `Ready` ma historyczny
logon trigger, którego ta sesja nie zmieniła. STOP przed UAC, Install, warm
runs, rollback, P4/B operational continuation, P5 i R06.
