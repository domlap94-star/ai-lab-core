# R03 A3 — źródłowe pliki KB w nowym punkcie recovery

## Wynik i granica

R03-A3 ma stan `KB_SOURCE_CAPTURE_READY_FOR_REVIEW /
WAITING_NEW_POINT_DRILL_APPROVAL`. Cały R03 pozostaje `WAITING_APPROVAL`.
Właściciel przyjął dowód A2 na
`afedb4d1025feb8bd287272c36935ce9feb4f877` z ograniczeniem: źródłowe pliki
KB nie były częścią starego punktu (`0/10`). A3 nie zatwierdza pełnego drill,
escrow, rollout harmonogramów, cleanupu ani R04.

## Źródło poprawki i reprodukcja

- Start A3: `afedb4d1025feb8bd287272c36935ce9feb4f877`.
- SOURCE_PASS: `9e7df2068e1138fbbb5ca2e213c13efffe4c0945`.
- Execution HEAD jedynego capture:
  `af812c0b2bdea97aa35686f2b65a44111bd18840`.
- Tool manifest: `NEXT_STABIL_RECOVERY_TOOL_V1`, wersja `1.2.0`.
- `backup-production.ps1`: 34 059 B, SHA-256
  `F895E4874A10E4CE964B8E9EDAC37A2A58DB734A0C8E2D5E33241591DBD6B28F`.
- `restore-checkpoint.ps1`: 36 737 B, SHA-256
  `AD7C665C22E0C8805B51BF6E25633C7DF945F9F52C9235292628BF2E28B519C4`.

Fail-before wywołał rzeczywisty writer ze startowego kodu i syntetyczne,
zamockowane granice zewnętrzne. Zakończył się exit `1` na asercji
`real_writer_declares_kb_source_domain`. Log jest `LOCAL_ONLY`, SHA-256
`D3B56B9C8D46011CF0AC58AC315AB333B363A87DA2D360205DE1029E7A7614B4`.
Wcześniejsza próba z błędem parsera nakładki nie jest dowodem produktu i jest
oznaczona jako taka w lokalnym indeksie.

Minimalna poprawka zachowuje V1 i historyczny V2, a bieżący V2 deklaruje pięć
domen storage oraz addytywny kontrakt `NEXT_STABIL_STORAGE_COVERAGE_V1`.
Writer sprawdza wszystkie trwałe referencje `knowledge_base_items` w jawnej
transakcji read-only przed pierwszym zapisem i ponownie przed/po archiwizacji:
root, dostępność, reparse point, rozmiar, SHA-256 oraz fingerprint zbioru.
Reader wymaga tego kontraktu tylko od bieżącego V2. Historyczny V2 bez niego
pozostaje czytelny, ale nie dowodzi pełnego bieżącego pokrycia.

## Testy syntetyczne

