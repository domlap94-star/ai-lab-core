# R03 A4 — dowód izolowanego drill nowego punktu

## Wynik

`R03 A4 NEW_POINT_DRILL_READY_FOR_REVIEW / WAITING_ESCROW_DECISION`.

Dokładny punkt `E:\ai-lab-backup\20260908T210559Z` odtworzono do nowych,
odizolowanych celów A4. PostgreSQL, pięć domen storage, obie kolekcje Qdrant,
release, niesekretna konfiguracja i struktura eksportów n8n przeszły kontrolę.
Aplikacji ani integracji nie uruchomiono. A4 i cały R03 nie są samodzielnie
`ACCEPTED`; escrow, odzyskanie credentials i pełne RTO pozostają niewykonane.

## Niezmienne wejście

| Element | Dowód |
|---|---|
| Katalog | `E:\ai-lab-backup\20260908T210559Z` |
| Schemat | `NEXT_STABIL_BACKUP_V2` + `NEXT_STABIL_STORAGE_COVERAGE_V1` |
| Manifest SHA-256 przed/po | `8F20A7845473097EE74019966583EC3F121139C4B562265F9A7391FAFAF6BE4B` / taki sam |
| Artefakty | `9/9`, `8 232 583 217` B |
| DB revision | `followup_assistant_chat_history_20260829` |
| Capture writer/tool HEAD | `af812c0b2bdea97aa35686f2b65a44111bd18840` |
| Source/runtime HEAD zapisany przez capture | `72950657ac79b50d0afe72753632ba4cde810b95` |
| Reader/helper | tool manifest `1.2.0`; wykonanie A4 rozpoczęte na recovery `243623972971a0c0a681d16cc6b456b0a34a53da` |

Końcowy `restore-checkpoint.ps1 -ValidateOnly -Mode Full` zakończył się kodem
`0`: `valid=true`, storage `COMPLETE`, obie kolekcje obecne. Historyczny
manifest celowo pozostał z `restore_status=NOT_RUN_WAITING_APPROVAL` i
`full_eligible=false`; odrębny dowód drill nie zmienia bajtów capture.

### Hashe wejściowych artefaktów

| Składnik | Bajty | SHA-256 |
|---|---:|---|
| PostgreSQL | 466 498 039 | `307B69DDBF19BD898F80CF0250F331451BA585729046D4F997D5EC250F2769DB` |
| storage | 6 291 914 010 | `C0F11AA47FC1B599810B7952ADFCCB7D97202A01A796D16E3F807959AD6AACD5` |
| release | 1 123 192 986 | `F54D3B475DAA13572CE551DE7AE5A3FEC3B7AF0C9EE96F4A8B7E8F4BC00F53EA` |
| Qdrant document | 348 404 224 | `00058A609A518F3A5F68D92C4022825954DBC96942579902CC6C9C983B48A668` |
| Qdrant KB | 2 449 920 | `FDDB762B1C6A5BC3566649D7E1A8ABAA8EED64ADF7E40554FD130EA30A1C5661` |
| n8n workflow | 106 059 | `A76CCEA57520E890511BFAF12DBF9BAE31D154465F7DE736B728C4AF9C3B5C96` |
| n8n credentials, opaque encrypted | 4 612 | `73AEA0E9FE77B8314264ACD668D94211ADD6EDF74D1EB91D20B9C254A6C126A7` |
| konfiguracja | 4 066 | `13E7F9388C311C3584C2C82FB76D194A98BEB8BB2AC18E939D389D6F0553279B` |
| runtime inventory | 9 301 | `C82D9703576AC57AAF3F8048383F29BBF603D883AAF3D167C5A312C8F9F8F763` |

## Narzędzia, obrazy i izolacja

- `restore-checkpoint.ps1`: SHA-256
  `AD7C665C22E0C8805B51BF6E25633C7DF945F9F52C9235292628BF2E28B519C4`.
- `verify-qdrant-snapshot-offline.ps1`: SHA-256
  `5876A111BF6CF9C7EDB937473FD20C2BF6B8B088CD168C627FB42149A7E0EF41`.
- PostgreSQL: `postgres@sha256:a426e44bac0b759c95894d68e1a0ac03ecc20b619f498a91aae373bf06d8508d`.
- Qdrant: `qdrant/qdrant@sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286`.
- Klient: image ID
  `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`.

Przed pierwszym zapisem wszystkie exact-name cele nie istniały. Trzy sieci są
`internal`; host ports `0`, privileged `0`, produkcyjne sieci/mounty `0`,
Docker socket `0`. Root ma wyłączone dziedziczenie ACL. PostgreSQL użył nowego
wolumenu i lokalnego `trust` wyłącznie wewnątrz niepublikowanej sieci drill;
nie użyto produkcyjnego hasła.

## Polecenia wykonawcze

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File operations/hardening/restore-checkpoint.ps1 -CheckpointPath 'E:\ai-lab-backup\20260908T210559Z' -Mode Full -ValidateOnly

