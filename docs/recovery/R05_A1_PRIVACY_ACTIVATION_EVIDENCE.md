# R05-A1 — wspólna kontrola eksportu Vision V1 / Visual V2

## Wynik

Status podetapu: `HANDOFF_SCOPE_TRANSACTION_FIX_READY_FOR_REVIEW / NOT_DEPLOYED`.

Właściciel rozszerzył D-20 na źródła Vision V1, Visual V2, wspólny handoff
oraz wskazane testy `SOURCE / TEST ONLY`. Zaakceptowany punkt wejścia to
recovery `8550a11991924d5c905813374e4630e7c38b8244`; przyjęty wcześniej
R04-A3 source pozostaje
`41d2b844a7b120a79001ad5cfbe6304b30580dfc`, a evidence
`457a4321db835421c0d06847e2132d9623d735ae`.

Obie aktywne ścieżki backendu korzystają teraz z jednej serwerowej decyzji
exact-byte oraz jednego trwałego claimu/handoffu. Wynik obejmuje testy
syntetyczne, prawdziwe metody serwisów, prawdziwy routing HTTP/auth i dwie
równoległe sesje PostgreSQL. Nie obejmuje realnego eksportu, uploadera,
workera, Supervisora, Temporary Chat, modelu, panelu operatora ani wdrożenia.
Cały R05 pozostaje `IN_PROGRESS`.

Przegląd materiału na
`b9508291282a8eee0a56d89575ab242630e1ebad` pozostawił cztery precyzyjne
uwagi RV05-01–04. Domknięcie zostało przetestowane i przypięte w source
`3a36d5b3866e277b9186028b1926debfe92209e6`; nie zmienia to braku
deploymentu ani statusu całego R05.

## Granica i mapa przepływu

1. `VisionProcessingService` albo `VisualV2Service` wybiera maksymalnie
   cztery źródła i zapisuje istniejący `AnalysisJob` / `AnalysisJobSource`.
2. `VisualV2Service` przygotowuje finalne rastry w lokalnym stagingu oraz
   wylicza source hash, final raster hash i package hash.
3. Administrator pobiera kandydat z serwerowego ledgeru i zatwierdza dokładny
   zestaw bajtów dla sprawy, źródła, wersji/checksum oryginału, kanału
   `temporary_chat_visual`, polityki `visual-export-v1` i okresu ważności.
4. `claim_approved_export()` ponownie sprawdza scope, klasyfikację, ścieżki,
   źródła, finalne bajty, pakiet, wygaśnięcie i cofnięcie. V1 i V2 używają
   tego samego claimu `visual_export_<request_key>`.
5. `submit_claimed_export()` jeszcze raz wylicza hash bajtów bezpośrednio
   przed jedyną atrapioną w testach granicą `create_job()`.
6. Trwały claim pozostaje po niepewnym handoffie i blokuje automatyczne
   ponowienie; potwierdzony zewnętrzny identyfikator zapisuje wspólny wynik.

Alternatywne wejścia przejrzane w tym zakresie: dokumentowe API Vision V1,
`vision_dispatcher.py`, bezpośrednie `advance()`, wcześniejszy queued job,
Visual V2 dispatcher oraz call-site `TechnicalAiService`. Normalnego lifespan
ani dispatcherów produktu nie uruchomiono.

## Zmiana źródłowa

- `VISUAL_V2_ENABLED` ma bezpieczny domyślny stan `false`; brak/false nie
  uruchamia pętli Visual V2.
- Brak dopuszczenia, `restricted_never_external`, niepewna klasyfikacja,
  obcy scope, cofnięcie, wygaśnięcie, zmiana źródła/rastra/pakietu albo
  niebezpieczna ścieżka kończą się jawnie bez wywołania zewnętrznego.
- Zwykły request, import lub payload modelu nie nadaje sobie zgody. Kandydat,
  approve i revoke są addytywnymi trasami z rzeczywistym auth i wymaganiem
  aktywnego administratora.
