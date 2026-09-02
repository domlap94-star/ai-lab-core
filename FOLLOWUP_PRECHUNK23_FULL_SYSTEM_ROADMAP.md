# NEXT Stabil — PRE-CHUNK23 pełnosystemowa roadmapa naprawcza

**CANONICAL ROADMAP STATUS: ACTIVE**

**ROADMAP STATUS: ACTIVE**

**PRODUCTION MIGRATION: HOLD / NO-GO**

**CHUNK23: NOT STARTED**

## 1. Przeznaczenie i zasady zamykania

Ten dokument jest kanoniczną, żywą checklistą napraw PRE-CHUNK23 wynikających
z pełnego audytu read-only z 2026-08-31. Zakończone pozycje pozostają w pliku
jako historia audytowa. Każde zamknięcie musi wskazywać dowód, wynik testów i
commit lub zatwierdzony artefakt operacyjny.

- `[ ] OPEN` — brak wdrożonej i zweryfikowanej naprawy.
- `[~] FIXED_UNVERIFIED` — kod został zmieniony, ale wymagany dowód nie zamyka
  jeszcze kryterium.
- `[x] CLOSED` — kompletna naprawa oraz dowód akceptacyjny.
- Sama zmiana kodu bez testów i dowodu ma status `FIXED_UNVERIFIED`, nigdy
  `CLOSED`.
- Migracja produkcyjna pozostaje owner-gated. Ten dokument nie jest zgodą na
  jej zastosowanie.
- Żadna pozycja PRE-CHUNK23 nie upoważnia do rozpoczęcia CHUNK23.

## 2. Baseline, bezpieczeństwo i stan audytu

### 2.1 Źródła i identyfikatory

- [x] Audyt read-only zakończony: 2026-08-31.
- [x] Raport źródłowy:
  `FOLLOWUP_PRECHUNK23_FULL_SYSTEM_READONLY_AUDIT_20260831` — raport chat-only,
  niewpisany do repozytorium.
- [x] `origin/main` w czasie audytu:
  `4cc7446f9ad311c63c72727a969a55f319258669`.
- [x] Branch audytowy:
  `audit/visual-evidence-v2-migration-20260831`.
- [x] Commit audytowy:
  `65783d1c1e1b7b13d0fcccf85f922d8af8c0bf1c`.
- [x] Produkcyjny Alembic head:
  `followup_assistant_chat_history_20260829`.
- [x] Kandydat migracji:
  `followup_visual_evidence_v2_20260831`.
- [x] Parent migracji:
  `followup_assistant_chat_history_20260829`.
- [x] SHA-256 migracji:
  `E67BB96F3D5EF5C14CEDDED9A0601BD20ED540CC13EFB66E16882BB3A5E64E03`.
- [x] SHA-256 testu migracji:
  `3633487C33B078C8D1553478203B5D7ED7965E1158C41497964270C76DB98188`.
- [x] Visual V2 production tables: absent.
- [x] PRE-CHUNK23: active.
- [x] CHUNK23: `NOT STARTED`.
- [x] Production migration: owner-gated, `HOLD / NO-GO`.

### 2.2 Snapshot produkcyjny z audytu

| Obszar | Stan 2026-08-31 |
|---|---|
| Backend | HTTP 200 |
| Public gateway | HTTP 200 |
| Supervisor | READY |
| Public `/control` | HTTP 404 |
| Supervisor Analysis queue | 0 |
| Supervisor Vision queue | 0 |
| Ollama resident models | 0 |
| Active Documents | 5,982 |
| AssistantRuns | 14 |
| Document preparation jobs | 52 |
| AnalysisJobs | 117 |
| BackupRuns | 22 |
| Gmail CandidateSources | 4,297 |
| Active Assistant/Backup/Restore | 0/0/0 |

### 2.3 Dokumenty i przygotowanie

- [x] Nowe canonical Documents po aktywacji durable preparation: 48.
- [x] Dokładne powiązane preparation jobs: 48; brakujących: 0.
- [x] Statusy: ready 19; failed/ocr-required 9; failed 11; queued 8;
  stale running `local_analysis` 1.
- [x] Stale job:
  `8ae38109-d239-4448-a07f-9de33501d7e0`, Document `8926`, trigger
  `ingestion`, stage `local_analysis`, lease wygasł
  `2026-08-31 13:05:32 UTC`; osiem queued ingestion jobs pozostawało za nim.

### 2.4 Gmail

- [x] Active Gmail CandidateSources: 4,297; Matching V2 metadata: 35;
  historical/unversioned: 4,262.
- [x] Linked to Client: 4,144; unmatched: 153.
- [x] Current matcher: certain 1,524; high 692; ambiguous 1,908;
  unresolved 173.
- [x] Historical/unversioned certain existing Client: 1,516.
- [x] Unmatched sources resolving to certain existing Client: 6.
- [x] Active Gmail attachments: 5,945; linked: 5,722; unlinked: 223;
  sources z co najmniej jednym unlinked document: 83.
- [x] Mailbox 30-day: 90 IDs; PostgreSQL: 85; missing: 5;
  duplicate active external IDs: 0.

### 2.5 Backup

- [x] Enabled schedules: 3.
- [x] BackupRuns: 22 completed; queued/running/failed: 0/0/0.
- [x] Active RestoreRuns: 0.
- [x] `backup_retention_delete_enabled=false`.
- [x] Wszystkie bieżące destinations dostępne; brak bieżącego zagrożenia
  pojemności.
- [x] Bieżące policies nie kodują docelowych 10% / 14 dni / 60 dni.
- [x] E: total `1,024,208,490,496` B; free `800,647,315,456` B;
  free 78.17%.
- [x] F: total `500,091,056,128` B; free `495,783,350,272` B;
  free 99.14%.

### 2.6 Zasoby i CAD

- [x] Windows available: około 8.94 GiB.
- [x] WSL available: około 14.00 GiB; WSL swap used: około 1.98 MiB.
- [x] Cold Qwen9 projection na Windows: `8.94 - 6.60 = 2.34 GiB` przy
  wymaganej rezerwie 4 GiB.
- [x] `FALSE_RESOURCE_STARVATION_RISK = MEDIUM`; nie jest to dowód wycieku
  pamięci.
