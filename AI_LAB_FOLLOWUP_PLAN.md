# NEXT STABIL / AI LAB — POST-PROJECT FOLLOW-UP PLAN

Status: **AKTYWNY PLAN ROZWOJU PO FINAL SYSTEM AUDIT**

## Źródła i punkt bazowy

Źródła planu:

- `FINAL_SYSTEM_AUDIT.md`,
- decyzje właściciela produktu,
- residual items z końcowego audytu,
- nowe wymagania UX, CRM, Email, Calendar, Knowledge Base i AI.

Punkt bazowy:

- release: `NEXT Stabil 1.0.2+21`,
- HEAD: `a16e26eafce1a149cef2cf5a2edc27a807a45f17`,
- DB: `chunk16audit_20260819`.

Zakończony `AI_LAB_MASTER_PLAN.txt` pozostaje historycznym masterplanem głównej
implementacji. `FINAL_SYSTEM_AUDIT.md` jest kanonicznym audytem stanu bazowego.
Ten dokument jest od teraz jedyną aktywną roadmapą kolejności dalszych prac.

## Global execution rules

Każdy FOLLOW-UP CHUNK:

1. Zaczyna się od:
   - Git pre-flight,
   - audytu istniejącej implementacji,
   - live DB/runtime audit,
   - ustalenia, czy migracja jest potrzebna.
2. Kończy się:
   - focused tests,
   - odpowiednią pełną regresją,
   - Flutter analyze,
   - Flutter full tests, jeśli frontend był zmieniany,
   - data-safety report,
   - commit + push,
   - osobnym release promptem, jeśli release jest potrzebny.
3. Bez osobnego approval nie może wykonywać:
   - destructive business writes,
   - historical cleanup,
   - Qdrant rebuild/backfill,
   - Qdrant upgrade,
   - zmian Tailscale/Funnel/Serve,
   - zmian firewall,
   - zmian public gateway,
   - credential rotation,
   - destructive retention,
   - arbitrary production cleanup.
4. Migracje przechodzą kolejno przez:
   - design,
   - isolated upgrade/downgrade,
   - report,
   - human gate,
   - apply.
5. Nowe automaty muszą być:
   - auditable,
   - idempotent,
   - bounded,
   - fail-closed dla write.
6. Zabronione polecenia/praktyki:
   - `git add .`,
   - `flutter clean`,
   - `docker system prune`,
   - `docker volume prune`.

Nie wolno po cichu przeskakiwać do późniejszego CHUNK-a. Każdy jawny gate
zatrzymuje pracę do czasu podania właściwego approval tokenu.

## Priority definitions

- **P0** — blocker albo realny problem bezpieczeństwa lub integralności danych.
- **P1** — wysoki priorytet produkcyjny.
- **P2** — istotne rozszerzenie lub zadanie operacyjne.
- **P3** — cleanup, optymalizacja albo R&D.

## [✓] FOLLOW-UP CHUNK 01 — DOCUMENT PROCESSING ANOMALIES — COMPLETE

**Priority: P1**

Audit findings:

- Document `1913` — stale `extracting`,
- Document `5626` — `failed`, invalid JSON text representation.

Cel pierwszego etapu: wyłącznie diagnoza read-only.

Sprawdzić source, historię statusu, storage, checksum, pages/assets,
OCR/render, dokładną przyczynę oraz inne rekordy o tym samym wzorcu.

Bez osobnego approval nie wykonywać retry, reset, delete ani rewrite.

Human gate: `FOLLOWUP_DOCUMENT_REMEDIATION_APPROVAL_REQUIRED`.

Diagnostic result (2026-08-19):

- Document `1913` has a valid 25-page PDF and 25 completed page renders, but no
  database pages. Processing was interrupted after the committed `extracting`
  transition and render completion, before extraction/OCR result persistence.
  No historical stale-processing recovery scan exists, by design.
- Document `5626` failed because EXIF GPS metadata contained non-finite `NaN`
  values rejected by PostgreSQL JSON. Current source already sanitizes this
  class of value (commit `f676b124`); read-only extraction of the unchanged file
  now passes strict JSON serialization.
- These are the only records matching their respective stale-extracting and
  JSON/`NaN` failure patterns.
- No schema migration or production write was performed. Both records require
  a checksum-gated, single-document, non-force retry under
  `FOLLOWUP_DOCUMENT_REMEDIATION_APPROVAL_REQUIRED`.

Evidence and remediation design:
`FOLLOWUP_CHUNK01_DOCUMENT_ANOMALY_DIAGNOSIS.md`.

Remediation result (2026-08-19):

- Human gate `FOLLOWUP_DOCUMENT_REMEDIATION_APPROVAL_REQUIRED` was granted.
- Stored size and SHA-256 were verified independently immediately before each
  retry.
- Documents `1913` and `5626` were processed sequentially through the existing
  production service with `force=False`; no bulk/history scan was used.
- Document `1913` finished `processed` with 25 unique pages and no error.
- Document `5626` finished `processed` with one page, strict JSON metadata,
  zero non-finite values, and no error.
- No duplicate page numbers or asset checksums were created. Source checksums
  remained unchanged.
- Vision jobs: `0`; Qdrant writes: `0`; assets remained unchanged.
- No automatic historical retry/recovery mechanism was added.

## [✓] FOLLOW-UP CHUNK 02 — CLIENT STATUS CONSISTENCY + DATE DISPLAY — COMPLETE

**Priority: P1**

Problemy:

- status klienta na liście i w szczegółach nie jest spójnie powiązany,
- data ma być wszędzie pokazana razem z rokiem,
- wynik wyszukiwania klienta ma pokazywać status.

Cel: jeden kanoniczny source statusu dla Clients list, Client Details, Search,
Global Search, Dashboard cards i AI source cards pokazujących Client.

Acceptance: status jest identyczny we wszystkich widokach, a daty zawierają
rok.

Human gate: brak przed audytem/source implementation; osobny release prompt,
jeżeli zmiana ma zostać wydana.

Completion record (2026-08-19):

- Root cause: Client list i Client Details pobierały workflow status osobnym
  endpointem i łączyły go przez procesowy singleton Fluttera. Po zapisie
  szczegóły i lista nie odświeżały tej samej projekcji, a Global Search nie
  zwracał statusu w ogóle. Business/Client AI miały dodatkowo własne
  interpretacje labeli.
- Canonical source: `client_workflow_statuses.status` wraz z
  `effective_date`; brak aktywnego rekordu oznacza `untouched`. Nowy wspólny
  `ClientWorkflowStatusProjectionService` zasila Client list/detail,
  compatibility endpoint, Global Search, Business Analytics, Client AI i
  read-only Agent tools.
- API zmieniono wyłącznie addytywnie: Client projection zawiera
  `workflow_status`, `workflow_status_label`, `workflow_effective_date`, a
  Global Search odpowiadające pola `client_workflow_*`. Legacy endpoint
  workflow statuses pozostaje dostępny.
- Flutter Client model korzysta bezpośrednio z projekcji serwera; usunięto
  niezależny `ClientWorkflowMemory`. Po zapisie statusu odświeżane są Client
  Details i lista, więc Back/re-fetch nie przywraca starego statusu. Clients
  Search, Global Search i istniejące Client cards pokazują status.
- Daty związane z klientem używają wspólnego formatera UI:
  `dd.MM.yyyy` lub `dd.MM.yyyy, HH:mm`; API nadal zwraca ISO i timestampy nie
  są trwale konwertowane.
- Tests: backend focused/regression `42/42 PASS`, dodatkowe kontrakty
  Client/Auth i rollback PASS, Client list contract E2E PASS; Flutter analyze
  PASS, focused status/search `21/21 PASS`, full Flutter `170/170 PASS`.
- Migration: NO. Production business writes: `0`. Qdrant writes: `0`.
  Vision jobs: `0`. Release: NOT PERFORMED.
- Implementation commit: `Unify client status and date presentation`.

## [✓] FOLLOW-UP CHUNK 03 — EDITABLE CLIENT ADDED DATE + SORTING — COMPLETE

**Priority: P1**

Cel: umożliwić edycję biznesowej daty dodania klienta.

Najpierw ustalić, czy `created_at` jest technicznym, immutable audit timestamp.
Jeśli tak, nie wolno go edytować. Wprowadzić osobne pole, np.
`client_added_at`, wraz z edycją, walidacją, sortowaniem ASC/DESC, filtrami i
auditem kto/kiedy zmienił.

Design audit 2026-08-19:

- `clients.created_at` jest technicznym, immutable timestampem z
  `TimestampMixin` i nie może być edytowany.
- `source_record_date` jest read-only projekcją daty źródłowej Google Sheets,
  a `workflow_effective_date` opisuje zmianę statusu; żadne z tych pól nie może
  przejąć semantyki ręcznie ustawianej daty dodania.
- Live schema nie ma odpowiedniego trwałego pola. Wymagana jest addytywna
  kolumna `clients.client_added_at DATE NULL`, bez server default i bez
  historycznego backfillu.
- Canonical fallback: `client_added_at → source_record_date → created_at.date()`.
  W audycie 1010 z 3237 aktywnych Clients miało datę źródłową, a 2227 bezpieczny
  fallback do niepustego `created_at`.
- Istniejący kompatybilny kontrakt `sort_order=newest|oldest` pozostaje i po
  implementacji będzie sortował po canonical effective added date z
  deterministycznym tie-breakiem po Client ID.
- Pełny projekt migracji, API, UI, rollbacku i testów:
  `FOLLOWUP_CHUNK03_CLIENT_ADDED_DATE_DESIGN.md`.
- Baseline verification: backend health PASS; source-date/sorting contract PASS;
  Client list pagination/search contract PASS; production writes `0`.
- Migration: REQUIRED, not created or applied. Implementation/UI: NOT STARTED.
- Design commit: `Design editable client added date`.

Completion record (2026-08-19):

- Human gate `FOLLOWUP_CLIENT_SCHEMA_MIGRATION_APPROVAL_REQUIRED` został
  udzielony i wykorzystany wyłącznie dla addytywnej kolumny
  `clients.client_added_at DATE NULL`.
- Migration `followup_clientdate_20260819` (parent
  `chunk16audit_20260819`) przeszła isolated upgrade, downgrade i re-upgrade,
  następnie została zastosowana na produkcji. Server default, index, trigger,
  backfill i rewrite: NO.
- Historyczne Clients z explicit `client_added_at`: `0`; Clients total po
  migracji: `3243`; `created_at` coverage: `3243/3243`.
- Canonical backend fallback:
  `client_added_at → source_record_date → created_at.date()`.
- Additive API zwraca `client_added_at` i `effective_added_date`; PATCH rozróżnia
  omitted, set i explicit NULL/clear. Daty przed 1900-01-01 oraz przyszłe są
  odrzucane.
- `sort_order=newest|oldest` pozostał kompatybilny; backend sortuje po effective
  date przed paginacją, z deterministycznym tie-breakiem Client ID. Search i
  filtry zachowano bez zmian CHUNK 04.
- Flutter Client edit ma date picker i clear do źródłowego/technicznego
  fallbacku; lista i szczegóły używają wyłącznie backendowego
  `effective_added_date` w formacie `dd.MM.yyyy`.
- Tests: isolated migration round-trip PASS; backend CHUNK 03 `6/6 PASS`,
  focused Client/workflow/Global Search `16/16 PASS`, Client source/list oraz
  Auth/Admin PASS; Flutter analyze PASS, focused `22/22 PASS`, full
  `174/174 PASS`; production health aggregate PASS.
- Data safety: production Client value writes `0`; historical backfill `0`;
  Qdrant writes `0`; Vision jobs `0`; n8n changes `0`.
- Implementation commit: `Add editable client added date and sorting`.
- Release: NOT PERFORMED; pozostaje `NEXT Stabil 1.0.2+21`.

