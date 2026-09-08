# R03 A4 — preflight i oczekiwanie na okno

- Checkpoint ID: `R03-20260908T232307Z-A4-PREFLIGHT-WINDOW`
- UTC: `2026-09-08T23:23:07Z`
- Repo / branch / worktree: `domlap94-star/ai-lab-core` /
  `recovery/next-stabil-repair-completion` / `C:\ai-lab-core-recovery`
- Start local/remote: `fed9b9423269047e116715edb4318033b37cc6c4`
- Decyzja właściciela: R03-A3 `ACCEPTED` na `fed9b942...`; dozwolony jest
  wyłącznie jeden izolowany drill R03-A4 punktu `20260908T210559Z`.
- Status podetapu: `PREFLIGHT / WAITING_OPERATION_WINDOW`
- Status całego R03: `WAITING_APPROVAL`

## Zakończone kontrole

- Recovery worktree był clean, local/remote zgodne; main `483f9bf8...` i
  rescue `5cd8f86e...` bez zmian. Nie stwierdzono drugiego wykonawcy A4.
- Rzeczywisty `restore-checkpoint.ps1 -ValidateOnly -Mode Full`: exit `0`,
  manifest `8F20A784...F6BE4B`, 9/9 artefaktów, `8 232 583 217` B, pięć
  domen storage, obie kolekcje i KB `10/10`; restore nadal `NOT_RUN`.
- Tool manifest `1.2.0`: cztery helpery mają zgodne bajty i SHA-256.
- Obrazy PostgreSQL, Qdrant i klienta istnieją lokalnie pod dokładnie
  przypiętymi digest/image IDs; nie wykonano pull ani substytucji.
- Cel root, 5 kontenerów, 3 wolumeny i 3 sieci A4 nie istnieją.
- Pojemność: C `629 124 489 216` B, E `776 057 212 928` B, Docker named-volume
  filesystem `980 507 533 312` B wolne; estymacja A4 co najmniej
  `11 118 564 814` B. Bramka 40 GiB jest spełniona z zapasem.
- Oryginalny dirty worktree: `203/203`, mismatch `0`, staged `0`; A2 i A3
  istnieją i pozostały niezmienione. Stary i nowy manifest zachowują hashe
  `1195AE5B...` i `8F20A784...`.
- Produkcja: backend/gateway HTTP `200`, DB head
  `followup_assistant_chat_history_20260829`, Preparation queued `15`,
  Advanced queued `16`, aktywne prace `0`, Ollama residency `0`, Qdrant
  `57/157`, snapshot counts `8/2`.

## Bramka operacyjna

O `2026-09-08T23:22:15Z` zadanie `NEXT Stabil - Backup - 3` było `Ready` z
najbliższym startem `2026-09-08T23:30:00Z`. Nie rozpoczyna się godzinnego drill
na osiem minut przed zarządzanym backupem. Nie anulowano zadania i nie
zatrzymano produkcji. Nie utworzono żadnego celu A4 ani danych drill.

Jeden następny bezpieczny krok: po naturalnym zakończeniu zadania ponownie
sprawdzić brak aktywnego Backup/Restore/Analysis, nowy termin harmonogramu,
hashe wejścia oraz nieistnienie dokładnych celów A4. Tylko przy PASS utworzyć
chroniony root i wykonać pojedynczą sekwencję operacyjną.

STOP przy aktywnej pracy lub kolizji. Bez nowego backupu, produkcyjnego restore,
escrow, rollout, cleanupu, zmian narzędzi i R04–R24.

Poprzedni checkpoint: `R03-20260908T214128Z-A3-KB-SOURCE-CAPTURE`.