- Oryginał nie jest modyfikowany. Metadane paczki nie zawierają nazwy klienta,
  oryginalnej nazwy pliku, ścieżki ani EXIF.
- Brak dopuszczenia w V1 daje `pending_auth` / `AUTH_REQUIRED`; dispatcher
  nie zapętla statusów oczekujących na decyzję.
- Lokalny reuse zaakceptowanego wyniku pozostaje możliwy i nie wraca do
  zewnętrznej ścieżki V1.
- Nie dodano migracji, tabel, workerów, pipeline'u ani kryptografii.

## Fail-before i wykryta regresja integracyjna

Pierwszy dowód wykonawczy wywołał rzeczywisty
`VisionProcessingService.advance()` na syntetycznym obrazie i fake
Supervisorze. Bez wspólnej bramki V1 wywołało `create_job()`:

- test:
  `test_r05_a1_legacy_v1_unapproved_pixels_do_not_reach_supervisor`;
- expected: `pending_auth`, zero wywołań;
- actual before: `queued`, jedno wywołanie;
- wynik: `1 failed`, exit `1`.

Po pierwszej implementacji izolowany PostgreSQL ujawnił błąd integracyjny:
separator `:` w identyfikatorze claimu nie spełniał istniejącego ograniczenia
DB. Bez migracji zmieniono format na
`visual_export_<64 hex>` (78 znaków) i powtórzono testy. Nie osłabiono
constraintu ani asercji.

Log fail-before:
`C:\ai-lab-core-staging\recovery\R05_A1_V1_V2_20260911T141704Z\v1-fail-before.log`,
SHA-256
`A1BF2E932B9EF5BD1DA08AB598B1F6E81FD1157415AA96D28FE88F6711ECE87D`.

## Pierwszy pass-after (historyczny etap b950829)

Przypięty lokalny obraz testowy:
`sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651`.
Źródła montowano read-only; testy bez DB miały `--network none`. Testy DB
użyły nowego PostgreSQL w sieci `internal`, bez host ports, produkcyjnych
mountów i prawdziwych zewnętrznych adresów. Supervisor/Ollama/Advanced/worker
pozostały atrapione lub nieosiągalne.

| Dowód | Komenda testowa | Wynik | Log SHA-256 |
|---|---|---:|---|
| regresje bez DB | `python -m pytest -q -p no:cacheprovider test/test_chunk15_vision_implementation.py test/test_visual_v2_service.py test/test_r05_visual_export_api.py test/test_assistant_visual_branch.py test/test_unified_assistant_scope_boundary.py test/test_unified_assistant_output_budget.py test/test_unified_assistant_kb_grounding.py test/test_unified_assistant_implementation.py test/test_unified_assistant_document_resolution.py test/test_unified_assistant_design_contract.py test/test_unified_assistant_contract_sync.py` | `301 passed`, exit `0` | `C88A63716EE58A29539A3F34A4369CA49EF94B6E94A018BCABBBA41074AFDA2F` |
| izolowany PostgreSQL | `python -m pytest -q -p no:cacheprovider test/test_r05_visual_export_postgres.py test/test_chunk14_technical_ai.py test/test_document_ingestion_vision_containment.py test/test_document_office_archive_safety.py` | `49 passed`, exit `0` | `5E7E1EB02F53ABB61845345BB6CCFDD5ECA10ECD94D6CE17F7CFAC2B00176CBB` |
| auth/lifespan | `python test/test_followup_chunk13_api_auth.py` w izolowanym kontenerze | `8 × 401`; product lifespan `0`; kontrolny TestClient context `1`; exit `0` | `47E12F02641D28E0375F6AF49F105500AB9A03EE7D74B18A534C30C8DA0CE63F` |
| składnia/import | `python -m compileall -q app test` | exit `0` | `F33DB72EB310E5485E84600C3827D4F6F9578A90426FD96850D66E51178B2F97` |

Pełne logi są `LOCAL_ONLY` w
`C:\ai-lab-core-staging\recovery\R05_A1_V1_V2_20260911T141704Z`.
Skrypty Office wymagające firmowego dokumentu 770 zostały zatrzymane na
collection w syntetycznej DB i mają `NOT_RUN`; nie są dowodem R05 ani błędem
produktu. Nie pobierano firmowego fixture.

