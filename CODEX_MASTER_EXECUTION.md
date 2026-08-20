# AI-Lab / NEXT Stabil — Codex Master Execution

Stan bazowy: 2026-08-14, commit wejściowy `5700681`. Dokument rozbija
`AI_LAB_MASTER_PLAN.txt` na małe checkpointy. Statusy wynikają z kodu, testów i
odczytowego audytu bazy, nie ze starych checkboxów.

## ACTIVE POST-PROJECT ROADMAP

**`AI_LAB_FOLLOWUP_PLAN.md`** jest aktywnym źródłem kolejności dalszych prac po
release 1.0.2+22.

- `AI_LAB_MASTER_PLAN.txt` jest zakończonym, historycznym masterplanem głównej
  implementacji.
- `FINAL_SYSTEM_AUDIT.md` jest kanonicznym audytem aktualnego stanu.
- `AI_LAB_FOLLOWUP_PLAN.md` definiuje aktywne priorytety, zależności i human
  gates dla wszystkich dalszych fixów i rozszerzeń.

Przed rozpoczęciem każdego nowego zadania rozwojowego po 1.0.2+21 należy:

1. przeczytać `AI_LAB_FOLLOWUP_PLAN.md`,
2. odnaleźć żądany FOLLOW-UP CHUNK,
3. zastosować jego priorytet, zależności i human-gate requirements,
4. nie wykonywać po cichu późniejszych CHUNK-ów,
5. zatrzymać się na każdym jawnym approval gate.

Current execution state:
**FOLLOW-UP CHUNK 12 — DASHBOARD REBUILD — COMPLETE.** Dashboard now uses the
canonical CHUNK 13 month/tasks projection, bounded real Mail and Documents,
and section-isolated read states in the required operational order. Legacy
Dashboard placeholders and the `Sprawy` menu item are removed while the legacy
route remains compatible. `Ostatnia aktywność` is a truthful compact hand-off
to CHUNK 14, and public backend health is the final section without treating an
unreachable private Supervisor as system offline. No migration, production
business write, Gmail send, n8n change, Vision job, Qdrant write or release was
performed.
Release B remains published as NEXT Stabil 1.0.2+22. Web, Windows and
Android artifacts use the production endpoints; public artifact hashes match
the stable manifest, `minimum_version` remains `1.0.0`, and the previous
`1.0.2+21` artifacts remain available for rollback. Release validation passed
the backend regression matrix, Flutter analyze, the full discovered Flutter
suite (`223/223`), focused updater/version tests (`16/16`) and the public Web
login smoke. No business-data write, Gmail send, migration, n8n workflow
change, Vision job or Qdrant write was performed by the release.

**NEXT PLANNED WORK: FOLLOW-UP CHUNK 14 — DASHBOARD LAST ACTIVITY. Do not start
CHUNK 14 or a release without a new owner prompt.** The approved
`followup_calendar_tasks_20260820` migration is applied at a single production
head. The implementation provides canonical WorkItems/notes/Documents,
absence approval, shared Dashboard/Tasks month projection and a sanitized
native Android Home Screen Widget. Production feature tables remain empty;
there was no backfill or existing business-row rewrite.

**FOLLOW-UP CHUNK 10 — MAIL REFRESH / RECONCILIATION + IMAGE PREVIEW —
COMPLETE.** A shared `DocumentImageThumbnail` and
`InternalImageViewer` now serve Documents, Client Documents, Document/Vision
details, Client Mail and Global Mail attachments. JPEG/PNG/WebP render as lazy
100-logical-pixel previews and open inside NEXT Stabil with fit/zoom/pan/Back;
non-images retain their prior behavior and HEIC/HEIF are explicitly unsupported
without a new conversion subsystem. The JWT-protected bounded 200 px thumbnail
endpoint reuses canonical Document authorization/storage resolution, validates
decoded MIME, handles EXIF orientation and creates no persistent cache or DB
state. Backend thumbnail `11/11`, Document/Vision/Mail regressions, Flutter
analyze and media regressions pass. Manual Global/Client Mail refresh now uses
a Header-Auth protected, unscheduled n8n read adapter and bounded 30-day/1000
message reconciliation. Exact provider-ID dedupe, canonical ImportIngest,
Matching V2, attachment ingest and a rich actor/plan-bound HMAC ensure missing
mail is ingested once and any Candidate/Client/document plan drift fails before
write. Final production dry-runs are clean at 30 and 7 days; recovery `13/13`,
parity `8/8`, focused Flutter `37/37` and full `214/214` pass.

**FOLLOW-UP CHUNK 05 — FILTERS / IGNORED SENDERS + USER MANAGEMENT POLISH —
COMPLETE.** Server-side multi-status exclusions, exact ignored email/domain
rules with canonical historical preservation, responsive User Management and
safe audited User Edit are complete. Approved migrations
`followup_ignored_mail_sources_20260820` and
`followup_change_history_entity_types_20260820` are applied; production ignored
rules and Change History remain empty. Flutter analyze, focused `51/51` and
full `260/260` pass with the backend regression matrix.

**RELEASE B: PUBLISHED IN NEXT STABIL 1.0.2+22.** Do not start CHUNK 13
automatically.
CHUNK 07 jest kompletny w source i DB: addytywna tabela
`change_history_events`, strict bounded sanitizer, atomowe audyty bieżących
Client/Candidate writes, read-only projekcje audytów domenowych oraz admin-only
API/UI przeszły isolated migration round-trip, regresje backendowe i pełne
Flutter 191/191. Backfill i realne acceptance writes nie były wykonywane;
release pozostaje NEXT Stabil 1.0.2+21. Nie rozpoczynać CHUNK 09 bez osobnego
promptu wykonawczego; wysyłanie maili nadal wymaga jawnego
`FOLLOWUP_EMAIL_SEND_APPROVAL_REQUIRED`.

## Zasada kompatybilności wdrożonych klientów

DEPLOYED BINARIES ARE API CONSUMERS. Zmiana aktualnego source nie oznacza, że
ostatnia stabilna aplikacja Windows, Android, live Web ani integracje/importy
zostały już zaktualizowane. Istniejącego publicznego response shape nie wolno
łamać bez versioned/additive endpointu, compatibility layer albo jawnej
strategii release/migracji. Legacy endpoint może zostać usunięty dopiero, gdy
minimum supported app version gwarantuje brak wspieranych konsumentów starego
kontraktu.

## CURRENT RELEASE — NEXT STABIL 1.0.2+22

- CHUNK 13 — BUSINESS ASSISTANT: RELEASED. Endpoint i UI są globalnym,
  read-only copilotem; deterministic analytics, Global Search retrieval,
  Client AI reuse, llama3.2 i deterministyczne citations pozostają bez
  business actions i bez conversation persistence.
- INSPECTION FIELD UX: RELEASED. Foreground location może zostać zapisana
  jawnie w szczegółach wizji; camera/gallery intake próbuje dołączyć aktualny
  GPS i nigdy nie blokuje uploadu przy odmowie. Ręczne pola współrzędnych
  usunięto z formularzy.
- Notatki wizji są edytowane inline, autosave po 800 ms jest serializowany i
  flushowany przy Back. Android SpeechRecognizer dopisuje transkrypcję pl-PL
  do tego samego pola. Audio nie trafia do CRM ani backendu; nie deklarujemy
  gwarancji offline systemowego recognizera.
- Flutter analyze PASS; pełny suite 146/146 PASS. Backend release regressions
  50/50 PASS, focused Business Assistant/Inspection 18/18 PASS. DB migration:
  NO; revision pozostaje `inspectclient_20260818 (head)`.
- Web/Windows/Android 1.0.2+19: PUBLISHED; minimum_version 1.0.0. Fizyczny
  Android GPS/camera/STT smoke: UNVERIFIED (brak urządzenia ADB).
- CHUNK 14 — TECHNICAL AI: RELEASED. Read-only
  Technical mode reuses Global Search, Client AI and existing vectors with
  strict Client/Inspection scoping, deterministic citations and explicit
  facts / hypotheses / missing-data sections. No visual/photo analysis or OCR
  was implemented. Web, Windows and Android use the production API URL;
  semantic coverage remains limited to the existing 57 chunks / 11 documents
  and no vector backfill was performed.
- CHUNK 15 — VISION / MULTIMODAL: RELEASED IN NEXT STABIL 1.0.2+20.
  Deterministic VisionNeedClassifier klasyfikuje każdy rzeczywiście nowy
  Document, a wymagane obrazy/strony mogą przejść przez prywatny supervisor i
  izolowany ChatGPT Temporary Chat browser worker. Wynik V1 jest walidowany i
  używany przez Technical AI z cytowaniem oryginalnego źródła. Historyczne
  Documents pozostają on-demand, bez backfillu; OpenAI API, local Vision,
  image embeddings i Qdrant writes nie są używane. Produkcyjna automatyzacja
  jest aktywna dla nowych Documents; historia pozostaje on-demand bez
  backfillu. Temporary Chat podlega aktualnej polityce retencji OpenAI.
