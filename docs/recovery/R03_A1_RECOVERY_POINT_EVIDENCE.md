# R03 A1 — dowód nowego punktu odtworzenia

## Wynik i granica

Podetap A1 ma status `CHECKPOINT_READY_FOR_REVIEW / WAITING_ISOLATED_DRILL_APPROVAL`.
Cały R03 pozostaje `WAITING_APPROVAL`. Utworzono i zweryfikowano capture; nie
wykonano firmowego restore/drill, escrow ani pomiaru RTO.

- Punkt: `E:\ai-lab-backup\20260908T135012Z`.
- Manifest: `NEXT_STABIL_BACKUP_V2`, SHA-256
  `1195AE5BE68CF589D9B9231C85B0BE678C87117FD471034417B9DC8C5620FD57`.
- Artefakty: `9/9`, razem `8,181,448,907` B; writer i niezależny reader
  `-ValidateOnly` potwierdziły rozmiary, SHA-256 i strukturę.
- `capture_status=COMPLETE`, `scope_status=COMPLETE`,
  `provenance_status=RECORDED`.
- `consistency_status=COMPONENT_WINDOWS_RECORDED_NON_TRANSACTIONAL`:
  ograniczone dowody spójności są pozytywne, lecz nie jest to atomowy snapshot
  wszystkich usług.
- `qdrant_restore_verified=false`, `restore_status=NOT_RUN_WAITING_APPROVAL`,
  `escrow_status=NOT_RUN_WAITING_OWNER_DECISION`, `rto_status=NOT_MEASURED`.

## Przypięte źródła

- Pierwsza wersja writer/reader/proof: `228b4898010d4bb805ec593316e338326301dcdf`.
- Funkcjonalny commit użytego narzędzia (bez odczytu `.env` i pełnego
  `docker inspect`): `c6faca0dba5944a9900cef3cd20f24d35c3060f7`.
- Capture uruchomiono z recovery HEAD
  `1050e9e5494f5dd7f6e28a6804768d54faa11cd0`; różnica tool paths względem
  `c6faca0...` wynosiła `0`, a manifest zapisuje ten wykonawczy HEAD jako
  `tool_source_head`.
- `source_head=72950657ac79b50d0afe72753632ba4cde810b95` opisuje source/data root
  `C:\ai-lab-core`, nie udaje tożsamości live backendu.
- Runtime inventory zapisuje oddzielnie backend z czystego
  `main@483f9bf8b1a591ded8a42df5da87663c664ed5d4` oraz hostowe gatewaye,
  Supervisor i worker z mixed runtime.

## Zmiana kontraktu względem V1

V2 dodaje jawne `required_qdrant_collections` i rekord dla każdej kolekcji,
osobny artefakt/hash/snapshot/config/count/alias, `tool_source_head`, bounded
runtime inventory, okna składników oraz rozdzielone statusy capture,
spójności, restore, escrow i RTO. Wymagane są dokładnie:
`ai_lab_document_chunks` oraz `ai_lab_knowledge_base_chunks`.

Wspólny reader rozpoznaje V1 i V2. Test dowiódł, że V1 nadal jest rozpoznawany,
ale nie udaje pełnego V2. Trzy niezmienione czytniki V1-only jawnie odmawiają
V2 zamiast interpretować go jako punkt jednokolekcyjny. CaptureOnly nie wywołuje
restore helpera i nie fabrykuje `restore_verified`.

## Testy