- [x] CAD inventory: DWG 41; DXF 0; IFC 0; DGN 0.

### 2.7 Stopka bezpieczeństwa audytu

- [x] Source changes: 0.
- [x] Production DB writes: 0; migration apply: 0.
- [x] Backup writes/deletes: 0.
- [x] Gmail mutations: 0.
- [x] Visual/Vision jobs: 0; Analysis jobs: 0; Temporary Chat calls: 0.
- [x] Model calls/unloads: 0/0.
- [x] Restarts: 0; Qdrant writes: 0; APK: 0.
- [x] CHUNK23: `NOT STARTED`.

## 3. Kanoniczny rejestr blockerów

| Kod | Severity | Scope | Status | Finding | Closure requirement | Dependencies | Evidence | Closing commit |
|---|---|---|---|---|---|---|---|---|
| VIS-01 | P0 | audit migration only | OPEN | Invalid failed sanitization can become externalizable. | Legal privacy combination constraints plus positive/negative PostgreSQL tests. | Visual V2 frozen contract | — | — |
| VIS-02 | P0 | audit migration only | OPEN | Visual consumer request ownership can be bypassed under MATCH SIMPLE. | Independent consumer -> request FK plus nullable-run negative test. | Visual consumer schema | — | — |
| VIS-03 | P0 | audit migration only | OPEN | Visual atom uses Assistant FACT/ESTIMATE/HYPOTHESIS/MISSING authority classes. | Perception-only atom vocabulary and contract tests. | Visual result contract | — | — |
| VIS-04 | P0 | audit migration only | OPEN | External requirement binding is not tied to the canonical frozen RequirementSourceBinding. | Exact relational binding and foreign-source negative tests. | Requirement provenance | — | — |
| VIS-05 | P0 | audit migration only | OPEN | `partial + required_coverage_satisfied=false` can create an artifact. | Four independent coverage counters, relational recomputation and artifact rejection tests. | Artifact acceptance | — | — |
| VIS-06 | P0 | audit migration only | OPEN | Final-consumer cancellation can race artifact acceptance. | Shared lock order, fencing, exact consumer-set hash and concurrency tests. | Consumer lifecycle | — | — |
| VIS-07 | P1 | audit migration only | OPEN | `work_attached` occupies the active request fingerprint. | Correct active pre-plan partial-index predicate and retry/idempotency tests. | Request state vocabulary | — | — |
| VIS-08 | P1 | audit migration only | OPEN | Privacy assessment does not persist detector generation. | Exact detector generation in assessment and fingerprint/reuse tests. | Privacy reproducibility | — | — |
| VIS-09 | P1 | audit migration only | OPEN | Visual capability vocabulary is open. | Closed perception-capability vocabulary plus rejection tests. | Capability contract | — | — |
| VIS-10 | P1 | audit migration only | OPEN | Migration test omits critical frozen-contract invariants. | Expanded isolated PostgreSQL matrix, concurrency tests and roundtrip proof. | VIS-01..VIS-09 | — | — |
| DOC-01 | P0 | present today | FIXED_UNVERIFIED | Normal document ingestion can trigger explicit external Vision V1. | Canonical ingestion ends at local Material V3; no automatic external Vision. | Runtime containment | Independent source review PASS; audit `f4041f709b88a111cd1fe9eba4d8640b1bede15f`; promoted main source `d69e373fc435c6a5373a256b1acd206fddd3d184`; focused `9/9` and main-based relevant regression `42/42` PASS; deployment/live verification pending. | pending |
| DOC-02 | P0 | present today | FIXED_UNVERIFIED | OOXML/ODF media extraction uses unbounded `archive.read(member)`. | Entry count, per-entry bytes, total bytes, compression-ratio and streaming bounds. | File-safety layer | Independent source review PASS; audit `c08b55a07ac1a8b761f0c06ed70dd90085a7b944`; promoted main source `5ae13876ed4e0104a9c049e5b68d67177b0372d9`; focused T01–T24, main-based relevant regression `34/34`, and actual XLSX/PPTX/ODT promotion probes PASS; deployment/live verification pending. | pending |
| DOC-03 | P1 | present today | FIXED_UNVERIFIED | Expired running preparation blocks eight queued jobs. | Lease recovery, fencing and queue-drain regression test. | Preparation dispatcher | Independent source review PASS; audit `b1dee3d0afff1aefb5235176502cf0256fe975ce`; promoted main source `f601c2c4cb88f58f5095b842b0135316d8721f6f`; focused T01–T18 and consolidated main-based regression `91/91` PASS; queue-drain, child-cancellation and shutdown-propagation probes PASS; deployment/live verification pending. | pending |
| DOC-04 | P1 | present today | OPEN | Document 8903 contains two unpaired low-surrogate escapes in each of `metadata_raw` and `metadata_normalized`. | Shared recurrence hardening and isolated repair rehearsal, followed by a separate owner-approved controlled data repair with verified backup and audit proof. | DOC-02 safety; DOC-04A; owner write gate | Independent projection review PASS; audit report `9567583fcef4278b32e46d0c81e8328106332499`; promoted main report `5e2167fabf8229b703b8757853f059fc20c14f50`; DOC-04A source hardening independently accepted at final audit `116c43d65e9045d2feac85ffaaf9cdfa380ba9af` and main source `243e6e53df2d293476e2c38ece49bd6c73932ecc`; U/R/G/H/I isolated matrices and PostgreSQL concurrency/parent-control proof PASS; recurrence path and guarded repair source accepted. Windows-host runtime, deployment and production repair remain pending. `SOURCE_HARDENING_FIXED_UNVERIFIED / WINDOWS_RUNTIME_BLOCKED / PRODUCTION_REPAIR_PENDING`. | pending |
| AUTO-01 | P0 | target V3 design | OPEN | No durable non-Assistant owner exists for automatic Text Intelligence. | Document/material-generation-scoped durable Text Intelligence work ledger or explicitly approved equivalent. | Material V3 schema | — | — |
| ASST-01 | P0 | present today | OPEN | Visual stages are planned but not executed; Advanced can start before required Visual. | Local-only reasoner, executable Visual branch, local re-synthesis and Advanced ordering proof. | Visual V2 + Text Intelligence V3 | — | — |
| GMAIL-01 | P1 | present today | OPEN | Five mailbox messages are missing from PostgreSQL; six unmatched sources now resolve certainly; one current linked conflict exists. | Bounded, idempotent, owner-approved mailbox/import reconciliation and repair report. | GMAIL-02; backup gate | — | — |
| GMAIL-02 | P1 | present today | OPEN | New Gmail attachment reconciliation is unreachable because it depends on Vision eligibility. | Trigger deterministic second pass after local Material/Text completion, independent of Vision. | Material/Text runtime | — | — |
| RES-01 | P1 | present architecture | OPEN | NEXT model ownership is process-local and is lost after backend restart. | Durable/fenced model residency ownership without taking ownership of user or Open WebUI models. | Resource coordinator | — | — |
| RES-02 | P1 | present architecture | OPEN | OCR, rendering, LibreOffice, asset extraction and backup have no shared heavy resource admission. | Cross-system admission, priority, concurrency and backpressure policy. | RES-01; workload measurements | — | — |
| BACKUP-01 | P1 | present configuration | OPEN | Owner E/F retention policy is not encoded and real deletion remains off. | Separate approved schedule/retention configuration and separately approved real-delete activation. | Owner cadence/scope decision | — | — |