- CHUNK 16 — AGENT: RELEASED IN NEXT STABIL 1.0.2+21. The JWT-protected
  `/api/v1/ai/agent/ask` orchestrates a deny-by-default allowlist of bounded
  application-service reads with `llama3.2`, deterministic source mapping,
  strict Client/Inspection scope and sanitized persistent execution audit.
  Hard limits are 5 planner rounds, 8 calls and 180 seconds. Write tools,
  shell/SQL, Docker/supervisor control, general browser access, live Vision
  triggers and conversation persistence are absent.
- CHUNK 17 — PRODUCTION HARDENING: COMPLETE / VERIFIED. Known-good service
  images are pinned without upgrades; protected backup, isolated PostgreSQL/
  storage/n8n restore and migration roundtrip drills passed. The daily 03:00
  backup task and a controlled host reboot recovery proof passed, including
  synthetic Vision and read-only Agent smokes. Residual items are explicit:
  public security headers are deferred pending a separate compatibility
  approval, Qdrant isolated restore remains technically blocked on 1.18.3,
  protected environment-secret escrow is manual, and physical Android final
  smoke is unverified without ADB.
- MASTERPLAN IMPLEMENTATION COMPLETE — FINAL SYSTEM AUDIT COMPLETE. Canonical
  reconciliation, residual-risk register and evidence are in
  `FINAL_SYSTEM_AUDIT.md`.
- LOGIN / SESSION HOTFIX: RELEASED in 1.0.2+18. The Login page remains mounted
  during authentication, errors are user-facing, token persistence is read
  back after save, and stale 401 responses are generation-scoped. The +17
  Web/Windows/Android outputs accidentally used development API defaults;
  +18 was rebuilt with the production API and private supervisor URLs.

## Reconciliation stanu

| Obszar | Stan | Dowód / luka |
|---|---|---|
| Auth, role, wymuszona zmiana hasła | DONE | JWT, `User.role`, `must_change_password`, admin API i Flutter flow; live head to `followup_clientdate_20260819`. |
| Flutter Windows / Android / Web | DONE | produkcyjne platformy i frontend są wydane w 1.0.2+21; analyze PASS i pełny suite 168/168 PASS. iOS/macOS są świadomie nieobecne. |
| Release channel / self-update | DONE | stable manifest 1.0.2+21, zweryfikowane SHA-256 i reguły forced/optional/no-update. Publikacja pozostaje human-gated. |
| Supervisor i gateway split | DONE | bindy 8787/8788/8789 na loopback; public gateway jawnie odrzuca `/control`. |
| Document Intelligence | DONE | centralny pipeline, pages/assets/OCR/Office/archive oraz testy regresyjne. Batch 30 istnieje; pełny cel jakościowy pozostaje częściowo otwarty. |
| Chunking / embeddings / Qdrant / semantic retrieval | DONE | migracja chunk 2.0, embedding service, Qdrant store i realny baseline Hit@3/5 3/3. |
| RAG / citations / evidence | DONE | chroniony `/api/v1/ai/rag`; test 401/200/422 i claim→evidence→source PASS. |
| CRM frontend | DONE WITH DEFERRED SCOPE | lista klientów, repozytorium dokumentów, Client 360, inspections/timeline i trzy tryby AI są wydane; nazwany model Contact Person pozostaje osobną decyzją. |
| Candidate pipeline | DONE/PARTIAL | review/promotion, duplicate protection i read-only identity projection działają; trwały multi-contact i quality cleanup są otwarte. |
| Document read API/UI | DONE | bezpieczne auth list/detail/content API oraz responsywne Flutter Documents UI działają na wspólnej sesji i Dio. |
| Dane CRM | QUALITY DEBT | Live audit: 3,243 Clients and 3,561 Candidates. Historical identity/notes cleanup was not applied and remains separately gated; see `FINAL_SYSTEM_AUDIT.md`. |

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

### 1. Client list contract — DONE

- Cel biznesowy: użytkownik widzi i przeszukuje wszystkie 3194+ klientów.
- Zależności: chunk 0.
- Zakres wykonany w source: kontrakt `{items,total,skip,limit}`; count z tym
  samym filtrem; sortowanie po
  case-insensitive name + ID; globalny server-side search; filtry typu i branży;
  Flutter z rozmiarem strony 50, prawdziwym totalem i kontrolkami stron.
- Pliki: client repository/service/schema/router; Flutter client data/domain,
  controller i page; testy backend/Flutter.
- Migracje: brak. Dane produkcyjne: odczyt. Późniejszy HOTFIX 3A wykazał, że
  wdrożona aplikacja +4 była nadal konsumentem legacy array; kontrakty zostały
  rozdzielone addytywnie na `/clients` oraz `/clients/page`.
- Testy: API 401/200/422, total=3194, strony 50/50 i ostatnia 44, brak duplikatów,
  search klienta ID 2152 spoza pierwszej strony, type total=996, industry
  total=0 zgodny z rzeczywistym brakiem przypisań; Candidate API regression;
  Flutter parser/repository/pagination widget, analyze i 15 testów PASS.
- Acceptance: spełnione. Kombinacja search+type+industry nie ma obecnie
  reprezentatywnych danych i pozostaje warunkowo testowana, bez tworzenia danych.
- Commit: `Complete paginated client list contract`.

### 2. Document read API — DONE

- Cel: bezpieczny dostęp do 5899+ dokumentów. Zależności: 0.
- Zakres wykonany: JWT list/detail/content, `{items,total,skip,limit}`, search
  metadanych, filtry client/source/match/processing/link/content type, projekcja
  bez ścieżek oraz download po ID. Upload zachował osobny import API key.
- Pliki: documents router/schema/repository, osobny read service, containment w
  document service i read-only E2E. Migracje: brak. Dane: odczyt.
- Bezpieczeństwo: jawna projekcja SQL bez `storage_path`/text/pages/chunks/assets;
  dwa LEFT JOIN bez N+1; resolved path musi pozostać w resolved data root;
  traversal, absolute escape, symlink escape i missing file są odrzucane.
- Testy/acceptance: real JWT 401/200/404/422; total 5899; strony 50/50/last 49;
  stable order; search ID 5878; wszystkie filtry i link totals 5639/161/99;
  checksum download dokumentu 4817; import-key 401/403/valid-key-to-422;
  client list auth regression i compile PASS; read-only extraction smoke dla
  DOCX/ODT/PNG/XLSX/PDF zakończony, z istniejącym uszkodzonym PDF 4812 nadal
  raportowanym jako failed.
- Commit: `Complete authenticated document read API`.

### 3. Document repository UI — DONE

- Cel: używalne repozytorium dokumentów. Zależności: 2.
- Zakres wykonany: osobne warstwy Flutter data/domain/application/presentation,
  paginacja server-side po 50, debounce search, filtry link/source/match/
  processing/content type/client, desktopowa tabela, mobilne karty, detail oraz
  uwierzytelnione otwieranie pliku.
- Windows/Android pobierają bajty przez wspólne Dio z JWT, zapisują bezpieczną
  nazwę w katalogu tymczasowym i otwierają przez `open_filex`; Web pobiera te
  same bajty z auth, tworzy Blob/Object URL i nie umieszcza JWT w URL.
- Dane: wyłącznie odczyt i jawny download. Migracje: brak. Backend bez zmian.
- Testy/acceptance: parser nullable, query params, controller pagination/search/
  filters, widget debounce/lista i testowalny open service; Flutter analyze/test,
  Web release build, Windows debug build i real Document Read API E2E PASS.
- Commit: `Complete document repository UI`.

### 3A. Deployed API compatibility + live Web safety — DONE

- Przyczyna: wydana aplikacja NEXT Stabil 1.0.1+4 nadal parsowała JSON array z
  `GET /api/v1/clients`, podczas gdy CHUNK 1 zmienił root na obiekt paginowany.
- Additive fix: legacy `/clients` ponownie zwraca `list[ClientRead]` z search,
  skip, legacy default 100 i max 500; wspólna warstwa repository/service nadal
  zapewnia stabilne sortowanie i nie duplikuje logiki query.
- Nowy source Flutter korzysta z `/clients/page`, który zachowuje total,
  search, filtry client_type/industry_id, strony po 50 i max 100.
- Trwały gate `test_deployed_client_1_0_1_4_compatibility.py` waliduje real JWT,
  array root, search array i wszystkie elementy jako `ClientRead`.
- Web-only corrective build używa `https://domai.tail1927bd.ts.net` oraz
  `https://domai.tail1927bd.ts.net:8443/control`; live JS nie zawiera endpointów
  127.0.0.1:8789/8788. Public `/control` pozostaje 404, private health 200.