## [✓] FOLLOW-UP CHUNK 04 — CLIENT SEARCH USING GLOBAL SEARCH ENGINE — COMPLETE

**Priority: P1**

Problem: zapytanie odnajduje Client w Global Search, lecz nie w zakładce
Clients.

Cel: reuse istniejących Global Search/client-search primitives dla nazwy,
emaila, telefonu, adresu, alias/source identity i statusu. Nie budować trzeciego
silnika wyszukiwania.

Acceptance: kontrolowana macierz zapytań daje zgodny wynik w Clients Search i
Global Search.

Human gate: brak dla audytu/source implementation; release osobnym promptem.

Completion record (2026-08-19):

- Root cause: Clients Search i Global Search utrzymywały dwa niezależne zestawy
  SQL predicates i normalizacji. Rozjazdy obejmowały whitespace, cyfrową
  reprezentację NIP, notes oraz osobne implementacje kontaktów/telefonów.
- `ClientSearchMatchingService` jest jednym canonical primitive dla
  normalizacji i generowania Client candidate predicates. Używają go zarówno
  `ClientRepository`, jak i Client branch `GlobalSearchService`; endpointy UI
  pozostały rozdzielone.
- Wspólne matching fields: name, legal name, NIP, primary i dodatkowe
  email/phone, główny i dodatkowe adresy oraz istniejące Client notes. Global
  Search nie miał Client alias/provenance primitive, więc nie dodano nowej,
  niesprawdzonej semantyki source identity.
- Normalizacja: trim/collapse whitespace, case-insensitive SQL matching,
  casefold dla oceny rankingu, digits oraz wspólna normalizacja polskiego
  prefiksu telefonu. Brak nowego fuzzy/unaccent engine.
- Controlled equivalence matrix: `17/17 PASS`, mismatches `0`, w tym exact i
  partial name, legal name, email/case, contact email, trzy postacie telefonu,
  city/street/postal code, multiple matches, whitespace, normalized NIP, notes
  oraz no-match.
- Clients-specific filters, effective-added-date ASC/DESC, deterministic ID
  tie-break, pagination i empty-query behavior pozostały zachowane. Global
  Search nadal odpowiada za własny scoring/ranking, a Client list za business
  date sorting.
- Performance na kontrolowanym zestawie przy 3243 Clients: mediany
  `29.406–40.707 ms`, maksimum `41.343 ms`; index migration nie jest potrzebna.
- Tests: CHUNK 04 `4/4 PASS`; Global Search + CHUNK 02/03 + Agent `29/29 PASS`;
  Client source/list, deployed compatibility i Auth/Admin PASS; focused Flutter
  Clients `9/9 PASS`; production health aggregate PASS.
- Data safety: business writes `0`; synthetic fixtures transaction rollback;
  migration `NO`; Qdrant writes `0`; Vision jobs `0`; n8n changes `0`.
- Implementation commit: `Unify client search with global search matching`.
- Release: NOT PERFORMED; pozostaje `NEXT Stabil 1.0.2+21`.

## [✓] FOLLOW-UP CHUNK 05 — FILTERS / IGNORED SENDERS + USER MANAGEMENT POLISH — COMPLETE

**Priority: P1**

Zakres A: filtr `Nie pokazuj` dla jednego lub wielu statusów klientów.

Zakres B: admin-only globalna konfiguracja `Ignorowane adresy i domeny`:
add email/domain, list, remove i audit. Ignorowane źródło nie usuwa historii;
wpływa wyłącznie na future ingestion/routing.

Migration: prawdopodobna.

Human gate: osobny schema/migration approval wymagany po audycie projektu
danych; żadnej konfiguracji produkcyjnej bez jawnego apply approval.

Completion evidence (2026-08-20):

- Client list accepts repeated canonical workflow-status exclusions and applies
  them server-side before pagination. Search, effective-added-date ordering,
  `newest|oldest`, stable ID tie-break and additive deployed-client response
  compatibility remain unchanged. Flutter holds a multi-select exclusion set
  and reloads backend paging instead of filtering a fetched page locally.
- Approved additive revision `followup_ignored_mail_sources_20260820` creates
  only `ignored_mail_sources`. Exact normalized email/domain rules are
  admin-only, reactivatable and reversible; no wildcard, substring or subdomain
  matching is accepted. The table remains empty in production.
- Existing Gmail history and Client links are never rewritten. New unresolved
  Gmail from an active ignored rule remains a canonical CandidateSource and is
  suppressed from review as a rejected Candidate. A deterministic Matching V2
  Client resolution wins over the ignore rule and remains linked safely.
- Global Mail and Client Mail expose additive ignored-state filters and badges.
  Existing linked Client correspondence remains visible by default; no Gmail
  source, provider message, Candidate or historical link is deleted.
- Approved constraint-only revision
  `followup_change_history_entity_types_20260820` preserves all prior Change
  History entity/action values and adds entities `ignored_mail_source`, `user`
  plus actions `activated`, `deactivated`. Isolated upgrade/downgrade/re-upgrade
  PASS in 0.443 s; production apply changed zero Change History/business rows.
- Ignored-rule lifecycle writes `created`, `deactivated`, `activated` atomically
  with the domain change. Email-like audit values are masked by the canonical
  sanitizer. User edits use `entity_type=user`, `action=updated`, and audit only
  username/email/role; passwords, hashes, tokens and secrets are excluded.
- User Management uses a responsive identity card and separate wrapping action
  row on narrow widths, keeping username, ellipsized email and role readable at
  360/390/600/1200. Explicit `Edytuj użytkownika` updates only username, email
  and role; password reset remains separate. Typed duplicate handling,
  self-demotion and last-active-Administrator protections remain enforced.
- Verification: CHUNK 05 focused backend PASS; migration round-trip PASS;
  Client Search `4/4`, Global Mail `29/29`, Matching V2 `24/24`, reconciliation
  recovery `13/13`, parity `8/8`, Mail Send `7/7`, Image Preview `11/11`,
  Documents `9/9`, Timeline `4/4`, Client Mail and Admin lifecycle PASS.
  Flutter analyze PASS, focused `51/51`, full `260/260`.
- Production safety: Clients `3243`, Candidates `3570`, Documents `5922`, Gmail
  sources `4272`, Candidate Client-links `3345`, mail-send ledger `4`, Activity
  `0`, Change History `0`, ignored rules `0`, Qdrant points `57`. No production
  User/Client/Candidate/mail-link mutation, Gmail send, n8n change, Vision job,
  Qdrant write or release occurred.
- Release B functional scope is complete. Release remains `NEXT Stabil
  1.0.2+21`; release requires a separate owner-approved prompt.

## [✓] FOLLOW-UP CHUNK 06 — CLIENT ACTIVITY LOG + TIMELINE V2 — COMPLETE

**Priority: P1**

Cel: Oś czasu zawiera faktyczną historię działań.

Telefon po użyciu `Zadzwoń` zapisuje user, timestamp, Client,
`action=call_initiated` i contact reference, bez nagrywania rozmowy.

Email zapisuje kierunek incoming/outgoing, kto, kiedy i temat, bez body.

Dodatkowe eventy: status change, document added, inspection, task,
realization, note, merge i inne istotne działania biznesowe. Preferowany jest
generic activity-event model.

Migration: prawdopodobna.

Human gate: `FOLLOWUP_ACTIVITY_AUDIT_MIGRATION_APPROVAL_REQUIRED`.

Design audit (2026-08-19):

- Current Timeline is a bounded read-only projection over Clients, legacy
  Projects, Inspections, Documents/photos, deduplicated Gmail sources and
  document Client-link events. It has no durable source for `call_initiated`,
  does not project Candidate merge, and `client_workflow_statuses` retains only
  current state rather than status history.
- Existing Candidate merge, Document link, user lifecycle and Agent execution
  tables are domain-specific and cannot safely be reused as a generic business
  activity log.
- Required architecture is hybrid: persist only actions without another
  canonical source (initially call and future status-change history), while
  continuing to derive email, Document, Inspection and Candidate merge events.
- Proposed additive revision `followup_client_activity_20260819` creates
  `client_activity_events` with strict event/metadata contracts, JWT actor,
  unique content-free source key and `(client_id, occurred_at, id)` index.
  Backfill, trigger and business-row rewrite: NO.
- Call endpoint is explicit and idempotent; it validates a Client-owned phone
  contact, never accepts actor/event type/arbitrary metadata from Flutter and
  stores no phone value. A log failure must not block the mocked/real dialer.
- Live read-only evidence: table absent; 3243 Clients, 4262 Gmail sources,
  workflow status rows 3; representative 127-event history returned a bounded
  20-item page in 82.048–127.701 ms with zero duplicate stable keys and zero
  body/raw payload metadata leakage. Production writes: `0`.
- Full schema, endpoint, transaction, UI, rollback and 25-case acceptance spec:
  `FOLLOWUP_CHUNK06_CLIENT_ACTIVITY_DESIGN.md`.
- Approved implementation completed with additive revision
  `followup_client_activity_20260819`; isolated upgrade/downgrade/re-upgrade
  PASS, production apply PASS, no backfill, and zero production activity rows
  after apply.
- `client_activity_events` persists only `call_initiated` and future
  `client_status_changed`. Strict per-event metadata contains no phone value,
  email/document content, raw payload, secrets or arbitrary JSON. Actor always
  comes from JWT; content-free `source_key` provides idempotency.
- The call endpoint validates active Client-owned phone contacts, rejects
  cross-Client references and operation conflicts, and the Flutter dialer
  remains available after a bounded logging warning. Dialer acceptance was
  mocked; real phone calls: `0`.
- Workflow-status change and its activity row share one DB transaction; no-op
  status updates create no event. Prior status history was not invented.
- Timeline V2 is hybrid: persistent call/status events plus derived canonical
  Gmail, Document/photo, Inspection, Document-link and Candidate-merge events.
  Stable prefixed keys, deterministic sorting, bounded backend pagination,
  batch actor projection, bounded metadata and deep links are preserved.
- Tests: isolated Activity focused `7/7 PASS`; Timeline/status and selected
  Candidate/Inspection/Agent regressions PASS; Flutter analyze PASS, focused
  call/Timeline `14/14 PASS`, full suite `182/182 PASS`. No production Client/status
  write, email, Vision job, Qdrant write or n8n change occurred.
- Implementation commit: `Add client activity log and timeline`.
- Release: NOT PERFORMED; remains `NEXT Stabil 1.0.2+21`.
- Design commit: `Design client activity log and timeline`.

## [✓] FOLLOW-UP CHUNK 07 — ADMIN CHANGE HISTORY — COMPLETE

**Priority: P1**

Admin-only zakładka `Historia zmian`: kto, kiedy, entity, ID, action, changed
fields oraz bounded before/after.

Zakres obejmuje Client edits, status, dates, contacts, addresses, merges,
Candidate promotion, settings, backup settings, ignored email config oraz
tasks/calendar.

Nie zapisywać passwords, tokens, secrets, full emails ani full documents.

Human gate: schema/migration approval po projekcie audytu; trwały log nie może
powstać jako niekontrolowane pole JSON.

Design audit (2026-08-19):

- Live DB ma wyłącznie domenowe/operacyjne audyty:
  `candidate_merge_events`, `client_activity_events`,
  `document_client_link_events`, `user_lifecycle_events` i
  `agent_executions`; żadna z tych tabel nie ma ogólnego, bounded kontraktu
  entity/action/before/after. `change_history_events` nie istnieje.
- CHUNK 06 Activity pozostaje user-facing business timeline. Candidate merge,
  Document link i User lifecycle pozostają kanonicznymi audytami domenowymi i
  będą projektowane read-only zamiast kopiowane do drugiego store'u.
- Wymagana jest addytywna rewizja `followup_change_history_20260819` z parentem
  `followup_client_activity_20260819`, tworząca wyłącznie
  `change_history_events`. Backfill, trigger i business-row rewrite: NO.