**OPEN P0: 10**

**OPEN P1: 11**

**OPEN BLOCKERS: 21**

## 4. Workstream: Visual Evidence Pipeline V2 migration

> **DO NOT APPLY THE CURRENT AUDIT MIGRATION TO PRODUCTION.**

### 4.1 Privacy i exact-byte authorization

- [ ] VIS-01: zamknąć pełną macierz legalnych stanów
  `SourcePrivacyAssessment`.
- [ ] Odrzucić `sanitizable_external + allowed_external + failed` oraz każdą
  kombinację bez poprawnego authorized payload.
- [ ] Powiązać raw, sanitized i authorized SHA-256 z dokładnymi bajtami.
- [ ] Zapisać policy generation, detector generation i sanitizer generation.
- [ ] Dodać pozytywne i negatywne testy PostgreSQL dla wszystkich stanów.
- [ ] Udowodnić, że `restricted_never_external` nie może wejść do external batch.

### 4.2 Ownership, vocabulary i idempotency

- [ ] VIS-02: dodać niezależny FK
  `VisualConsumer.visual_request_id -> visual_analysis_requests.id`, skuteczny
  także przy `visual_run_id IS NULL`.
- [ ] Zamknąć i przetestować vocabulary VisualRequest, VisualRun, VisualStage i
  VisualConsumer.
- [ ] VIS-07: wyłączyć `work_attached` z active pre-plan fingerprint predicate.
- [ ] Udowodnić brak duplikatów equivalent VisualRuns przy wyścigu.
- [ ] VIS-09: zamknąć perception-capability vocabulary i odrzucać obce wartości.
- [ ] Zweryfikować generation, lease, heartbeat, retry, cancellation,
  supersession i recovery.

### 4.3 Percepcja, provenance i coverage

- [ ] VIS-03: zastąpić Assistant authority classes percepcyjnym vocabulary
  atomów; Visual nie tworzy autorytatywnych FACT/ESTIMATE/HYPOTHESIS/MISSING.
- [ ] VIS-04: związać każdy external requirement przez dokładny canonical
  `RequirementSourceBinding`.
- [ ] Zachować exact source checksum, generation, page/asset identity i
  external batch source binding.
- [ ] VIS-05: przechowywać i relacyjnie przeliczać osobno:
  planned requirement count, covered requirement count, required requirement
  count, covered required requirement count.
- [ ] Egzekwować: complete + required=true -> artifact; partial + required=true
  -> artifact z limitation; partial + required=false -> no artifact/review;
  none -> no artifact.
- [ ] Nie traktować partial coverage jako complete.

### 4.4 Consumer race i artifact acceptance

- [ ] VIS-06: zdefiniować wspólną kolejność locków i fencing dla final consumer
  cancellation oraz artifact acceptance.
- [ ] Przeliczać exact active consumer set i jego hash w tej samej transakcji.
- [ ] Akceptować artifact tylko dla rzeczywiście aktywnych consumers.
- [ ] Odrzucać late result po anulowaniu wszystkich consumers.
- [ ] Udowodnić, że checksum/generation source change czyni artifact stale.

### 4.5 Migracja i test matrix

- [ ] VIS-10: rozszerzyć isolated PostgreSQL matrix o wszystkie frozen
  invariants i negatywne FK/CHECK/UNIQUE tests.
- [ ] Dodać concurrency tests dla request dedupe, consumer cancel i artifact
  acceptance.
- [ ] Isolated upgrade PASS.
- [ ] Downgrade z V2 data deterministycznie refused.
- [ ] Clean downgrade do parent PASS.
- [ ] Re-upgrade PASS; jeden Alembic head; brak duplicate constraints/indexes.
- [ ] Production-shape rehearsal bez production writes.
- [ ] Final migration source review PASS.

## 5. Natychmiastowe production containment

Kolejność jest obowiązkowa.

### 5.1 DOC-01 — ingestion-driven V1 externalization

**Status: `FIXED_UNVERIFIED`.** Containment accepted: ordinary ingestion can no
longer enter legacy external Vision. Known limitation: scan-only ingestion now
fails closed until Material V3/Visual V2 provides the replacement local-first
workflow. Full closure still requires deployment/live proof, a canonical local
Material V3 terminal state, proof of no automatic external Vision, and an
accepted recovery path for later explicit analysis.

- [ ] Usunąć automatyczne przejście zwykłego ingestion do external Vision V1.
- [ ] Udowodnić canonical przepływ:
  `Document ingestion -> local Material only`.
- [ ] Udowodnić brak przepływu:
  `ingestion -> vision_processing -> explicit Vision V1 -> Temporary Chat`.
- [ ] Pozostawić legacy explicit Vision wyłącznie jako compatibility path do
  kontrolowanego retirement, nigdy jako automatyczny skutek ingestion.
- [ ] Testy dla text PDF, scan PDF, image i Office potwierdzają zero
  automatycznej externalization.

### 5.2 DOC-02 — OOXML/ODF ZIP allocation

**Status: `FIXED_UNVERIFIED`.** Source containment is independently accepted;
deployment and live verification remain pending.