- Legacy `/clients` pozostaje wspierane do czasu podniesienia minimum supported
  app version ponad ostatniego konsumenta starego kontraktu.
- Dane: NONE. Migracje: NONE. CHUNK 4 nie został rozpoczęty.
- Commit: `Restore deployed client API compatibility`.

### 4. Client 360 documents — DONE

- Cel: prawdziwe dokumenty klienta. Zależności: 2–3.
- Zakres wykonany: domyślnie zwinięty panel ładuje pierwszą stronę po pierwszym
  expand, zachowuje wynik przy collapse/expand, ma jawny refresh oraz strony po
  10 filtrowane server-side przez `client_id`.
- Panel wykorzystuje wspólne DocumentsRepository, modele, auth/Dio,
  DocumentOpenService i wyciągnięte presentation mappers; nie powstał drugi
  parser, download flow ani endpoint backendu.
- UI: kompaktowe responsywne wiersze, total/range, source/processing/match,
  empty/error/retry i opening progress. Mail pozostaje placeholderem.
- Link do `/documents?client_id=...&client_name=...` uruchamia pełne
  repozytorium ze scoped początkowym filtrem bez fetch-all klientów.
- Migracje: brak. Dane: odczyt. Backend/API: bez zmian.
- Acceptance: Flutter analyze i 28 testów PASS; real client ID 1915 ma 9/9
  zgodnych dokumentów, content ID 3974 otwiera 750481 bytes; client ID 1 daje
  poprawny empty total 0; Document Read i oba Client List gates PASS.
- Commit: `Connect client 360 documents`.

### 5. Client 360 email history — DONE

- Cel: źródłowa komunikacja Gmail z provenance zamiast transcriptów w `notes`.
- Zakres wykonany: addytywny JWT endpoint
  `/clients/{client_id}/emails`, SQL pagination/count/dedupe, stabilne sortowanie
  message datetime DESC NULLS LAST + source ID DESC, publiczny model bez raw
  payloadu oraz lazy/collapsible Flutter panel po 10 wiadomości.
- Źródła: wyłącznie aktywne `gmail_message` po relacji CandidateSource →
  ClientCandidate → matched_client_id dla semantycznie powiązanych statusów
  accepted/merged/duplicate. Nie użyto dopasowania po nazwie/emailu/telefonie.
- Normalizacja: istniejący GmailMessageBoundaryService oddziela current body;
  HTML jest zamieniany na nieaktywny tekst, a SENT/INBOX lub jawny direction
  daje sent/received/unknown bez zgadywania z treści.
- Attachments: batchowe powiązanie Document.gmail_message_id z external Gmail
  message ID; UI otwiera przez istniejący DocumentOpenService.
- Real data: 4095 wiadomości / 1338 klientów; klient 2504 ma 127 maili;
  klient 1 ma empty state; klient 2344 ma 153 attachment documents w 30 mailach.
- Coverage cleanup gate: 809 transcript-like notes, 809 z sourced Gmail, 0 bez;
  529 Gmail-linked klientów bez transcript notes. Notes pozostały bez zmian.
- Migracje: brak. Dane: NONE. Kompatybilność: wyłącznie nowy endpoint.
- Acceptance: backend compile, Email API/normalization, Candidate, deployed +4,
  Client List, Document Read, auth oraz Flutter analyze/test PASS.
- Commit: `Add sourced client email history`.

### PRE-RELEASE CHUNK — ADMIN USER LIFECYCLE — DONE

Status: DONE / RELEASE NOT PUBLISHED.

- Additive admin-only `POST /admin/users/{user_id}/deactivate` ustawia wyłącznie
  `User.is_active=false`; nie istnieje physical-delete path i username/email/
  role/conversations/history pozostają zachowane.
- Self-deactivation, inactive repeat i last-active-Administrator są odrzucane
  jako 409. PostgreSQL advisory transaction lock oraz actor/target/active-admin
  `FOR UPDATE` serializują operację; actor jest ponownie autoryzowany po locku.
- Additive tabela `user_lifecycle_events` zapisuje actor, target, DEACTIVATED i
  timestamp w tej samej transakcji. Audit failure rollbackuje zmianę User.
- `get_current_user` sprawdza aktywność w DB dla wszystkich chronionych API;
  test potwierdza natychmiastowe 401 istniejącego JWT oraz generic 401 loginu.
- Reset hasła inactive User zwraca 409 i nie reaktywuje konta. Unique username/
  email nadal obejmują inactive users.
- Flutter pokazuje „Usuń użytkownika”, wyjaśnia soft deactivation i wymaga
  dokładnego wpisania username; self/inactive/reset actions są disabled, a
  konflikty backendu mają jawne polskie komunikaty.
- Additive migration `userlife_20260815` PASS; baseline real users przed/po:
  total 4, active 4, inactive 0, active Administrator 1, active User 3;
  produkcyjne lifecycle events 0, physical deletes 0.
- Existing API shapes pozostają bez zmian; dodano tylko lifecycle endpoint.
  Release nie został zbudowany ani opublikowany i nadal wymaga human gate.
- Commit: `Add safe admin user deactivation`.

### 5A. Client email attachment scope hardening — DONE

- Read-only audit: 0 external Gmail ID collisions między import sources i 0
  Document.gmail_message_id collisions między różnymi jawnymi client_id.
- Wykryto 20 attachment documents bez client_id/candidate_id, które wcześniejsze
  zapytanie mogło eksponować wyłącznie na podstawie message ID.
- Attachment batch query wymaga teraz zgodnego `Document.client_id` albo — tylko
  dla candidate-only document — aktywnego kandydata ze zgodnym matched_client_id
  i statusem accepted/merged/duplicate. Unscoped i cross-client są odrzucane.
- Dedupe używa provenance-safe `(import_source_id, external_id)`, ponieważ schema
  i importer nie gwarantują globalnego namespace external_id.
- Izolowany test tworzy kolizję Client A/Client B, potwierdza scope przez realny
  endpoint i wykonuje rollback; trwałe modyfikacje danych: 0.
- Publiczny Email API contract, CHUNK 5 DONE i Client.notes pozostają bez zmian.
- Commit: `Harden client email attachment scope`.

### 6. Client identity quality dry-run — DONE

- Baseline read-only: 3194 aktywnych klientów; email-as-name 463,
  phone-as-name 284, file-as-name 1, overlap 0, unikalny union 748.
- Linkage: 748/748 ma co najmniej jednego aktywnego, semantycznie powiązanego
  kandydata; 18 ma wielu kandydatów (accepted/merged).
- Existing Client Entity Projection 1.4.6 jest wykonywany osobno per candidate.
  Dry-run jawnie wyłącza candidate_name_entity, candidate-name person fallback
  i base_fallback, więc podejrzana wartość nie jest własnym dowodem.
- Wynik: SAFE_RENAME_CANDIDATE 8, REVIEW_REQUIRED 1,
  INSUFFICIENT_EVIDENCE 738, POTENTIAL_DUPLICATE_OR_MERGE 1,
  FIRST_PARTY_OR_RELAY_REVIEW 0, NO_CHANGE 0.
- Evidence: Gmail-backed 6, Sheets-backed 4, both 0; 738 bez wiarygodnego
  source-backed identity. Proposed client_type zmienia się w 10 dry-runach.
- Duplicate risk: POSSIBLE 1, STRONG 1. STRONG nigdy nie jest SAFE i wymaga
  osobnego merge gate.
- Future promotion hardening blokuje email/phone/filename jako Client.name oraz
  first-party/relay projection; prawidłowe person/company i zwykły promotion
  nadal działają. Import może zachować surowy candidate do review, ale nie może
  już wypromować podejrzanej nazwy do klienta.
- Lokalne raporty JSONL/JSON/TXT są ignorowane i nie są commitowane. Raport nie
  zawiera raw_payload, całych body, sekretów ani tokenów.
- Dane: DRY-RUN ONLY, production writes 0. Migracje: brak. API: bez zmian.
- PRODUCTION IDENTITY CLEANUP: NOT APPLIED / HUMAN GATE.
- Commit: `Add client identity cleanup dry run`.

### 6A. Identity evidence attribution + human review bundle — DONE

- `identity_support_evidence` jest oddzielone od ogólnego projection/contact
  evidence i wymaga dokładnej zgodności normalized evidence.value z
  proposed_name; substring matching jest zabroniony.
- Proposal confidence i ranking candidate groups używają wyłącznie
  identity-specific confidence. Silny evidence osoby kontaktowej nie podnosi
  confidence innej proponowanej organizacji.
- SAFE wymaga jawnego identity support >= 0.90, braku conflict, duplicate risk
  NONE oraz przejścia first-party/relay/name-quality policy.
- Krytyczna regresja: organizacja 0.88 + niezwiązany kontakt 0.95 pozostaje
  REVIEW; dokładny person_contact_fallback 0.95 może być SAFE.