Testy tego etapu pokrywają: flagę startupu, bezpośrednie i queued V1/V2, syntetyczne PII
w pikselach, restricted/unknown, brak/stare/cofnięte dopuszczenie, obcy scope,
nieuprawnionego aktora, zmianę bajtu źródła i finalnego rastra, zmianę pakietu,
obcą ścieżkę/symlink, minimalne metadata, lokalny reuse i niepewny handoff.
Opublikowany w tym etapie test nazwany V1/V2 uruchamiał dwukrotnie
`VisualV2Service`; jest dowodem V2/V2, nie faktycznej pary V1/V2. Korekta
pokrycia i jej rzeczywisty wynik znajdują się poniżej.

## Domknięcie RV05-01–04

### Fail-before

Na rzeczywistym `VisualV2Service`, syntetycznym storage i fake Supervisorze
kontrolowany zegar oraz świeże sesje wykazały:

- expiry po claimie i cancel po claimie nie blokowały submitu;
- zmiana `client_id`, `project_id`, `inspection_id` lub `candidate_id` przy
  niezmienionych bajtach nie unieważniała dopuszczenia ani przed claimem, ani
  między claimem i submitem.

Wynik: `1 passed, 10 failed`, exit `1`; log SHA-256
`82C583EC134E103C9FF7ACB5F32E3380F5AD716B5373732F665EDE1F68A6232B`.

Na rzeczywistym PostgreSQL candidate-first zwrócił ID, lecz po zamknięciu
requestu nowa sesja nie widziała `AnalysisJob`. W tym samym biegu V2/V2 oraz
rzeczywiste `VisionProcessingService` + `VisualV2Service` przeszły. Wynik:
`2 passed, 1 failed`, exit `1`; log SHA-256
`7D701D7FAC0599854FE209730D0B172E91A14A879C04102809946441537A3155`.

### Minimalna zmiana

- Finalna granica submit odświeża i blokuje wiersz joba, ponownie sprawdza
  cancel, ważność/cofnięcie decyzji, business scope, package i dokładne bajty,
  a lock utrzymuje do trwałego zapisu external ID. Transakcja nie obejmuje
  pracy modelu; niepewny skutek kontaktu zachowuje claim i blokuje retry.
- Wersjonowany binding i fingerprint zawierają serwerowo wyprowadzony
  `document_id/client_id/project_id/inspection_id/candidate_id`. Null oznacza
  jawnie nieprzypisany dokument, nie zgodę globalną; starszy binding bez scope
  nie otrzymuje automatycznego dopuszczenia.
- Revoke może zwolnić claim tylko przy udowodnionym braku rozpoczęcia kontaktu;
  `HANDOFF_UNCERTAIN` i external ID nadal blokują cofnięcie/retry.
- Endpoint candidate zatwierdza swoją transakcję po auth i kontroli scope;
  globalne `get_db()` pozostaje bez zmiany.

### Pass-after i klasy dowodu

| Zakres | Wynik | Klasa dowodu | Log SHA-256 |
|---|---:|---|---|
| końcowy guard: positive, expiry, cancel, revoke, scope before/after claim | `39 passed`, exit `0` | rzeczywiste metody, SQLite/syntetyczny filesystem, fake Supervisor | `9D9FD3AF5DF57849D1C16C8312CC4B7E6DFC91A9D50A25031B4F215CD80EF690` |
| candidate-first + prawidłowe relacje client/project/inspection + V1/V2 valid/expired | `10 passed`, exit `0` | rzeczywisty PostgreSQL, dwie sesje/requesty, fake Supervisor | `8C7072D66E3F9A46642908DF3448DE9A1660067A0A433A6CE031F2F69B58D371` |
| regresja V1/V2/Assistant bez DB | `313 passed`, exit `0` | pinned image, `--network none` | `70A818C8538CE5EAEFB4BE016A70FC3EC1B78AC55B74E7A808DEB8DA17B05F8E` |
| regresja PostgreSQL | `58 passed`, exit `0` | internal network, host ports `0`, syntetyczna DB | `FDF7AA6EB90F559609E995DE743169B196DC923FA207D607CA3FA3756819D729` |
| auth/lifespan | `8 × 401`, product lifespan `0`, exit `0` | rzeczywisty router/dependencies, kontrolowany TestClient | `47E12F02641D28E0375F6AF49F105500AB9A03EE7D74B18A534C30C8DA0CE63F` |
| `compileall` | exit `0` | source read-only, bytecode w tmpfs | `C1E97067C5F479A44A6F57297A0A8F87A59D181C3C529910F8BF059094BC3ABB` |

