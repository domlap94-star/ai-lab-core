# R04 / D-21 / P3 — świeży punkt rollbacku i izolowany drill

Status: `ROLLBACK_TOOL_PROVENANCE_RECONCILED / EVIDENCE_READY_FOR_REVIEW / CAPTURE_AND_ISOLATED_DATA_RESTORE_RESULTS_PRESERVED / NO_CUTOVER`

Okno wykonania: `2026-09-17T08:20:22Z–09:09:01Z`
Punkt: `E:\ai-lab-backup\20260917T082022Z`
Manifest SHA-256: `2759D684710FB857DBCD0D985B5C480857122E3B139B9DDC362BFF4903895597`
Katalog dowodów: `E:\ai-lab-backup\D21-P3-VERIFY-20260917T082022Z`

Ten raport dokumentuje jeden ręczny `RecoveryPointV2 / full / CaptureOnly`
i jeden izolowany drill dokładnie tego punktu. Nie jest odbiorem całego P3,
zgodą na cutover, produkcyjnym restore ani pełnym disaster recovery hosta.

## 1. Tożsamość narzędzi i źródeł — korekta provenance

- branch/worktree wykonania: `recovery/next-stabil-repair-completion` /
  `C:\ai-lab-core-recovery`;
- entry/tool-root commit zapisany przez writer w immutable manifeście:
  `e3f2125883420a12c8721c5ba597203dcf403add`;
- źródło danych/config: `C:\ai-lab-core`, `source_head`
  `72950657ac79b50d0afe72753632ba4cde810b95`;
- faktyczny backend podczas capture:
  `9d9b46c530412e48562b5427a0586b08c1e919ff293ec2cbd1489faffc98615a`,
  `/app=C:/ai-lab-core/build/deploy-main-483f9bf8/backend`.

Entry HEAD i evidence HEAD `d64062261d0ff76ae5a9152e1e41803116d35692`
mają dla wszystkich czterech ścieżek te same kanoniczne bloby. Obiekty zostały
odczytane lokalnie przez `rev-parse <commit>:<path>` i potwierdzone jako typ
`blob` przez `cat-file -t`. Kanoniczny SHA-256 policzono bez tekstowego
przekodowania stdout `git cat-file`.

| Plik / historyczne wykonanie | Ostatni commit pliku w entry HEAD | Kanoniczny blob / kanoniczne bajty SHA-256 | Surowy plik lokalny w checkout / `hash-object --no-filters` | EOL / BOM |
|---|---|---|---|---|
| `C:\ai-lab-core-recovery\operations\hardening\backup-production.ps1`; bezpośredni writer, wynik w `logs\capture.log`, a `tool_source_head` zapisany przez jego `$PSScriptRoot` | `9e7df2068e1138fbbb5ca2e213c13efffe4c0945` | `5b1cfeee2d99f453ac45333cede492f0e60a0487`; 33 446 B; `AAA9C0642761C05B6D2B394FD7314B2E116D41B49372B3ABB5B603F2DA4B183D` | 34 059 B; `F895E4874A10E4CE964B8E9EDAC37A2A58DB734A0C8E2D5E33241591DBD6B28F`; raw-blob ID `dca03eb6548db8b9b33364dfa5d29b5770a308d8` | 613 CRLF, 0 lone LF, bez BOM |
| `C:\ai-lab-core-recovery\operations\hardening\restore-checkpoint.ps1`; reader `-ValidateOnly`, wynik w `logs\validate-only.log` | `9e7df2068e1138fbbb5ca2e213c13efffe4c0945` | `44caeaa9b2d7064e4fdb84a46706afb1ba14fd3c`; 36 129 B; `A9EAEDCDD74DA433DD748CEE942DFDE208B9386D520A007D5F0ABD3804145F26` | 36 737 B; `AD7C665C22E0C8805B51BF6E25633C7DF945F9F52C9235292628BF2E28B519C4`; raw-blob ID `7cbfbc0e7f805c50dd1dc67e510d53a18b1f689c` | 608 CRLF, 0 lone LF, bez BOM |
| `C:\ai-lab-core-recovery\operations\hardening\verify-qdrant-snapshot-offline.ps1`; dwa proofy, których JSON odpowiada `logs\qdrant-1-restore.stdout.log` i `qdrant-2-restore.stdout.log` oraz zachowanym nazwom zasobów | `228b4898010d4bb805ec593316e338326301dcdf` | `b35e702ee9ecc1efa37a386b5208b6f264399800`; 12 356 B; `5876A111BF6CF9C7EDB937473FD20C2BF6B8B088CD168C627FB42149A7E0EF41` | 12 356 B; ten sam SHA-256 i blob ID `b35e702ee9ecc1efa37a386b5208b6f264399800` | 257 LF, 0 CRLF, bez BOM |
| `operations/recovery/recovery-tool-manifest.json`; entry manifest wiążący rozmiary i raw SHA-256 helperów | `9e7df2068e1138fbbb5ca2e213c13efffe4c0945` | `7f2dc8665f4ba88f686c7465c5d2054a147e09de`; 826 B; `77C79757AED827F8D46B72D90D1BE3D3628C6F0A77E038478DCDC363128CAB0A` | 843 B; `97755DD0927DF7C3A4E106981E6747DAE87D01D293F378FE559861A4425CEE2D`; raw-blob ID `9f43cae5372df0718af9077a5f6ad946ecd4f452` | 17 CRLF i 9 lone LF, bez BOM |