- `ChangeHistoryService` będzie mieć ścisłe allowlisty entity/action/pól,
  server-side JWT actor, deterministyczny diff, bounded before/after i
  fail-closed zapis w tej samej transakcji co business write. Arbitrary JSON,
  secrets, email/document/OCR body oraz raw payload są zakazane.
- Contact policy: email/phone/NIP są maskowane i opatrywane digestem; adresy
  zapisują tylko faktycznie zmienione, bounded pola; long notes przechowują
  wyłącznie length/hash descriptor. Nie ma generic write endpointu.
- Current Client create/edit/delete oraz Candidate accept/reject nie przekazują
  aktora do service i część ich repozytoriów wykonuje commit wewnętrznie. Implementacja
  po approval musi przenieść granicę transakcji do application services, aby
  audit failure wycofywał business write.
- Admin API będzie JWT/admin-only (401/403), paginowane 50/max 200 i filtrowane
  po entity, actor, action i date range. Flutter UI nie jest częścią etapu
  design-only.
- Read-only design audit PASS: live revision
  `followup_client_activity_20260819`, ungranted locks `0`, production writes
  `0`. Pełny schema/API/sanitizer/transaction/test design:
  `FOLLOWUP_CHUNK07_ADMIN_CHANGE_HISTORY_DESIGN.md`.
- Implementacja 2026-08-19: addytywna rewizja
  `followup_change_history_20260819` utworzyła wyłącznie tabelę
  `change_history_events`; backfill i business-row rewrite: NO. Isolated
  upgrade/downgrade/re-upgrade zachował 3243 Clients, 3561 Candidates, 5915
  Documents oraz istniejące audyty, a produkcyjna tabela po apply pozostała
  pusta.
- `ChangeHistoryService` zapisuje bounded diff w transakcji caller-a, ma ścisłe
  allowlisty i limit 40 pól / 8 KiB na before i after. Email, telefon i NIP są
  maskowane z digestem; notes mają wyłącznie length/hash; secrets, content i
  arbitrary nested JSON są odrzucane.
- Current Client create/update/delete, Client contacts/addresses, workflow
  status oraz Candidate accept/reject emitują audyt z aktorem JWT. Awaria
  audytu wycofuje business write; status Activity i Change History są
  atomowe. Candidate merge, Document link i User lifecycle są projektowane z
  ich kanonicznych audytów bez duplikowania persistence. CHUNK 06 Activity
  pozostaje oddzielnym business timeline.
- Admin-only `GET /api/v1/admin/change-history` ma filtry entity/entity ID,
  actor, action i date range, stabilne sortowanie oraz paginację 50/max 200.
  Flutter Settings zawiera admin-only `Historia zmian`, bounded expandable
  diff, masked values, filtry i responsive layout 360/390/600/1200.
- Acceptance: migration round-trip PASS; focused backend 11/11 i jawne
  regresje 26/26 PASS; unauthenticated 401, non-admin 403, admin 200; Flutter
  analyze PASS, focused 9/9 PASS, full 191/191 PASS. Production Client/
  Candidate writes: 0; release: NOT PERFORMED.
- Implementation commit: `Add admin change history` (this change).

## [✓] FOLLOW-UP CHUNK 08 — CANDIDATE ACCEPT CONFLICT + MERGE — COMPLETE

**Priority: P1**

Cel: ustalić przyczynę HTTP 406 przy akceptacji Candidate. Jeśli przyczyną jest
duplicate, zamiast niejasnego błędu pokazać kontrolowany merge.

Merge musi porównać rekordy, konflikty, canonical values, contacts, addresses,
provenance, documents/emails i audit. Zakaz automatic fuzzy merge; human
confirmation jest obowiązkowe.

Human gate: osobne approval przed jakimkolwiek merge/apply danych.

Diagnostic 2026-08-19: current source and available runtime logs do not expose
an HTTP 406 Candidate accept path. Since the review endpoint was introduced,
exact duplicates have used an additive typed HTTP 409 response
(`candidate_matches_existing_client`). The real gap is that the matcher returns
only the first tax-id/email/phone match, does not expose conflicting or multiple
evidence, and repeated promotion is not an idempotent prior-result response.
Synthetic rollback characterization: `12/12 PASS`; production Clients and
Candidates changed: 0.

Implementation 2026-08-19: the additive migration
`followup_candidate_merge_audit_20260819` added the bounded
`candidate_merge_events` audit table without backfill or business-row rewrite.
Candidate promotion keeps the compatible typed HTTP 409 fields and now exposes
up to 10 deterministic `matches[]` with exact NIP, e-mail and phone evidence.
The JWT-protected preview is read-only; apply requires a canonical operation
UUID, current preview version, explicit conflict decisions and a second UI
confirmation. Merge is transactional and idempotent, preserves provenance,
deduplicates contacts/addresses, relinks existing Documents without copying or
Vision restart, retains Candidate history and writes exactly one metadata-only
actor/effect audit event.

Acceptance used only the isolated `ai_lab_chunk08_isolated` database and
rollback fixtures: migration upgrade/downgrade/re-upgrade PASS; focused backend
26/26 PASS; Client Search regression 4/4 PASS; Candidate/API compatibility PASS;
Flutter analyze PASS and full Flutter suite 180/180 PASS. No real production
Candidate or Client was merged; production received only the approved schema
migration and the audit table remained empty. No release was performed.
Implementation commit: `Add audited candidate merge flow` (this change).

## [✓] FOLLOW-UP CHUNK 09 — GLOBAL MAIL WORKSPACE — COMPLETE

**Priority: P1**

Dodać `Maile` do menu i Dashboard.

Etap 1 — read: inbox/list, search, filters, threads, sender, recipients, date,
subject, body, attachments, Client linking, deep links oraz read/unread, jeśli
obecna integracja bezpiecznie to obsługuje.

Etap 2 — write: compose, reply, forward. Wysyłanie jest external side effect.
Agent nadal nie może autonomicznie wysyłać emaili.

Human gate: przed write wymagany
`FOLLOWUP_EMAIL_SEND_APPROVAL_REQUIRED`.

Audit/design record (2026-08-19):

- Canonical source remains `candidate_sources` (`gmail_message`) with existing
  Candidate/Client linkage and attachment Documents; no second mail store is
  justified.
- Production contains 4,262 canonical messages. A bounded prototype returned
  the latest 50 in about 748 ms without evaluating historical JSON, but
  correct backend direction/read filtering exceeded the 10-second client
  timeout because these fields exist only inside large `raw_payload` values.
- Gmail full-text search already has a production GIN index. Minimal additive
  direction/read/message-time expression indexes are required for correct
  filtering, stable pagination and canonical ordering. No column, default,
  trigger, backfill or business-row rewrite is proposed.
- Exact schema/read/write design and verification gates are recorded in
  `FOLLOWUP_CHUNK09_GLOBAL_MAIL_WORKSPACE_DESIGN.md`.
- Production writes, email sends, Client relinks, DB migration and n8n changes:
  `0`. The unverified prototype was not retained. Release was not performed.

Execution record (2026-08-19):

- Approved revision `followup_mail_query_indexes_20260819` created only three
  partial expression indexes: direction, nullable read state and guarded
  message time. No column, backfill, trigger, default or business-row rewrite
  occurred; Gmail count remained 4,262.
- The first intended isolated invocation used the wrong environment override
  name and applied the approved index-only revision to production before the
  isolated round-trip. Build duration was 49.57 s. Backend recovered healthy,
  pending locks were 0 and all audited counts were unchanged. This sequencing
  exception is recorded explicitly and was not hidden by downgrade/reapply.
- Correct isolated upgrade/downgrade/re-upgrade subsequently passed; upgrade
  and re-upgrade were approximately 46.6 s, downgrade 1.6 s, counts unchanged.
- Query acceptance did not pass: rare `unknown` and `unread` filters used the
  indexes and completed in about 250/70 ms, while common `incoming` and `read`
  combined with canonical time ordering took about 16/18 s. That exceeds the
  Flutter 10-second timeout.
- A composite `(direction/read, message_time, id)` query index is required.
  Normal transactional construction on the 524 MB table is materially
  blocking, so no additional index or Stage 1 API/UI was implemented.

Online-index execution record (2026-08-19):

- The isolated target was explicitly verified as
  `ai_lab_chunk09_online_20260819` using `POSTGRES_DB` plus
  `current_database()` before DDL; this prevents recurrence of the earlier
  production-first sequencing exception.
- On the full isolated clone, narrow partial indexes measured 80 KiB
  (`received`) and 152 KiB (`read`) with 215/107 ms plans. Full composite
  alternatives measured 208/184 KiB with 242/105 ms plans. Production
  evidence required the final hybrid: partial `(message_time, id)` for
  `received`, and composite `(read_state, message_time, id)` for `read`.
- Revision `followup_mail_composite_indexes_20260819` uses Alembic
  `autocommit_block()` with `CREATE/DROP INDEX CONCURRENTLY`. Isolated
  upgrade/downgrade/re-upgrade passed; the three baseline indexes remained,
  both new indexes are valid/ready, and counts remained 4,262 Gmail / 6,984
  total sources.
- Production online construction kept backend health at 200, observed zero
  waiting locks, rewrote zero rows, and produced valid/ready 80/184 KiB
  indexes. After `ANALYZE`, `received LIMIT 50` uses the new index and improved
  to about 244 ms.
- The hard gate still failed for `read`: PostgreSQL continues to choose the
  older single-column `ix_candidate_sources_gmail_read_state`, evaluates
  historical TOAST JSON and sorts 4,242 rows. Exact, full-key and bounded
  ordered-subquery forms took about 18.5–25.4 s and ignored the ordered
  composite path. Therefore Stage 1 API/Flutter was not implemented.
- Production safety audit remained unchanged: Clients 3,243; Candidates
  3,561; Documents 5,915; Change History 0; Activity 0; Qdrant 57; backend,
  Vision and n8n healthy. No email, link, Candidate, n8n, Vision or Qdrant
  write occurred.

Planner-remediation evidence (2026-08-19):

- A fresh full-size clone was verified as
  `ai_lab_chunk09_planner_20260819`; production `ai_lab` received no DDL.
- After isolated `ANALYZE`, the exact read query reproduced the conflict:
  legacy read-state index, 4,242 rows, top-N sort and 17,907.796 ms.
- Dropping only `ix_candidate_sources_gmail_read_state` on the isolated clone
  took about 20.3 ms. After `ANALYZE`, the planner used the valid/ready ordered
  read/time index and completed in 87.232 ms without a sort.
- The first 200 IDs and positions were identical before/after (0 ID-set and 0
  order mismatches). Unread was 29.990 ms, nullable state 0.039 ms, latest
  132.239 ms, received 205.964 ms and sent/outgoing 2,878.154 ms.
- Repo search and production `pg_depend` found no runtime/dependent consumer
  of the legacy index name outside its historical migration and documentation.
  Full evidence and rollback are in
  `FOLLOWUP_CHUNK09_READ_PLANNER_REMEDIATION.md`.

Production supersession and remaining hard-gate record (2026-08-19):

- Approved revision `followup_mail_read_index_supersession_20260819` used an
  Alembic autocommit block to drop only
  `ix_candidate_sources_gmail_read_state` with `DROP INDEX CONCURRENTLY`.
  Downgrade recreates the exact historical expression/partial predicate with
  `CREATE INDEX CONCURRENTLY`; no row, column, trigger or default changed.
- Verified isolated upgrade/downgrade/re-upgrade passed before production.
  Production DB identity was explicitly `ai_lab`; backend remained HTTP 200,
  waiting locks were 0, and ordered replacement
  `ix_candidate_sources_gmail_read_time` remained valid/ready.
- The exact common `read LIMIT 50` plan changed from the legacy index plus
  4,242-row top-N sort (18,527.250 ms) to the ordered read/time index without
  sort (348.775 ms immediately after apply; 102–111 ms warm measurements).
  Result IDs/order remained identical to the isolated proof.