docker exec next-stabil-r03-a1-drill-20260908-a4-postgres createdb -U postgres ai_lab_restore_test_r03_20260908_a4
docker cp 'E:\ai-lab-backup\20260908T210559Z\artifacts\postgres.dump' next-stabil-r03-a1-drill-20260908-a4-postgres:/tmp/r03-a4-postgres.dump
docker exec next-stabil-r03-a1-drill-20260908-a4-postgres pg_restore -U postgres -d ai_lab_restore_test_r03_20260908_a4 --no-owner --exit-on-error /tmp/r03-a4-postgres.dump

tar.exe -xzf 'E:\ai-lab-backup\20260908T210559Z\artifacts\document-storage.tar.gz' -C 'C:\ai-lab-core-staging\recovery\R03_DRILL_A4_20260908T210559Z\restored\storage'
tar.exe -xzf 'E:\ai-lab-backup\20260908T210559Z\artifacts\release-stable.tar.gz' -C 'C:\ai-lab-core-staging\recovery\R03_DRILL_A4_20260908T210559Z\restored\release'
tar.exe -xzf 'E:\ai-lab-backup\20260908T210559Z\artifacts\configuration.tar.gz' -C 'C:\ai-lab-core-staging\recovery\R03_DRILL_A4_20260908T210559Z\restored\configuration'