- Real-data wynik nie zmienił się: SAFE 8, REVIEW 1, INSUFFICIENT 738,
  POTENTIAL_DUPLICATE_OR_MERGE 1. Wszystkie 8 SAFE ma dokładny strong identity
  support; actionable human-review bundle zawiera 10 rekordów.
- Diagnostyka insufficient jest overlap-aware: Gmail 370, Sheets 393, oba 25,
  quoted boundary 127, candidate-self-only 738; 326 klientów ma łącznie 1015
  dokumentów mogących stanowić przyszły, osobno walidowany evidence source.
- Raporty JSONL/summary/TXT/human-review są lokalne, ignorowane i niecommitowane.
  Dane: DRY-RUN ONLY, production writes 0. Migracje/API: brak zmian.
- PRODUCTION IDENTITY CLEANUP: NOT APPLIED / HUMAN GATE STILL CLOSED.
- Commit: `Bind cleanup confidence to identity evidence`.

### 6A.1. Address-as-identity rejection — DONE

- Root cause: legacy Sheets candidate 1322 stored `Pruszków ul. Guzikowa` in
  the structured `NAZWISKO` field. The person-name classifier accepted its
  three non-numeric tokens and emitted `person_contact_fallback` at 0.94.
- Shared high-precision name-quality logic now reports
  `ADDRESS_OR_LOCATION_AS_NAME` for explicit street/address markers combined
  with a building number or a preceding location. It does not use a city list.
- Both projection layers reject address-like values as person and entity
  identity. Cleanup retains an independent final quality gate, and candidate
  promotion blocks future address/location values as `Client.name`.
- False-positive controls preserve real people/organizations, including
  `Budimex Warszawa`, `Hotel Warszawa`, `Warszawska Grupa Inwestycyjna` and
  `Plac Zabaw Sp. z o.o.`; e-mail domains ending in `.pl` are not addresses.
- Client 13 is now `INSUFFICIENT_EVIDENCE` with no proposed identity. Client
  2560 remains proposed as `M. Kłapa`, but initial-only
  `person_contact_fallback` is conservatively `REVIEW_REQUIRED`; no full given
  name exists in its Gmail display names, current signatures or attachments.
- Real-data AFTER: SAFE 6, REVIEW 2, INSUFFICIENT 739,
  POTENTIAL_DUPLICATE_OR_MERGE 1. The four reports were regenerated locally
  under PostgreSQL READ ONLY and remain ignored.
- DATA IMPACT: DRY-RUN ONLY; PRODUCTION WRITES 0; MIGRATIONS NONE;
  API CONTRACT UNCHANGED.
- PRODUCTION IDENTITY CLEANUP: NOT APPLIED / HUMAN GATE STILL CLOSED.
- Commit: `Reject address values as client identity`.

### 6B. Controlled client identity apply — DONE

- Human approval obejmował dokładnie Client IDs 39, 113, 1912, 1915, 2269
  i 2282 oraz wyłącznie pole `Client.name`.
- Przed zapisem aktualny dry-run PostgreSQL READ ONLY potwierdził dla wszystkich
  sześciu: dokładne OLD/NEW, SAFE_RENAME_CANDIDATE, duplicate risk NONE,
  identity support, brak conflict oraz czyste quality gates.
- Dedykowany fail-closed skrypt domyślnie działa jako dry-run, wymaga lokalnego
  manifestu o przypiętym SHA256, dokładnie sześciu oczekiwanych ID i wykonuje
  apply w jednej transakcji z `SELECT ... FOR UPDATE`.
- Transakcja zmieniła dokładnie sześć `Client.name`; automatyczny `updated_at`
  zmienił się zgodnie z modelem. Pozostałe snapshot fields, notes hashes,
  document IDs/counts, Email History totals i matched candidate IDs są identyczne.
- Quality BEFORE: active 3194, email 463, phone 284, file 1, unique 748.
  AFTER: active 3194, email 462, phone 279, file 1, unique 742. Delta dokładnie
  odpowiada zatwierdzonym sześciu rename.
- Client 13 pozostaje INSUFFICIENT. Clients 1745 i 2256 pozostają odpowiednio
  POSSIBLE/STRONG duplicate HOLD. Client 2560 pozostaje abbreviated identity
  HUMAN REVIEW/HOLD.
- APPROVED/APPLIED CLIENT RENAMES: 6. Client type changes: 0. Merges: 0.
  Notes cleanup: 0. Migracje/API contract: brak zmian.
- Lokalne approval/before/after/rollback oraz dry-run reports zawierające CRM
  data są ignorowane i niecommitowane. Rollback artifact nie został wykonany.
- Pozostały identity quality debt: 742 suspicious, w tym 739 insufficient;
  identity cleanup nie jest zakończony.
- PRE-RELEASE ADMIN USER LIFECYCLE: DONE / RELEASE NOT PUBLISHED.
- Commit: `Apply approved client identity renames`.

### 6C. Legacy email notes cleanup dry-run — DONE

- Read-only baseline: 3194 active clients, 3146 non-empty notes, 809
  transcript-like notes; all 809 have sourced Gmail history and 0 are blocked
  for missing source history.
- Full legacy audit found 2430 blocks in four deterministic marker variants.
  Every real block is paragraph-bounded, all transcript-like notes start and
  end with transcript content, and no manual/other non-empty lines occur in
  that population. There are 449 multi-message clients and at most 118 blocks
  in one notes value.
- The parser requires a complete ordered wrapper, explicit sent/received
  direction, timezone-aware timestamp and blank-line paragraph boundaries.
  It never removes text through body replacement or a single-marker match and
  preserves manual paragraphs byte-for-byte apart from one removed transport
  boundary separator.
- Conservative source cross-check uses exact direction + UTC timestamp and
  exact subject when present; exact normalized body is used only to
  disambiguate multiple otherwise-equal sources. Results: 2386 confirmed
  blocks, 44 no-source-match blocks, 0 non-unique and 0 ambiguous blocks.
- Classification: SAFE_REMOVE_TRANSCRIPT_ONLY 0, SAFE_CLEAR_NOTES 789,
  REVIEW_REQUIRED 20, BLOCKED_NO_SOURCE_HISTORY 0, NO_CHANGE 0. The 789 safe
  records propose removing 2119 legacy blocks / 2077937 characters and setting
  notes to NULL; this proposal has not been applied.
- Local JSONL/summary/review/text reports and the 789-record safe manifest are
  ignored and not committed. The manifest explicitly states that apply is not
  approved. No apply script was added in this chunk.
- DATA IMPACT: DRY-RUN ONLY; PRODUCTION WRITES 0; MIGRATIONS NONE;
  API CONTRACT UNCHANGED.
- PRODUCTION NOTES CLEANUP: NOT APPLIED / HUMAN GATE.
- CHUNK 7: NOT STARTED. PRE-RELEASE ADMIN USER LIFECYCLE: DONE / RELEASE NOT
  PUBLISHED.
- Commit: `Add legacy email notes cleanup dry run`.

### 6C.1. Client.notes downstream dependency audit — DONE / BLOCK_6D

- The regenerated PostgreSQL READ ONLY 6C safe manifest is byte-stable:
  789 SAFE_CLEAR_NOTES records, 2119 safe legacy blocks and 2119/2119
  CONFIRMED_SOURCE_MATCH results; source/linkage/normalization anomalies: 0.
- Current backend and Flutter source does not use Client.notes for Client List,
  document search, semantic retrieval, RAG, embeddings or sourced Email
  History. Client detail only serializes nullable notes; current Client 360
  displays them as notes and otherwise uses the independent Email API.
- PostgreSQL Document/DocumentChunk and the current 57-point Qdrant collection
  contain no Client.notes-derived or legacy-marker content. Active n8n runtime
  was audited read-only: its notes fields belong to candidate import payloads;
  it does not read Client.notes. Export/report consumers were not found.
- BLOCKING dependency: the published Android/Windows 1.0.1+4 source commit
  predates Client Email History. It displays Client.notes while its Mail panel
  is a placeholder, so clearing the 789 values would remove the only visible
  mail history for those deployed native consumers despite canonical Gmail
  data remaining intact.
- Required prerequisites: publish and human-verify Android/Windows clients with
  sourced Email History, establish a supported-version cleanup gate, create a
  private encrypted full-notes rollback snapshot, then rerun 6C/6C.1 without
  manifest or source drift.
- GO / NO-GO: BLOCK_6D. PRODUCTION NOTES CLEANUP: NOT APPLIED. CHUNK 6D is
  BLOCKED pending native Email History release + supported-version gate;
  CHUNK 7: NOT STARTED. PRE-RELEASE ADMIN USER LIFECYCLE: DONE / RELEASE NOT
  PUBLISHED.