- Initial production query matrix (maximum observed): latest 199 ms, received
  692 ms, sent 3,669 ms, unknown direction 142 ms, read 112 ms, unread 37 ms,
  search 275 ms, Client filter 12 ms and date range 139 ms. The prior
  `unknown read` figure of about 2 ms used the historical index expression,
  which incorrectly classifies a missing-label payload as `read`.
- A strict contract audit found exactly one Gmail source (technical ID 2)
  without either labels array. Correct nullable semantics (`missing/unusable`
  means `null`) require evaluating historical JSON; the exact bounded unknown
  filter took 13,364 ms and therefore fails the 10-second hard gate.
- A thread JSON fallback also measured 13.7 s; read-only evidence showed
  canonical `external_parent_id` on all 4,262 Gmail sources and zero mismatches,
  so the canonical thread query itself is viable at about 54 ms. This does not
  solve the nullable read-state filter.
- A read-only API/Flutter prototype was exercised to expose these issues, then
  removed before commit because Stage 1 acceptance did not pass. No production
  email/link/Candidate row, n8n workflow, Vision job or Qdrant point changed.
- Required next architecture decision: approve a corrected nullable
  read-state ordered expression index (online/concurrent) or a separately
  designed canonical projection. Do not approximate missing labels as `read`.
- Verification retained for this stage: isolated migration
  upgrade/downgrade/re-upgrade PASS and structural test `2/2 PASS`.

Historical decision at that checkpoint was
`FOLLOWUP_CHUNK09_QUERY_ARCHITECTURE_BLOCKED`; it was superseded by the
nullable-state remediation and Stage 1 completion record below.

Nullable read-state and Stage 1 completion record (2026-08-19):

- Root cause was SQL three-valued logic: when both Gmail label fields were
  absent, `json_typeof(NULL) <> 'array'` evaluated to `NULL`, so the historical
  expression incorrectly fell through to `read`. The canonical shared SQL now
  maps missing/non-array labels to `NULL`, `UNREAD` arrays to `unread`, and
  remaining arrays to `read`. Production truth is 4,241 read / 20 unread / 1
  unknown, with zero malformed non-array payloads; technical source ID 2 is
  correctly unknown.
- Revision `followup_mail_nullable_read_state_20260819` built
  `ix_candidate_sources_gmail_read_state_v2_time` concurrently, verified it
  valid/ready, then concurrently superseded the incorrect ordered
  `ix_candidate_sources_gmail_read_time`. Downgrade restores the exact prior
  ordered index before removing V2. The explicitly verified full-size clone
  `ai_lab_chunk09_nullable_20260819_a` passed upgrade/downgrade/re-upgrade;
  V2 is 184 KiB and no row/count changed. Production build took 26.377 s,
  backend stayed HTTP 200 and waiting locks remained zero.
- The production planner initially chose bitmap + broad sort for the common
  state despite the corrected index. The service therefore expresses the
  logically constant read-state key first in `ORDER BY`, followed by canonical
  message time and ID. This preserves result semantics while forcing the full
  ordered index path: read 50 is about 254 ms median, unread 30 ms and unknown
  1.6 ms. Full measured maxima were latest 377 ms, received 779 ms, sent
  3,826 ms, unknown direction 227 ms, search 2,391 ms, Client filter 11 ms,
  thread filter 41 ms and date range 225 ms; requests over 10 s: zero.
- Stage 1 now provides authenticated additive `GET /api/v1/mail`,
  `/mail/{source_id}` and `/mail/threads/{thread_id}` endpoints with bounded
  filters/pagination, canonical Client linkage, safe text-only detail,
  attachment Document projections and no raw payload/filesystem paths. Thread
  lookup uses canonical `external_parent_id` only.
- Flutter now exposes `Maile` in main navigation and a minimal Dashboard card,
  responsive list/detail/thread UX, server-side filters and paging,
  read/unread/unknown states, Client/Document deep links and mobile Back state.
- Verification: nullable migration/service tests 28/28 PASS; selected
  Client Mail, Timeline V2, Matching V2, Candidate, Documents, Search, Auth and
  Agent regressions 48 PASS / 13 skipped; Client Mail E2E and attachment-scope
  rollback PASS; authenticated Global Mail list/detail/thread smoke 200;
  Flutter analyze PASS, focused Mail 8/8 PASS, full Flutter 199/199 PASS.
- Production safety remained Clients 3,243, Candidates 3,561, Documents 5,915,
  Gmail 4,262, Change History/Activity/Candidate merge audit rows 0, Qdrant 57,
  Vision queue 0, n8n/backend healthy. Email writes/sends, Client relinks,
  n8n/Vision/Qdrant writes and business-row rewrites: zero. No release.

Stage 2 compose/reply/forward is not implemented. Active gate and next work:
`FOLLOWUP_EMAIL_SEND_APPROVAL_REQUIRED`. CHUNK 10 and Release B remain stopped.
Implementation commit: `Complete global mail read workspace` (this change).

Stage 2 send audit/design record (2026-08-19):

- Human gate `FOLLOWUP_EMAIL_SEND_APPROVAL_REQUIRED` was granted. No provider
  send was performed during the required audit-first stage.
- Gmail OAuth exists only inside the active n8n runtime. The backend exposes no
  Gmail credential/send primitive, and the current workflow contains read/sync
  nodes only. The installed Gmail node supports provider send and native reply,
  so credentials must remain isolated in n8n behind a bounded backend adapter.
- None of `candidate_sources`, `change_history_events`,
  `client_activity_events` or `candidate_merge_events` can safely provide the
  pre-provider durable claim needed for operation UUID idempotency. Reusing
  them would either leave a double-send race or overload a different audit
  domain.
- Minimal additive revision `followup_mail_send_ops_20260819` is required to
  create only `mail_send_operations`: content-free operation/payload hashes,
  actor/action/state, bounded counts and provider/canonical IDs. It stores no
  body, subject, recipient list, attachment path, arbitrary JSON or secret and
  performs no backfill/business rewrite.
- The state machine is fail-closed across the external transaction boundary:
  provider acceptance is persisted before canonical ingest; a replay resumes
  ingest without re-sending, while unknown provider outcome cannot be retried
  automatically.
- Exact migration, n8n adapter, endpoint, attachment, UI, rollback and
  controlled three-send acceptance design:
  `FOLLOWUP_CHUNK09_EMAIL_SEND_DESIGN.md`.
- Migration, source/UI implementation, n8n workflow changes, email sends and
  customer/business writes: `0`. A controlled acceptance mailbox was not
  assumed and must be supplied/verified before any real test send.

Current gate and next work:
`FOLLOWUP_EMAIL_SEND_SCHEMA_MIGRATION_APPROVAL_REQUIRED`. CHUNK 10 and Release B
remain stopped.

Stage 2 approved implementation record (2026-08-19):

- Approved additive revision `followup_mail_send_ops_20260819` created only the
  bounded `mail_send_operations` ledger. Isolated upgrade/downgrade/re-upgrade
  PASS; production apply PASS; ledger rows `0`, no backfill, trigger or
  business-row rewrite. Current DB head is the new revision.
- Backend implements authenticated compose/reply/forward, server-side payload
  hashing, durable pre-provider operation claims, typed replay/conflict,
  fail-closed unknown outcome, provider-accepted persistence and canonical
  ImportIngest continuation without re-sending.
- The inactive, tracked n8n adapter template supports exactly compose/reply/
  forward, keeps Gmail OAuth inside n8n and requires a dedicated runtime
  secret. Existing ingestion workflow/schedule was not modified and no CHUNK
  10 behavior was added.
- Flutter adds compose, reply and forward with transient drafts and mandatory
  final confirmation. Backend attachment selection is Document-ID allowlisted,
  path-safe, MIME/count/size bounded and never accepts a Flutter path/URL.
- Verification: backend focused/migration/Auth/Stage 1 regressions PASS;
  Flutter analyze PASS, focused Mail `9/9`, full `200/200`. Mock provider
  replay count `1`; payload conflict `409`; `unknown` cannot resend.
- Runtime audit found no explicitly configured controlled test target and no
  activated send webhook URL/secret. Therefore the adapter was not activated,
  provider calls and emails sent remained `0`, and live acceptance was not
  claimed.

Current gate and next work:
`FOLLOWUP_EMAIL_SEND_TEST_TARGET_REQUIRED`. After a controlled mailbox and
runtime secret are supplied, acceptance is limited to one compose, one reply
and one forward. CHUNK 10 and Release B remain stopped.

Final live-acceptance record (2026-08-20):

- Stage 1 READ remains complete, including the corrected nullable Gmail
  read-state contract and its online query indexes. Stage 2 compose, reply and
  forward are complete through the authenticated backend, durable
  `mail_send_operations` idempotency ledger and bounded n8n Gmail adapter.
- The n8n OAuth identity was verified as `podnoszenieposadzek@gmail.com` and
  remained isolated inside n8n. Native Header Auth protects the unscheduled
  send adapter; the backend is the application caller and Agent has no mail
  write tool.
- Controlled live acceptance sent exactly three synthetic app-generated
  messages to `root.test112@gmail.com`: one compose, one reply and one forward.
  The manual inbound reply seed is not an app send. Replay returned the prior
  result without another provider call, changed payload under the same UUID
  returned `409`, and customer/business or non-approved recipients were `0`.
- Canonical Gmail evidence is retained: source `8038` compose, `8039` manual
  seed, `8040` reply and `8041` forward. Provider IDs are unique, the reply
  thread is `[8038, 8039, 8040]`, forward remains separate, and all four
  sources remain unlinked.
- Ledger evidence is retained truthfully: one technical pre-provider `failed`
  operation and three `canonical_synced` operations. The ledger contains no
  body, subject, recipient list, credential, token or arbitrary payload.
- Candidates `5530`–`5533` are intentionally retained as **CHUNK 09 CONTROLLED
  LIVE ACCEPTANCE ARTIFACTS**. Each is pending and unlinked, has no Client,
  Document, contact/address or unrelated domain/audit relation, and owns only
  its controlled synthetic Gmail source. The final Candidate count is `3565`.
- This is existing canonical ingestion policy, not a CHUNK 09 defect:
  `ImportIngestService._find_candidate_for_email()` intentionally creates a
  pending Candidate for unresolved Gmail so it remains reviewable. CHUNK 09
  does not change CandidateSource FK nullability, Candidate creation policy,
  Matching V2 semantics or historical ingestion. A future unlinked-mail model
  would require a separate owner-approved product/domain scope.
- Final verification: Mail Send `7/7`, Global Mail `29/29`, Matching V2
  `24/24`, Client Mail/attachment scope, Timeline `4/4`, Documents `9/9`,
  Agent `13/13` and Auth regressions PASS; Flutter analyze PASS, focused Mail
  `33/33`, full `200/200`. No additional provider send or release was made.

## RELEASE B — PUBLISHED — NEXT STABIL 1.0.2+22

- Published 2026-08-20 from source commit
  `b375b2184ae5bb87742fb870153fa92953a343ae`; release commit subject:
  `Release NEXT Stabil 1.0.2+22`.
- Release B includes completed CHUNK 06 (Client Activity/Timeline V2), CHUNK 07
  (Admin Change History), CHUNK 09 (Global Mail read/send), CHUNK 10 (image
  preview and bounded manual reconciliation), and CHUNK 05 (communication
  filters, ignored senders and User Management polish).
- Web, Windows installer and Android APK were built with the production API
  and supervisor URLs. Stable Windows/Android artifacts were published before
  the stable manifest moved to build `22`; SHA-256 values were verified from
  the public channel. `minimum_version` remains `1.0.0`, so `1.0.2+21` sees an
  optional update rather than a forced update.
- Release validation: backend Release B regression matrix PASS; Flutter
  analyze PASS; full discovered Flutter suite `223/223` PASS; focused updater
  and version smoke `16/16` PASS; public Web login smoke PASS without console
  errors. No Gmail send, business-data write, migration, n8n change, Vision
  job or Qdrant write occurred during release.