RV05-01, RV05-02 i RV05-03 są `REPRODUCED_THEN_FIXED_IN_SOURCE`.
RV05-04 jest `EVIDENCE_DESCRIPTION_CORRECTED`: stary test faktycznie był
V2/V2, natomiast nowy test rzeczywiście wywołuje `VisionProcessingService`
oraz `VisualV2Service` z dwóch niezależnych sesji. Dla ważnej zgody powstaje
dokładnie jeden fake `create_job`; dla wygasłej — zero. Nie wykonano realnego
Supervisora ani eksportu.

Pełne nowe logi pozostają `LOCAL_ONLY` pod
`C:\ai-lab-core-staging\recovery\R05_A1_HANDOFF_SCOPE_20260911T173756Z`.
Zachowano także niezaliczone próby recepty (brak pól syntetycznego env, błędne
hasło syntetycznej roli, brak `PYTHONPATH`, read-only `__pycache__`) i nie
zaliczono ich jako wad produktu.

## Skutki i zasoby

Utworzono wyłącznie syntetyczne rekordy/pliki oraz:

- kontener `next-stabil-r05-a1-test-20260911t155338z-postgres`, pełny ID
  `7429505b864c668b2229926e0bb92b42464f83db872f44744fcb07262739441c`;
- sieć `next-stabil-r05-a1-test-20260911t155338z-network`, ID
  `69b0663c76750f78479898921357ce8d80545256f490884a24d286b2912d22db`.

Oba zasoby miały owner/run R05, sieć była internal, kontener nie miał portów
ani mountów. Po zachowaniu dowodów usunięto dokładnie te dwa zasoby; named
volume nie utworzono. Dokładne rekordy pozostawione przez pierwszą nieudaną
próbę usunięto z syntetycznej DB, a następnie potwierdzono brak syntetycznych
dokumentów/użytkowników.

Nie uruchomiono produktu, realnych dispatcherów, Supervisora, Temporary Chat,
Qwena, embeddingu, Qdrant, Gmaila ani kolejek. Nie wykonano produkcyjnych
zapisów, migracji, eksportu, deployu, buildu frontendowego ani zmian
main/rescue/originalnego worktree.

## Zmienione pliki i ograniczenia

Kod i kontrakt:

- `backend/app/core/config.py`;
- `backend/app/main.py`;
- `backend/app/services/visual_v2_service.py`;
- `backend/app/services/vision_processing_service.py`;
- `backend/app/services/vision_dispatcher.py`;
- `backend/app/api/documents/router.py`;
- `backend/app/schemas/vision.py`.

Testy:

- `backend/test/test_visual_v2_service.py`;
- `backend/test/test_r05_visual_export_api.py`;
- `backend/test/test_r05_visual_export_postgres.py`;
- `backend/test/test_assistant_visual_branch.py`;
- `backend/test/test_chunk14_technical_ai.py`;
- `backend/test/test_chunk15_vision_implementation.py`;
- `backend/test/test_followup_chunk13_api_auth.py`.

Pozostają `NOT_VERIFIED`: rzeczywisty uploader/worker, realny Supervisor i
Temporary Chat, używalny panel operatora, realny eksport, e2e, build oraz
deployment. Źródłowa gotowość A1 nie nadaje żadnym plikom klienta zgody i nie
zamyka R05/R06/R15.