Repo ma `text=auto` dla tych ścieżek i systemowe `core.autocrlf=true`.
`hash-object --path=<path>` daje kanoniczne bloby z tabeli; różne raw-blob IDs
writer/reader/manifestu są więc oczekiwanym `RAW_FILE_VS_CANONICAL_BLOB`, nie
innym kodem. Entry `recovery-tool-manifest.json` zawiera dokładnie surowe
rozmiary i SHA-256 trzech helperów z tabeli, a skrypty nie zmieniły się między
entry i evidence HEAD. Immutable capture manifest wiąże wykonanie z tool root
`e3f2125883420a12c8721c5ba597203dcf403add`; nie zawiera jednak osobnego
per-invocation SHA-256 każdego skryptu, co pozostaje jawną granicą dowodu raw
representation.

Wartości nazwane wcześniej blobami (`5b1d1d00...`, `44cad855...`,
`b35fb0fd...`) nie rozwiązują się jako lokalne obiekty i nie są też raw-blob
IDs. SHA-256 readera, Qdrant helpera i tool manifestu w poprzedniej wersji §1
również nie odpowiadają ani bajtom kanonicznym, ani surowym. Klasyfikacja:
`REPORT_TRANSCRIPTION_ERROR`, a nie inny source wykonania. Wpisany wcześniej
`9e7df257e866a971c1492c2db964aef085ead819` jest lokalnie nierozwiązywalny jako
commit. Poprawny ostatni commit writer/reader/tool manifestu to
`9e7df2068e1138fbbb5ca2e213c13efffe4c0945`: jest lokalnym obiektem `commit`,
przodkiem entry HEAD (65 commitów) i należy do historii lokalnego
`origin/recovery/next-stabil-repair-completion`. Tool-root commit samego
wykonania pozostaje entry HEAD `e3f212588...`, nie ostatni commit pojedynczego
pliku.

Immutable `backup-manifest.json` pozostaje niezmieniony: 7 613 B, SHA-256
`2759D684710FB857DBCD0D985B5C480857122E3B139B9DDC362BFF4903895597`.

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
(PostgreSQL), 348 330 230 B i 482 554 069 B (Qdrant). Chroniony manifest
zasobów zachował następujące pełne tożsamości, bez publikowania pełnego
`docker inspect`:

| Zasób | Pełna nazwa | Pełne ID |
|---|---|---|
| PostgreSQL container | `next-stabil-r03-a1-drill-d21p3-20260917t082022z-postgres` | `80b178d7643cc09637833955690d9df2fede8881901aadd329b165e0e359922a` |
| Qdrant 1 server | `next-stabil-r03-a1-drill-d21p3-20260917t082022z-qdrant-1-server` | `32691cd2393202ce0affd169c4d7fa0e2c75c4eec9210095668d129c85f0d748` |
| Qdrant 1 client | `next-stabil-r03-a1-drill-d21p3-20260917t082022z-qdrant-1-client` | `acbe8ac3a1f98b2f2568f3e4328dfa032f5ef6b2279c21a6dcd3e631bb216bac` |
| Qdrant 2 server | `next-stabil-r03-a1-drill-d21p3-20260917t082022z-qdrant-2-server` | `ce73f48c6c8e1fdfdd76a0398c765cd2a78f8f0b1289dab19df4946a8d57e612` |
| Qdrant 2 client | `next-stabil-r03-a1-drill-d21p3-20260917t082022z-qdrant-2-client` | `20b1412f9a90fea1e07f1404b3b3c39af8a34003eef389247f3335002d486014` |
| PostgreSQL network | `next-stabil-r03-a1-drill-d21p3-20260917t082022z-network` | `e029d1fc122894e84e336446be857151bf5a2e945123ecd67497962e776b8f7d` |
| Qdrant 1 network | `next-stabil-r03-a1-drill-d21p3-20260917t082022z-qdrant-1-network` | `0cbc98656beb80502efbf042f8613076d737a771282208e6bfeed2e2d7a72a68` |
| Qdrant 2 network | `next-stabil-r03-a1-drill-d21p3-20260917t082022z-qdrant-2-network` | `ba174a12c0357a549e93b58fd64d82d24ffdcbaea67784b290d3f497c8b9b4f7` |

Pełne nazwy volumes: `next-stabil-r03-a1-drill-d21p3-20260917t082022z-postgres-data`,
`next-stabil-r03-a1-drill-d21p3-20260917t082022z-qdrant-1-data` oraz
`next-stabil-r03-a1-drill-d21p3-20260917t082022z-qdrant-2-data`.