- Previous `1.0.2+21` Windows and Android artifacts remain available for
  rollback.

**RELEASE B COMPLETE. NEXT PLANNED WORK: PHASE C — FOLLOW-UP CHUNK 13.**

**DO NOT START CHUNK 13 WITHOUT A NEW OWNER PROMPT.**

## [✓] FOLLOW-UP CHUNK 10 — MAIL REFRESH / RECONCILIATION + IMAGE PREVIEW — COMPLETE

**Priority: P1**

Dodać `Odśwież` w globalnym Mail workspace i mailach Client. Funkcja ma
odnajdywać wiadomości pominięte przez standardową synchronizację.

Preferowana architektura: standardowy n8n ingestion pozostaje, manual trigger
wykonuje bounded reconciliation z checkpoint/idempotency/dedupe. Automatyczny
daily reconciliation można rozważyć dopiero po audycie.

Acceptance: brak duplikatów.

Human gate: zmiana n8n/schedule lub produkcyjny reconciliation wymaga osobnego
approval.

### IMAGE THUMBNAILS + INTERNAL VIEWER — COMPLETE (2026-08-20)

- Jeden wspólny Flutter contract obsługuje media dokumentów:
  `DocumentImageThumbnail`, `InternalImageViewer` i `openDocumentMedia`.
  Obsługiwane JPEG, PNG i WebP są otwierane wewnątrz NEXT Stabil przez
  `InteractiveViewer`; nie uruchamiają Gallery, Photos, browsera ani
  systemowego file openera. PDF i pozostałe nieobrazy zachowują dotychczasowe
  zachowanie. HEIC/HEIF pozostają bez thumbnail/internal preview, ponieważ
  Flutter nie zapewnia bezpiecznego dekodowania na Windows, Android i Web bez
  nowego subsystemu konwersji.
- Repozytorium Documents, Client Documents, Client Mail attachments, Global
  Mail attachments oraz Document/Vision details korzystają z tego samego
  komponentu. Miniatura ma `100` logical px szerokości, zachowuje proporcje,
  placeholder/loading/error, semantyczny tap target oraz jest pobierana leniwie
  tylko dla wyrenderowanego elementu. Viewer ma fit-to-screen, zoom do 8×,
  pan, retry i poprawny Back do poprzedniego kontekstu.
- Addytywny, JWT-protected
  `GET /api/v1/documents/{document_id}/thumbnail?max_size=200` używa dokładnie
  tej samej ścieżki autoryzowanego Document content. Pillow dekoduje wyłącznie
  JPEG/PNG/WebP, weryfikuje rzeczywisty format względem canonical MIME,
  ogranicza source do 40 MP, stosuje EXIF orientation, nie upscale'uje i
  zwraca bounded PNG z private HTTP cache. Nie ujawnia storage path i nie
  tworzy trwałych thumbnail files ani drugiego store'u.
- Large-image proof: syntetyczne `6000×4000` → `200×133` w `195.436 ms`, bez
  preładowania oryginałów przez listę. Backend thumbnail `11/11`, Document
  Read, Vision `10/10`, Client attachment scope i Global Mail `29/29` PASS.
  Flutter analyze PASS, focused media/screens `34/34`, full `211/211`, w tym
  360/390/600/1200, Back oraz assertion, że image preview nie wywołuje
  external opener.
- DB migration/cache artifacts/business writes: `NO/0/0`. Clients,
  Candidates, Documents rows, Client links, Gmail/n8n, Vision i Qdrant nie
  zostały zmienione. Release nie został wykonany.

### MAIL REFRESH / RECONCILIATION — COMPLETE (2026-08-20)

- Global Mail i Client Mail mają wspólne `Odśwież`: JWT-protected dry-run,
  jawną akceptację planu tylko przy brakach, disabled/loading/double-tap guard,
  bounded summary i przeładowanie bieżącego kontekstu. Client refresh zachowuje
  mailbox-wide semantics i nie przekazuje dowolnego Client-specific Gmail
  query ani nie wymusza linku.
- Backend i osobny n8n webhook realizują manualny, bounded reconciliation:
  maks. 30 dni, 1000 zbadanych i 100 brakujących wiadomości. Adapter jest
  chroniony Header Auth, ma wyłącznie Gmail `getAll/get`, nie ma schedule ani
  background execution i nie zmienia normalnego workflow co 15 minut ani jego
  checkpoint/history state. Gmail OAuth pozostaje wyłącznie w n8n.
- Canonical provider message ID jest jedynym dedupe key. Dry-run jest
  read-only; apply korzysta z `ImportIngestService`, canonical attachment path
  i Matching V2. HMAC token jest ważny 10 minut i wiąże aktora, okno, kolejność
  provider IDs, Candidate classification/reuse IDs, resolved Client ID,
  confidence/evidence i wszystkie przewidywane delty. Pełny plan jest
  przeliczany przed pierwszym zapisem; drift zwraca
  `reconciliation_plan_drift`.
- Pierwszy zatwierdzony apply ujawnił błąd starej predykcji. Plan przewidywał
  `CandidateSources +2 / Candidates +2 / Documents +1 / new Client links +0`,
  a canonical wynik wyniósł `+2 / +1 / +1 / +0`. Źródła `8047/8048`
  zachowano; jedno utworzyło pending Candidate `5538`, drugie poprawnie użyło
  istniejącego Candidate `3578`, już powiązanego z Client `3105`. Client,
  Candidate i historyczny link nie zostały zmienione; rollback nie był
  potrzebny.
- Root cause: uproszczony dry-run pomijał canonical
  `ForwardSourceIngestionService.prepare()` przed Matching V2. Wspólny
  read-only resolver został wyodrębniony do `ImportIngestService`; predykcja i
  apply korzystają teraz z tej samej normalizacji oraz rozstrzygnięcia
  Candidate. Klasyfikacje to `new_candidate`,
  `reuse_existing_candidate_unlinked` i
  `reuse_existing_candidate_client_linked`.
- Drugi rich plan objął `19ff76b8b8cfb56c` (`new_candidate`, certain
  `exact_sender_email`, resolved Client `957`, Candidate/Document/link
  `+1/+1/+1`) oraz `19fddf3a841ebabb` (`new_candidate`, unresolved,
  `+1/+1/+0`). Podpisany plan i prewrite revalidation były identyczne; apply
  zakończył się dokładnie `CandidateSources +2`, `Candidates +2`, `Documents
  +2`, `new Client links +1`, failures `0`. Powstały sources `8049/8050` i
  Candidates `5539/5540`; istniejący Client `957` i historyczne linki nie
  zostały zmodyfikowane.
- Końcowy read-only reconciliation: 30 dni `90 examined / 77 present / 0
  missing`, 7 dni `36 / 30 / 0`; wszystkie cztery reviewed provider IDs są
  canonical dokładnie raz. Final counts: Clients `3243`, Candidates `3570`,
  Documents `5922`, Gmail sources `4272`, Client-linked Candidates `3345`,
  Qdrant `57`. Gmail sends, n8n schedule changes i Qdrant writes: `0`.
- Verification: recovery `13/13`, isolated parity `8/8`, Global Mail `29/29`,
  Matching V2 `24/24`, Image Preview backend `11/11`, Client Mail, Documents,
  Timeline `4/4`, Mail Send `7/7`, Agent `13/13` i Auth PASS. Flutter analyze
  PASS, focused reconciliation/Mail/Client/media `37/37`, full `214/214`.
- Automatyczne/daily reconciliation pozostaje niezaimplementowane i wymaga
  osobnego `FOLLOWUP_EMAIL_RECONCILIATION_SCHEDULE_APPROVAL_REQUIRED`.
  Release nie został wykonany.

## [✓] FOLLOW-UP CHUNK 11 — EMAIL ↔ EXISTING CLIENT MATCHING V2 — COMPLETE

**Priority: P1**

Cel: poprawić przypisywanie maili do istniejących klientów.

Hierarchia evidence:

1. exact normalized email,
2. existing verified contact,
3. thread/message relation,
4. phone/reference IDs,
5. attachment metadata,
6. email body,
7. attachment extracted text/OCR,
8. bounded AI-assisted reconciliation.

Confidence: `certain`, `high`, `ambiguous`, `unresolved`. Auto-link tylko dla
deterministic/certain. Ambiguous trafia do review queue. Vision tylko wtedy,
gdy attachment faktycznie wymaga analizy wizualnej.

Kryterium krytyczne: zero cross-client wrong linking.

Human gate: każde historyczne relink/apply wymaga osobnego data approval.

Completion record (2026-08-19):

- Root cause: dotychczasowy ingest sprawdzał NIP, email i telefon kolejno, a
  repozytorium zwracało pierwszy exact match. Dodatkowo identyfikatory z body
  Gmaila mogły być traktowane jak zweryfikowane dane nadawcy i dopisywane do
  kontaktów dopasowanego Client.
- Wspólny bounded matcher zbiera wszystkie exact matches (maks. 10 Clients),
  rozdziela zweryfikowanego nadawcę od niezaufanej treści i klasyfikuje wynik
  jako `certain`, `high`, `ambiguous` albo `unresolved`. Auto-link jest
  dozwolony wyłącznie dla jednego niesprzecznego `certain` Client.
- Evidence hierarchy obejmuje canonical email/contact, pełny NIP, canonical
  telefon, reference ID, wspierającą relację thread oraz bounded body. Name,
  city, thread i email znaleziony wyłącznie w body są tylko propozycją do
  review; AI-only i name-only nigdy nie są `certain`.
- Niepewne nowe wiadomości pozostają osobnymi pending Candidates z bounded
  metadata-only evidence. Replay tego samego Gmail message ID pozostaje
  idempotent; istniejący link nigdy nie jest po cichu zmieniany.
- Future-only reconciliation załączników korzysta z już zapisanego extracted
  text, OCR i validated Vision (maks. 3 attachments, 8 pages/assets, bounded
  text). Nie uruchamia OCR, LLM ani Vision job; sprzeczny późniejszy dowód
  zachowuje aktualny Client i kieruje rekord do review.
- Historyczny relink/backfill: NO. Schema migration: NO. n8n change: NO.
  Produkcyjne Client/email/Candidate links zmienione podczas acceptance: `0`.
- Read-only real-source sample: 12 najnowszych rekordów; 5 aktualnych linków
  potwierdzonych, 3 linked-review, 4 unlinked-review, 0 exact conflict i 0
  zmienionych produkcyjnych linków.
- Tests: controlled matcher/reconciliation `24/24 PASS`; Gmail source boundary,
  Candidate CHUNK 08 `13/13`, Vision `10/10`, Documents, Sheets idempotency,
  Global Search, compatibility i Auth/Admin PASS; backend compile PASS.
- Implementation commit: `Improve email to existing client matching`.
- Release: NOT PERFORMED; pozostaje `NEXT Stabil 1.0.2+21`.

## [✓] FOLLOW-UP CHUNK 12 — DASHBOARD REBUILD — COMPLETE

**Priority: P1**

Usunąć z Dashboard `Sprawy`, puste `Analizy` i puste `Zadania`; usunąć
`Sprawy` także z menu.

Nowa kolejność:

1. Kalendarz + Zadania,
2. Maile,
3. Dokumenty,
4. Ostatnia aktywność,
5. Status systemu / Backend Online.

`Backend Online` znajduje się na samym dole. Dashboard korzysta z realnych
danych; nowe dokumenty, maile, zadania i aktywność nie mogą trafiać do martwych
placeholderów.

Human gate: brak przed source implementation; release osobnym promptem.

### IMPLEMENTATION COMPLETE (2026-08-20)