powershell.exe -NoProfile -ExecutionPolicy Bypass -File operations/hardening/verify-qdrant-snapshot-offline.ps1 -SnapshotPath 'E:\ai-lab-backup\20260908T210559Z\artifacts\qdrant\ai_lab_document_chunks.snapshot' -TargetCollection ai_lab_document_chunks -ExpectedPoints 57 -ExpectedDimensions 1024 -ExpectedDistance Cosine -OperationId next-stabil-r03-a1-drill-20260908-a4-qdrant-1 -QdrantImage 'qdrant/qdrant@sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286' -ClientImage 'sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702' -KeepResources
powershell.exe -NoProfile -ExecutionPolicy Bypass -File operations/hardening/verify-qdrant-snapshot-offline.ps1 -SnapshotPath 'E:\ai-lab-backup\20260908T210559Z\artifacts\qdrant\ai_lab_knowledge_base_chunks.snapshot' -TargetCollection ai_lab_knowledge_base_chunks -ExpectedPoints 157 -ExpectedDimensions 1024 -ExpectedDistance Cosine -OperationId next-stabil-r03-a1-drill-20260908-a4-qdrant-2 -QdrantImage 'qdrant/qdrant@sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286' -ClientImage 'sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702' -KeepResources
```

Kontrole DB i powiązań były transakcjami read-only / content-free. Surowe
polecenia, exit codes i allowlistowane referencje są `LOCAL_ONLY`; Git nie
zawiera ścieżek klientów, tekstu, credentials ani wartości konfiguracji.

## Wyniki komponentów

### PostgreSQL

- `pg_restore --no-owner --exit-on-error`: exit `0`, `104.036 s`.
- `current_database()` wskazał wyłącznie
  `ai_lab_restore_test_r03_20260908_a4`.
- Alembic: jeden head `followup_assistant_chat_history_20260829`.
- 52 tabele, 113 FK, 114 PK; niewalidowane FK `0`.
- Bezpieczne liczniki zapisano z odtworzonej bazy; nie użyto produkcji do
  uzupełnienia backupu. Nie wykonano migracji ani napraw danych.

### Storage i źródła KB

Przed ekstrakcją listy archiwów miały unsafe paths `0` i link entries `0`.
Odtworzono 6 364 pliki, `6 698 494 888` B, w pięciu domenach:

| Domena | Pliki | Bajty |
|---|---:|---:|
| `documents` | 5 989 | 6 428 257 894 |
| `document-pages` | 351 | 202 174 564 |
| `document-assets` | 10 | 5 631 553 |
| `archive-extracted` | 4 | 2 186 946 |
| `knowledge-base` | 10 | 60 243 931 |

Odtworzona DB ma `6 359` referencji: resolved `6 359`, missing/unsafe/size
mismatch `0/0/0`. Sprawdzono `6 008` hashy, mismatch `0`. KB ma
`10/10` plików i `10/10` zgodnych hashy. Zachowano pięć historycznych orphan
files; nie usuwano ani nie poprawiano żadnego rekordu.

### Qdrant i bindingi

| Kolekcja | Restore | Punkty / konfiguracja | DB binding | Czas |
|---|---|---|---|---:|
| `ai_lab_document_chunks` | PASS | `57`, `1024/Cosine`, aliasy `0` | `57/57`, missing/mismatch/duplicate `0/0/0` | `48.174 s` |
| `ai_lab_knowledge_base_chunks` | PASS | `157`, `1024/Cosine`, aliasy `0` | `157/157`, missing/mismatch/duplicate `0/0/0` | `18.344 s` |

Wszystkie 57 historycznych payloadów dokumentowych nadal nie mają
`embedding_version`; niczego nie dopisano. KB zachowuje jedną zgodną parę
`qwen3-embedding:0.6b` / `v1`. Nie wykonano embeddingu, upsertu, reindexu,
delete ani backfillu.

### Release, konfiguracja, n8n i reprezentatywny łańcuch

- Release: 55 plików, wersja `1.0.2+29`; bieżące Windows/Android artefakty
  zgadzają się z hashami manifestu, a manifest konfiguracji ma te same bajty.
- Konfiguracja: 12 plików, forbidden filename matches `0`; runtime inventory
  deklaruje brak wartości sekretów, 6 kontenerów, 10 host artifacts i obie
  kolekcje. Bajtów wskazanych poza drill nie odczytywano:
  `NOT_VERIFIED_OUTSIDE_DRILL`.
- n8n: 4 workflow i 4 rekordy credentials są strukturalnie czytelne.
  Credentials potraktowano jako opaque encrypted bytes; bez odszyfrowania,
  klucza, importu i startu workflow.
- Zanonimizowany join potwierdził jeden łańcuch klient–dokument–plik–strona–
  document chunk oraz osobny materiał KB–plik–strona–KB chunk, wyłącznie na
  odtworzonych komponentach.

## Czasy i granica dowodu

- Okno źródłowego capture według komponentów manifestu:
  `2026-09-08T21:15:24.5186949Z` – `2026-09-08T21:23:00.6830079Z`
  (`456.164 s`).
- Drill od utworzenia chronionego rootu do końca kontroli:
  `2026-09-08T23:39:20.6577505Z` – `2026-09-09T00:13:42.4697076Z`
  (`2061.812 s`).
- Jest to czas odtworzenia i kontroli danych, nie pełne RTO firmy.
- `COMPONENT_WINDOWS_RECORDED_NON_TRANSACTIONAL` pozostaje prawdziwe.
- Aplikacja, gatewaye, Supervisory, workery, schedulery i integracje z
  odtworzonego zestawu: `NOT_RUN`.
- Recovery key, działanie credentials i escrow:
  `NOT_RUN_WAITING_OWNER_DECISION`; pełne RTO: `NOT_MEASURED`.

## Zachowane zasoby A4

Chroniony root:
`C:\ai-lab-core-staging\recovery\R03_DRILL_A4_20260908T210559Z`,
`8 707 671 777` B po zapisaniu lokalnego indeksu dowodów. Pięć kontenerów
zatrzymano i zachowano:

- PostgreSQL `294d93d8234dba78973d27e8fe6d115a99dd337dd187d110468536be552af051`;
- Qdrant document server/client
  `59adf004f6de2df49bcdb9ef9c65e9aa20d7510e4455ce5bd7b8af5a3ed90f55` /
  `c267cfd1a371ff1cf37e21a3ddb7edaa3d839eb8fe6323e21579fc10f09ca49e`;
- Qdrant KB server/client
  `a4dd18937dadebb3de72d0aeb55a60230d4307c3595ff1202a985e99b254ef41` /
  `11abc3c9bc6d69110283bde4102c4c41207975eed045ad1ba88e651ba1758eae`.

Zachowano wolumeny PostgreSQL/document/KB o rozmiarach odpowiednio
`1 465 750 369` / `348 330 230` / `482 554 069` B oraz trzy exact-name sieci
internal. Niczego nie usunięto. Kody wyjścia Qdrant `143` i klientów `137`
wynikają z kontrolowanego zatrzymania po udanych kontrolach, nie z restore.
Cleanup wymaga osobnej exact-name zgody.

## Wpływ operacyjny i zachowanie

- Produkcyjne ID kontenerów bez zmian; backend/gateway HTTP `200`, public
  `/control` `404`.
- Produkcyjny DB head niezmieniony; Preparation queued `15`, Advanced queued
  `16`, aktywne prace `0`.
- Produkcyjny Qdrant pozostał `57/157`, snapshoty `8/2`; Ollama residency `0`.
- A4 nie wykonało produkcyjnego zapisu biznesowego, snapshotu, upsertu,
  reindexu, model call, queue drain, restartu, migracji ani escrow.
- Niezależny harmonogram Backup-3 zakończył się w oczekiwanym oknie i
  zwiększył completed backup runs `40→41`; to zaobserwowana aktywność innego
  procesu, nie skutek A4.
- Oryginalny worktree: `203/203` hashy, mismatch `0`, 6 modified + 197
  untracked, staged `0`; A2/A3 i stary manifest `1195AE5B...` bez zmian.

Surowe dowody pozostają `LOCAL_ONLY`. Manifest 18 plików dowodowych ma SHA-256
`19BF01D4F17AC16CBA1C580619D44E8D0C330F33EB572D386AFFD27A55D61345`.

Następny krok: właściciel ocenia A4 oraz oddzielnie rozstrzyga escrow i
cleanup dokładnie nazwanych celów. Bez R04.
