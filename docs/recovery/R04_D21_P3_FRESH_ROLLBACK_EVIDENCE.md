# R04 / D-21 / P3 — świeży punkt rollbacku i izolowany drill

Status: `FRESH_ROLLBACK_POINT_READY_FOR_REVIEW / CAPTURE_AND_ISOLATED_DATA_RESTORE_PASS / NO_CUTOVER`

Okno wykonania: `2026-09-17T08:20:22Z–09:09:01Z`
Punkt: `E:\ai-lab-backup\20260917T082022Z`
Manifest SHA-256: `2759D684710FB857DBCD0D985B5C480857122E3B139B9DDC362BFF4903895597`
Katalog dowodów: `E:\ai-lab-backup\D21-P3-VERIFY-20260917T082022Z`

Ten raport dokumentuje jeden ręczny `RecoveryPointV2 / full / CaptureOnly`
i jeden izolowany drill dokładnie tego punktu. Nie jest odbiorem całego P3,
zgodą na cutover, produkcyjnym restore ani pełnym disaster recovery hosta.

## 1. Tożsamość narzędzia i źródeł

- branch/worktree: `recovery/next-stabil-repair-completion` /
  `C:\ai-lab-core-recovery`;
- parent local/tracking/remote: `e3f2125883420a12c8721c5ba597203dcf403add`;
- tool root: recovery; źródło danych/config: `C:\ai-lab-core`;
- faktyczny backend podczas capture:
  `9d9b46c530412e48562b5427a0586b08c1e919ff293ec2cbd1489faffc98615a`,
  `/app=C:/ai-lab-core/build/deploy-main-483f9bf8/backend`;
- `backup-production.ps1`: blob
  `5b1d1d00b0b52f318899596238005f5aa1009ce0`, SHA-256
  `F895E4874A10E4CE964B8E9EDAC37A2A58DB734A0C8E2D5E33241591DBD6B28F`;
- `restore-checkpoint.ps1`: blob
  `44cad85551cb037821c3066949506f2c0be90f69`, SHA-256
  `AD7C25ECFCF4C6F98C057C06CECC8B9D5719EBB88A0CD2A2E83F587520FFCA88`;
- `verify-qdrant-snapshot-offline.ps1`: blob
  `b35fb0fd5602912408b3ddc4f76f5690d26cc59f`, SHA-256
  `5876A69EF72B93DF06EB276F46F82D2D0BCFD33B0393A2CDB745B3444C52CE52`;
- tool source commit: `9e7df257e866a971c1492c2db964aef085ead819`;
- recovery-tool manifest SHA-256:
  `9775523F5ACF7F2541E80A006D22469FB5C017F34A735208D4AF603C108152F4`.

Oba katalogi na E: mają wyłączone dziedziczenie i tylko `SYSTEM`, lokalnych
administratorów oraz właściciela z `FullControl`. Nośnik E: jest odrębny od
aktywnego D:. Junction `C:\ai-lab-core\data -> D:\ai-lab-data` nie został
zmieniony.

## 2. Capture i integralność

Wywołano jeden raz istniejący writer z `Scope=full`,
`ManifestFormat=RecoveryPointV2`, `QdrantProofMode=CaptureOnly`, dwiema
wymaganymi kolekcjami, release `1.0.2+29` i niesekretnym runtime inventory.
Polecenie trwało 350,332 s, zakończyło się exit `0` i `BACKUP_COMPLETE`.

| Artefakt | Bajty | SHA-256 | Wynik |
|---|---:|---|---|
| PostgreSQL dump | 466 506 951 | `031B84C7AFF492795C8D63FB19734EFAC3A5C84A3C093EC8F73904D7244535B3` | match |
| pięć domen storage | 6 292 514 119 | `E20F0ED96EA53B989E847198A387153347555F33510852C14B98C09D701BF289` | match |
| stable release | 1 123 192 986 | `3BE61930F0EA4596C2484476F4A1CF01A619201F9356A0B2955E9B3F86A819B9` | match |
| Qdrant document chunks | 348 404 224 | `0D6C83B4B4526B661F26868F10C9E7A661F73447C3E2B5A03D446A6184E5707E` | match |
| Qdrant KB chunks | 2 449 920 | `21D96C9F1C232C6C9D5B3CB5DB25EFE25DA496576D3854D7048A34178798E441` | match |
| n8n workflows | 106 059 | `A76CCEA57520E890511BFAF12DBF9BAE31D154465F7DE736B728C4AF9C3B5C96` | match |
| n8n credentials encrypted | 4 612 | `7AB3BFB96F4F4B8941B36C1C5214298BFD6FA649017D2FA9AD197198A44CD90A` | match |
| configuration | 4 066 | `0619EB3012454E3063F74587865A3B718A28929E2CFCF105B9AD66EB72FE0846` | match |
| runtime inventory | 11 349 | `D3DE5C85E73F9B6771A5480D9A7E90A923CE0079BB2850702D5081E884D0EBC0` | match |

Łącznie: 9 artefaktów, `8 233 194 286` B. Niezależne
`restore-checkpoint.ps1 -ValidateOnly -Mode Full` zakończyło się exit `0`:
manifest `valid=true`, storage/KB complete, oba snapshoty strukturalnie valid.
`full_eligible=false` było oczekiwane przed drillem, ponieważ immutable manifest
CaptureOnly ma `qdrant_restore_verified=false`; nie zmieniano go po fakcie.

## 3. Okna składników i spójność