- DATA IMPACT: READ ONLY; PRODUCTION DATABASE WRITES 0; QDRANT WRITES 0;
  MIGRATIONS NONE; API CONTRACT UNCHANGED.
- Commit: `Audit client notes downstream dependencies`.

### NATIVE RELEASE CHECKPOINT — NEXT STABIL 1.0.2+5 — PUBLISHED

- Status: PUBLISHED / WAITING FOR HUMAN VERIFICATION.
- Android i Windows zbudowano dokładnie z prep commit
  `c234ade9a7fb27d2071685d7ac5bba77c675fdac`, wersja 1.0.2, build 5.
- Build config: public API `https://domai.tail1927bd.ts.net`; private
  supervisor `https://domai.tail1927bd.ts.net:8443/control`.
- APK version/signing i Windows installer metadata zweryfikowane; publiczne
  artifact Content-Length/SHA256 są zgodne z lokalnymi plikami.
- Stable manifest: 1.0.2+5; minimum_version pozostaje 1.0.0, więc 1.0.1+4
  otrzymuje AVAILABLE, nie REQUIRED. Production Web pozostaje bez zmian.
- PRE-RELEASE ADMIN USER LIFECYCLE: DONE. Real users: 4 active, 0 inactive;
  żadna lifecycle operation nie została wykonana przez release checkpoint.
- CHUNK 6D: BLOCKED — WAITING FOR HUMAN VERIFICATION + SUPPORTED-VERSION GATE.
- POST-RELEASE CANDIDATE AUTO-PROMOTION: PLANNED / NOT STARTED.
- GOLDEN BACKUP: WAITING FOR HUMAN VALIDATION OF 1.0.2+5.
- Release nie jest production-validated; użytkownik musi zweryfikować Android
  i Windows. Brak auto-install, notes cleanup, auto-promotion i golden backup.

### 7. Contact and address model — DONE

- Reconciliation: multi-email, multi-phone, primary scalar synchronization,
  CRUD, Flutter contact UI and forward ingestion are already DONE.
- Implemented: provenance-aware `ClientAddress`, contact provenance references,
  additive `chunk7addr_20260816` migration, legacy-compatible ClientRead/PATCH
  projection and responsive Flutter address edit/details.
- Production audit: 3194 total/active clients, 2 clients with any scalar address,
  4981 active contact points; no existing address/contact-person tables.
- Backfill was direct field-for-field for only those 2 scalar-address clients;
  no parsing, cleanup, guessing or geocoding. Migration
  `chunk7addr_20260816` applied; post-audit has 0 scalar/primary mismatches.
- Backend regressions, Flutter analyze and 53/53 Flutter tests PASS.
- Contact persons are a separate CHUNK 7B: introduce ClientContactPerson and
  explicit optional contact-person ownership without overloading client-level
  contact points. Not implemented in this migration.
- CHUNK 7 COMPLETE EXCEPT SEPARATE 7B CONTACT PERSON MODEL.
- CHUNK 7B: NOT STARTED. CHUNK 8: NOT STARTED.

### 8. Document-client matching workspace — DONE

- Cel: rozstrzygnąć 99 unmatched i 161 candidate-only. Zależności: 2–4.
- Zakres: suggestions/confidence, manual link/unlink/move, audit trail, UI.
- Quality debt: aktualny audit wykazuje 97 Gmail attachment documents bez
  client_id/candidate_id; workspace nie wykonuje automatycznego przypisania.
- Migracje: audit model prawdopodobny. Ryzyko: błędne przypisanie. Dane: jawne
  pojedyncze mutacje; medium confidence wymaga approval.
- Acceptance: każda zmiana audytowalna i odwracalna. Commit: `Add document matching workspace`.

#### CHUNK 8 completion checkpoint

- Reconciliation: Document already has `client_id`, `candidate_id`,
  match status/confidence and repository/client-360 reads. Manual link,
  unlink, atomic move, deterministic explainable suggestions and durable
  operator audit were missing.
- Read-only production audit: 5899 total; 5639 client-linked (also retaining
  candidate provenance), 161 candidate-only, 99 unmatched, 97 unmatched Gmail
  attachments; 0 current client/candidate association conflicts.
- Applied additive revision `chunk8doclink_20260817` with RESTRICT foreign
  keys and no destructive alteration. It records LINK/UNLINK/MOVE, actor,
  old/new client, candidate provenance, bounded evidence metadata and explicit
  reversals. Existing document associations remained unchanged.
- Deterministic candidate/exact-contact/checksum suggestions,
  explicit conflict confirmation, transactional single-document operations,
  undo endpoint and responsive Flutter matching controls. No bulk/AI apply.
- Backend matching/audit/undo suite, required regressions, Flutter analyze and
  full 56-test suite PASS. Synthetic link/move/unlink/undo was rolled back;
  production durable test writes 0 and audit rows remained 0.
- CHUNK 8: DONE. CHUNK 7B: NOT STARTED.

### 9. Upload, photos, mobile field data — DONE

- Cel: bezpieczny terenowy intake. Zależności: 2, 7–8.
- Zakres: user-auth upload/multi/camera, captured/GPS/accuracy/link/session UI.
- Implemented shared JWT per-file intake with optional Client linkage, bounded
  JSON provenance, 250 MB limit, checksum dedupe and existing processing/EXIF
  pipeline. Import API-key upload remains unchanged.
- Flutter supports multi-file partial success, gallery, Android-only camera,
  optional foreground GPS (denial does not block upload), per-file progress and
  retry in Client 360 and global Documents. Original bytes are preserved.
- Existing nullable inspection session and metadata JSON provide additive
  future linkage without fake Project/Inspection foreign keys. No migration,
  AI image analysis or offline synchronization was added.
- Backend intake/regression tests, Flutter analyze and full 57-test suite PASS.

### 10. Projects / realizations / inspections / timeline — DONE

- Cel: klient→realizacja→lokalizacja→inspekcja→media. Zależności: 7,9.
- Zakres: osobne additive model/API/UI subchunki. Migracje: tak.
- Ryzyko: szeroki model domeny. Dane: nowe jawne rekordy, backfill gated.
- Acceptance: każdy vertical slice ma CRUD/auth/audit/testy.
- Commit: osobny per encja, zaczynając `Add project foundation`.
- CHUNK 10A — PROJECT / REALIZATION FOUNDATION: DONE.
  Additive `chunk10aproject_20260817` migration created `projects` and the
  nullable `documents.project_id` RESTRICT relation. No projects or historical
  document relations were backfilled. JWT CRUD, server pagination/search/client
  and status filters, soft delete, independent location, actor attribution,
  document intake linkage, Realizacje UI and Client 360 integration are active.
  Rollback-only backend tests and the full 63-test Flutter suite passed; durable
  production test writes were 0.
- CHUNK 10B — INSPECTION FOUNDATION: DONE.
  Additive `chunk10binspect_20260817` migration created canonical
  `inspections` and nullable `documents.inspection_id` RESTRICT relation.
  There was no historical backfill or conversion of the legacy string
  `inspection_session_id`. JWT CRUD, pagination/search/project/client/status/
  date filters, deterministic completed/reopen handling, GPS/notes, soft
  delete, Project panel, global/detail Flutter UI and CHUNK 9 upload/camera/
  gallery integration are active. Rollback-only backend tests, required
  regressions, Flutter analyze and all 69 Flutter tests passed; 5899 documents
  and their association baseline remained unchanged, with 0 durable test writes.
- CHUNK 10C — TIMELINE: DONE.
  A migration-free, read-only projection aggregates credible Client and Project
  events from Client, Project, Inspection, Document/capture provenance,
  deduplicated Gmail history and DocumentClientLinkEvent audit rows. It exposes
  authenticated, stably sorted, filtered and paginated Client/Project APIs with
  bounded metadata only; raw Gmail bodies/payloads and document text are never
  copied. Flutter Client 360 and Realizacja details reuse one lazy responsive
  timeline panel with load-more, type filters and source navigation.
  No inferred status history or project Gmail association is fabricated.
  The large-email read (127 events) measured 258.86 ms and the document-heavy
  read (153 documents, 184 events) 68.05 ms for the first 20 items. Backend
  tests/regressions, Flutter analyze and all 72 Flutter tests passed; durable
  production writes and historical backfill were 0.
- CHUNK 7B — CONTACT PERSON MODEL: NOT STARTED.

### 11. Global hybrid search — COMPLETE

- CHUNK 11A — STRUCTURED + LEXICAL GLOBAL SEARCH: DONE. Authenticated
  `GET /api/v1/search` aggregates Clients, Projects, Inspections, Documents,
  Emails and Candidates with bounded snippets, explainable reasons,
  deterministic exact > lexical > semantic ranking, entity deduplication,
  type filters and bounded pagination. Queries are read-only.
