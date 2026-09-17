# Checkpoint R04 / D-21 / P3 — rollback tool provenance

- UTC: `2026-09-17T10:19:53Z`
- start local/tracking: `d64062261d0ff76ae5a9152e1e41803116d35692`
- capture/drill entry and tool-root commit:
  `e3f2125883420a12c8721c5ba597203dcf403add`
- immutable point: `E:\ai-lab-backup\20260917T082022Z`
- immutable manifest SHA-256:
  `2759D684710FB857DBCD0D985B5C480857122E3B139B9DDC362BFF4903895597`
- result: `ROLLBACK_TOOL_PROVENANCE_RECONCILED / EVIDENCE_READY_FOR_REVIEW`
- previously executed data drill result preserved:
  `CAPTURE_AND_ISOLATED_DATA_RESTORE_PASS / VERIFIED_LINKS_IN_TESTED_SCOPE`

## Rozstrzygnięcie

1. Entry HEAD i evidence HEAD mają niezmienione kanoniczne bloby:
   `5b1cfeee2d99f453ac45333cede492f0e60a0487` (writer),
   `44caeaa9b2d7064e4fdb84a46706afb1ba14fd3c` (reader),
   `b35e702ee9ecc1efa37a386b5208b6f264399800` (Qdrant helper) oraz
   `7f2dc8665f4ba88f686c7465c5d2054a147e09de` (tool manifest).
2. Wcześniej wpisane „bloby” oraz commit `9e7df257...` nie rozwiązują się jako
   lokalne obiekty. Poprawny ostatni commit writer/reader/tool manifestu to
   `9e7df2068e1138fbbb5ca2e213c13efffe4c0945`; jest przodkiem entry HEAD.
   Qdrant helper ostatnio zmienił
   `228b4898010d4bb805ec593316e338326301dcdf`.
3. `text=auto` plus systemowe `core.autocrlf=true` wyjaśniają różnicę
   surowych CRLF writer/reader od kanonicznych LF blobów. Błędne wartości z
   raportu nie są jednak raw-blob IDs: klasyfikacja to
   `REPORT_TRANSCRIPTION_ERROR`, nie inne źródło wykonania.
4. Historyczne wyjścia capture, ValidateOnly i obu Qdrant proofów, immutable
   `tool_source_head=e3f212588...`, entry tool manifest z raw SHA-256 oraz brak
   zmian ścieżek entry→evidence wiążą wykonanie z recovery tool rootem. Capture
   manifest nie ma osobnego per-invocation SHA-256 każdego skryptu; ta granica
   raw representation pozostaje jawna.

## Odstępstwa zachowane bez retroaktywnego PASS

- `PROCEDURAL_DEVIATION_OWNER_RUN_LABELS_MISSING`: alternatywna tożsamość
  zasobów opiera się na pełnych ID, nazwach, obrazach, mountach, internal
  networks, zero host ports i tym samym chronionym resource manifest; cleanup
  `5/3/3`, remaining `0/0/0`.
- `UNINTENDED_ALPINE_IMAGE_PULL`: krótkotrwały kontener pomiarowy `--rm`
  faktycznie użył `alpine:3.20`; nie był usługą produktu. Dokładne argumenty,
  exit/stdout oraz mount/network nie zostały zachowane i pozostają `UNKNOWN`.
  Obraz został usunięty, remaining `0`; zakaz pull był naruszony.
- `POSTGRES_TMPFS_COPY_NOT_PRESENT`: pierwsze dostarczenie pliku nie doszło do
  `pg_restore`; po skopiowaniu dokładnego dumpa do świeżego volume wykonano
  jeden restore, exit `0`.

W bieżącej sesji korekty provenance nie wykonano żadnej nowej operacji
Docker/WSL/API/SQL/Task Scheduler, backupu, restore, aplikacji, workera ani
cleanupu. Historyczny capture i izolowany drill opisane powyżej pozostają
wykonanymi skutkami poprzedniej sesji. Nie zmieniono immutable backup manifestu,
logów, `drill-summary.safe.json`, lokalnego indeksu, aplikacji, narzędzi, danych,
junctionu, harmonogramów ani oryginalnego worktree.

Następny bezpieczny krok: review dokładnie tego punktu po korekcie provenance;
ewentualny ograniczony odbiór punktu i okno source-switch wymagają osobnej
decyzji. Cutover i produkcyjny manifest pozostają nieautoryzowane.
