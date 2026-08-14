# AI-Lab / NEXT Stabil — Codex Master Execution

Stan bazowy: 2026-08-14, commit wejściowy `5700681`. Dokument rozbija
`AI_LAB_MASTER_PLAN.txt` na małe checkpointy. Statusy wynikają z kodu, testów i
odczytowego audytu bazy, nie ze starych checkboxów.

## Reconciliation stanu

| Obszar | Stan | Dowód / luka |
|---|---|---|
| Auth, role, wymuszona zmiana hasła | DONE | JWT, `User.role`, `must_change_password`, admin API i Flutter flow; migracja `authv1_20260813` jest aktualnym headem. |
| Flutter Windows / Android / Web | DONE | katalogi platform i działający frontend; analyze oraz 10 testów PASS. iOS/macOS są świadomie nieobecne. Linux istnieje, lecz nie jest celem produkcyjnym. |
| Release channel / self-update | DONE | stable manifest 1.0.1+4, SHA-256, testy decyzji/hash, instalacja Windows/Android. Publikacja pozostaje human-gated. |
| Supervisor i gateway split | DONE | bindy 8787/8788/8789 na loopback; public gateway jawnie odrzuca `/control`. |
| Document Intelligence | DONE | centralny pipeline, pages/assets/OCR/Office/archive oraz testy regresyjne. Batch 30 istnieje; pełny cel jakościowy pozostaje częściowo otwarty. |
| Chunking / embeddings / Qdrant / semantic retrieval | DONE | migracja chunk 2.0, embedding service, Qdrant store i realny baseline Hit@3/5 3/3. |
| RAG / citations / evidence | DONE | chroniony `/api/v1/ai/rag`; test 401/200/422 i claim→evidence→source PASS. |
| CRM frontend | PARTIAL | klient list/details/create/edit istnieją; lista pobiera maks. 100, documents to placeholder, Client 360 ma placeholder panels. |
| Candidate pipeline | DONE/PARTIAL | review/promotion, duplicate protection i read-only identity projection działają; trwały multi-contact i quality cleanup są otwarte. |
| Document read API/UI | NOT STARTED | istnieje tylko import-key upload; brak auth list/search/filter/download, UI jest placeholderem. |
| Dane CRM | QUALITY DEBT | 3194 aktywnych; 463 email-name, 284 phone-name, 1 file-name, 3193 bez structured address, 809 mail transcripts w notes. |

## Problemy źródłowe wykryte w CHUNK 0

- Dwa katalogi źródłowe Flutter były nieśledzone mimo importowania przez
  śledzony kod: `client_candidates/data` i `system_status/data`.
- Workspace zawiera nieśledzone backupy `*.corrupted_backup*`, plik
  `*.before_phase1p_r`, katalogi `releases/`, `staging/` i liczne raporty.
  Nie należą do checkpointu i wymagają osobnej decyzji porządkowej.
- W `backend/app/services` znajdują się śledzone pliki `*.before_rfc822`; to
  historyczne kopie obok kodu produkcyjnego, do usunięcia tylko w osobnym,
  zatwierdzonym hygiene chunku.
- `test_import_candidate_name_quality_protection.py` wykonuje transakcje z
  `commit` na skonfigurowanej bazie. W baseline wartość kontrolna pozostała
  niezmieniona, ale test należy przenieść na izolowaną bazę/rollback fixture.
- Brak jednolitego runnera testów backendu; katalog zawiera skrypty E2E,
  audyty i potencjalnie mutujące narzędzia obok testów.
- Obrazy Compose używają pływających tagów (`latest`/`main`) w części usług;
  wersje należy przypiąć w production hardening.

## Chunks

### 0. Baseline / safety / repo hygiene — DONE

- Cel biznesowy: odtwarzalny, bezpieczny punkt startowy i prawdziwa mapa prac.
- Zależności: działający Docker Desktop, repo `main`, Flutter SDK.
- Aktualny stan i zakres: audyt repo/Git/ignore/usług/DB; reconciliation;
  baseline backend/Flutter; śledzenie brakujących źródeł; dokumenty operacyjne.
- Pliki: `AGENTS.md`, `CODEX_MASTER_EXECUTION.md`,
  `AI_LAB_MASTER_PLAN.txt` oraz trzy brakujące pliki Dart.
- Migracje: brak. Ryzyka: istniejące artefakty untracked; nie są modyfikowane.
- Dane produkcyjne: tylko odczyt. Test identity wykonał commit tej samej wartości
  kontrolnej — bez zmiany biznesowej, ale jest to wskazane ryzyko testowe.
- Testy: Compose config/ps, CRM audit, Alembic current/heads, compileall,
  candidate API, projection, RAG API, retrieval baseline, Flutter analyze/test,
  `git diff --check`.