- Additive revision `chunk11search_20260818` adds the partial Gmail GIN/FTS
  index only. It modified no business rows; pre/post counts were identical and
  the planner uses `ix_candidate_sources_gmail_search_vector`.
- Measured p95: exact phone 138.9 ms, Client/name 56.8 ms, document lexical
  80.8 ms, Gmail lexical 700.5 ms and global no-result 218.3 ms. Warm hybrid
  p95 is 908.0 ms; the first cold Ollama request measured 2.66 s.
- CHUNK 11B — SEMANTIC SEARCH: LIMITED TO EXISTING VECTOR COVERAGE. Existing
  Qdrant collection `ai_lab_document_chunks` contains 57 current 1024-dimension
  chunks for 11 documents using `qwen3-embedding:0.6b`. Current production has
  5903 documents (5892 without semantic coverage). No vector backfill, Qdrant
  write, collection rebuild or upgrade was performed.
- Qdrant/Ollama failure is fail-open for structured/lexical results. Flutter
  provides mobile AppBar and desktop-shell entry, 320 ms debounce, request
  cancellation, filters, badges, bounded error/retry and source deep links.
  Search result Back returns through Search to Dashboard.
- Backend focused/regression suites, semantic E2E, Flutter analyze and the
  complete 120-test Flutter suite: PASS. Production business writes: 0.
- Commit: `Add global hybrid search`.

### 12. AI client knowledge — DONE / RELEASED IN 1.0.2+15

- Wydany zakres: client-scoped retrieval, deterministic direct answers,
  `llama3.2`, backend-owned source map, citations and semantic fail-open.
- Brak conversation persistence i write actions. Strict client scope and
  cross-client tests remain mandatory.
- Commits: `Add client-scoped AI knowledge`, release `5ee7f25`.

### 13. Business assistant — DONE / RELEASED IN 1.0.2+17

- Wydany zakres to read-only Business Assistant: deterministic analytics,
  Global Search/Client AI retrieval, `llama3.2` and deterministic citations.
- Nie tworzy ani nie publikuje ofert, umów lub maili; draft/write workflow z
  pierwotnego targetu pozostaje future scope, nie ukrytą częścią release.
- Commits: `Add read-only business assistant`, release `4f1b99c`.

### 14. Technical AI — DONE / RELEASED IN 1.0.2+19

- Wydany zakres: scoped technical retrieval and synthesis with explicit
  facts/hypotheses/missing information, measurement caution and deterministic
  original-source citations. Model remains `llama3.2`.
- Dedykowany calculation engine/normative database from the original target is
  not claimed as delivered.
- Commits: `Add evidence-grounded technical AI`, release `188e5b8`.

### 15. Vision / multimodal — DONE / RELEASED IN 1.0.2+20

- Deterministic classification covers genuinely new Documents; bounded pages/
  images use a private supervisor and Temporary Chat worker. V1 results are
  validated, checksummed, persisted and supplied to Technical AI.
- Historical Vision is on-demand. Local Vision, OpenAI API, image embeddings,
  Qdrant writes and historical backfill are not part of the release.
- Commits: `f102b64`, `8db57be`, `31b257e`, `f0752f3`, release `b13d413`.

### 16. Agent — DONE / RELEASED IN 1.0.2+21

- Read-only, deny-by-default registry with strict Client/Inspection scope,
  deterministic sources and sanitized persistent `agent_executions` audit.
- Hard bounds: 5 rounds / 8 calls / 180 seconds. No write, SQL, shell,
  Docker/supervisor, general browser or live Vision execution tools.
- Commits: `7550453`, `17e9e5b`, `4441e33`, release `bbe37db`.

### 17. Production hardening — COMPLETE / VERIFIED

- Known-good images are pinned without upgrades; protected backup, isolated
  PostgreSQL/storage/n8n restore, migration roundtrip and controlled host reboot
  recovery passed. Daily backup runs at 03:00.
- Residuals remain explicit: public headers, Qdrant isolated restore, manual
  secret escrow and physical Android validation. No destructive retention.
- Commits: `e83d81f`, `9b4ff83`, `9d59c30`, `c3f388a`.

### POST-RELEASE HOTFIX — NEXT STABIL 1.0.2+6 — PUBLISHED

- Client List: filtry bazowe są wewnątrz zwijanego panelu, paginacja działa
  nad i pod listą, a zmiana strony przewija do początku wyników.
- Addytywne `source_record_date` jest wyliczane read-only z aktywnego
  provenance Google Sheets; najwcześniejsza prawidłowa data `DD.MM.YYYY`
  wygrywa, bez migracji i bez mutacji CRM.
- Client i Candidate drill-down używają `push`; system/AppBar Back wraca do
  listy, z fallbackiem dla direct entry.
- Android i Windows: 1.0.2+6 opublikowane. Web: bez zmian. `minimum_version`
  nadal 1.0.0, więc aktualizacja z +5 ma stan AVAILABLE.
- POST-RELEASE HOTFIX 1.0.2+6: PUBLISHED / WAITING FOR HUMAN VERIFICATION.
- 1.0.2+5: SUPERSEDED BY 1.0.2+6.
- DATA ARTIFACT CLEANUP: DEFERRED UNTIL GOLDEN BACKUP.
- GOLDEN BACKUP: WAITING FOR HUMAN VERIFICATION OF 1.0.2+6.
- CHUNK 6D: BLOCKED. CANDIDATE AUTO-PROMOTION: NOT STARTED. CHUNK 7:
  NOT STARTED.

### INSPECTION SIMPLIFICATION PATCH — NEXT STABIL 1.0.2+16 — PUBLISHED

- Inspection create/update is Client-only: no Project picker or manual title.
  The backend generates a deterministic technical title and keeps legacy
  Project relations readable but optional.
- Alembic `inspectclient_20260818` is applied. It only changes
  `inspections.project_id` from NOT NULL to nullable; no rows were rewritten,
  deleted or backfilled, and the RESTRICT FK remains.
- Client 360 and the global Inspection module use the simplified forms and
  document upload links Client + Inspection without requiring Project.
- Backend release regressions PASS; Flutter analyze PASS; full Flutter suite
  130/130 PASS. Web, Windows and Android 1.0.2+16 are published.
- CHUNK 13 — BUSINESS ASSISTANT: NOT STARTED.

### CHUNK 13 — BUSINESS ASSISTANT — COMPLETE

- Added authenticated `POST /api/v1/ai/business/ask` with bounded question and
  request-local conversation context, explainable coverage, limitations,
  semantic status and deterministic source routes.
- `BusinessAnalyticsService` performs read-only counts, status breakdowns,
  UTC recency windows, stale-email-contact detection, recent activity,
  inspection/project summaries and explainable attention signals. LLM is not
  used for arithmetic.
- Descriptive retrieval reuses `GlobalSearchService`; exact client ambiguity is
  returned for user selection instead of guessing. Existing local `llama3.2`
  receives only bounded, enumerated, untrusted evidence and unknown citations
  are discarded.
- Existing `/ai` placeholder is now the responsive Business Assistant with four
  examples, loading/cancel, friendly retry, answer, limitations and source
  deep links. Android/Web Back remains on the existing central route policy.
- Current semantic coverage is deliberately limited: Qdrant remains 57 chunks
  / 11 of 5909 Documents, with 0 points carrying `client_id`. No vector
  backfill, Qdrant write/upgrade, migration, n8n change, business mutation or
  conversation persistence occurred.
- Gates: focused backend 8/8 PASS; relevant backend regression 47/47 plus
  script-based suites PASS; controlled local LLM E2E 8/8 PASS with rollback;
  Flutter analyze PASS and full 137/137 tests PASS.
- CHUNK 14 — TECHNICAL AI: later completed and released in 1.0.2+19.

### P1 STABILIZATION — COMPLETE — NEXT STABIL 1.0.2+10

- Central authenticated-Dio 401 handling: DONE. Expired/revoked/inactive-user
  sessions are cleared once, user-scoped state is invalidated and Flutter
  returns to login with `Sesja wygasła. Zaloguj się ponownie.` Login failures
  and 403/404/409/422/500/network errors do not clear an active session.
- JWT implementation commit: `b3a83f2005caf1c32ebc064324cbeca43f4b7c0f`.
  Flutter analyze and full 86-test suite: PASS. Required backend regression
  suites: PASS.
- NEXT Stabil 1.0.2+10 Web, Windows and Android: BUILT/PUBLISHED from current
  CHUNK 7–10 code. `minimum_version` remains 1.0.0.
- Google Sheets credential `Google Sheets account`: RECONNECTED. `My workflow`
  remains active on its unchanged 15-minute schedule; workflow/source IDs and
  credential secrets were not changed.
- Sheets idempotency: DONE. Natural executions 960 and 961 each emitted zero
  `existing_source_updated`; execution 961 added one genuine new source and
  candidate while stable rows remained unchanged.
- P1 status: COMPLETE. CHUNK 11: NOT STARTED.

