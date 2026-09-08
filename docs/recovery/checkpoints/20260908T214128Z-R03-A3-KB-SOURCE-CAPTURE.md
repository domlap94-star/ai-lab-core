# R03 A3 — KB source capture handoff

- Checkpoint ID: `R03-20260908T214128Z-A3-KB-SOURCE-CAPTURE`
- UTC: `2026-09-08T21:41:28Z`
- Repo / branch / worktree: `domlap94-star/ai-lab-core` /
  `recovery/next-stabil-repair-completion` / `C:\ai-lab-core-recovery`
- Start A3: `afedb4d1025feb8bd287272c36935ce9feb4f877`
- SOURCE_PASS: `9e7df2068e1138fbbb5ca2e213c13efffe4c0945`
- Capture execution HEAD: `af812c0b2bdea97aa35686f2b65a44111bd18840`
- Status podetapu: `KB_SOURCE_CAPTURE_READY_FOR_REVIEW /
  WAITING_NEW_POINT_DRILL_APPROVAL`
- Status całego R03: `WAITING_APPROVAL`

## Zakończone

- Właściciel przyjął dowód A2 na `afedb4d...` z ograniczeniem źródeł KB
  `0/10`; A3 nie zmienia historii starego punktu.
- Fail-before rzeczywistego writera: exit `1` na braku domeny KB.
- Poprawka writer/reader/runbook i testy zostały opublikowane jako SOURCE_PASS.
- Końcowe testy opublikowanego source: `58/58`, `15/15`, trzy suite Node
  `PASS/PASS/PASS`; wszystkie exit `0`.
- Wykonano dokładnie jeden `CaptureOnly` do
  `E:\ai-lab-backup\20260908T210559Z`.
- Nowy manifest `NEXT_STABIL_BACKUP_V2`, SHA-256
  `8F20A7845473097EE74019966583EC3F121139C4B562265F9A7391FAFAF6BE4B`:
  9/9 artefaktów, `8 232 583 217` B, obie kolekcje, pięć domen storage,
  capture/scope/provenance `COMPLETE/COMPLETE/RECORDED`, consistency
  `COMPONENT_WINDOWS_RECORDED_NON_TRANSACTIONAL`, restore `NOT_RUN`.
- Ograniczony roundtrip wyłącznie KB: expected/captured/extracted/hash matched
  `10/10/10/10`, missing/mismatch `0/0`, unsafe/link entries `0/0`.
- Niezależny `ValidateOnly / Full` nowego punktu: exit `0`; pełny drill nadal
  `NOT_RUN_WAITING_APPROVAL`.
- Historyczny punkt `20260908T135012Z` przeszedł walidację 9/9, lecz reader
  uczciwie raportuje brak nowego kontraktu: `storage_coverage=NOT_RECORDED`,
  `capture_complete=false`, `full_eligible=false`. Jego manifest pozostał
  `1195AE5BE68CF589D9B9231C85B0BE678C87117FD471034417B9DC8C5620FD57`.

## Skutki i zachowanie

- Rzeczywiste skutki: jeden nowy backup, dwa nowe snapshoty Qdrant, eksporty
  n8n, runtime inventory oraz chroniony staging 10 plików KB.
- Qdrant live: punkty `57/157` bez zmian; snapshot counts `7/1 -> 8/2`.
- Backend/gateway HTTP `200`; DB head
  `followup_assistant_chat_history_20260829`; Preparation queued `15`,
  Advanced queued `16`, aktywne prace `0`, Ollama residency `0`.
- Produkcyjne kontenery nie zostały odtworzone ani zrestartowane. Nie wykonano
  biznesowych zapisów SQL, upsert/delete/reindex, modeli, queue drain, restore,
  escrow ani pełnego drill.
- Zasoby A2 są zachowane: 5/5 kontenerów `exited`, 3 wolumeny, 3 internal
  networks i root A2 bez cleanupu.
- Oryginalny worktree: `203/203`, mismatch `0`, staged `0`, HEAD `729506...`.
- Zaplanowane backupy nadal wskazują starą ścieżkę `C:\ai-lab-core`; rollout
  poprawki A3 nie został wykonany i wymaga osobnej zgody.

## Dowody i STOP

Pełny sanitizowany opis: `docs/recovery/R03_A3_KB_SOURCE_COVERAGE_EVIDENCE.md`.
Hashy dowodów LOCAL_ONLY:
`docs/recovery/R03_A3_LOCAL_EVIDENCE_MANIFEST.csv`. Chroniony root:
`C:\ai-lab-core-staging\recovery\R03_A3_KB_SOURCE_CAPTURE`.

Następny bezpieczny krok: odbiór A3 przez właściciela; następnie osobna zgoda
na pełny izolowany drill dokładnie manifestu `8F20A784...`. Escrow i cleanup
pozostają osobnymi decyzjami. STOP przed pełnym drill, escrow, rollout,
cleanupem, deploymentem i R04–R24.

Poprzedni checkpoint: `R03-20260908T210559Z-A3-CAPTURE-GATE`.