- [x] Zastąpić unbounded `archive.read(member)` bounded/streaming extraction.
- [x] Egzekwować max archive entries.
- [x] Egzekwować per-entry uncompressed bytes.
- [x] Egzekwować total uncompressed bytes.
- [x] Egzekwować compression-ratio bound.
- [x] Egzekwować asset-count i asset-bytes bounds.
- [x] Egzekwować image dimension i pixel bounds przed pełnym decode.
- [x] Zachować istniejące assets/files po hard preflight rejection z `force=True`.
- [x] Dodać bezpieczne testy ZIP-bomb bez alokacji niekontrolowanych danych.
- [ ] Wdrożyć i potwierdzić live bounded extraction bez production file processing.

Znane ograniczenia, które nie blokują source containment:

- po udanym Phase-A validation ścieżka `force=True` nadal usuwa i zatwierdza
  poprzednie assets przed commitem kompletnego replacement set; późniejszy
  Phase-B persistence failure może pozostawić dokument bez starych assets;
  pełna transakcyjność replacement pozostaje hardeningiem Material V3;
- wspólna admission/control dla upload bytes, LibreOffice, OCR, PDF rendering,
  Assistant Qwen i backup IO pozostaje osobnym blockerem `RES-02`;
- committed evidence jest najsilniejsze dla DOCX i konwertowanego DOC;
  dodatkowe main-promotion probes potwierdziły rzeczywistą bounded persistence
  dla XLSX, PPTX i ODT.

### 5.3 DOC-03 — stale preparation recovery

**Status: `FIXED_UNVERIFIED`.** Source lease recovery and attempt fencing are
independently accepted; deployment, live queue recovery and Material V3 final
replacement remain pending.

- [x] Używać unikalnego claim tokenu dla każdej próby.
- [x] Odzyskiwać retryable expired running leases z poprawnym fencing.
- [x] Terminalizować expired leases po wyczerpaniu prób.
- [x] Nie pozwalać staremu workerowi zapisać wyniku po lease takeover.
- [x] Fence'ować heartbeat dokładnym claim tokenem.
- [x] Izolować cancellable intelligence work w child tasku.
- [x] Utrzymywać niezależny bounded recovery poll podczas długiej pracy.
- [x] Udowodnić kolejkę: jeden stale running nie blokuje kolejnych jobs.
- [x] Przetestować child cancellation, dispatcher shutdown i drain kolejki.
- [ ] Wdrożyć source commit i potwierdzić runtime/live recovery.
- [ ] Odzyskać produkcyjną kolejkę wyłącznie po osobnym owner gate.
- [ ] Potwierdzić live brak duplicate model/Vision work.
- [ ] Zastąpić compatibility pipeline docelowym Material V3.

Znane ograniczenia:

- publikacja `PreparationJob` jest fenced, ale zapisy stron, assets i Document
  wykonywane przez `DocumentProcessingService` nie mają jeszcze claim tokenu;
  pełna attempt-scoped publikacja materiału pozostaje pracą Material V3;
- przejście stanu po legacy Vision jest fenced, ale synchronicznego
  `process_explicit_vision_document` uruchomionego przez `asyncio.to_thread` nie
  można force-stopować przez anulowanie coroutiny; late result nie może
  awansować replacement PreparationJob;
- zdrowa długa intelligence albo legacy resume nadal może opóźniać serialną
  kolejkę; DOC-03 zamyka expired-lease deadlock, nie Material V3/AUTO-01/RES-02
  concurrency i backpressure;
- source nie jest jeszcze wdrożony, a produkcyjny stale job pozostaje
  niezmieniony.

### 5.4 DOC-04 — controlled metadata repair

**Status:** `OPEN — SOURCE_HARDENING_FIXED_UNVERIFIED / WINDOWS_RUNTIME_BLOCKED / PRODUCTION_REPAIR_PENDING`

- [x] Production diagnosis wykonano read-only.
- [x] Affected scope ograniczono do Document `8903`.
- [x] Zidentyfikowano affected columns: `metadata_raw` i
  `metadata_normalized`.
- [x] Zapisano exact before hashes.
- [x] Zapisano exact deterministic candidate hashes.
- [x] Zweryfikowano storage size/checksum integrity.
- [x] Wybrano minimal lexical repair.
- [x] Isolated PostgreSQL `jsonb` candidate validation: PASS.
- [x] Zaprojektowano compare-and-swap, backup i write gates.
- [x] Customer-content-free projection committed.
- [x] Zaimplementować shared surrogate-safe metadata persistence boundary.
- [x] Dodać recurrence-prevention tests.
- [x] Zbudować exact isolated repair executable.
- [x] Egzekwować backup scope, freshness i physical proof guards.
- [x] Weryfikować runtime critical Git blob identity.
- [x] Używać canonical operation advisory lock i preparation-row fencing.
- [x] Używać `READ COMMITTED` fresh-snapshot coordination.
- [x] Wykonać isolated database execution/rollback matrix i production-shape
  source-contract rehearsal bez production write.
- [ ] Zbudować versioned Windows-host repair runtime.
- [ ] Potwierdzić Windows-host readiness.
- [ ] Wdrożyć source hardening.
- [ ] Wykonać actual production preflight.
- [ ] Utworzyć fresh verified physical backup.
- [ ] Uzyskać osobne owner approval dla production write.
- [ ] Freshly recheck before hashes, `xmin`, `updated_at` i storage checksum.
- [ ] Naprawić dokładnie jeden row i dwie columns.
- [ ] Wygenerować post-repair before/after evidence.
- [ ] Potwierdzić, że żaden inny Document się nie zmienił.

The actual production repair is **NOT authorized** by the projection report or
this roadmap update.

#### 5.4.1 DOC-04A — recurrence hardening and isolated repair executable

**DOC-04A STATUS:** `FIXED_UNVERIFIED — SOURCE ACCEPTED / WINDOWS RUNTIME NOT READY / NO PRODUCTION WRITE`

Repair source jest zaakceptowany, ale nie może zostać użyty wobec production,
dopóki dedykowany versioned runtime nie przejdzie host-readiness.

Potwierdzona luka recurrence:

- `DocumentMetadataService._json_safe` przyjmuje strings bez zmian;
- `DocumentMetadataService._clean` nie odrzuca unpaired surrogates;
- dynamic keys są stringified bez surrogate check;
- intake metadata może wejść do `metadata_raw`;
- `DocumentProcessingService` zapisuje wynik bez wspólnej surrogate-safe
  persistence boundary;
- PostgreSQL `JSON` może przyjąć wartość odrzuconą później przez operatory
  `jsonb`.

Source-level DOC-04A jest zakończony. Production repair nadal wymaga osobno:
versioned Windows-host runtime, wdrożenia, actual production preflight, fresh
verified backup, odświeżenia wszystkich exact guards i jawnej zgody właściciela.

## 6. Material V3

- [ ] Material V3 wykonuje wyłącznie lokalne structural preparation.
- [ ] Wdrożyć bounded native extraction.
- [ ] Wdrożyć selective local OCR.
- [ ] Wdrożyć bounded page rendering.
- [ ] Inwentaryzować embedded assets z limitami ilości i bajtów.
- [ ] Utworzyć immutable `MaterialGeneration` dla checksum/generation.
- [ ] Utrwalać exact `MaterialSources` i ich SHA-256/provenance.
- [ ] Weryfikować source checksum przed przyjęciem wyniku.
- [ ] Utrwalać jawne limitations, truncation i unsupported capability.
- [ ] Zapewnić bounded retry, lease, heartbeat, fencing i recovery.
- [ ] Zapewnić backpressure dla seryjnego ingestion burst.
- [ ] Material V3 nie używa Qwen.
- [ ] Material V3 nie używa Vision/Visual.
- [ ] Material V3 nie używa Temporary Chat ani Advanced.
- [ ] Dodać lazy recovery dla deduplicated historical Documents bez current
  MaterialGeneration.

## 7. Automatic Text Intelligence V3

**Wymaganie produktu:** każdy nowy wspierany Document otrzymuje, bez
AssistantRun: (1) Material V3, następnie (2) local Text Intelligence V3.

- [ ] AUTO-01: zakończyć osobny design gate przed zmianą frozen migration.
- [ ] Wybrać i zatwierdzić durable non-Assistant owner, np.
  `DocumentIntelligenceJob`, albo jawnie zatwierdzony odpowiednik.
- [ ] Powiązać job z Document i exact MaterialGeneration.
- [ ] Utrwalać source-set fingerprint i analyzer generation.
- [ ] Zdefiniować status/stage vocabulary.
- [ ] Zdefiniować lease, heartbeat, retry, cancellation i fencing.
- [ ] Zdefiniować supersession po source checksum/generation change.
- [ ] Zapewnić idempotency i consumer sharing.
- [ ] Uruchamiać najwyżej jedną equivalent local Qwen analysis naraz.
- [ ] Nie uzależniać ingress intelligence od AssistantRun.
- [ ] Ocenić, czy potrzebna jest addytywna korekta migracji; każda produkcyjna
  migracja wymaga osobnego owner gate.

## 8. Unified Assistant

- [ ] Zachować deterministic target/scope/privacy validation.
- [ ] Wyodrębnić `UnifiedAssistantLocalReasoner` jako local-only first pass.
- [ ] Pierwszy local pass nie zależy od Advanced.
- [ ] Local reasoner nie tworzy `AnalysisJob`.
- [ ] Utrzymać strict local result contract, source refs i tool refs.
- [ ] Wykonać `VisualNeedGate` po local pass.
- [ ] ASST-01: zaimplementować rzeczywiście wykonywalny Visual branch.
- [ ] Required Visual zawsze kończy się przed możliwością Advanced.
- [ ] Utrzymać poprawny `VisualConsumer` lifecycle i isolation per AssistantRun.
- [ ] App close/minimize/reopen nie anuluje pracy i odtwarza właściwy stan.
- [ ] Po Visual wykonać local re-synthesis; Temporary Chat output nigdy nie
  dociera bezpośrednio do użytkownika.
- [ ] Final answer pozostaje source-bound i przechodzi lokalne validation gates.
- [ ] Zachować Chat History isolation między conversations.
- [ ] Explicit cancel anuluje właściwego consumer/run; delete chat nie oznacza
  cancel run.
- [ ] Udowodnić recovery po backend i worker restart.
- [ ] Przeprowadzić F0 parity requalification po zmianie reasoning boundary.

## 9. Document capability matrix

### 9.1 PDF

- [ ] Native text extraction z exact page provenance.
- [ ] Selective OCR wyłącznie dla stron bez usable text.
- [ ] Bounded page render dla diagramów, map i tabel.
- [ ] Jawny page limit; obecny bound ma być mierzalny i testowany.
- [ ] Truncation zawsze jako explicit limitation, nigdy implicit complete.

### 9.2 Office i RTF

- [ ] DOC/DOCX, ODT, PPT/PPTX, ODP i RTF: lokalna bounded conversion/extraction.
- [ ] Rendered pages i local OCR dla potrzebnych stron.
- [ ] Embedded media z provenance i limitami.
- [ ] Conversion timeout, memory limit i output-size limit.
- [ ] Brak orphan LibreOffice processes po success, failure i cancel.

### 9.3 Spreadsheets

- [ ] XLS/XLSX/ODS: cell oraz formula/value provenance.
- [ ] Zachować sheet identity i table structure.
- [ ] Inwentaryzować embedded media, charts, shapes i drawings.
- [ ] Zapewnić visual-ready render albo explicit limitation.
- [ ] Jawnie obsłużyć hidden sheets, external links i macros bez wykonania
  niezaufanego kodu.

### 9.4 Obrazy

- [ ] JPG/JPEG, PNG, WEBP, HEIC/HEIF, TIFF i BMP.
- [ ] Bounded decode oraz decoded-pixel limits.
- [ ] Local OCR, exact checksums i source provenance.
- [ ] EXIF/privacy sanitization przed jakąkolwiek externalization.

### 9.5 EML

- [ ] Bounded headers/body extraction.
- [ ] MIME part count i decoded-byte limits.
- [ ] Attachment inventory z exact provenance.
- [ ] Nested-message depth/count limits.

### 9.6 CAD/BIM

- [ ] Osobny owner design/approval dla DWG, DXF, IFC i DGN.
- [ ] Wymagać lokalnego bounded parser/converter.
- [ ] Nie wysyłać raw CAD do Temporary Chat.
- [ ] PDF export pozostaje obsługiwany jako PDF.
- [ ] Current state: 41 active DWG, brak canonical analysis path,
  fail-closed unsupported.