- Dashboard ma jedną operacyjną hierarchię opartą wyłącznie na realnych
  providerach: `Kalendarz i zadania`, `Maile`, `Dokumenty`, mały prawdziwy
  stan przejściowy `Ostatnia aktywność` oraz `Status systemu` jako ostatnia
  sekcja. Usunięto martwe `Sprawy`, `Analizy` i `Zadania: 0`; `Sprawy`
  usunięto z głównej nawigacji bez kasowania kompatybilnej trasy/backendu.
- Dashboard współdzieli CHUNK 13 `OperationalMonthCalendar`, month projection
  i formularze `Dodaj zadanie` / `Dodaj absencję`. Nie powstał drugi calendar
  provider ani formularz.
- Maile i Dokumenty używają istniejących uwierzytelnionych API z limitem 6.
  Dokumenty zachowują wspólne 100 px thumbnails i internal image viewer;
  Dashboard nie pobiera pełnej skrzynki ani repozytorium dokumentów.
- Każda sekcja ma własny loading/error/empty state, a wspólne ręczne
  odświeżenie unieważnia wyłącznie read providery. Niedostępny health jest
  prezentowany jako `NIEDOSTĘPNY`, nie jako fałszywe `OFFLINE`; prywatny
  Supervisor nie jest używany jako prawda o publicznym backendzie.
- Pełna globalna aktywność pozostaje zakresem CHUNK 14. CHUNK 12 rezerwuje jej
  właściwe miejsce bez dummy entries, fake counters ani nowego activity API.
- Responsive/failure/order/navigation tests obejmują 360/390/600/1200.
  Flutter analyze PASS, focused Dashboard/Mail/Search/navigation `41/41`, full
  suite `238/238`; Android debug, Web release i Windows debug builds PASS.
  Brak urządzenia/ADB, więc physical Android smoke pozostaje `UNVERIFIED`.
  Backend read/isolated Calendar, WorkItems, Absence, Global Mail, Timeline,
  Documents i Auth regressions PASS.
- Migration: NO. Production business writes, Gmail sends, n8n changes, Vision
  jobs, Qdrant writes i release: `0` / NOT PERFORMED.

**NEXT PLANNED WORK: FOLLOW-UP CHUNK 14 — DASHBOARD LAST ACTIVITY. Do not
start without a new owner prompt.**

## [✓] FOLLOW-UP CHUNK 13 — CALENDAR / TASKS / REALIZATIONS / NOTES — COMPLETE

**Priority: P1 — MAJOR FEATURE**

Dodać Kalendarz na Dashboard i workspace `Zadania`.

Typy: task, zlecenie, realizacja, reminder, event.

Kalendarz jest centralnym operational calendar NEXT Stabil, bez integracji z
Google/System Calendar. Primary UX to miesiąc z labelami w komórkach, bounded
`+N więcej`, selected-day agenda i wspólnym presentation contract.

Pola: title, description, start, end/deadline, status, priority, assignee,
optional Client oraz optional free-text party/name. Client nie jest wymagany.

Jeżeli Client jest wybrany: widoczne linked documents, Client deep link,
timeline/activity i możliwość utworzenia `Realizacja`. Client-linked realizacja
automatycznie pojawia się w Client Details.

Notatki obsługują text, Android speech-to-text, file, image, camera, gallery i
foreground geolocation. Audio nie musi być zapisywane. Odmowa GPS nie blokuje
camera/gallery. Client-linked attachments trafiają do Client Documents z
provenance.

Absence ma osobny approval domain (`absence_requests`), a nie typ task:
vacation/day off/sick leave/other, requested/approved/rejected/cancelled,
employee self-service, Administrator review bez self-approval i range
projection bez tworzenia wiersza per day. Dashboard pokazuje live month view i
quick actions `Dodaj zadanie` oraz `Dodaj absencję`.

Android Home Screen Widget pokazuje sanitized current-month snapshot i agenda,
działa offline na last-success state i deep-linkuje do Tasks/day/item/absence.
Nie przechowuje JWT, Client/employee PII, notes ani document content i nie
wykonuje Gmail/system-calendar/background-location operations.

Migration: TAK.

Migration approval was supplied and the additive implementation is complete.

### PRODUCTION DESIGN COMPLETE (2026-08-20)

- Audyt potwierdził brak canonical Task/Calendar domain. Istniejące `projects`
  (legacy Realizacje) i `inspections` nie spełniają kontraktu opcjonalnego
  Client, assignee, priority, reminder/event i notes; pozostają kompatybilne,
  bez backfillu i bez automatycznej konwersji.
- Zaprojektowano jeden addytywny `work_items` dla `task`, `order` (UI:
  zlecenie), `realization`, `reminder` i `event`, z bounded status/priority,
  `TIMESTAMPTZ`, all-day/timezone, optional assignee/Client/party, actor
  provenance, soft archive i optimistic version.
- Notes i Document provenance używają projektowanych `work_item_notes` oraz
  `work_item_documents`; canonical Document storage, camera/gallery,
  foreground GPS, Android STT i internal image viewer są współdzielone, bez
  drugiego file store'u lub audio uploadu. Odmowa GPS nie blokuje uploadu.
- Client Details pokazuje canonical Client-linked realizations i Documents bez
  kopiowania. Timeline jest derived z WorkItem/Note i nie tworzy duplikatów w
  `client_activity_events`. Change History wymaga dodania entity types
  `work_item`, `work_item_note`, `work_item_document`; obecne actions wystarczą.
- Proposed migration `followup_calendar_tasks_20260820`, parent
  `followup_change_history_entity_types_20260820`, nie ma backfillu. Dokładne
  tabele, FK/CHECK/indexy, API, Flutter UX, rollback i test matrix opisuje
  `FOLLOWUP_CHUNK13_CALENDAR_TASKS_DESIGN.md`.
- Owner scope update rozszerzył design o primary operational month calendar,
  wspólny Dashboard/Tasks month component, `absence_requests`, bounded
  `/api/v1/calendar/month`, authorization/privacy matrix i natywny Android
  `AppWidgetProvider`/`RemoteViews`. Proposed migration tworzy teraz cztery
  tabele i dodaje także Change History entity `absence_request`; nadal nie
  istnieje plik migracji ani source implementation.
- W tym kroku nie utworzono pliku migracji ani source implementation, nie
  zmieniono schematu/produkcji i nie rozpoczęto CHUNK 12/14.

### IMPLEMENTATION COMPLETE (2026-08-20)

- Applied the approved linear migration `followup_calendar_tasks_20260820`
  (parent `followup_change_history_entity_types_20260820`). Production is at a
  single head; all four new tables are empty and existing business counts are
  unchanged. The isolated migration upgrade/downgrade/re-upgrade passed and
  downgrade refuses to destroy feature or audit rows.
- Added canonical, JWT-protected WorkItem, note, Document-link, absence and
  bounded month-projection APIs. Work items use allowlisted types/statuses/
  priorities, timezone-aware timestamps, actor provenance, optimistic version
  checks and soft archive/restore. Absences use inclusive DATE ranges,
  transaction-serialized overlap checks, employee self-service and
  Administrator review without self-approval.
- Reused canonical Documents, thumbnail/internal viewer, camera/gallery,
  foreground GPS and Polish speech-to-text. Client-linked realizations,
  Documents and derived Timeline entries reuse canonical relationships and do
  not persist duplicate Activity rows.
- Added the shared responsive operational month calendar to Dashboard and the
  Zadania workspace, with bounded labels/`+N więcej`, agenda, `Dodaj zadanie`,
  `Dodaj absencję`, list/detail/edit, Client/assignee pickers and absence review.
  This is the minimal functional Dashboard insertion; CHUNK 12 was not started.
- Added the native Android `AppWidgetProvider`/`RemoteViews` calendar widget.
  Its MODE_PRIVATE bounded snapshot contains no JWT, Client names, employee
  names, notes or document content; it retains last safe state and deep-links
  only into authenticated Tasks/calendar/form routes. No Calendar Provider,
  notification or background-location permission was added.
- Backend migration/domain/service/Auth, Timeline, Change History, Matching V2,
  Mail and Image Preview regressions pass. Flutter analyze passed, focused
  CHUNK 13/shared-field tests passed `20/20`, and the complete discovered suite
  passed `230/230`; Android debug APK compiles.
  No ADB device was connected, so physical camera/gallery/STT/GPS/widget smoke
  remains truthfully unverified.

**NEXT PLANNED WORK: FOLLOW-UP CHUNK 12 — DASHBOARD REBUILD. Do not start
without a new owner prompt. No release was performed.**

## [✓] FOLLOW-UP CHUNK 14 — DASHBOARD LAST ACTIVITY — COMPLETE

**Priority: P1**

Dependency: FOLLOW-UP CHUNK 06.

`Ostatnia aktywność` korzysta z prawdziwego activity log i pokazuje user,
timestamp, action, entity, bounded summary i deep link.

Human gate: brak przed source implementation po ukończeniu CHUNK 06; release
osobnym promptem.

Completion evidence (2026-08-20):

- Dashboard transitional copy was replaced with authenticated
  `GET /api/v1/activity/recent`, capped to `1..50` and used with `limit=8` on
  Dashboard. Every source query is independently bounded, results use canonical
  timestamps and a stable key tie-break, and actor/Client labels are batch
  loaded without N+1 queries.
- Projection precedence is explicit: `client_activity_events`, generic Change
  History, canonical merge/document-link/user-lifecycle fallbacks, then safe
  derived creation/send facts. Semantic deduplication collapses the Activity +
  Change History representation of one Client workflow-status action.
- WorkItem/note/document-link and absence activity comes only from sanitized
  Change History, not duplicate WorkItem timestamps. Normal users do not see
  User/ignored-sender admin activity or another employee's absence activity;
  Administrators receive the additional safe rows.
- DTO summaries are limited to 200 characters and never use descriptions,
  note text, absence reasons, raw audit payloads, email bodies, credentials or
  storage paths. App send activity uses only `canonical_synced` ledger facts;
  inbound mailbox traffic is deliberately excluded to avoid feed noise.
- Dashboard rows show entity icon, bounded summary, truthful actor (`System`
  when no actor exists), canonical event time, optional safe Client context and
  only verified routes. Loading/empty/error states are section-local and the
  Dashboard refresh invalidates this read provider without write side effects.
- Production read sample: 17 bounded rows considered, 8 returned, 0 duplicates
  suppressed, 0 unsafe rows suppressed for the Administrator sample, 12 SQL
  statements, 71.6 ms, with guarded business counts unchanged. EXPLAIN showed
  indexed Change History reads and current small Document/Activity scans at
  2.0/0.08 ms; no index migration is justified.
- Backend isolated/rollback regressions cover auth, role filtering, newest-first
  stable ordering, limit, dedupe, privacy, deep links and query bound. Timeline,
  Change History, WorkItems/absence, Client Search, Global Mail, Auth and Image
  Preview regressions pass. Flutter analyze PASS; focused Dashboard `10/10`
  and full discovered suite `240/240` PASS. Android, Web and Windows debug
  compilation PASS; physical Android smoke remains `UNVERIFIED` because no ADB
  executable/device was available.
- Migration: NO. Production business writes, Gmail sends, n8n changes, Vision
  jobs, Qdrant writes and release: `0` / NOT PERFORMED.

**[✓] RELEASE C — PUBLISHED — NEXT STABIL 1.0.2+23.**

Release C publishes the complete Phase C functional scope: CHUNK 13 Calendar,
WorkItems, notes/Documents, absences and Android Home Screen Widget; CHUNK 12
live operational Dashboard; and CHUNK 14 bounded, role-aware Last Activity.
Source before release was
`3e7f71a60f409185eabd0b8d89b39e4fffa51417`. Windows installer, signed Android
APK and Web build use the approved production endpoints, and public bytes
matched local SHA-256 values before the stable manifest moved to build `23`.
`minimum_version` remains `1.0.0`, so update from `1.0.2+22` is optional.
Flutter analyze, focused Phase C `23/23`, updater `10/10` and full `240/240`
pass. Production DB remains at `followup_calendar_tasks_20260820`; release-
attributable business writes, Gmail sends, n8n changes, Vision jobs and Qdrant
writes were zero. Previous `1.0.2+22` artifacts remain available for rollback.
Physical Android widget and CHUNK 13 smokes remain `UNVERIFIED` because no ADB
device was connected.