- Acceptance: liczby audytu potwierdzone; schema na head; baseline PASS; brak
  ignorowanego kodu; wymagane źródła śledzone; public/private boundary bez zmian.
- Commit: `Establish verified execution baseline`.

### 1. Client list contract — TODO

- Cel biznesowy: użytkownik widzi i przeszukuje wszystkie 3194+ klientów.
- Zależności: chunk 0.
- Zakres: paginowana odpowiedź `{items,total,skip,limit}`; count z tym samym
  filtrem; deterministyczne sortowanie; globalne server-side search; filtry typu
  i branży; kompatybilne przejście Flutter; stan strony i wybór „wszyscy”.
- Pliki: client repository/service/schema/router; Flutter client data/domain,
  controller i page; testy backend/Flutter.
- Migracje: brak. Ryzyka: zmiana kontraktu istniejącego API; potrzebny model
  kompatybilności. Dane produkcyjne: odczyt.
- Testy: unit count/search/filter/order; API 401, 200, granice paginacji i total;
  Flutter repository/controller/widget; analyze/test.
- Acceptance: total=3194 dla pustego filtra w momencie audytu; rekord spoza
  pierwszych 100 jest znajdowalny; zmiana stron nie duplikuje/nie gubi wyników;
  filtry i sortowanie zachowane.
- Commit: `Add paginated full-database client list`.

### 2. Document read API — TODO

- Cel: bezpieczny dostęp do 5899+ dokumentów. Zależności: 0.
- Zakres/pliki: auth list/detail/search/filter/count oraz kontrolowany download
  w documents router/schema/repository/service i testach; bez ujawniania
  `storage_path`. Migracje: brak przewidywanych.
- Ryzyka: path traversal, MIME/content-disposition, duże pliki. Dane: odczyt.
- Testy/acceptance: 401/403/404, filtry client/link/source/match, total i
  pagination, traversal rejected, download właściwego pliku.
- Commit: `Add authenticated document read API`.

### 3. Document repository UI — TODO

- Cel: używalne repozytorium dokumentów. Zależności: 2.
- Zakres/pliki: Flutter documents data/domain/application/page, paginacja,
  filtry, responsive layout, open/download. Migracje: brak.
- Ryzyka: pamięć/mobile download. Dane: odczyt lokalny + jawny download.
- Testy/acceptance: repository/widget tests, analyze/test; pełny total, search,
  filters i open działają na Windows/Web/Android.
- Commit: `Build document repository UI`.

### 4. Client 360 documents — TODO

- Cel: prawdziwe dokumenty klienta. Zależności: 2–3.
- Zakres: zastąpić placeholder panelem lazy/collapsible po `client_id`, z
  source/match/open. Pliki: client details/workspace + providers/tests.
- Migracje: brak. Ryzyko: ciężki ekran. Dane: odczyt.
- Acceptance: klient pokazuje tylko swoje dokumenty i poprawny total.
- Commit: `Connect client 360 documents`.

### 5. Client 360 email history — TODO

- Cel: komunikacja z provenance zamiast `notes`. Zależności: 0, candidate source.
- Zakres: read API i zwinięta lazy lista Gmail: direction/date/from/to/subject/
  current body/attachments/evidence. Migracje: możliwe tylko gdy payload nie
  wystarcza. Ryzyko: quoted-thread leakage i PII. Dane: odczyt.
- Acceptance: historia pochodzi z CandidateSource, ma paginację i provenance;
  notes nie są usuwane. Commit: `Add sourced client email history`.

### 6. Client identity quality dry-run — TODO

- Cel: odzyskać tożsamość bez automatycznego zgadywania. Zależności: 5.
- Zakres: read-only projection dla 463/284/1, provenance-ranked old→new,
  confidence/conflicts i reguły zapobiegające regresji. Migracje: brak.
- Ryzyko/dane: DRY-RUN, późniejszy apply ma HUMAN GATE.
- Acceptance: pełny raport i zero writes; testy regresji promotion/import.
- Commit: `Add client identity cleanup dry run`.

### 7. Contact and address model — TODO

- Cel: wiele kontaktów/emaili/telefonów/adresów z provenance. Zależności: 6.
- Zakres: modele/API/UI, Alembic additive migrations, read-only backfill plan.
- Ryzyko: konflikty i kompatybilność scalar fields. Dane: DRY-RUN; backfill gate.
- Acceptance: CRUD i provenance testowane, downgrade/rollback migracji, audit.
- Commit: `Add provenance-aware client contact model`.

### 8. Document-client matching workspace — TODO

