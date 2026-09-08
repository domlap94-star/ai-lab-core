# R03 A4 — rozpoczęcie izolowanej operacji

- Checkpoint ID: `R03-20260908T233516Z-A4-OPERATION-START`
- UTC: `2026-09-08T23:35:16Z`
- Repo / branch / worktree: `domlap94-star/ai-lab-core` /
  `recovery/next-stabil-repair-completion` / `C:\ai-lab-core-recovery`
- Bieżący local HEAD: `7bf2a1ae16ab3e0ee665c94bf97cf3aeab38b231`
- Status podetapu: `PREFLIGHT_PASS / OPERATION_START`
- Status całego R03: `WAITING_APPROVAL`

## Ponowny preflight po oknie harmonogramu

- Zarządzane zadanie `NEXT Stabil - Backup - 3` uruchomiło się naturalnie o
  `2026-09-08T23:30:01Z` i zakończyło wynikiem `0`. Nie było anulowane ani
  zmieniane przez A4. Następny termin to `2026-09-09T23:30:00Z`.
- Bounded read-only DB: head `followup_assistant_chat_history_20260829`, aktywne
  Assistant/Preparation/Analysis/Backup/Restore `0/0/0/0/0`, Preparation queued
  `15`, Advanced queued `16`. Liczba completed backup runs zmieniła się `40→41`
  wskutek powyższego harmonogramu, nie wskutek A4.
- Recovery worktree jest clean; wejściowy manifest nadal ma SHA-256
  `8F20A7845473097EE74019966583EC3F121139C4B562265F9A7391FAFAF6BE4B`.
  Exact-name root, kontenery, wolumeny i sieci A4 nadal nie istnieją.
- Produkcyjne ID kontenerów są niezmienione, Ollama residency `0`, snapshoty
  Qdrant `8/2`. Obrazy przypięte i tool manifest `1.2.0` są zgodne.
- Wolne: C `629 112 582 144` B, E `776 057 212 928` B, właściwy filesystem
  Docker named volumes `980 507 533 312` B. Bramka 40 GiB i estymacja
  `11 118 564 814` B są spełnione.

## Dokładne cele zatwierdzonej pojedynczej operacji

- Root: `C:\ai-lab-core-staging\recovery\R03_DRILL_A4_20260908T210559Z`
- Owner/prefix: `next-stabil-r03-a1-drill-20260908-a4`
- PostgreSQL: kontener `next-stabil-r03-a1-drill-20260908-a4-postgres`,
  wolumen `next-stabil-r03-a1-drill-20260908-a4-postgres-data`, sieć
  `next-stabil-r03-a1-drill-20260908-a4-network`, baza
  `ai_lab_restore_test_r03_20260908_a4`.
- Qdrant operation IDs: `next-stabil-r03-a1-drill-20260908-a4-qdrant-1` oraz
  `next-stabil-r03-a1-drill-20260908-a4-qdrant-2`; helper dodaje wyłącznie
  suffixy `-server`, `-client`, `-data`, `-network`.

Pierwsza mutacja nastąpi dopiero po opublikowaniu tego checkpointu. Jeden
następny bezpieczny krok: utworzyć root z restrykcyjnym ACL, zapisać lokalny
resource manifest i utworzyć dokładnie powyższe izolowane cele PostgreSQL.

STOP przy kolizji, niespełnionej izolacji lub błędzie etapu. Bez ponowienia
restore do użytego celu, bez cleanupu sukcesu, escrow, rollout i R04–R24.

Poprzedni checkpoint: `R03-20260908T232307Z-A4-PREFLIGHT-WINDOW`.