**PHASE C AND RELEASE C COMPLETE. PRE-CHUNK15 TRASH HOTFIX COMPLETE. OWNER
FLUTTER PATCH COMPLETE. CANONICAL NEXT ROADMAP ITEM: FOLLOW-UP CHUNK 15 —
ADMIN BACKUP UI. Do not start CHUNK 15 without a new owner prompt.**

## OWNER FLUTTER PATCH — CALENDAR / TASK DETAIL / REALIZATION INTEGRATION

**[✓] COMPLETE — 2026-08-21.**

- Task Detail uses the WorkItem title in the AppBar, Polish execution ranges,
  canonical Client phone/Maps actions, visible Notes and lazy Documents.
- Official `pl_PL` Material localizations make WorkItem date pickers
  Monday-first without changing timestamp, timezone, all-day or inclusive
  date-range semantics.
- The shared month calendar renders deterministic continuous week-row event
  bars, stable collision lanes and bounded `+N więcej`; agenda and native
  Android widget rows show date ranges without type-letter prefixes.
- Additive `followup_work_item_realization_link_20260821` atomically links each
  newly created realization WorkItem to one Project. No backfill was performed;
  the owner-created legacy realization remains unchanged and unlinked.
- One canonical Document row/file is projected through Client, WorkItem and
  linked Project; cross-Client and cross-Project re-parenting fails closed.
- Client Details conditionally shows Realizacja last, with multiple bounded
  projects, canonical Documents and WorkItem/Project deep links.
- Isolated migration and realization tests PASS; Flutter analyze PASS, focused
  tests PASS, full suite 250/250 PASS; Android/Web/Windows debug builds PASS.
  Production acceptance created no business rows and made no Gmail, Vision,
  Qdrant, n8n or release changes.

## PRE-CHUNK15 HOTFIX — ADMIN TRASH / 7-DAY RETENTION

**[✓] COMPLETE — SCHEMA + TRASH/RESTORE + 7-DAY SCHEDULER + EXACT-OWNERSHIP
QDRANT PURGE.**

Owner inserted this bounded gate immediately before CHUNK 15. The audited
design is recorded in `FOLLOWUP_ADMIN_TRASH_RETENTION_DESIGN.md`. Normal delete
will become a server-timestamped seven-day Trash lifecycle for Documents,
Clients and Users with Administrator-only Settings UI, same-ID restore,
fail-closed permanent purge and surviving Change History evidence.

The FK audit rules out blind SQL hard delete. Clients and Users require
irreversible non-active anonymized tombstones to preserve historical identity;
Documents require content/file purge plus a minimal row tombstone so WorkItem
and link provenance survive. Vectorized Documents remain blocked unless exact
Qdrant point deletion receives separate approval. Six legacy soft-deleted
Clients and one inactive User are not backfilled and never become purge
eligible automatically.

Migration `followup_admin_trash_retention_20260820` (parent
`followup_calendar_tasks_20260820`) is applied in production. It adds the
canonical `trash_entries` lifecycle ledger, entity visibility/tombstone
markers, User token versioning and the minimal Change History CHECK extensions.
There was no backfill: the six legacy soft-deleted Clients and one legacy
inactive User remain outside the Trash lifecycle, and the production Trash
queue was empty after activation.

Automated purge uses the existing Windows Task Scheduler operational pattern,
never n8n. `NEXT Stabil - Trash Purge` is enabled every four hours with a
singleton guard, maximum 100 entries per run, row-lock revalidation,
per-entity failure isolation and no early purge. Its controlled production
acceptance runs saw zero eligible entries and performed zero purges.

The separately approved vector purge now derives the exact bounded point set
from canonical `document_chunks`, verifies both DB `vector_id` and Qdrant
`document_id`/`chunk_id` ownership, blocks foreign or untracked points, deletes
only explicit verified IDs, and confirms their absence before Document bytes,
content or chunks can be purged. Missing exact points are treated as an
idempotent prior-delete state; Qdrant outage or ownership drift leaves the
Document safely blocked. Destructive Qdrant tests refuse the production
collection and use a temporary `ai_lab_test_*` collection. Production remained
at 57 points during empty-queue acceptance.

Test-safety follow-up: updated mutating/isolated suites validate `POSTGRES_DB`
before application engine import and verify the connected PostgreSQL
`SELECT current_database()` through one shared guard. Production `ai_lab`,
unsafe test names and configuration/connection mismatches are rejected;
`DATABASE_URL` cannot select an isolated database for these tests.

**TRASH HOTFIX AND OWNER FLUTTER PATCH COMPLETE. CANONICAL NEXT ROADMAP ITEM:
FOLLOW-UP CHUNK 15 — ADMIN BACKUP UI.** Do not start CHUNK 15 without a new
owner prompt.

## OWNER PATCH RELEASE — NEXT STABIL 1.0.2+24

**[✓] PUBLISHED — 2026-08-21. INTERIM RELEASE BETWEEN RELEASE C AND PHASE D;
THIS IS NOT RELEASE D.**

The stable Windows, signed Android and live Web channels now publish the
completed Admin Trash / seven-day retention hotfix and Calendar / Task Detail /
Realization owner patch. User-visible scope includes Administrator `Kosz`,
recoverable deletion, compact Task Detail with Client call/Maps actions, Polish
Monday-first date selection, continuous multi-day calendar bars, improved
Android calendar widget presentation, canonical realization WorkItem-to-Project
linkage and one-Document Client/WorkItem/Project projections.

Release source was `d06707cef5da0e94cbc92e9c9843d67cdbcac7c6` and production
DB remains at `followup_work_item_realization_link_20260821`. Flutter analyze,
focused owner-patch/Trash `17/17`, updater `10/10` and full `250/250` pass.
Public Windows, Android and Web bytes matched their locally validated SHA-256
values before the stable manifest moved to build `24`; `minimum_version`
remains `1.0.0`, so update from `1.0.2+23` is optional. Release-attributable
business writes, Gmail sends, n8n changes, Vision jobs and Qdrant writes were
zero. The owner-created legacy realization remains unchanged and unlinked;
physical Android/widget smoke remains `UNVERIFIED` because ADB is unavailable.

Canonical next roadmap item remains **FOLLOW-UP CHUNK 15 — ADMIN BACKUP UI —
NOT STARTED**.

## POST-1.0.2+24 CONSISTENCY HOTFIX

**[✓] CLIENT DOCUMENT TRASH + ACTIVE USER CLEANUP + LEGACY REALIZATION
REPAIR — COMPLETE — 2026-08-21.**

- Client Details Documents now reuse the canonical Administrator-only Document
  Trash confirmation/API path. Successful Trash invalidates Client, global,
  Dashboard, WorkItem and Project projections; responsive overflow actions and
  pagination clamping prevent stale rows or invalid page ranges. No production
  Document was trashed for acceptance.
- The default Administrator User Management endpoint is active-only. Inactive,
  trashed and purged Users stay out of the manageable-user list while
  recoverable entries remain in Settings → Kosz.
- Exact test User `phase2f_103833` (User ID `2`) was inactive and not previously
  in Trash. The owner-approved canonical lifecycle created Trash entry `2`, set
  `trashed_at`, incremented `auth_version` to `1`, and retained same-ID restore
  through the exact seven-day deadline. No other User was modified.
- The one exact legacy realization WorkItem `fundament 600kg` (WorkItem ID `1`,
  Client `Szymon Pastuszak`, 2026-08-25–2026-08-28) had no matching Project.
  One transaction created canonical Project `1080`, linked `project_id`, and
  wrote safe WorkItem Change History. No broad backfill or unrelated
  WorkItem/Project mutation occurred.
- The repair service is Administrator-only, row-locked, exact-match aware and
  idempotent: an already linked WorkItem returns its existing Project and an
  ambiguous matching Project set fails closed. New realization atomic
  create/edit/status/archive/restore behavior remains verified.
- Backend isolated Trash/realization/Auth/History/Activity/Search regressions
  PASS. Flutter analyze PASS, focused consistency tests `45/45` PASS and the
  full discovered suite `252/252` PASS. DB head remains
  `followup_work_item_realization_link_20260821`; release remains
  `NEXT Stabil 1.0.2+24` and no release was performed.

Canonical next roadmap item remains **FOLLOW-UP CHUNK 15 — ADMIN BACKUP UI —
NOT STARTED**. A separate owner prompt is required; a later `1.0.2+25`
publication is also separately gated.

## HOTFIX RELEASE — NEXT STABIL 1.0.2+25

**[✓] PUBLISHED — 2026-08-21. POST-1.0.2+24 CONSISTENCY HOTFIX; THIS IS NOT
RELEASE D.**

- Stable Windows, signed Android and live Web publish the canonical Client
  Documents Trash action, active-only User Management list and repaired
  WorkItem-to-Project realization linkage.
- Exact test User `phase2f_103833` remains inactive and recoverable in Trash;
  the release did not restore or otherwise modify it. Exact WorkItem
  `fundament 600kg` remains linked to canonical Project `1080`.
- Flutter analyze, focused hotfix/updater tests and the full discovered
  `252/252` suite pass. Production DB remains at
  `followup_work_item_realization_link_20260821` with one Alembic head and no
  release migration.
- Public Windows, Android and Web bytes match their locally verified hashes.
  `minimum_version` remains `1.0.0`, so update from `1.0.2+24` is optional;
  `1.0.2+24` and `1.0.2+23` artifacts remain available for rollback.
- Release-attributable business writes, Gmail sends, n8n changes, Vision jobs
  and Qdrant writes are zero. Physical Android smoke is `UNVERIFIED` because
  ADB is unavailable.

Canonical next roadmap item remains **FOLLOW-UP CHUNK 15 — ADMIN BACKUP UI —
NOT STARTED**. A new owner prompt is required.

## OWNER MICRO-FIX — CLIENT DETAILS SECTION EDITING

**[✓] COMPLETE — 2026-08-21. NO RELEASE.**

- Client Details retains the complete `Edytuj klienta` flow and adds local
  `Edytuj` actions for the client name, basic data, registration data,
  contacts, addresses and system information.
- Each local action exposes only its bounded field set. Contact editing keeps
  multiple phone/e-mail entries and primary selection, address editing uses
  the canonical structured address fields, and system editing exposes only
  the business added date.
- Section saves reuse the existing partial Client update contract, validation
  and audit path, then refresh Client Details and the Clients projection. No
  backend change or database migration was required.
- Flutter analyze passes, focused Client editing tests pass `26/26`, and the
  clean discovered Flutter suite passes `260/260`, including 360/390/600/1200
  responsive coverage. No production business write or release occurred.

Canonical next roadmap item remains **FOLLOW-UP CHUNK 15 — ADMIN BACKUP UI —
NOT STARTED**. CHUNK 16 is also not started.

## FOLLOW-UP CHUNK 15 — ADMIN BACKUP UI

**Priority: P1**

Settings → admin-only `Backup`, maksymalnie 10 harmonogramów.

Każdy: name, enabled, cadence, time, destination, source/scope, last run, next
run i result. Allowlist scope: Full/System checkpoint, Database, Documents,
Qdrant i n8n/config. Zakaz arbitrary filesystem backup.

`Wykonaj backup teraz` wymaga confirmation, concurrency guard, progress,
manifest/hash verification i audit. Path validation blokuje repo, active data
dir, traversal oraz brak wolnego miejsca.

Human gate: dla Task Scheduler wymagany
`FOLLOWUP_BACKUP_SCHEDULER_CHANGE_APPROVAL_REQUIRED`.

## FOLLOW-UP CHUNK 16 — ADMIN KNOWLEDGE BASE