- Cel: rozstrzygnąć 99 unmatched i 161 candidate-only. Zależności: 2–4.
- Zakres: suggestions/confidence, manual link/unlink/move, audit trail, UI.
- Migracje: audit model prawdopodobny. Ryzyko: błędne przypisanie. Dane: jawne
  pojedyncze mutacje; medium confidence wymaga approval.
- Acceptance: każda zmiana audytowalna i odwracalna. Commit: `Add document matching workspace`.

### 9. Upload, photos, mobile field data — TODO

- Cel: bezpieczny terenowy intake. Zależności: 2, 7–8.
- Zakres: user-auth upload/multi/camera, captured/GPS/accuracy/link/session UI.
- Migracje: możliwe dla sesji/metadata. Ryzyko: privacy, rozmiar, offline retry.
- Dane: jawne uploady użytkownika. Acceptance: Android capture/upload i
  idempotent retry. Commit: `Add mobile field document capture`.

### 10. Projects / realizations / inspections / timeline — TODO

- Cel: klient→realizacja→lokalizacja→inspekcja→media. Zależności: 7,9.
- Zakres: osobne additive model/API/UI subchunki. Migracje: tak.
- Ryzyko: szeroki model domeny. Dane: nowe jawne rekordy, backfill gated.
- Acceptance: każdy vertical slice ma CRUD/auth/audit/testy.
- Commit: osobny per encja, zaczynając `Add project foundation`.

### 11. Global hybrid search — TODO

- Cel: exact/Postgres/semantic/hybrid nad klientami i dokumentami.
- Zależności: 2, istniejący semantic retrieval.
- Zakres: query/filter/ranking API + Flutter; bez duplikacji Qdrant/RAG.
- Migracje: ewentualne indeksy. Ryzyko: ranking/latency. Dane: odczyt.
- Acceptance: benchmark exact + semantic, source links i open page/document.
- Commit: `Add global hybrid search`.

### 12. AI client knowledge — TODO

- Cel: grounded „co wiemy o kliencie?”. Zależności: 4–5,10–11.
- Zakres: client-scoped retrieval, summary/timeline/open topics/actions z
  citations. Migracje: brak początkowo. Ryzyko: cross-client leakage.
- Acceptance: strict client filter, no-source safety, evidence mapping.
- Commit: `Add grounded client knowledge summary`.

### 13. Business assistant — TODO

- Cel: drafty ofert/umów/maili z approval. Zależności: 10–12.
- Zakres: templates, versions, approval states. Migracje: tak.
- Ryzyko: wysłanie/zaakceptowanie bez zgody. Dane: drafts; finalizacja gated.
- Acceptance: provenance/versioning/audit i brak automatycznej publikacji.
- Commit: `Add approval-gated business drafts`.

### 14. Technical AI — TODO

- Cel: deterministyczne, weryfikowalne obliczenia. Zależności: 11–13.
- Zakres: units/formulas/assumptions/intermediate results/source standards.
- Migracje: możliwe. Ryzyko: bezpieczeństwo inżynierskie. Dane: nowe analizy.
- Acceptance: golden calculations, dimensional validation, verification state.
- Commit: `Add deterministic calculation engine foundation`.

### 15. Vision / multimodal — TODO

- Cel: analiza stron, assetów i zdjęć. Zależności: 9,11,14.
- Zakres: OCR/vision/image embeddings/multimodal retrieval/before-after.
- Migracje: wersje analizy/embeddingu możliwe. Ryzyko: koszt i false positives.
- Acceptance: versioned outputs, source asset/page, benchmark i human review.
- Commit: `Add versioned multimodal retrieval foundation`.

### 16. Agent — TODO

- Cel: bezpieczne narzędzia najpierw read, potem draft/write. Zależności: 12–15.
- Zakres: permissions, tool registry, audit, approval gates. Migracje: audit log.
- Ryzyko: nieautoryzowane działania. Dane: read-only w pierwszym subchunku.
- Acceptance: deny-by-default, tenant/client scoping, pełny audit, high-risk gate.
- Commit: `Add read-only agent tool framework`.

### 17. Production hardening — TODO

- Cel: odtwarzalna i monitorowana produkcja. Zależności: wszystkie releasowane
  chunki; prace można dzielić wcześniej.
- Zakres: pin images, backup/restore drill, retention, monitoring/audit/security,
  migration rollback, compatibility i forced-update verification.
- Migracje: zależne; destructive wymagają gate. Ryzyko: downtime/data loss.
- Dane: backup/restore na izolowanym celu; produkcja bez mutacji bez approval.
- Acceptance: udokumentowany restore, alerts, version matrix i rollback drill.
- Commit: osobne checkpointy, zaczynając `Pin production service versions`.