Wszystkie komendy wykonano z `C:\ai-lab-core-recovery` w Windows PowerShell
5.1, bez produkcyjnych zapisów i bez zasobów Docker:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File operations/recovery/test-r03-a1-recovery-tools.ps1
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File operations/recovery/test-recovery-tool.ps1
node operations/supervisor/test_qdrant_snapshot_validator.js
node operations/supervisor/test_backup_storage.js
node operations/supervisor/test_backup_scheduler.js
```

Wyniki końcowe na opublikowanym source:

- writer/reader/guard: `58/58 PASS`, exit `0`;
- wrapper/tool manifest: `15/15 PASS`, exit `0`;
- Qdrant validator: `PASS`, exit `0`;
- backup storage: `PASS`, exit `0`;
- backup scheduler: `PASS`, exit `0`.

Testy obejmują: prawidłowy KB archive roundtrip, brak pliku, wyjście poza root,
size/hash mismatch przy tym samym rozmiarze, pusty potwierdzony korpus,
reparse point, drift inventory, przerwany capture, brak domeny w archiwum,
niezmienione V1, węższy historyczny V2, wymagania bieżącego V2 oraz brak
automatycznego restore. Granice `docker` i `docker.exe` były kontrolowane.

## Jeden nowy capture

Użyto dokładnie raz poprawionego `backup-production.ps1` w trybie
`RecoveryPointV2 / CaptureOnly`.

| Pole | Wynik |
|---|---|
| Katalog | `E:\ai-lab-backup\20260908T210559Z` |
| Start / koniec UTC | `2026-09-08T21:15:21.6811930Z` / `2026-09-08T21:23:27.6943038Z` |
| Manifest | `NEXT_STABIL_BACKUP_V2` |
| SHA-256 manifestu | `8F20A7845473097EE74019966583EC3F121139C4B562265F9A7391FAFAF6BE4B` |
| Artefakty | `9/9`, `8 232 583 217` B |
| DB revision | `followup_assistant_chat_history_20260829` |
| Capture / scope / provenance | `COMPLETE / COMPLETE / RECORDED` |
| Consistency | `COMPONENT_WINDOWS_RECORDED_NON_TRANSACTIONAL` |
| Restore / escrow / RTO | `NOT_RUN_WAITING_APPROVAL / NOT_RUN_WAITING_OWNER_DECISION / NOT_MEASURED` |

Artefakty to: dump PostgreSQL, jedno archiwum storage, release stable, dwa
snapshoty Qdrant, export czterech workflow n8n, export czterech credentials w
postaci zaszyfrowanej, niesekretna konfiguracja i runtime inventory. Kontrola
konfiguracji wykazała 23 wpisy i 0 nazw odpowiadających `.env`, cookies,
kluczom prywatnym lub plikom certyfikatów. Zawartości eksportów i konfiguracji
nie odczytywano ani nie publikowano.

Zakres storage zapisany w manifeście:

| Domena | Pliki | Bajty |
|---|---:|---:|
| `documents` | 5 989 | 6 428 257 894 |
| `document-pages` | 351 | 202 174 564 |
| `document-assets` | 10 | 5 631 553 |
| `archive-extracted` | 4 | 2 186 946 |
| `knowledge-base` | 10 | 60 243 931 |

Obie kolekcje zostały uchwycone w osobnych artefaktach: document chunks
`57`, KB chunks `157`, obie `1024/Cosine`, aliasy `0`. Snapshotów nie
odtwarzano. Liczniki produkcyjnych snapshotów zmieniły się zgodnie z
autoryzacją dokładnie `7/1 -> 8/2`; punkty pozostały `57/157`.

Niezależny reader `-ValidateOnly -Mode Full` zakończył się exit `0`, potwierdził
9/9 hashy, obie kolekcje i `storage_coverage=COMPLETE`, ale zachował
`full_eligible=false`, `qdrant_restore_verified=false` i `restore_status=NOT_RUN`.
Capture log zawiera jeden `BACKUP_COMPLETE`, siedem etapów i zero wywołań lub
tokenów restore.

## Roundtrip plików KB

Przed ekstrakcją sprawdzono pełną listę 6 464 wpisów archiwum: unsafe paths
`0`, link entries `0`. Do chronionego stagingu wypakowano wyłącznie domenę
`knowledge-base`, bez wykonania plików, OCR, importu, indeksacji lub odczytu
treści.

| Kontrola | Wynik |
|---|---:|
| Referencje oczekiwane | 10 |
| Pliki uchwycone / wypakowane | 10 / 10 |
| Zgodne hashe źródła / roundtrip | 10 / 10 |
| Missing / mismatch | 0 / 0 |
| Bajty | 60 243 931 |
| Fingerprint referencji zgodny z manifestem | TAK |

Pełny join do odtworzonej DB i odtworzenie obu kolekcji dla nowego punktu są
`NOT_RUN_WAITING_APPROVAL`; wyniku A2 nie przepisano na nowy manifest.

## Kompatybilność i zachowane artefakty

- Stary punkt `E:\ai-lab-backup\20260908T135012Z` pozostał niezmieniony;
  manifest nadal ma SHA-256
  `1195AE5BE68CF589D9B9231C85B0BE678C87117FD471034417B9DC8C5620FD57`.
- Bieżący reader zweryfikował 9/9 jego historycznych artefaktów i zwrócił
  `valid=true`, ale prawidłowo: `storage_coverage_status=NOT_RECORDED`,
  `capture_complete=false`, `full_eligible=false`, KB source coverage
  `NOT_RECORDED`. Dowód A2 zachowuje jawne `0/10`.
- Zasoby A2: 5/5 kontenerów nadal `exited`, 3 wolumeny i 3 sieci internal
  zachowane pod tymi samymi ID; root A2 nie został zmieniony ani usunięty.
- Oryginalny dirty worktree: `203/203`, mismatch `0`, staged `0`, HEAD
  `72950657ac79b50d0afe72753632ba4cde810b95`.

## Wpływ operacyjny i brak rollout

Utworzono nowy katalog backupu, dump, archiwum storage, dwa snapshoty Qdrant,
eksporty n8n, release/config/runtime inventory oraz chroniony staging roundtrip
KB. Efemeryczne pliki eksportu n8n zostały objęte istniejącym `finally`; nie
wykonywano workflow i nie odszyfrowywano credentials.

Nie było restartu lub odtworzenia kontenera produkcyjnego, zapisu biznesowego
SQL, zmiany DB head, upsert/delete/reindex Qdrant, model call, pracy kolejki,
pełnego drill ani escrow. Po operacji backend/gateway HTTP `200`, DB head
niezmieniony, Preparation queued `15`, Advanced queued `16`, aktywne prace `0`,
Ollama residency `0`.

Poprawka nie została wdrożona do harmonogramów. Trzy aktywne zadania backupu
nadal uruchamiają `C:\ai-lab-core\operations\hardening\run-backup-schedule.ps1`
i istniejący backend/Supervisor; wyłączone zadanie Daily Backup również wskazuje
`C:\ai-lab-core\operations\hardening\backup-production.ps1`. Te pliki różnią
się hashem od recovery. Rollout A3 do scheduled backupów wymaga osobnej zgody.

## Dowody lokalne

Chroniony root:
`C:\ai-lab-core-staging\recovery\R03_A3_KB_SOURCE_CAPTURE`.
Dziedziczenie ACL rootu jest wyłączone, obowiązują trzy jawne reguły. Raw logi
i inventory z nazwami plików firmy pozostają `LOCAL_ONLY`. Zanonimizowany indeks
hashy: `docs/recovery/R03_A3_LOCAL_EVIDENCE_MANIFEST.csv`.

Następny bezpieczny krok: odbiór A3 przez właściciela, a następnie osobna zgoda
wskazująca manifest `8F20A784...` na pełny izolowany drill. Escrow i późniejszy
cleanup pozostają oddzielnymi decyzjami.