Ten sam manifest łączy `created_at`, dokładne nazwy/obrazy/mounty/internal
networks/zero host ports z cleanupem `5/3/3`, `errors=[]` i końcowym
`0/0/0`. Drill-summary potwierdza `production_networks=0`,
`production_mounts=0`, Docker socket `0` i `privileged=false`. To wystarcza do
powiązania utworzenia z cleanupem i braku przecięcia z produkcją w badanym
zakresie, lecz owner/run labels nie były kompletne. Odstępstwo pozostaje:
`PROCEDURAL_DEVIATION_OWNER_RUN_LABELS_MISSING`; alternatywny dowód nie tworzy
wstecznego proceduralnego PASS.

Katalog verify pozostaje do odbioru: 6471 plików, `8 707 757 116` B. Jego
`drill-summary.safe.json` ma SHA-256
`56D046CFDE08C5B7780D890C10A44C81CB3FE7A857AB43736BFDB492169E93DB`,
a lokalny indeks 34 rekordów SHA-256
`E32E8D62146D8B02F00EF25CD16EBA2EB498DE75BB8ACE7EE511379062B8E205`.

`UNINTENDED_ALPINE_IMAGE_PULL`: podczas końcowego pomiaru zasobów wrapper
wykonał krótkotrwały kontener pomiarowy `--rm` z `alpine:3.20`; ponieważ obrazu
nie było lokalnie, nastąpił nieautoryzowany pull. Nie była to usługa produktu,
ale nie wolno opisywać tego
jako brak uruchomienia jakiegokolwiek kontenera. Zachowany manifest podaje
powód `Post-cleanup WSL/Docker memory observation command`, tag, image ID
`sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc`,
`remediated=true` i `remaining=0`. Dokładne argumenty polecenia pomiarowego,
exit/stdout oraz mount/network krótkotrwałego kontenera nie zostały zachowane,
więc jego dalszy zakres jest `UNKNOWN`; nie deklaruje się braku sieci ani
mountów. Zakaz pull został rzeczywiście naruszony i nie otrzymuje
retroaktywnego PASS.

Pierwsza próba dostarczenia dumpa do tmpfs nie pozostawiła pliku; `pg_restore`
nie został wtedy uruchomiony. Dokładny dump został następnie skopiowany do
świeżego testowego volume i wykonano jeden rzeczywisty `pg_restore`, exit `0`.
To `POSTGRES_TMPFS_COPY_NOT_PRESENT` plus jeden restore, nie dwa restore'y.

Przyszła receptura musi przed utworzeniem zasobu potwierdzić lokalny image
ID/digest, używać `--pull=never` oraz od razu odczytać owner/run. Brak lokalnego
obrazu zatrzymuje polecenie; nie jest zgodą na pull lub fallback.

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

Wynik danych pozostaje `CAPTURE_AND_ISOLATED_DATA_RESTORE_PASS` oraz
`VERIFIED_LINKS_IN_TESTED_SCOPE`: 9/9 artefaktów, 6362/6362 rozwiązanych
referencji, z czego 6011 miało dostępny i zgodny hash, oraz Qdrant 57/157
powiązany z odtworzoną DB. Korekta provenance nie poszerza testu n8n ponad
strukturę i opaque encrypted credentials ani nie zmienia nieatomowych okien.

Status review: `ROLLBACK_TOOL_PROVENANCE_RECONCILED /
EVIDENCE_READY_FOR_REVIEW`; odstępstwa są zapisane jako
`PROCEDURAL_DEVIATIONS_RECORDED / NO_RETROACTIVE_PASS`. Produkcyjny manifest
pozostaje `NOT_APPROVED_FOR_START`, a cutover `NOT_AUTHORIZED / NOT_RUN`.

## 7. Odbiór właściciela 2026-09-17 i dalsza granica

Właściciel przyjął ograniczony wynik danych punktu
`E:\ai-lab-backup\20260917T082022Z`, immutable manifest SHA-256
`2759D684710FB857DBCD0D985B5C480857122E3B139B9DDC362BFF4903895597`,
jako `ROLLBACK_POINT_DATA_EVIDENCE_ACCEPTED_WITH_RECORDED_LIMITATIONS`.
Odbiór obejmuje capture/integrity i izolowane odtworzenie tylko w sprawdzonym
zakresie. Nie usuwa `COMPONENT_WINDOWS_RECORDED_NON_TRANSACTIONAL`, braku
owner/run labels, historycznego niezatwierdzonego pull/run `alpine:3.20`,
pierwszego niedostarczonego transferu tmpfs ani braku dowodu pełnego
host/VHD/model/profile/credential/escrow recovery. Nie jest proceduralnym PASS
dla tych odstępstw i nie zmienia immutable dowodów.

Odbiór punktu nie jest zgodą na restore danych. Właściciel później zatwierdził
jedno backend-only przełączenie pakietu
`R04-D21-P3-CORE-SWITCH-20260917T141404Z`, przyjmując wskazane ograniczenia.
Operacja zakończyła się wynikiem `CORE_BACKEND_SOURCE_SWITCH_READY_FOR_REVIEW /
LIMITED_RUNTIME_VERIFIED`; rollback kodu/config ani restore danych nie były
potrzebne lub wykonywane. Punkt pozostaje zachowany i nie uzyskuje przez to
szerszego odbioru host/VHD/model/profile/credential/escrow recovery.
