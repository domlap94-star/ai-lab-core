# R03 A2 — dowód izolowanej próby odtworzenia

## Wynik

`R03 A2 ISOLATED_DRILL_READY_FOR_REVIEW / WAITING_ESCROW_DECISION`.
Wszystkie 9 zatwierdzonych artefaktów odtworzono lub zweryfikowano w nowych,
odizolowanych celach. Cały R03 pozostaje `WAITING_APPROVAL`: nie uruchomiono
aplikacji, nie odzyskano credentials i nie wykonano escrow. Ujawniono realną
lukę zakresu kopii: brak 10 źródłowych plików KB.

## Niezmienne wejście

| Element | Dowód |
|---|---|
| Katalog | `E:\ai-lab-backup\20260908T135012Z` |
| Schemat | `NEXT_STABIL_BACKUP_V2` |
| Manifest SHA-256 przed/po | `1195AE5BE68CF589D9B9231C85B0BE678C87117FD471034417B9DC8C5620FD57` / taki sam |
| Artefakty | `9/9`, `8,181,448,907 B`, hash/size/structure PASS |
| DB revision | `followup_assistant_chat_history_20260829` |
| Capture writer / wykonawczy HEAD | `c6faca0dba5944a9900cef3cd20f24d35c3060f7` / `1050e9e5494f5dd7f6e28a6804768d54faa11cd0` |
| Reader | tool `1.1.1`, `restore-checkpoint.ps1` SHA-256 `49E7F690CE8D23760B55E5EADE02A07F23727A38947DFD3A9087603D0A7A36A0` |
| Offline Qdrant helper | SHA-256 `5876A111BF6CF9C7EDB937473FD20C2BF6B8B088CD168C627FB42149A7E0EF41` |

Końcowe `ValidateOnly / Full` zakończyło się kodem `0`, nadal zwracając
`restore_status=NOT_RUN_WAITING_APPROVAL` i `full_eligible=false`. Jest to
zamierzone: dowód drill jest osobnym dokumentem i nie zmienia historycznych
bajtów manifestu.

## Izolacja i obrazy

| Składnik | Przypięta tożsamość | Wynik |
|---|---|---|
| PostgreSQL | `postgres@sha256:a426e44bac0b759c95894d68e1a0ac03ecc20b619f498a91aae373bf06d8508d` | lokalny image ID zgodny |
| Qdrant | `qdrant/qdrant@sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286` | lokalny image ID zgodny; `1.18.3` |
| Klient walidacyjny | `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702` | lokalny image ID zgodny |

Każdy cel nie istniał przed pierwszym zapisem. Sieci są `internal`, host
ports `0`; kontenery nie mają privileged, host PID, Docker socketa,
produkcyjnych sieci ani produkcyjnych mountów. PostgreSQL użył nowego wolumenu
i lokalnego trybu `trust` wyłącznie w niepublikowanej sieci drill. Nie użyto
produkcyjnego hasła ani czynnego serwera.

## Istotne polecenia wykonawcze

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File operations/hardening/restore-checkpoint.ps1 -CheckpointPath 'E:\ai-lab-backup\20260908T135012Z' -Mode Full -ValidateOnly

docker exec next-stabil-r03-a1-drill-20260908-a1-postgres createdb -U postgres ai_lab_restore_test_r03_20260908_a1
docker cp 'E:\ai-lab-backup\20260908T135012Z\artifacts\postgres.dump' next-stabil-r03-a1-drill-20260908-a1-postgres:/tmp/r03-a2-postgres.dump
docker exec next-stabil-r03-a1-drill-20260908-a1-postgres pg_restore -U postgres -d ai_lab_restore_test_r03_20260908_a1 --no-owner --exit-on-error /tmp/r03-a2-postgres.dump

powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File operations/hardening/verify-qdrant-snapshot-offline.ps1 -SnapshotPath 'E:\ai-lab-backup\20260908T135012Z\artifacts\qdrant\ai_lab_document_chunks.snapshot' -TargetCollection ai_lab_document_chunks -ExpectedPoints 57 -ExpectedDimensions 1024 -ExpectedDistance Cosine -OperationId next-stabil-r03-a1-drill-20260908-a1-qdrant-1 -QdrantImage 'qdrant/qdrant@sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286' -ClientImage 'sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702' -KeepResources

powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File operations/hardening/verify-qdrant-snapshot-offline.ps1 -SnapshotPath 'E:\ai-lab-backup\20260908T135012Z\artifacts\qdrant\ai_lab_knowledge_base_chunks.snapshot' -TargetCollection ai_lab_knowledge_base_chunks -ExpectedPoints 157 -ExpectedDimensions 1024 -ExpectedDistance Cosine -OperationId next-stabil-r03-a1-drill-20260908-a1-qdrant-2 -QdrantImage 'qdrant/qdrant@sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286' -ClientImage 'sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702' -KeepResources
```

Tworzenie sieci, wolumenów, kontenera PostgreSQL i ekstrakcja archiwów były
wykonane jawnie dla exact-name celów z checkpointu. Pełny zapis komend, exit
codes i surowe wyjścia pozostaje `LOCAL_ONLY`; Git nie zawiera sekretów ani
danych firmy.

## Wyniki komponentów

### PostgreSQL

- `pg_restore --no-owner --exit-on-error`: exit `0`, `103.260 s`.
- `current_database()` wskazał wyłącznie
  `ai_lab_restore_test_r03_20260908_a1`.
- Alembic: jeden head, `followup_assistant_chat_history_20260829`.
- 52 tabele, 113 FK, 114 PK; nieważne FK `0`, zduplikowane PK `0`.
- 14/14 bezpiecznych counts jest zgodnych z dowodem A1.
- Nie wykonano migracji, upgrade/downgrade ani naprawy rekordów.

### Document storage, release i konfiguracja

- Archiwum storage: 6354 pliki, 99 katalogów, `6,638,250,957 B` po
  ekstrakcji; unsafe paths `0`, links/reparse points `0`.
- Zakres zawiera po jednym katalogu `documents`, `document-pages`,
  `document-assets`, `archive-extracted`.
- Odtworzona DB ma 6349 odwołań do tych czterech zakresów: resolved
  `6349`, missing `0`, unsafe `0`, size mismatch `0`; sprawdzono 5998 hashy,
  mismatch `0`. Pięć historycznych orphan files zachowano bez zmian.
- Release: 55 plików, `2,006,301,613 B`; manifest `1.0.2` i jego hash są
  zgodne z runtime inventory. Konfiguracja: 12 plików, forbidden filename
  matches `0`.
- Runtime inventory zapisuje 6 tożsamości kontenerów i 10 artefaktów hosta.
  Bajtów wskazanych poza drill nie odczytywano:
  `NOT_VERIFIED_OUTSIDE_DRILL`.

### Qdrant i wiązania

| Kolekcja | Restore | Punkty / konfiguracja | DB binding | Legacy metadata |
|---|---|---|---|---|
| `ai_lab_document_chunks` | PASS, `38.458 s` | `57`, `1024/Cosine`, aliasy `0` | `57/57`, brakujące `0` | `embedding_version` brak w `57/57` payloadach; nic nie dopisano |
| `ai_lab_knowledge_base_chunks` | PASS, `13.908 s` | `157`, `1024/Cosine`, aliasy `0` | `157/157`, brakujące `0` | jedna zgodna para `qwen3-embedding:0.6b` / `v1` |

Walidacja pobrała wyłącznie allowlistowane pola referencyjne; nie pobierała
`content`, nazw plików, tytułów ani tekstu. Nie wykonano embeddingu, upsertu,
reindexu ani backfillu.

### n8n i przypadek reprezentatywny

- Cztery rekordy workflow i cztery rekordy credentials są strukturalnie
  czytelne. Credentials potraktowano jako nieprzejrzysty zaszyfrowany payload;
  nie odszyfrowano go ani nie sprawdzono dostępu do kont.
- Zanonimizowany przypadek ma klienta, encję biznesową, zgodny plik dokumentu,
  wyrenderowaną stronę i powiązany chunk. Oddzielny materiał KB ma poprawne
  wiązania item/page/index.
- Luka: DB wskazuje 10 źródłowych plików KB, ale kopia nie zawiera katalogu
  `knowledge-base`; dostępność w capture wynosi `0/10`. Nie jest to błąd
  restore dziewięciu artefaktów, lecz potwierdzony brak zakresu recovery.

## Czasy i status DR

- Okno capture: `2026-09-08T14:01:57.3063773Z` –
  `2026-09-08T14:09:19.2480913Z` (`441.942 s`).
- Drill i kontrole: `2026-09-08T18:07:34Z` –
  `2026-09-08T19:06:51.5589263Z` (`3557.559 s`).
- To czas odtworzenia i kontroli danych w tym drill, nie RTO firmy.
- `COMPONENT_WINDOWS_RECORDED_NON_TRANSACTIONAL` pozostaje prawdziwe; poprawny
  restore nie czyni capture transakcyjnym snapshotem wielu usług.
- Aplikacja E2E, recovery key, credentials i escrow: `NOT_RUN` /
  `WAITING_OWNER_DECISION`.

## Skutki i zachowane cele

Zatrzymano wyłącznie pięć nowych kontenerów. Nie usunięto żadnego celu:

- container `next-stabil-r03-a1-drill-20260908-a1-postgres`, ID
  `f64567fd782a6a322db8498d11e0bb530178beb71c6ae1ffa197ef95275b4f3c`;
- containers `next-stabil-r03-a1-drill-20260908-a1-qdrant-1-server` /
  `next-stabil-r03-a1-drill-20260908-a1-qdrant-1-client`,
  IDs `846871485e3eee219e6d7973a1c532de69d16b31b54b9df8e859807fbfc8eb75` /
  `8847f0eb5e137b61de7012d0c33f4854119a862244677d01f00c04e56e70fa76`;
- containers `next-stabil-r03-a1-drill-20260908-a1-qdrant-2-server` /
  `next-stabil-r03-a1-drill-20260908-a1-qdrant-2-client`,
  IDs `846fc6826e44400d4089253d6050d54493693f1c67e19055f985dd9da3c7fd32` /
  `b5dde433aa8b969d1d145675746e2f42edc4adc02dacee1797bcb04694e9184d`;
- volumes `next-stabil-r03-a1-drill-20260908-a1-postgres-data`
  (`1,465,676,641 B`), `next-stabil-r03-a1-drill-20260908-a1-qdrant-1-data`
  (`348,330,230 B`) i `next-stabil-r03-a1-drill-20260908-a1-qdrant-2-data`
  (`482,554,069 B`);
- networks `next-stabil-r03-a1-drill-20260908-a1-network`,
  `next-stabil-r03-a1-drill-20260908-a1-qdrant-1-network` i
  `next-stabil-r03-a1-drill-20260908-a1-qdrant-2-network`, wszystkie `internal`;
- protected root: `C:\ai-lab-core-staging\recovery\R03_DRILL_20260908_A1`,
  `8,646,543,469 B` łącznie z małymi końcowymi manifestami.

Końcowe stany kontenerów to `exited`: PostgreSQL `0`, Qdrant servers `143`,
clients `0/137`. Kody 143/137 wynikają z kontrolowanego zatrzymania zachowanych
procesów po zakończonych kontrolach, nie z wyniku restore. Root ma wyłączone
dziedziczenie ACL; dostęp mają lokalny wykonawca, SYSTEM i Administrators.

Cleanup tych zasobów wymaga osobnej zgody. Produkcyjnych kontenerów nie
restartowano; nie było produkcyjnych zapisów biznesowych, model calls, queue
drain, nowych snapshotów, migracji ani escrow. Końcowo produkcja ma DB head
`followup_assistant_chat_history_20260829`, Preparation queued `15`, Advanced
queued `16`, Qdrant `57/157`, snapshoty `7/1` i Ollama residency `0`.

## Lokalny dowód i bramka

Surowe logi, szczegółowe referencje i odtworzone dane są `LOCAL_ONLY` pod
chronionym rootem drill. Manifest jedenastu dowodów ma SHA-256
`55B0313911E229BAB6DA32DBEDE5EF26C22853109E8C7FF24A393401743ADA82`;
jego bezpieczny indeks jest w `R03_A2_LOCAL_EVIDENCE_MANIFEST.csv`.

Następny krok wymaga decyzji właściciela: odbiór A2, domknięcie zakresu
źródłowych plików KB, escrow/recovery key i późniejszy exact-name cleanup.
Bez R04.
