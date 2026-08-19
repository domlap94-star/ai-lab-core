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

## FOLLOW-UP CHUNK 05 — CLIENT FILTERS / HIDE STATUS / IGNORED MAIL SOURCES

**Priority: P1**

Zakres A: filtr `Nie pokazuj` dla jednego lub wielu statusów klientów.

Zakres B: admin-only globalna konfiguracja `Ignorowane adresy i domeny`:
add email/domain, list, remove i audit. Ignorowane źródło nie usuwa historii;
wpływa wyłącznie na future ingestion/routing.

Migration: prawdopodobna.

Human gate: osobny schema/migration approval wymagany po audycie projektu
danych; żadnej konfiguracji produkcyjnej bez jawnego apply approval.

## FOLLOW-UP CHUNK 06 — CLIENT ACTIVITY LOG + TIMELINE V2

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

## FOLLOW-UP CHUNK 07 — ADMIN CHANGE HISTORY

**Priority: P1**

Admin-only zakładka `Historia zmian`: kto, kiedy, entity, ID, action, changed
fields oraz bounded before/after.

Zakres obejmuje Client edits, status, dates, contacts, addresses, merges,
Candidate promotion, settings, backup settings, ignored email config oraz
tasks/calendar.

Nie zapisywać passwords, tokens, secrets, full emails ani full documents.

Human gate: schema/migration approval po projekcie audytu; trwały log nie może
powstać jako niekontrolowane pole JSON.

## [~] FOLLOW-UP CHUNK 08 — DIAGNOSTIC COMPLETE / MERGE AUDIT MIGRATION APPROVAL REQUIRED

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

The existing Candidate state model already supports `merged` and
`matched_client_id`, but existing audit tables cannot persist the required actor,
target and bounded field/relation effects. Design and evidence are recorded in
`FOLLOWUP_CHUNK08_CANDIDATE_406_MERGE_DIAGNOSIS.md`. Required next gate:
`FOLLOWUP_CANDIDATE_MERGE_AUDIT_MIGRATION_APPROVAL_REQUIRED`. No merge/apply,
migration, frontend change or release was performed. Active work remains CHUNK
08 until the audited merge flow is implemented and verified.

## FOLLOW-UP CHUNK 09 — GLOBAL MAIL WORKSPACE

**Priority: P1**

Dodać `Maile` do menu i Dashboard.

Etap 1 — read: inbox/list, search, filters, threads, sender, recipients, date,
subject, body, attachments, Client linking, deep links oraz read/unread, jeśli
obecna integracja bezpiecznie to obsługuje.

Etap 2 — write: compose, reply, forward. Wysyłanie jest external side effect.
Agent nadal nie może autonomicznie wysyłać emaili.

Human gate: przed write wymagany
`FOLLOWUP_EMAIL_SEND_APPROVAL_REQUIRED`.

## FOLLOW-UP CHUNK 10 — MAIL REFRESH / RECONCILIATION

**Priority: P1**

Dodać `Odśwież` w globalnym Mail workspace i mailach Client. Funkcja ma
odnajdywać wiadomości pominięte przez standardową synchronizację.

Preferowana architektura: standardowy n8n ingestion pozostaje, manual trigger
wykonuje bounded reconciliation z checkpoint/idempotency/dedupe. Automatyczny
daily reconciliation można rozważyć dopiero po audycie.

Acceptance: brak duplikatów.

Human gate: zmiana n8n/schedule lub produkcyjny reconciliation wymaga osobnego
approval.

## FOLLOW-UP CHUNK 11 — EMAIL ↔ EXISTING CLIENT MATCHING V2

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

## FOLLOW-UP CHUNK 12 — DASHBOARD REBUILD

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

## FOLLOW-UP CHUNK 13 — CALENDAR / TASKS / REALIZATIONS / NOTES

**Priority: P1 — MAJOR FEATURE**

Dodać Kalendarz na Dashboard i workspace `Zadania`.

Typy: task, zlecenie, realizacja, reminder, event.

Pola: title, description, start, end/deadline, status, priority, assignee,
optional Client oraz optional free-text party/name. Client nie jest wymagany.

Jeżeli Client jest wybrany: widoczne linked documents, Client deep link,
timeline/activity i możliwość utworzenia `Realizacja`. Client-linked realizacja
automatycznie pojawia się w Client Details.

Notatki obsługują text, Android speech-to-text, file, image, camera, gallery i
foreground geolocation. Audio nie musi być zapisywane. Odmowa GPS nie blokuje
camera/gallery. Client-linked attachments trafiają do Client Documents z
provenance.

Migration: TAK.

Human gate: `FOLLOWUP_CALENDAR_TASKS_MIGRATION_APPROVAL_REQUIRED`.

## FOLLOW-UP CHUNK 14 — DASHBOARD LAST ACTIVITY

**Priority: P1**

Dependency: FOLLOW-UP CHUNK 06.

`Ostatnia aktywność` korzysta z prawdziwego activity log i pokazuje user,
timestamp, action, entity, bounded summary i deep link.

Human gate: brak przed source implementation po ukończeniu CHUNK 06; release
osobnym promptem.

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

**FOLLOW-UP CHUNK 08 — CANDIDATE ACCEPT 406 + MERGE**

FOLLOW-UP CHUNK 04 został zakończony wspólnym Client matching primitive dla
Clients i Global Search, bez zmiany publicznych endpointów, migracji ani
release. Zgodnie z kolejnością Phase A następną pracą jest CHUNK 08; CHUNK 05
pozostaje w późniejszej fazie Communication.