- [ ] Nie traktować CAD implementation jako już zatwierdzonej.

## 10. Gmail -> Client

### 10.1 New Gmail messages

- [ ] Tylko `certain` może auto-linkować do istniejącego Client.
- [ ] Ambiguous/unresolved pozostaje review-only.
- [ ] Nie tworzyć automatycznie niepoprawnych Clients.

### 10.2 Historical/unversioned Gmail sources

- [ ] Zachować baseline 4,262 historical/unversioned.
- [ ] Przygotować bounded dry-run z old -> proposed new projection.
- [ ] Naprawa wymaga verified backup, owner approval i audit trail.

### 10.3 Attachment-assisted second pass

- [ ] GMAIL-02: uruchamiać deterministic second pass po local Material/Text
  completion, niezależnie od Vision eligibility.
- [ ] Text PDF otrzymuje second pass bez Vision.
- [ ] Zapewnić idempotency i ochronę istniejących poprawnych Client links.

### 10.4 Mailbox-to-database completeness

- [ ] Wyjaśnić/importować 5 brakujących mailbox message IDs w zatwierdzonym,
  bounded planie.
- [ ] Potwierdzić brak duplicate active external IDs po naprawie.

### 10.5 Controlled historical repair

- [ ] GMAIL-01: rozstrzygnąć 6 unmatched certain matches oraz 1 linked conflict
  bez masowego relinkowania.
- [ ] Zachować ambiguity jako manual review.
- [ ] Nie wykonywać Gmail mutations poza jawnie zatwierdzonym read/import.
- [ ] Zarchiwizować exact before/after counts i repair audit.

## 11. Resource coordination i false starvation

**FALSE_RESOURCE_STARVATION_RISK = MEDIUM**

Nie klasyfikować tego jako udowodniony memory leak i nie obniżać 4 GiB / 3 GiB
przed pomiarami.

### 11.1 Ownership i model admission

- [ ] RES-01: utrwalić/fence'ować NEXT model residency ownership przez backend
  restart.
- [ ] Nigdy nie przejmować własności user/Open WebUI/unknown model na podstawie
  samej nazwy.
- [ ] Skalibrować cold Qwen9 i warm Qwen9 na aktualnym runtime.
- [ ] Skalibrować embedding -> Qwen transition i warm -> cold thrash.
- [ ] Wykrywać stale static projections i unload failure.
- [ ] Zdefiniować zachowanie przy telemetry failure i swap growth.
- [ ] Zachować normal reserve 4 GiB i emergency floor 3 GiB.

### 11.2 Cross-system heavy admission

- [ ] RES-02: objąć wspólną polityką OCR, rendering, LibreOffice, asset
  extraction, Qwen, embedding i backup I/O.
- [ ] Zdefiniować interactive vs background priority.
- [ ] Zdefiniować concurrency caps i queue backpressure.
- [ ] Nie pozwalać ingestion generować ciężkiej pracy szybciej niż bounded queue
  może ją odprowadzić.
- [ ] Przeprowadzić long-run no-leak, false-starvation, unload recovery i final
  Ollama residency audit.

### 11.3 Obowiązkowe scenariusze akceptacyjne

- [ ] Cold model.
- [ ] Warm NEXT-owned model.
- [ ] Backend restart z surviving NEXT model.
- [ ] External/user-owned model resident.
- [ ] Embedding resident.
- [ ] OCR/render running.
- [ ] LibreOffice running.
- [ ] Backup running.
- [ ] Burst of mail attachments.
- [ ] Assistant requested during background ingestion.

## 12. Backup

Stan audytu: bieżące backupy są safe/verified, capacity jest healthy, real
deletion jest disabled, a owner retention policy nie jest jeszcze configured.

- [ ] Zweryfikować trzy schedules i ich cadence/scope/destination.
- [ ] Wymagać `plan_revision == last_reconciled_revision` przed operacją.
- [ ] Monitorować destination health, BackupRuns i RestoreRuns.
- [ ] Monitorować E/F volume health.
- [ ] Retention preview porównuje latest, max(last 5) i average(last 5) size.
- [ ] Zakodować owner-approved hard floor 10% i cleanup target 12%.
- [ ] F: minimum protected age 14 full days.
- [ ] E: minimum protected age 60 full days.
- [ ] Zachować minimum retained count.
- [ ] Unassigned backups nigdy nie mają deletion authority.
- [ ] Wymagać pre/post backup enforcement i fresh revalidation.
- [ ] Real delete wymaga osobnego approval i live gate.
- [ ] Zapisać deletion audit trail i zweryfikować actual reclaimed bytes.
- [ ] Wykonać restore drill.
- [ ] Wykonać verified pre-migration backup.

### 12.1 OWNER DECISION — cadence i scope

- [ ] Potwierdzić docelową cadence względem bieżącego production:
  aktualny E schedule jest weekly full, a wcześniej podany cel mógł oznaczać
  biweekly full-system/DB/KB.
- [ ] Potwierdzić, czy bieżące F schedules — daily database i `n8n_config` —
  wyczerpują znaczenie „daily architecture backup”.
- [ ] Nie zmieniać cadence ani scope bez jawnej decyzji właściciela.

### 12.2 Google Drive boundary

- [ ] Cloud synchronization pozostaje niezależną warstwą.
- [ ] Google Drive failure/quota nie może blokować physical backup ani retention.
- [ ] Backup completion nie może zależeć od cloud sync.

## 13. Kolejność napraw

### PHASE 0 — Roadmap and evidence freeze

- [x] Utworzyć canonical roadmap.
- [x] Zachować baseline 21 blockerów.
- [ ] Podpiąć późniejsze evidence/closing commits bez przepisywania historii.

### PHASE 1 — Immediate production containment

- [ ] DOC-01 — `FIXED_UNVERIFIED`; deployment and Material V3 closure pending.
- [ ] DOC-02 — `FIXED_UNVERIFIED`; deployment/live verification and Material V3 finalization pending.
- [ ] DOC-03 — `FIXED_UNVERIFIED`; deployment, live queue recovery and Material V3 finalization pending.
- [ ] **NEXT ACTIVE: DOC-04B — build a versioned one-shot Windows-host repair runtime and perform only synthetic/non-production host readiness.**
- [ ] Po DOC-04B: deployment, actual production preflight, verified backup i
  osobne owner production-repair approval.