### P2 USABILITY STABILIZATION — COMPLETE

- Mobile widths below 700 px use one central, left-side, scrollable Drawer
  with all eight modules, active-route highlighting and full-size touch
  targets. The eight-item bottom NavigationBar is no longer rendered.
- Root module AppBars use the shared shell menu action; Client, Project and
  Inspection detail AppBars retain their existing Back behavior.
- Responsive widget coverage at 360x800, 390x900, 600x900 and 1200x900,
  cross-module navigation, drawer close, active state and Android Back: PASS.
  Flutter analyze and full 91-test suite: PASS.
- Project, Inspection and Timeline reads now use a shared bounded API-error
  mapper and a consistent explicit read retry; raw Dio/response internals are
  not rendered and mutations are not retried automatically.
- Timeline email events use their existing CandidateSource ID in a scoped
  client deep link. Client Details auto-opens Email History, requests only the
  exact source, expands/highlights it and shows a safe fallback when absent.
- Flutter analyze and full 98-test suite: PASS. Timeline/Email History,
  Client API, Auth/Admin and deployed compatibility backend regressions: PASS.
- Backend DB schema, ingestion workflow, release version and CHUNK 11:
  UNCHANGED. CHUNK 11 remains NOT STARTED.

### STABILIZATION RELEASE — NEXT STABIL 1.0.2+11 — PUBLISHED

- P1 Sheets source idempotency, the central mobile Drawer, bounded friendly
  read errors/retry and the scoped Timeline email deep link are included with
  the complete current CRM.
- Web, Windows and Android artifacts: PUBLISHED. Public Windows/Android hashes
  and the served Web bundle match the local release outputs.
- Backend release regressions: PASS. Flutter analyze: PASS. Full 98-test suite:
  PASS before and after the version bump.
- Stable build: 1.0.2+11. `minimum_version`: 1.0.0.
- CHUNK 11 — GLOBAL HYBRID SEARCH: NOT STARTED.

### PRE-CHUNK 11 CRM USABILITY / SOURCE CONSISTENCY PATCH

- Persistent Client workflow status/category: DONE through additive revision
  `prechunk11status_20260817`; historical rows retain neutral absence/default.
- Candidate bulk accept and Client bulk workflow-status/soft-delete are
  bounded to 100 and return per-record outcomes. Existing safety guards and
  historical relations remain authoritative.
- Client search: server-side name/legal/NIP, primary/secondary e-mail and
  phone, legacy/structured address, city and postal-code matching; no N+1 or
  fetch-all picker path.
- Client Details status editing, reusable debounced Client picker, Project
  scoping in Inspection and lazy Client 360 inspections: DONE.
- Google Sheets source-date projection and idempotency: preserved. Live n8n
  workflow `23i1FJJ6dZJbuMRo`, version
  `2026c515-0ba9-4d27-9920-9a52120a3791`, has four active Sheets branches,
  no dead duplicates and explicit bounded `skipped_no_identity`; the schedule
  remains every 15 minutes.
- Natural execution 980: SUCCESS; 2748 rows read = 2721 ingestable + 27
  explicitly skipped, all 2721 accepted, 0 backend failures and 0
  `existing_source_updated` for unchanged rows.

### PRE-CHUNK 11 CRM CORRECTNESS RELEASE — NEXT STABIL 1.0.2+12 — PUBLISHED

- Candidate/Client multi-select, bounded bulk accept/status/soft-delete,
  persistent Client workflow status, expanded server-side Client search,
  Sheets source-date projection, Client 360 inspections and the reusable
  searchable Client picker are included with the current P1/P2 stabilization.
- Web, Windows and Android artifacts: PUBLISHED. Public Windows/Android hashes
  and the served Web bundle match their local release outputs.
- Backend release regressions: PASS. Flutter analyze: PASS. Full 100-test
  Flutter suite: PASS before and after the version bump.
- Stable build: 1.0.2+12. `minimum_version`: 1.0.0.
- CHUNK 11 — GLOBAL HYBRID SEARCH: NOT STARTED.

### ANDROID BACK NAVIGATION PATCH — NEXT STABIL 1.0.2+13 — PUBLISHED

- A central Android `PopScope` policy defines Dashboard as the authenticated
  root. Main modules fall back to Dashboard; detail routes and validated
  Inspection return contexts fall back one logical level without per-screen
  Android exit workarounds.
- Mobile Drawer root switching discards the prior logical branch; Drawer and
  overlays close before route navigation. Logout and expired-session state
  reset the shared router to Dashboard before a future authenticated session.
- Dashboard requires two Back attempts within two seconds and shows
  `Naciśnij jeszcze raz, aby wyjść` after the first. No `exit(0)` or
  `SystemNavigator.pop()` was added.
- Flutter analyze: PASS. Full suite: 112/112 PASS before and after version
  bump, including 11 central routing/deep-link/double-Back tests and protected
  stack reset after logout/session expiration.
- Web, Windows and Android 1.0.2+13: PUBLISHED; local/public/manifest hashes
  match and `minimum_version` remains 1.0.0. Physical Android Back smoke is
  UNVERIFIED because no ADB device was connected.
- Backend, DB and n8n: UNCHANGED.

### CHUNK 11 GLOBAL HYBRID SEARCH — NEXT STABIL 1.0.2+14 — PUBLISHED

- Dashboard is the primary Global Search entry through a responsive SearchBar
  above all dashboard cards. Query handoff uses `/search?q=...` and the same
  repository/controller/results flow as mobile AppBar and desktop shell.
- Pagination is verified against stable entity keys and a combined reference;
  pages are disjoint and deterministic, while adjacent results may share a
  type. No production ranking/scoring change was made for the prior brittle
  type-change assertion.
- Backend release regressions and performance gates: PASS. Flutter analyze:
  PASS. Full Flutter suite: 126/126 PASS before and after version bump.
- Web, Windows and Android 1.0.2+14: PUBLISHED. Public artifact and Web bundle
  hashes match local outputs; minimum_version remains 1.0.0.
- Qdrant remains unchanged at 57 chunks covering 11 of 5903 Documents. No
  Qdrant write, upgrade, rebuild or vector backfill was performed.
- CHUNK 11: RELEASED. CHUNK 12 — AI CLIENT KNOWLEDGE: COMPLETE.

### CHUNK 12 — AI CLIENT KNOWLEDGE — COMPLETE

- Added JWT-protected `POST /api/v1/clients/{client_id}/ai/ask`. The service
  loads exactly one active Client and performs no business-data writes.
- Deterministic answers cover phone, e-mail, NIP, address and workflow status.
  Bounded retrieval adds Projects, Inspections, Timeline, Client Email History
  and lexical Documents; semantic chunks are optional and filtered by
  `client_id` with a second DB ownership check.
- The prompt treats evidence as untrusted data, permits only numbered source
  IDs supplied by retrieval and requires an explicit insufficient-data answer.
  Sources use bounded snippets and existing Client/Email/Document/Project/
  Inspection routes. Conversation context remains bounded session state only.
- Client 360 includes the responsive `Zapytaj AI o klienta` panel with example
  questions, loading/cancel, friendly error/retry and source deep links.
- Active local models remain `llama3.2` for generation and
  `qwen3-embedding:0.6b` (1024 dimensions) for embeddings. Qdrant remains at
  57 chunks covering 11 of 5903 Documents globally; client-scoped vector
  availability is narrower where legacy payloads lack `client_id`. Lexical
  retrieval and structured answers fail open without Qdrant.
- Verification: focused backend 8/8 PASS; controlled local LLM E2E 5/5 PASS;
  backend regressions and health PASS; Flutter analyze PASS; full Flutter suite
  130/130 PASS. No migration, vector backfill, Qdrant write, n8n change,
  conversation persistence or production business write occurred.
- CHUNK 13 — BUSINESS ASSISTANT: NOT STARTED.

### CHUNK 12 AI CLIENT KNOWLEDGE — NEXT STABIL 1.0.2+15 — PUBLISHED

- Web, Windows and Android publish the client-scoped `Zapytaj AI o klienta`
  panel, deterministic structured answers, bounded evidence retrieval,
  citations and structured/lexical fail-open behavior using `llama3.2`.
- Runtime models remain unchanged: generation `llama3.2`, embeddings
  `qwen3-embedding:0.6b`, Qdrant collection `ai_lab_document_chunks` at 1024
  dimensions. AI Client Knowledge does not have full semantic coverage of all
  Documents: 57 chunks cover 11 of 5903 Documents globally, and 0 current
  points have a valid `client_id` usable by client-scoped vector retrieval.
- No vector backfill, Qdrant write/rebuild/upgrade, n8n change, conversation
  persistence, migration, historical cleanup or production business write was
  performed. Structured and lexical Client retrieval remains available.
