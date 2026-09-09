# R04-20260909T233459Z-A2-WEBFIRST-HANDOFF

- UTC wykonania: `2026-09-09T22:37:59Z`–`2026-09-09T23:34:59Z`
  (`2026-09-10` Europe/Warsaw).
- Branch/worktree: `recovery/next-stabil-repair-completion` /
  `C:\ai-lab-core-recovery`.
- Parent dokumentacji: `a6e8f7f50a843c26334bff90440905e00f163d61`.
- Code under test: `f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99`.
- Poprzedni checkpoint:
  `docs/recovery/checkpoints/20260909T223759Z-R04-A2-WEBFIRST-START.md`.

## Wykonane

1. Zapisano decyzję D-17: Web-first dla wspólnego API/logiki; Android runtime
   `DEFERRED_BY_OWNER / NOT_TESTED`. Zachowany APK nie był uruchamiany,
   instalowany ani przebudowywany.
2. Preflight potwierdził recovery local/remote na oczekiwanym parent, main i
   rescue bez driftu, oryginalny worktree 203 wpisy/staged 0, niezmieniony
   source archive oraz 316 tracked plików Web zgodnych z code-under-test.
3. Istniejący monitor zasobów miał potwierdzoną wadę harnessu PowerShell 5.1:
   literalne `\"` w argumentach Docker i niewłaściwe klucze etykiet
   `next.stabil.*`. Minimalna poprawka nie zmieniła progów. Parser = PASS,
   3 realne próbki = PASS; błędny ID/owner/run = 3 bezpieczne odmowy.
4. Wznowiono wyłącznie trzy pełnym ID zweryfikowane kontenery A2, bez migracji
   i seeda. DB/user/head, dwa syntetyczne rekordy, dokument, flagi izolacji,
   `/health` i `/version` przeszły kontrolę.
5. Jeden realny przebieg browsera wykonał W-01–W-05. W-01, W-03 i W-04 = PASS.
   W-02 zachował UI action oraz plik 204 B/SHA `C0EBC642...`, ale lokalny
   `file://` został zablokowany przez politykę przeglądarki; widoczna treść
   pozostaje `WAITING_OWNER_VISUAL_EVIDENCE`, nie product FAIL.
6. W-03 wykonał dokładnie jedną mutację pola syntetycznego z preimage
   `R04-A2-UI-MUTATION-ONE` na `R04-A2-WEBFIRST-0910-ONE`. Log ma 1/1 udane
   żądanie mutujące; read-only DB ma 1 primary row, 1 marker row, 2 klientów i
   1 dokument.
7. W-05 wykonał dokładnie jeden stop/start zweryfikowanego backendu. Web pokazał
   właściwy komunikat, po retry odzyskał listę i zachował marker bez duplikatu.
   `LateInitializationError` nie odtworzył się teraz, lecz historyczny
   `R04-A2-UI06` pozostaje `KNOWN_DEFECT_OPEN_R16` do zaakceptowanej naprawy.
8. Monitor zebrał 203/203 PASS: minimum Windows available `5.875 GiB`, commit
   reserve `35.257 GiB`, pool available `13.641 GiB`, swap max `1.9 MiB`.
9. Zamknięto własne karty i Web, zatrzymano trzy kontenery A2, usunięto jedyny
   telemetry container po kontroli ID/owner/run; porty `18004/18005` wolne.
   Zachowano DB volume, storage, download, APK, cache i dowody `LOCAL_ONLY`.

## Status i skutki

- `R04 A2 WEB_EVIDENCE_READY_FOR_REVIEW / TEST_ONLY`.
- `WEB_SMOKE_PARTIAL / KNOWN_UI_DEFECT_OPEN_R16`.
- `ANDROID_RUNTIME_DEFERRED_BY_OWNER / NOT_TESTED`.
- R04 pozostaje `IN_PROGRESS`; R03 pozostaje
  `WAITING_APPROVAL / WAITING_ESCROW_DECISION`.
- D-15/D-16, 9B, embedding, Assistant, KB, Vision i Temporary Chat: `NOT_RUN`.
- Trwały skutek danych: dokładnie jedna mutacja w syntetycznej DB. Produkcja,
  main/rescue, backup, escrow, Qdrant, Gmail, modele i kolejki: 0 działań.
- Pakiet 3 screenshotów `LOCAL_ONLY`:
  `web-first-20260909T223759Z/R04_A2_WEBFIRST_SAFE_SCREENSHOTS_20260909T223759Z.zip`,
  `100983 B`, SHA-256 `1A679F4B6F439FA475194702FA3AE8161D61A1D9C6BBD9074D775F4FD47A5E79`.

## Następny bezpieczny krok

Odbiór właściciela ograniczonego wyniku WEB-FIRST i osobna decyzja o małej
naprawie/regresji `R04-A2-UI06` w istniejącym zakresie R16. Nie uruchamiać
Androida, modeli, kolejnego podetapu R04 ani R05 bez nowej zgody.
