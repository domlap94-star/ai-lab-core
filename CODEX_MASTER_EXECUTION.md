# AI-Lab / NEXT Stabil — Codex Master Execution

Stan bazowy: 2026-08-14, commit wejściowy `5700681`. Dokument rozbija
`AI_LAB_MASTER_PLAN.txt` na małe checkpointy. Statusy wynikają z kodu, testów i
odczytowego audytu bazy, nie ze starych checkboxów.

## Zasada kompatybilności wdrożonych klientów

DEPLOYED BINARIES ARE API CONSUMERS. Zmiana aktualnego source nie oznacza, że
ostatnia stabilna aplikacja Windows, Android, live Web ani integracje/importy
zostały już zaktualizowane. Istniejącego publicznego response shape nie wolno
łamać bez versioned/additive endpointu, compatibility layer albo jawnej
strategii release/migracji. Legacy endpoint może zostać usunięty dopiero, gdy
minimum supported app version gwarantuje brak wspieranych konsumentów starego
kontraktu.

## Reconciliation stanu

| Obszar | Stan | Dowód / luka |
|---|---|---|
| Auth, role, wymuszona zmiana hasła | DONE | JWT, `User.role`, `must_change_password`, admin API i Flutter flow; migracja `authv1_20260813` jest aktualnym headem. |
| Flutter Windows / Android / Web | DONE | katalogi platform i działający frontend; analyze oraz 28 testów PASS. iOS/macOS są świadomie nieobecne. Linux istnieje, lecz nie jest celem produkcyjnym. |
| Release channel / self-update | DONE | stable manifest 1.0.1+4, SHA-256, testy decyzji/hash, instalacja Windows/Android. Publikacja pozostaje human-gated. |
| Supervisor i gateway split | DONE | bindy 8787/8788/8789 na loopback; public gateway jawnie odrzuca `/control`. |
| Document Intelligence | DONE | centralny pipeline, pages/assets/OCR/Office/archive oraz testy regresyjne. Batch 30 istnieje; pełny cel jakościowy pozostaje częściowo otwarty. |
| Chunking / embeddings / Qdrant / semantic retrieval | DONE | migracja chunk 2.0, embedding service, Qdrant store i realny baseline Hit@3/5 3/3. |
| RAG / citations / evidence | DONE | chroniony `/api/v1/ai/rag`; test 401/200/422 i claim→evidence→source PASS. |
| CRM frontend | PARTIAL | paginowana lista klientów, repozytorium dokumentów oraz lazy Client 360 Documents i Email History istnieją; dalsze workspace panels są TODO. |
| Candidate pipeline | DONE/PARTIAL | review/promotion, duplicate protection i read-only identity projection działają; trwały multi-contact i quality cleanup są otwarte. |
| Document read API/UI | DONE | bezpieczne auth list/detail/content API oraz responsywne Flutter Documents UI działają na wspólnej sesji i Dio. |
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

### PRE-RELEASE CHUNK — ADMIN USER LIFECYCLE — TODO

Status: MANDATORY BEFORE NEXT NATIVE RELEASE.

- Akcja „Usuń użytkownika” w Admin UI oraz backend admin-only.
- Preferowana bezpieczna deactivate/soft-delete zamiast hard delete, jeśli
  aktualny model pozwala zachować kompatybilność i audit.
- Zakaz self-delete/self-deactivate oraz usunięcia/dezaktywacji ostatniego
  aktywnego Administratora.
- Potwierdzenie operacji w UI i audit kto/kiedy wykonał akcję.
- Brak dalszego logowania oraz jawna weryfikacja zachowania istniejących JWT.
- Testy 401/403, self, last-admin i zwykłego użytkownika.
- Zachowanie deployed API compatibility.
- Zero publikacji release bez human approval.
- Ten checkpoint musi być DONE przed następnym Android/Windows release; nie
  został zaimplementowany w CHUNK 5.

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

### 7. Contact and address model — TODO

- Cel: wiele kontaktów/emaili/telefonów/adresów z provenance. Zależności: 6.
- Zakres: modele/API/UI, Alembic additive migrations, read-only backfill plan.
- Ryzyko: konflikty i kompatybilność scalar fields. Dane: DRY-RUN; backfill gate.
- Acceptance: CRUD i provenance testowane, downgrade/rollback migracji, audit.
- Commit: `Add provenance-aware client contact model`.

### 8. Document-client matching workspace — TODO

- Cel: rozstrzygnąć 99 unmatched i 161 candidate-only. Zależności: 2–4.
- Zakres: suggestions/confidence, manual link/unlink/move, audit trail, UI.
- Quality debt: osobno rozstrzygnąć 20 Gmail attachment documents bez
  client_id/candidate_id wykrytych w MICRO-FIX 5A; CHUNK 6 nie przypisuje ich.
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