| Składnik | UTC start | UTC koniec |
|---|---|---|
| PostgreSQL | 08:23:19.315276 | 08:24:00.732553 |
| storage | 08:24:00.733239 | 08:27:22.907829 |
| release | 08:27:22.907902 | 08:28:31.181729 |
| Qdrant documents | 08:28:31.189559 | 08:28:38.031534 |
| Qdrant KB | 08:28:38.031582 | 08:28:38.872509 |
| n8n exports | 08:28:38.877018 | 08:28:47.651350 |
| configuration | 08:28:47.651398 | 08:28:50.042846 |

Status pozostaje
`COMPONENT_WINDOWS_RECORDED_NON_TRANSACTIONAL`. Drill potwierdza linki w
badanym zakresie, nie atomowość jednego snapshotu DB/storage/Qdrant/n8n.

## 4. Izolowany drill

Drill użył jednego świeżego PostgreSQL i dwóch świeżych Qdrantów. Wszystkie
trzy sieci były `internal`, host ports `0`, production networks/mounts `0`,
Docker socket `0`, `privileged=false`. Użyto lokalnych, przypiętych obrazów;
aplikacja, n8n workflow, migracje i usługi zewnętrzne nie były uruchamiane.

### PostgreSQL

- `pg_restore --exit-on-error`: exit `0`, 52,687 s;
- DB: `ai_lab_restore_test_d21_p3_20260917`;
- revision: `followup_assistant_chat_history_20260829`;
- 52 tabele publiczne, 113 FK, 0 invalid FK, 114 PK;
- liczniki kontrolne: 3278 klientów, 6 użytkowników, 5998 dokumentów,
  436 stron, 10 assets, 57 document chunks, 10 KB items, 487 KB pages,
  117 analysis jobs, 15 assistant runs, 47 backup runs, 0 restore runs.

### Storage i DB bindings

- 6362/6362 referencje rozwiązane; missing/unsafe/size mismatch/hash mismatch = 0;
- 6011 referencji miało dostępny hash i wszystkie były zgodne;
- pięć domen zgadzało się liczbą plików i bajtów;
- KB inventory hash DB i storage:
  `54CE0DF0E6493A41013B04D93E3CBB4CCABB5DCD3FC31E7E4BADF847486038A1`;
- 5 orphan files zachowano; niczego nie usuwano;
- po rozpakowaniu nie wykryto reparse points ani niebezpiecznych ścieżek.

### Qdrant

- `ai_lab_document_chunks`: 57 punktów, 1024/Cosine, aliasy 0;
- `ai_lab_knowledge_base_chunks`: 157 punktów, 1024/Cosine, aliasy 0;
- wszystkie dostępne allowlisted bindingi do odtworzonej DB są zgodne;
- payload dokumentowy nie zawierał `embedding_version` dla 57/57 punktów;
  ograniczenie jest zapisane, nie uzupełniono expected jako observed;
- nie odczytywano treści payloadów, tylko ograniczone metadane powiązań.

### Release, config, n8n i inventory

- stable `1.0.2+29`, minimum `1.0.0`;
- Windows i Android artefact hash match;
- 12/12 wymaganych plików konfiguracji obecnych, stable manifest zgodny;
- runtime inventory po rozpakowaniu ma ten sam hash;
- 4 workflow i 4 encrypted credentials mają poprawną strukturę JSON; credentials
  pozostały opaque, nie były odszyfrowane ani wykonywane.

## 5. Zasoby, cleanup i skutki

Przed cleanupem izolowane magazyny miały odpowiednio około 1 932 371 912 B
(PostgreSQL), 348 330 230 B i 482 554 069 B (Qdrant). Pełne ID były zgodne z
chronionym manifestem zasobów; owner/run labels nie były obecne, więc nie są
przedstawiane jako dowód własności. Po zachowaniu dowodów usunięto wyłącznie
5 kontenerów, 3 volumes i 3 internal networks tego drillu. Odczyt końcowy:
`0/0/0` zasobów z prefiksem sesji.

Katalog verify pozostaje do odbioru: 6471 plików, `8 707 757 116` B. Jego
`drill-summary.safe.json` ma SHA-256
`56D046CFDE08C5B7780D890C10A44C81CB3FE7A857AB43736BFDB492169E93DB`,
a lokalny indeks 34 rekordów SHA-256
`E32E8D62146D8B02F00EF25CD16EBA2EB498DE75BB8ACE7EE511379062B8E205`.

Podczas końcowego pomiaru zasobów wrapper omyłkowo pobrał `alpine:3.20`.
Nie uruchomiono na nim usługi; kontener `--rm` zniknął, obraz
`sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc`
został natychmiast usunięty, a remaining count potwierdzono jako 0. Jest to
jawny skutek sesji, nie element właściwego drillu.

## 6. Stan po operacji i ograniczenia

Sześć bieżących kontenerów zachowało pełne ID i stan running. Backend nadal
używa `deploy-main-483f9bf8`, nie recovery/WIP. Supervisor pozostał
`INTENTIONALLY_STOPPED / NOT_STARTED_BY_THIS_SESSION`. Nie zmieniono kolejki,
flag, junctionu, mountów, harmonogramów backupu, retencji, main/rescue ani
chronionych 203 wpisów oryginalnego worktree.

Punkt nie obejmuje escrow/recovery key, pełnego hosta/VHD, modeli, profili,
pełnego RTO ani późniejszych zapisów po zakończeniu jego okien. Rollback
zwykłego błędu przyszłego source switch najpierw przywraca stary kod/config z
bieżącymi danymi; restore danych jest osobną potencjalnie destrukcyjną decyzją.

Wynik: `CAPTURE_AND_ISOLATED_DATA_RESTORE_PASS` oraz
`VERIFIED_LINKS_IN_TESTED_SCOPE`. Produkcyjny manifest pozostaje
`NOT_APPROVED_FOR_START`, a cutover `NOT_AUTHORIZED / NOT_RUN`.