- Release gates: focused backend 34/34 PASS plus all required regressions;
  controlled local LLM E2E 5/5 PASS with rollback; Flutter analyze PASS and
  full 130/130 suite PASS before and after bump. Windows runtime smoke PASS;
  Android physical upgrade UNVERIFIED because ADB reported no device.
- Public Web, Windows and Android hashes match local outputs and stable
  manifest. `minimum_version` remains 1.0.0.
- CHUNK 13 — BUSINESS ASSISTANT: COMPLETE. See the CHUNK 13 delivery section:
  global `/ai` read-only analytics/retrieval, deterministic citations,
  bounded request-local history, no actions and no persistence.
- CHUNK 14 — TECHNICAL AI: later completed and released in 1.0.2+19.

### CLIENT DETAILS ACTION LAYOUT PATCH — NEXT STABIL 1.0.2+9 — PUBLISHED

- Edit/Delete actions are outside and above the client header card in a
  responsive Wrap; long client names retain the available card width.
- Android and Windows 1.0.2+9: PUBLISHED. `minimum_version` remains 1.0.0.
- Backend, DB, migration and ingestion: UNCHANGED.
- NEXT STEP: NEW SOURCE INGESTION CORRECTNESS — NOT STARTED.

### NEW SOURCE INGESTION CORRECTNESS — FORWARD ONLY — DONE

- New Gmail/Google Sheets sources use deterministic current-author boundaries,
  identity artifact guards and multi-contact parsing before promotion.
- Gmail body is retained in CandidateSource / Email History provenance and is
  not copied into Client.notes for newly ingested sources.
- Existing valid Client.name and primary contacts are protected; new unique
  secondary contacts may be appended without weakening existing identity.
- Historical source reprocessing, historical client/notes cleanup, Qwen 9B,
  Vertex AI and optional local 4B inference were not performed.
- Synthetic/rollback smoke and ingestion regressions: PASS. Production CRM
  writes 0; Qdrant writes 0.
- NEXT STEP: human verification on the next real incoming Gmail and Google
  Sheets record.

### CLIENT MANAGEMENT PATCH — NEXT STABIL 1.0.2+8 — PUBLISHED

- Client edit and separate notes edit: DONE.
- Multiple e-mails and phones with synchronized legacy primary fields: DONE.
- Client soft-delete: DONE; historical documents, mail and provenance remain;
  physical client delete is not used.
- Direct document upload to the current client: DONE.
- Additive `contact_20260816` migration applied; 3194 clients preserved and
  4981 contact points backfilled without splitting or cleaning legacy values.
- Android and Windows 1.0.2+8: PUBLISHED. `minimum_version` remains 1.0.0.
- NEXT STEP: NEW SOURCE INGESTION CORRECTNESS — NOT STARTED.
- Historical AI cleanup: ABANDONED / NOT PURSUED. Local 4B assistance:
  FUTURE, NEW RECORDS ONLY.

### AI CLIENT RECONSTRUCTION — RESUMABLE LARGE-MODEL BATCH FOUNDATION — DONE

- Added per-record durable private JSONL, atomic checkpoints, fail-closed
  resume, bounded manifest windows, single-attempt failures, PostgreSQL READ
  ONLY transactions, memory gates and mandatory final model unload.
- Qwen 3.5 9B proof was strictly limited to manifest indices 0–9. Resume with
  the same ten-record window made 0 new inference calls and did not process
  record 11.
- Future direction only: SMALL MODEL FIRST -> capability gate -> LARGE MODEL
  ESCALATION -> chunked processing -> persisted partial results ->
  unload/reload -> aggregate conclusions -> small-model finalization if
  capable, otherwise large-model conclusion pass.
- Capability router, document pipeline, full 128/historical runs and apply:
  NOT IMPLEMENTED. Production DB writes 0; Qdrant writes 0.

### GOLDEN BACKUP — NEXT STABIL 1.0.2+7 — HUMAN ACCEPTED

- HUMAN ACCEPTED WITH KNOWN QDRANT OFFICIAL SNAPSHOT LIMITATION.
- AUTHORITATIVE VERIFIED QDRANT RECOVERY: raw storage copy — isolated restore
  PASS 57/57.
- OFFICIAL QDRANT SNAPSHOT: restore FAIL — not relied upon.
- FULL BARE-METAL RESTORE: NOT PERFORMED.

### AI CLIENT DATA RECONSTRUCTION — PHASE 1A

- IMPLEMENTATION: DONE. Reusable layers: minimized provenance evidence packet,
  OpenAI Responses API adapter (`store=false`, strict schema, no tools),
  deterministic evidence/duplicate validator, policy and local report generator.
- PRODUCTION WRITES: 0. QDRANT WRITES: 0. No apply/promotion path exists.
- PILOT: BLOCKED — `OPENAI_API_KEY` MISSING. Deterministic 128-client manifest
  (40 clean controls and historical HOLD cases) prepared read-only; model calls 0.
- FULL 3194 CLIENT DRY-RUN: NOT STARTED.
- AUTOMATIC APPLY: NOT IMPLEMENTED.
- INCREMENTAL GMAIL/SHEETS: DESIGNED / NOT ENABLED.
- CANDIDATE AUTO-PROMOTION: NOT STARTED. CHUNK 6D: NOT PERFORMED. CHUNK 7:
  NOT STARTED.

### AI CLIENT RECONSTRUCTION — EXISTING LOCAL MODELS CALIBRATION

- Live Ollama contains only `llama3.2:latest` (3.2B Q4_K_M, generative) and
  `qwen3-embedding:0.6b` (595.78M Q8_0, embedding only). No pull/download.
- Active Chat/RAG default and historical conversations use `llama3.2`; active
  semantic/embedding pipeline and 57 chunks use `qwen3-embedding:0.6b`.
  `gemma3:4b`, `qwen3:4b` and `nomic-embed-text` in `config/ai-lab.yaml` are
  stale/unwired declarations and are not installed.
- Added reusable local Ollama reconstruction adapter using Phase 1A packet,
  schema, validator and policy. `/api/chat`, stream false, temperature 0,
  no tools; all DB calibration transactions are READ ONLY.
- `llama3.2:latest` smoke 5/5 schema-valid; full existing manifest 128/128
  schema-valid. Policy: INSUFFICIENT 72, CONFLICT 43, MODEL_INVALID 10,
  POSSIBLE_DUPLICATE 2, POLICY_REJECTED 1, KEEP 0, HIGH_CONFIDENCE 0.
- MICRO-FIX benchmarku rescored the existing raw 128-run with zero new model
  calls. Corrected clean false-change is 1/40 (2.5%): KEEP 0, non-KEEP 40,
  abstention/rejection 39. Non-KEEP alone is no longer treated as a mutation.
- Safety metrics distinguish proposal from bypass: unsupported HC proposals 2
  / bypass 0; foreign evidence proposals 3 / bypass 0; duplicate-risk 3,
  POSSIBLE_DUPLICATE 2 / bypass 0; critical policy bypass 0; HOLD unsafe 0.
- High-confidence count/covered: 0/0; coverage is
  N/A_NO_HIGH_CONFIDENCE_CANDIDATES and does not independently fail the gate.
- Future model smoke set is deterministic and diverse: clean control 1875,
  HOLD 13, address artifact 543, richer-evidence abbreviated 2063, ambiguous
  abbreviated 203. The prior `[13,1745,2256,2560,203]` set was not diverse.
- DECISION: EXISTING_MODELS_INSUFFICIENT. Full 3194-client run NOT STARTED.
  Production CRM writes 0; Qdrant writes 0.

### FINAL PRE-BACKUP PATCH — NEXT STABIL 1.0.2+7 — PUBLISHED

- Branding wszystkich produkcyjnych Flutter/native user-facing sources:
  `NEXT Stabil`; internal `ai_lab`, package/application IDs i APP_ID bez zmian.
- Business creation date: `source_record_date ?? created_at.date()`; Client
  Details pokazuje jedną `Datę dodania`, a karty zachowują tę samą semantykę.
- `/clients/page` ma addytywny `sort_order=newest|oldest`, domyślnie newest.
  Globalne effective-date sortowanie z tie-breakerem ID odbywa się przed
  pagination i korzysta z tego samego batched source-date projection co API.
- Android i Windows 1.0.2+7: PUBLISHED. Web: UNCHANGED / NOT DEPLOYED.
  `minimum_version` nadal 1.0.0; aktualizacja z +6 ma stan AVAILABLE.
- FINAL PRE-BACKUP PATCH 1.0.2+7: PUBLISHED.
- GOLDEN BACKUP: NEXT CHECKPOINT / NOT STARTED.
- DATA ARTIFACT CLEANUP: DEFERRED UNTIL AFTER GOLDEN BACKUP.
- CHUNK 6D: BLOCKED. CANDIDATE AUTO-PROMOTION: NOT STARTED. CHUNK 7:
  NOT STARTED.