- [ ] DOC-04 repair wymaga osobnego approval; ten krok nie autoryzuje zapisu.

### PHASE 2 — Visual V2 migration correction

- [ ] VIS-01..VIS-10.
- [ ] Isolated PostgreSQL i concurrency validation.

### PHASE 3 — Automatic Text Intelligence design

- [ ] AUTO-01.
- [ ] Ustalić, czy migration candidate wymaga additive correction.

### PHASE 4 — Material V3 and Text Intelligence runtime

- [ ] Local-only processing.
- [ ] Durable ingress intelligence.

### PHASE 5 — Assistant runtime integration

- [ ] ASST-01.
- [ ] Local-only reasoner.
- [ ] Visual execution.
- [ ] Local re-synthesis.
- [ ] Advanced ordering.

### PHASE 6 — Gmail

- [ ] GMAIL-02 najpierw.
- [ ] GMAIL-01 bounded repair/import później.

### PHASE 7 — Resource coordination

- [ ] RES-01.
- [ ] RES-02.
- [ ] Calibration i physical stress tests.

### PHASE 8 — Backup configuration and restore

- [ ] BACKUP-01.
- [ ] Separate retention-delete gate.
- [ ] Restore rehearsal.

### PHASE 9 — Production migration rehearsal

- [ ] Production-shape isolated rehearsal.
- [ ] Migration timing i lock impact.
- [ ] Verified backup.

### PHASE 10 — Separate production apply approval

- [ ] Owner gate.
- [ ] Migration.
- [ ] Smoke.
- [ ] Live acceptance.

### PHASE 11 — Consolidated Android physical acceptance

- [ ] Zbudować candidate dopiero po zamknięciu source/runtime gates.
- [ ] Wykonać skonsolidowaną physical acceptance bez nieautoryzowanego
  versionCode use.

### PHASE 12 — CHUNK23 entry gate

- [ ] Spełnić wszystkie kryteria z sekcji 16.
- [ ] Uzyskać explicit owner decision `CHUNK23 START APPROVED`.

## 14. Production migration gate

Wszystkie poniższe warunki są obowiązkowe:

- [ ] Wszystkie P0 closed.
- [ ] Wszystkie blocking P1 closed.
- [ ] Migration source reviewed.
- [ ] Migration test reviewed.
- [ ] One Alembic head.
- [ ] No backfill.
- [ ] Downgrade with V2 data refused.
- [ ] Clean downgrade passed.
- [ ] Re-upgrade passed.
- [ ] Production-shape rehearsal passed.
- [ ] Lock duration measured.
- [ ] Verified backup checkpoint.
- [ ] Brak active backup/restore/Assistant/Visual work.
- [ ] Separate owner approval.

### 14.1 Production checkpoint

| Pole | Wartość |
|---|---|
| Production HEAD | — |
| DB head before | — |
| Backup ID | — |
| Backup path | — |
| Manifest SHA-256 | — |
| Verified time | — |
| Maintenance window | — |
| Migration start | — |
| Migration end | — |
| DB head after | — |
| Row-count checks | — |
| Service smoke results | — |

## 15. Functional acceptance gate

- [ ] TXT automatic Material/Text Intelligence.
- [ ] Native PDF.
- [ ] Scan PDF local OCR bez automatic Vision.
- [ ] Standalone image.
- [ ] DOCX z embedded image.
- [ ] PPTX.
- [ ] XLSX limitation/render behavior.
- [ ] Gmail existing Client certain match.
- [ ] Gmail ambiguity.
- [ ] Gmail attachment second pass.
- [ ] Historical mail repair sample.
- [ ] Assistant local answer.
- [ ] Required Visual before Advanced.
- [ ] Restricted source rejection.
- [ ] Visual provenance.
- [ ] Cancellation.
- [ ] Backend restart.
- [ ] Supervisor restart.
- [ ] Android minimize/reopen.
- [ ] No false resource starvation.
- [ ] No undocumented Ollama residency.
- [ ] Backup protection.

## 16. CHUNK23 entry gate

- [ ] `BACKUP_VERDICT`: PASS.
- [ ] `ASSISTANT_VERDICT`: PASS.
- [ ] `DOCUMENT_PIPELINE_VERDICT`: PASS.
- [ ] `GMAIL_MATCHING_VERDICT`: PASS.
- [ ] `AUTO_DOCUMENT_ANALYSIS_VERDICT`: PASS.
- [ ] `VISUAL_V2_MIGRATION_VERDICT`: PASS.
- [ ] `RESOURCE_GUARD_VERDICT`: PASS.
- [ ] `PRODUCTION_MIGRATION_VERDICT`: PASS.
- [ ] Zero open P0.
- [ ] Zero blocking P1.
- [ ] Production gate closed.
- [ ] Functional gate closed.
- [ ] Final closure report.
- [ ] No unauthorized versionCode use.
- [ ] Explicit owner decision: `CHUNK23 START APPROVED`.

## 17. Evidence log