Polecenia uruchomiono z `C:\ai-lab-core-recovery`:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File operations/recovery/test-r03-a1-recovery-tools.ps1
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File operations/recovery/test-recovery-tool.ps1
node operations/supervisor/test_qdrant_snapshot_validator.js
node operations/supervisor/test_backup_storage.js
node operations/supervisor/test_backup_scheduler.js
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File operations/recovery/test-r03-a1-synthetic-proof.ps1 -PostgresImage postgres@sha256:a426e44bac0b759c95894d68e1a0ac03ecc20b619f498a91aae373bf06d8508d -QdrantImage qdrant/qdrant@sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286 -ClientImage sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702
```

Wyniki: tool contract `38/38 PASS`, recovery PowerShell `15/15 PASS`, trzy
testy Node `PASS`, pełny synthetic proof `PASS`. Proof użył własnego ownera,
internal network, bez portów hosta, bind mountów produkcyjnych, Docker socketa
i privileged; końcowe containers/volumes/networks `0/0/0`.

Fail-before potwierdził 5/5 braków starego przepływu. Nowe testy obejmują dwie
kolekcje, brak kolekcji/artefaktu, zły hash, kolizję, przerwany capture,
nieobsługiwany manifest, brak restore w capture, rozdzielenie tool/source,
odmowę produkcyjnego/nieokreślonego Postgresa, host ports i bind mounts przed
pierwszym zapisem. Testy Asystenta i cała kampania aplikacji: `NOT_RUN`, poza A1.

## Preflight i capture

- Cel nie istniał; gate przestrzeni wynosił `40 GiB` przy około `8.05 GiB`
  jawnych źródeł. Wolne: C `597.14 GiB`, E `738.05 GiB`; backing store
  Postgres/Qdrant około `854/917 GiB`.
- Aktywne Assistant/Preparation/Analysis/Backup/Restore przed capture:
  `0/0/0/0/0`; Preparation queued `15`, nieprzetworzone.
- Trzy zadania backupu były `Ready`; najbliższy harmonogram przypadał ponad
  osiem godzin później.
- ACL celu ustanowiono przed artefaktami: dziedziczenie wyłączone, trzy jawne
  reguły dostępu, brak reguł deny.
- Pierwsza próba wywołania przez zewnętrzne `powershell.exe -File` źle
  przekazała tablicę i została odrzucona przed `BACKUP_STAGE`; katalog i nowe
  snapshoty nie powstały. Po teście tablicy użyto natywnego wywołania w jednym
  procesie PowerShell 5.1. To drugi command attempt, lecz pierwszy faktyczny
  przebieg danych.
- Faktyczny przebieg miał dokładnie etapy: database, documents, release,
  qdrant, n8n, configuration, verifying oraz jeden `BACKUP_COMPLETE`; żadnego
  etapu restore.

Okna UTC: DB `14:01:57–14:03:07`, document storage `14:03:07–14:07:13`,
release `14:07:13–14:08:40`, document Qdrant `14:08:40–14:08:51`, KB Qdrant
`14:08:51–14:08:52`, n8n `14:08:52–14:09:08`, configuration
`14:09:08–14:09:19`.

## Artefakty

| Plik | Bajty | SHA-256 |
|---|---:|---|
| `postgres.dump` | 466,492,223 | `552a7dd77d074a4fa8a4e81254d373021127102dcfbaa1a016d4441de1064b9e` |
| `document-storage.tar.gz` | 6,240,785,612 | `3a3c3f2e854301b956a924c40020b1320fa841eea20972ff85760455fb3d900b` |
| `release-stable.tar.gz` | 1,123,192,986 | `d6120b4420f3c8b3719f41c862eec01699baf0c9c3c69f702c3e799eba42bd09` |
| `ai_lab_document_chunks.snapshot` | 348,404,224 | `cd425bb21f41a3d4ceacf7e588e8bd2a239945321d3da32c4d78ce5880ec9fbf` |
| `ai_lab_knowledge_base_chunks.snapshot` | 2,449,920 | `9499a6966a82671452018a3e562ee409c94fc3abbfd3b32d7dcc74759b73759d` |
| `n8n-workflows.json` | 106,059 | `a76ccea57520e890511bfaf12dbf9bae31d154465f7de736b728c4af9c3b5c96` |
| `n8n-credentials.encrypted.json` | 4,612 | `aeea174188ec0ef03bc403924a2178f825bd76663b79de7d412a30ae8eac3b4d` |
| `configuration.tar.gz` | 4,128 | `dd65065d1d1ab6b79dab5ab8cdfcac17b84395a41f3b560d0426dcbcbaeef5fd` |
| `runtime-inventory.json` | 9,143 | `b8a79ccd47858aab35ba4f7f09a36f9b317e453507e3a4984dc88f11ff8f0817` |

Export credentials wykonano bez `--decrypted`; nie odczytano jego treści ani
klucza. `.env` nie został otwarty przez poprawiony writer i nie znajduje się w
punkcie. `secrets_in_protected_backup=false` oznacza brak escrow sekretów, nie
brak danych firmowych w dumpie lub dokumentach.

## Qdrant i ograniczona spójność

- Document: `57` punktów, `1024/Cosine`, aliasy `0`, struktura `valid`.
- KB: `157` punktów, `1024/Cosine`, aliasy `0`, struktura `valid`.
- Pre/post: 14 liczników tabel DB bez różnic, cztery źródła document storage bez
  różnic liczby/bajtów/ostatniego zapisu, Qdrant points bez różnic. Jedyna
  oczekiwana zmiana to snapshot count document `6→7`, KB `0→1`.
- Content-free scroll i read-only DB join: document `57/57`, KB `157/157`,
  missing/orphan/binding mismatch `0`.
- Ograniczenie: wszystkie `57` historycznych payloadów dokumentowych nie mają
  pola `embedding_version`; wartość nie została odgadnięta ani dopisana. KB ma
  kompletne kontrolowane pola generacji. Restore snapshotów nadal `NOT_RUN`.

Te dowody potwierdzają stabilne okno i referencje, lecz nie tworzą globalnej
transakcji DB/files/Qdrant/n8n. Zwykłe późniejsze dane zwiększają wiek punktu,
nie zmieniają jego historycznych hashy.

## Runtime i skutki

Runtime inventory jest `LOCAL_ONLY`, bez wartości sekretów. Zawiera sześć
image IDs/digestów, backend tree OID, 40-plikowy Web build (manifest SHA-256
`126852f50bf93a5ab36d1333c829c949791a485fb1337b1b9cfc393da7f9a517`),
hashe gatewayów/Supervisora/workerów, Qwen `qwen3.5:9b` digest
`6488c96f...` i embedding `qwen3-embedding:0.6b` digest `ac6da0df...`.
Ollama residency przed/po `0`.

Skutki operacyjne A1:

- zachowano nowy katalog i 9 artefaktów oraz po jednym źródłowym snapshotcie
  obu kolekcji;
- utworzono i usunięto dokładnie trzy pliki tymczasowe export/dump;
- Qdrant points/upsert/delete/reindex `0`; snapshot metadata/artifacts `2`;
- DB business counts, document storage, kontenery i DB head bez zmian;
- backend/Supervisor/gateway/n8n/Ollama nie zostały zrestartowane;
- modele, kolejki, workflow i odtworzona aplikacja nie zostały uruchomione;
- surowy log capture zawiera nazwy plików klientów i pozostaje chroniony
  `LOCAL_ONLY`; w Git są tylko zanonimizowane agregaty.

## Dowody LOCAL_ONLY

Root: `C:\ai-lab-core-staging\recovery\R03_A1_20260908T115703Z`.

| Dowód | SHA-256 |
|---|---|
| `fail-before.json` | `9A5A1A39E9EA3F37035AF69F59B0624DC5CCF405C4DB743D17F5038A947D35B8` |
| `synthetic-proof-final5.log` | `EBBEFECB5276B670A6E885E592236FDEBC0247FCEC6E0696AAE86E0B72812BBD` |
| błędne wywołanie przed etapem | `7B4D7DD39C7B5EF28E2155DBD9EE3855C23A7340DAE75FCEA9DDB54389BFCFEA` |
| surowy capture log (wrażliwy) | `1942F9A88BD78315945BA48F6270BE7F34329F2E1C44F587F04AAE5C8DBBD39C` |
| `validate-only-20260908T135012Z.log` | `91F461F777C939372D7FAA4EB99FC60BD2C181A3FE02ADBC12871704FE36EF4A` |
| runtime inventory | `B8A79CCD47858AAB35BA4F7F09A36F9B317E453507E3A4984DC88F11FF8F0817` |
| pre/post state | `D425A1AE31A953DBD931AC96055E74756673C0612A0C7A47B88D42C7E685DC6E` / `57F364DC672D892B9E3722266B564B4C4DDD4FFD4DB18E0B0CFF964FEC82DAF2` |
| reference consistency | `C1EBD4CB8C78F52265EDCD6FDAD2C363A31963C909D8535F3971C3EB0494986C` |

## Następna osobna decyzja

Właściciel może osobno zatwierdzić izolowany drill wyłącznie tego manifestu do
nieutworzonego celu `C:\ai-lab-core-staging\recovery\R03_DRILL_20260908_A1`,
project `next-stabil-r03-drill-20260908-a1`, kontenerów/wolumenów Postgres i
Qdrant oraz sieci `next-stabil-r03-internal-20260908-a1` wskazanych w
checkpointcie preflight. Sieć ma być internal, bez host ports i produkcyjnych
mountów; odtworzona aplikacja i schedulery nie mogą wystartować. Cleanup celu
wymaga dalszej zgody. Escrow/vault/recovery key są niezależną decyzją i nie są
warunkiem samego zatwierdzenia drill.

STOP: bez restore/drill, escrow, cleanupu źródłowych kopii i R04.