**Priority: P1**

Admin-only `Baza wiedzy`: building standards, norms, technical datasheets,
manuals, producer materials, formulas i reference calculations.

Metadata: source, publisher, version, effective date, category, tags oraz
current/superseded. Processing: extraction, OCR, optional Vision, search i
citations.

Nie mieszać customer documents i Knowledge Base bez jawnego source type lub
namespace.

Human gate: dla Qdrant wymagany
`FOLLOWUP_KNOWLEDGE_BASE_VECTOR_WRITE_APPROVAL_REQUIRED`.

## FOLLOW-UP CHUNK 17 — LOCAL ANDROID AI / CALCULATION ENGINE R&D

**Priority: P2 / R&D**

Cel: zbadać lokalny Android AI jako pomocniczy silnik obliczeniowy.

Preferowany przepływ:

1. NEXT Stabil pobiera wzór/wiedzę z Knowledge Base.
2. Wyciąga dane z Document/Client/Inspection/Data Repository.
3. Używa Vision tylko, jeśli jest wymagane.
4. Usuwa PII, Client i location.
5. Tworzy suchy problem: formula, variable definitions, values, units.
6. Wysyła wyłącznie suchy problem do lokalnego Android AI.
7. Wykonuje obliczenie dwa razy niezależnie.
8. Porównuje wyniki.
9. Disagreement uruchamia deterministic verification lub third route.
10. Pokazuje formula, variables, result, units, assumptions i evidence.

Preferować deterministic calculation engine, a LLM jako parser/guide. Nie
fine-tuning norm, jeśli retrieval wystarczy.

Benchmark: minimum 30 kontrolowanych obliczeń, unit checking, two-pass
agreement, brak PII, offline verification, latency i timeout/chunk strategy.

Human gate: R&D benchmark najpierw; żadnego production enablement bez osobnej
decyzji.

## FOLLOW-UP CHUNK 18 — SEMANTIC SEARCH COVERAGE V2

**Priority: P2**

Baseline: 57 Qdrant points, 11/5,915 Documents, 0 client-scoped usable vectors,
1,024 dimensions.

Najpierw design i quality benchmark. Plan: `qwen3-embedding:0.6b`, proper
`client_id`, checksum, version, dedupe, checkpoint, batches i snapshot przed
write. Backfill tylko, jeśli benchmark pokaże wartość ponad lexical/global
search.

Human gate: `FOLLOWUP_QDRANT_BACKFILL_APPROVAL_REQUIRED`.

## FOLLOW-UP CHUNK 19 — QDRANT RESTORE PROOF

**Priority: P2**

Domknąć `QDRANT_RESTORE_DRILL_BLOCKED_BY_ISOLATION` na Qdrant 1.18.3,
oddzielnym volume i nieprodukcyjnym porcie/network. Restore snapshot, verify 57
points, dimensions 1,024 i payload integrity; usunąć isolated target dopiero po
jednoznacznym potwierdzeniu jego ścieżek. Bez upgrade.

Human gate: osobne approval dla izolowanego runtime/cleanup; produkcyjny Qdrant
pozostaje read-only.

## FOLLOW-UP CHUNK 20 — SECURITY HARDENING V2

**Priority: P1**

Zakres A — public headers: nosniff, Referrer-Policy, framing, staged HSTS oraz
CSP Report-Only first. Zweryfikować Flutter Web, CanvasKit/WASM, workers,
service worker, fonts, downloads i API.

Human gate: `FOLLOWUP_PUBLIC_SECURITY_HEADERS_APPROVAL_REQUIRED`.

Zakres B — login rate limiting: IP/account-aware, bez user enumeration, z
cooldown, reverse-proxy/Tailscale awareness, ochroną przed lockout DoS i
auditem.

Human gate: public/auth behavior change wymaga osobnego approval po projekcie i
compatibility testach.

## FOLLOW-UP CHUNK 21 — WINDOWS BUILD REPRODUCIBILITY

**Priority: P1**

Problem: NSIS/`makensis` jest niedostępny. Ustalić dokładną wersję NSIS,
oficjalne źródło, checksum, build script i dokumentację. Nie republish +21.

Human gate: `FOLLOWUP_HOST_TOOL_INSTALL_APPROVAL_REQUIRED`.

## FOLLOW-UP CHUNK 22 — PHYSICAL ANDROID ACCEPTANCE

**Priority: P2**

Po udostępnieniu ADB/device: install/update, login, Clients, Search, Mail,
Documents, Inspection, GPS, camera/gallery, STT, Vision, Agent, Back, restart
persistence i updater. Bez urządzenia wynik pozostaje UNVERIFIED.

Human gate: dostęp operatora do urządzenia; brak zmian danych poza
kontrolowanymi fixtures.

## FOLLOW-UP CHUNK 23 — ENV SECRET ESCROW

**Priority: P1**

Domknąć manual DR requirement bez `.env` w Git. Użyć encrypted vault/media,
ACL, separate recovery key, inventory version/HEAD/date, periodic controlled
read verification i aktualizacji po rotation.

Human gate: osobna zgoda operacyjna na escrow/rotation; wartości nigdy nie
trafiają do raportu ani repo.

## FOLLOW-UP CHUNK 24 — BACKUP RETENTION + ALERTING

**Priority: P2**

Retention proposal: 7 daily, 5 weekly, 12 monthly.

Human gate: dla deletion wymagany
`FOLLOWUP_BACKUP_RETENTION_DELETE_APPROVAL_REQUIRED`.

Alerting obejmuje backup stale/failure, disk low, DB down, Vision
AUTH_REQUIRED/UI_CHANGED, Agent orphan, migration mismatch i n8n down. Kanał
zewnętrzny wymaga osobnego approval.

## FOLLOW-UP CHUNK 25 — N8N RETENTION

**Priority: P2**

Audyt bieżącej retencji historii wykonań n8n. Żadnego cleanup przed approval.

Human gate: `FOLLOWUP_N8N_RETENTION_APPROVAL_REQUIRED`.

## FOLLOW-UP CHUNK 26 — CONTACT PERSON DECISION

**Priority: P2**

Historyczny CHUNK 7B. Najpierw decyzja:

- A: istniejący multi-contact model jest wystarczający — Contact Person staje
  się OBSOLETE,
- B: dodać encję Contact Person z name, role, phones, emails, preferred,
  decision maker, notes, provenance i Client relationship.

Human gate: decyzja produktowa i ewentualny schema migration approval. W tym
CHUNK-u najpierw decision record, nie implementacja.

## FOLLOW-UP CHUNK 27 — UNRELATED POSTGRES:10 OWNERSHIP

**Priority: P2**

Read-only audit container name, labels, mounts, ports, age, project ownership i
data. Bez stop/delete.

Human gate: owner/data decision przed jakąkolwiek zmianą kontenera.

## FOLLOW-UP CHUNK 28 — STORAGE PROVENANCE / ORPHAN CLEANUP

**Priority: P3**

Baseline: 25 unreferenced files. Każdy sklasyfikować jako valid artifact,
failed-ingestion orphan, duplicate, synthetic albo unknown.

Human gate: `FOLLOWUP_STORAGE_CLEANUP_APPROVAL_REQUIRED`.

## FOLLOW-UP CHUNK 29 — OLD VISION MODELS / PILOT CLEANUP

**Priority: P3**

Audit: `qwen2.5vl:3b`, `gemma3:4b`, `qwen3.5:9b` oraz
`C:\Ollama-Vision-Pilot`.

Human gate: `FOLLOWUP_OLD_MODEL_CLEANUP_APPROVAL_REQUIRED`.

## FOLLOW-UP CHUNK 30 — HISTORICAL DATA QUALITY / CLEANUP

**Priority: P3**

Zebrać identity quality debt, name/phone artifacts, old notes/transcripts,
legacy links, failed processing i duplicates. Nie używać qwen3.5 reconstruction.

Proces: audit → dry-run → report → human approval → bounded apply → post-audit.

Human gate: `FOLLOWUP_HISTORICAL_DATA_CLEANUP_APPROVAL_REQUIRED`.

## FOLLOW-UP CHUNK 31 — VERSION ENDPOINT / DEBUG METADATA

**Priority: P2**

Audyt `/version`; stable manifest pozostaje canonical. Zdecydować: minimize,
remove, admin/private albo align metadata. Nie ujawniać niepotrzebnych internal
paths/debug info publicznie.

Human gate: public API/config change i ewentualny release osobnym approval.

## FOLLOW-UP CHUNK 32 — FINAL UX CONSISTENCY

**Priority: P2**

Po feature chunks audytować Dashboard, Clients, Client Details, Contacts,
Timeline, Mail, Calendar, Tasks, Documents, Inspections, AI, Settings, Backup,
Knowledge Base i History.

Sprawdzić naming, dates, statuses, permissions, loading, errors, responsive,
Back, deep links i empty states.

Human gate: brak dla audytu; fixes i release zgodnie z ich ryzykiem i osobnymi
promptami.

## Recommended execution order

### PHASE A — PRODUCTION FIXES

1. CHUNK 01 — Document anomalies
2. CHUNK 02 — Client status consistency
3. CHUNK 03 — Client added date
4. CHUNK 04 — Client search
5. CHUNK 08 — Candidate 406 / merge
6. CHUNK 11 — Email ↔ Client matching

### PHASE B — ACTIVITY / COMMUNICATION

7. CHUNK 06 — Client activity log
8. CHUNK 07 — Admin history
9. CHUNK 09 — Mail workspace
10. CHUNK 10 — Mail refresh
11. CHUNK 05 — Filters / ignored senders

### PHASE C — WORK MANAGEMENT

12. CHUNK 13 — Calendar / Tasks / Realizations / Notes
13. CHUNK 12 — Dashboard
14. CHUNK 14 — Last Activity

### PHASE D — ADMIN / KNOWLEDGE

15. CHUNK 15 — Backup UI
16. CHUNK 16 — Knowledge Base
17. CHUNK 26 — Contact Person decision

### PHASE E — AI / SEARCH

18. CHUNK 17 — Android AI R&D
19. CHUNK 18 — Semantic Search V2
20. CHUNK 19 — Qdrant restore

### PHASE F — SECURITY / OPERATIONS

21. CHUNK 20 — Security
22. CHUNK 21 — Windows reproducibility
23. CHUNK 22 — Android physical
24. CHUNK 23 — Env escrow
25. CHUNK 24 — Retention / Alerts
26. CHUNK 25 — n8n retention
27. CHUNK 31 — Version endpoint

### PHASE G — CLEANUP

28. CHUNK 27 — Unrelated PostgreSQL ownership
29. CHUNK 28 — Storage provenance
30. CHUNK 29 — Old Vision models/pilot
31. CHUNK 30 — Historical data quality

### PHASE H — POLISH

32. CHUNK 32 — Final UX consistency

## Release grouping

Nie wykonywać release po każdym micro-fixie.

- **Release A** — Client correctness, search i Candidate.
- **Release B** — Activity i Mail.
- **Release C** — Calendar, Tasks i Dashboard.
- **Release D** — Backup UI i Knowledge Base.
- **Release E** — Security/operations, jeśli zmieniają client/runtime artifacts.

Każdy release wymaga osobnego promptu.

## Global data-safety report contract

Każdy raport FOLLOW-UP CHUNK musi zawierać:

```text
DATA SAFETY
- business writes:
- synthetic writes:
- DB migration:
- historical rows touched:
- Qdrant writes:
- n8n changes:
- Vision jobs:
- emails sent:
- backup deletions:
- filesystem cleanup:
```

## Active next work

**PRE-CHUNK15 TRASH HOTFIX AND OWNER CALENDAR/REALIZATION PATCH COMPLETE.**

Current gate: `FOLLOW-UP CHUNK 15 — ADMIN BACKUP UI`.
CHUNK 15 is NOT STARTED and retains its own scheduler/backup execution gates.