| Date UTC | Blocker/Gate | Evidence | Commit/branch/report | Result | Verified by |
|---|---|---|---|---|---|
| 2026-08-31 | FULL-AUDIT | `FOLLOWUP_PRECHUNK23_FULL_SYSTEM_READONLY_AUDIT_20260831` | chat-only report | READ-ONLY AUDIT PASS / 21 BLOCKERS IDENTIFIED | pending owner/Assistant review |
| 2026-08-31 | VISUAL-MIGRATION-AUDIT-BRANCH | isolated migration roundtrip | `65783d1c1e1b7b13d0fcccf85f922d8af8c0bf1c` | TECHNICAL ROUNDTRIP PASS / FROZEN CONTRACT FAIL | verified by full audit |
| 2026-09-01 | DOC-01 | Independent source/test review and main-based promotion | audit `f4041f709b88a111cd1fe9eba4d8640b1bede15f`; main `d69e373fc435c6a5373a256b1acd206fddd3d184` | SOURCE CONTAINMENT PASS / FIXED_UNVERIFIED; deployment and Material V3 closure pending | Owner/Assistant independent Git review |
| 2026-09-01 | DOC-02 | Independent source/test review, main-based revalidation and bounded format probes | audit `c08b55a07ac1a8b761f0c06ed70dd90085a7b944`; main `5ae13876ed4e0104a9c049e5b68d67177b0372d9` | SOURCE RESOURCE CONTAINMENT PASS / FIXED_UNVERIFIED; deployment, live verification and Material V3 finalization pending | Owner/Assistant independent Git review |
| 2026-09-01 | DOC-03 | Independent source/test review, main-based fencing and queue-drain validation | audit `b1dee3d0afff1aefb5235176502cf0256fe975ce`; main `f601c2c4cb88f58f5095b842b0135316d8721f6f` | SOURCE LEASE RECOVERY/FENCING PASS / FIXED_UNVERIFIED; deployment, live queue recovery and Material V3 finalization pending | Owner/Assistant independent Git review |
| 2026-09-01 | DOC-04 PROJECTION | Independent Git/report review; single-row read-only projection; exact before/candidate hashes; isolated PostgreSQL validation | audit `9567583fcef4278b32e46d0c81e8328106332499`; main `5e2167fabf8229b703b8757853f059fc20c14f50`; `FOLLOWUP_PRECHUNK23_DOC04_METADATA_REPAIR_PROJECTION.md` | PLAN READY FOR OWNER REVIEW / DOC-04 REMAINS OPEN; no production repair; recurrence hardening and write gate pending | Owner/Assistant independent Git review |
| 2026-09-02 | DOC-04A | Independent cumulative source review; isolated Unicode, repair, backup, locking and fresh-snapshot matrices | audit `116c43d65e9045d2feac85ffaaf9cdfa380ba9af`; main `243e6e53df2d293476e2c38ece49bd6c73932ecc` | SOURCE HARDENING AND REPAIR CONTRACT PASS / FIXED_UNVERIFIED / WINDOWS RUNTIME AND PRODUCTION REPAIR PENDING | Owner/Assistant independent Git review |
| — | — | — | — | — | — |

## 18. Decision log

| Date UTC | Decyzja | Powód | Obowiązujący skutek |
|---|---|---|---|
| 2026-08-31 | Do not apply Visual V2 migration | Six P0 and four P1 migration defects | Production migration HOLD |
| 2026-08-31 | Do not treat current RAM issue as proven memory leak | Audit identified medium false-starvation risk and real overlapping workloads | Calibration required before changing guard thresholds |
| 2026-08-31 | Every new supported Document should receive local Material and Text Intelligence | Current target design lacks a non-Assistant durable Text Intelligence owner | AUTO-01 design gate required |
| 2026-08-31 | Physical backup remains independent from Google Drive synchronization | Cloud failure must not block canonical safety backup | No cloud dependency in backup completion gate |
| 2026-09-01 | Promote DOC-01 fail-closed containment to main | It prevents automatic external V1 Vision without changing production data or globally disabling explicit compatibility | Source accepted; no deployment; scan-only ingestion safely fails closed until Material V3/Visual V2 |
| 2026-09-01 | Promote DOC-02 bounded Office archive extraction to main | It removes the unbounded ZIP-member RAM allocation path and adds deterministic archive/image limits without changing formats, schema or external services | Source accepted; no deployment; remaining force-atomicity and shared-resource coordination are retained as explicit future hardening |
| 2026-09-01 | Promote DOC-03 lease recovery and attempt fencing to main | It prevents stale workers from mutating a reclaimed preparation attempt and keeps recovery active during long intelligence waits | Source accepted; no deployment or production-job recovery; structural side-effect fencing and serial throughput remain Material V3/RES-02 work |
| 2026-09-01 | Accept DOC-04 minimal lexical repair projection, but do not execute it yet | The plan proves one-row/two-column scope and deterministic candidates, while current metadata persistence still permits recurrence | Report promoted to main; source hardening and isolated repair rehearsal must precede any owner-approved production update |
| 2026-09-02 | Promote DOC-04A source hardening and guarded repair executable to main | The source now prevents recurrence, uses exact one-row repair semantics, canonical backup/restore coordination and fresh PostgreSQL snapshots | Source accepted without deployment or production write. A dedicated versioned Windows-host runtime remains mandatory before production preflight |

## 19. Current verdicts

**BACKUP_VERDICT:**

CURRENT BACKUPS SAFE AND VERIFIED; CAPACITY HEALTHY; OWNER RETENTION POLICY NOT ACTIVATED

**ASSISTANT_VERDICT:**

BLOCKED — VISUAL STAGES ARE NON-EXECUTABLE AND ADVANCED CAN PRECEDE REQUIRED VISUAL

**DOCUMENT_PIPELINE_VERDICT:**

BLOCKED — DOC-01/DOC-02/DOC-03 AWAIT DEPLOYMENT/LIVE VERIFICATION, SERIAL THROUGHPUT REMAINS, AND MATERIAL V3 IS PENDING

**CAD_VERDICT:**

FAIL-CLOSED / UNSUPPORTED — 41 ACTIVE DWG DOCUMENTS HAVE NO CANONICAL ANALYSIS PATH

**GMAIL_MATCHING_VERDICT:**

BLOCKED — FIVE MAILBOX MESSAGES MISSING, RECONCILIATION UNREACHABLE, REVIEW DEBT REMAINS

**AUTO_DOCUMENT_ANALYSIS_VERDICT:**

BLOCKED — CURRENT PIPELINE DOES NOT COMPLETE RELIABLY; TARGET V3 DURABLE TEXT OWNER MISSING

**VISUAL_V2_MIGRATION_VERDICT:**

BLOCKED — SIX P0 AND FOUR P1 MIGRATION DEFECTS

**RESOURCE_GUARD_VERDICT:**

CORE MODEL SAFETY CONTROLS PASS; MEDIUM FALSE-STARVATION RISK AND CROSS-SYSTEM ADMISSION GAP

**PRODUCTION_MIGRATION_VERDICT:**

DO NOT APPLY VISUAL V2 MIGRATION

**CHUNK23:**

NOT STARTED

---

**OPEN P0: 10**

**OPEN P1: 11**

**OPEN BLOCKERS: 21**

**PRODUCTION MIGRATION: HOLD**

**CHUNK23: NOT STARTED**
