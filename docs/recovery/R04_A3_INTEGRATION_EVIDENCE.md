# R04-A3 — kontrolowana integracja źródeł i powiązanie z artefaktami

## Wynik i granica

R04-A3 zakończyło się stanem
`INTEGRATION_SET_READY_FOR_REVIEW / SOURCE_AND_STAGING_ONLY`.
Przypięty commit źródłowy to
`41d2b844a7b120a79001ad5cfbe6304b30580dfc`, a jego rodzic to
`a0a51d67dc606db63f3d6a5f3f1750f27f6c3986`.

To nie jest deployment, release ani odbiór całego R04/R06. Kandydat zawiera
bezwarunkowe wywołanie `start_visual_v2_dispatcher()` wyłącznie wewnątrz
`lifespan`; obowiązuje `NO_APPLICATION_START_AUTHORIZATION`. Nie uruchomiono
aplikacji, dispatchera, Supervisora, Temporary Chat, modelu ani eksportu.
Privacy R05 pozostaje `OPEN_NOT_VERIFIED`, dlatego external export i operacyjne
użycie tego zestawu są zablokowane.

## Przypięte wejścia i selekcja

- merge-base: `origin/main@483f9bf8b1a591ded8a42df5da87663c664ed5d4`;
- rescue: `5cd8f86e63e1ab829692ca2601096fd0c0d9d53a`, dokładnie pięć commitów
  przed recovery integration;
- pełna lista 23 ścieżek i ich pochodzenie:
  `docs/recovery/R04_A3_SOURCE_SELECTION.csv`;
- decyzja: wszystkie 23 ścieżki końcowego diffu rescue mają `ADOPT_SOURCE`;
  20 blobów jest identycznych z finalnym rescue, a trzy różnice są celowe:
  `backend/app/main.py` zachowuje R04-A1 `/version`, test DOC-03 zachowuje
  izolację R02, a test Visual dodaje izolację fake Supervisora/spoolu i kontrolę
  AST miejsca startu dispatchera;
- `backend/app/services/vision_processing_service.py`, migracje, konfiguracja
  produkcji, stable/minimum i kod zaakceptowanego `DocumentsController` nie
  zostały nadpisane.

Zachowane poprawki recovery: R02 DOC-03, narzędzia R03 i kompatybilność
manifestów, R04-A1 wraz z `identity_kind`, a także source/test UI06
`48fbecae0a76edb25f60e9dd314bb8d65bfbae4b`.

## Testy wynikowego drzewa

Testy używały obrazu R02
`sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651`.
Testy bez DB miały `--network none`; testy DB korzystały wyłącznie z nowego
PostgreSQL `16-alpine` o image ID
`sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685`
na sieci `internal`, bez host ports i bez mountów produkcyjnych. Wartości
konfiguracji były syntetyczne; ich plik pozostaje `LOCAL_ONLY`.

| Zakres | Wynik bieżący | Exit | Dowód LOCAL_ONLY SHA-256 |
|---|---:|---:|---|
| version identity + Visual V2 + resource coordinator | `74 passed` | 0 | `0FCDC75FDE993152D6CE1A41CA943070861DF69F995E9223DB2D0BF3822BDF57` |
| Visual V2 po dodaniu dwóch guardów A3 | `32 passed` | 0 | `81B8534E6053AF84C446ED2785660A8487B35FEC73E93A06D63633AA0FF72968` |
| Assistant pipeline/chat/Visual/unified/current contract | `167 passed` | 0 | `0FC14B6279AACD8D5AE2CF6FB699B7BAA93C05048E13658D19AFFD2069E9831B` |
| migracje istniejącego schematu syntetycznej DB | head `followup_assistant_chat_history_20260829` | 0 | `FF472A3162A0D43C7B62977EE0FD351BE795C736294E7012F5C3881EB8633DD5` |
| dokumenty, ingestion containment i DOC-03 | `92 tests`, `OK` | 0 | `0010E63BADDDC3E800F931250A4AC63D5D00D101A111154E0D8129DFAFCDD5C7` |
| dwusesyjna publikacja/usunięcie czatu | `PASS`, query counts `1/4` | 0 | `B122EEF2B7C9C64BBAB382F31FEE8CA72A936B9A60756E70410318CA8CCA67AA` |
| Python compile zmienionych plików | `21/21` | 0 | `2EFF34F32A347A06972571224A2D03A7667D68A40A4D6B2383DC2D4F53E08671` |
| Flutter analyze | `No issues found` | 0 | `B00A53858D0D2EB3CC7A02AC6BB75C99C2B253DA71661227327BF4116EBE5E8B` |
| Flutter: dokumenty, unified contract, stable/update parser | `34 passed` | 0 | `02FA36CFB5C059942D9E06D667A52BA55A7B4A19C8569018125A07CD5254357D` |
| manifest comparator R04-A1 | expected `UNVERIFIED`; negatywny `MISMATCH` | 0 | `DDEF79A31BD93993C6855EE5A1535B84915E51692789DBF7D1638E9FEB2CC693` |

Najważniejsze polecenia (pełne wartości syntetycznego hasła nie są
publikowane):

```powershell
docker run --rm --network none --read-only --tmpfs /tmp `
  --mount type=bind,source=C:\ai-lab-core-recovery\backend,target=/workspace/backend,readonly `
  -w /workspace/backend <R02_IMAGE_ID> -m pytest -q `
  test/test_r04_version_identity.py test/test_visual_v2_service.py `
  test/test_local_model_resource_coordinator.py

docker run --rm --network <R04_A3_INTERNAL_NETWORK> `
  --env-file <LOCAL_ONLY_SYNTHETIC_ENV> `
  --mount type=bind,source=C:\ai-lab-core-recovery\backend,target=/workspace/backend,readonly `
  -w /workspace/backend <R02_IMAGE_ID> -m unittest -v `
  test.test_document_ingestion_vision_containment `
  test.test_document_office_archive_safety `
  test.test_document_intelligence_resource_wait `
  test.test_document_preparation_pipeline `
  test.test_document_metadata_unicode_safety `
  test.test_document_preparation_recovery_fencing

C:\FlutterSDK-New\flutter\bin\flutter.bat analyze
C:\FlutterSDK-New\flutter\bin\flutter.bat test --no-pub `
  test/features/documents/documents_api_test.dart `
  test/features/documents/documents_controller_test.dart `
  test/features/documents/documents_page_test.dart `
  test/features/documents/document_response_test.dart `
  test/features/documents/document_media_preview_test.dart `
  test/features/ai/unified_assistant_contract_sync_test.dart `
  test/update_decision_engine_test.dart test/update_hash_test.dart
```

Trzy pierwsze nieudane uruchomienia zachowano jako błędy recepty, nie produktu:
brak wymaganych syntetycznych pól ustawień przed collection, nazwa DB odrzucona
przez guard oraz snapshot Flutter obejmujący tylko `frontend`, gdy dwa testy
czytają repozytoryjne fixture z katalogów sąsiednich. Poprawione uruchomienia
wyżej przeszły. Pierwsze polecenie compile omyłkowo powtórzyło `python` przy
obrazie z pythonowym entrypointem; końcowa kompilacja `21/21` jest oddzielnym
dowodem.

Dodatkowego `test_followup_chunk13_api_auth.py` nie uruchomiono: jego import
`app.main` został zatrzymany przez bramkę bezpieczeństwa z powodu możliwego
lifespan. Nie obchodzono zakazu normalnego startupu. Uwierzytelnienie i scope
zmienianego kontraktu są objęte bezpiecznym testem addytywnego endpointu i
testami izolacji klienta w `test_unified_assistant_implementation.py`; nie jest
to live API smoke.

## Staging i build TEST_ONLY

Root `LOCAL_ONLY`:
`C:\ai-lab-core-staging\recovery\R04_A3_INTEGRATION_20260911T091750Z`.

| Artefakt | Rozmiar | SHA-256 / dowód |
|---|---:|---|
| source archive z dokładnego commita | 5,987,064 B | `018F73B669246B03EC0442E01B4E3655D11B15B76B411C6ED6D314751A31D613` |
| Web TEST_ONLY ZIP | 20,032,229 B | `BC1160A8BEDFB1AB6CEE760F9034C5528CC9485CB1867B1E1901E29E9F80F0A9` |
| Web unpacked | 40 plików / 62,867,536 B | file-manifest `50F580F554E34F6FF3A6E1C6BE469B18F8E5911D2F33407CB9957C182149D823` |
| `main.dart.js` | 18,090,353 B | `BCC480848980F9AB6C9D6F0902C6EFA256EF349172CA10CD275A236477483EDD` |

Build użył Flutter `3.44.8`, Dart `3.12.2`, niezmienionego locka
`A6DE957204E958A64D80FDB0CD8575DB48D1532CBA28CD2D7C8B41BC2F5347D6`,
`--debug --no-pub --no-web-resources-cdn` i
`API_BASE_URL=http://127.0.0.1:18004`. Nie uruchomiono Web ani UI. Komenda
zakończyła kompilację i utworzyła wymagane pliki, lecz stdout/exit wrappera nie
został zachowany przez warstwę wykonawczą; dlatego dowodem jest niezależna
kontrola struktury, bajtów i hashy, nie fikcyjny log exit. Post-build verification
ma SHA-256
`2F5DE9EE5562BE1C71AB70737A4D9FD9DD938783BA34A589D6F25FFE32405E00`.

Bramki zasobów przeszły. Przed buildem: Windows available `6.663 GiB`, commit
reserve `35.383 GiB`, właściwa pula Docker/WSL available `14.066 GiB`.
Po buildzie: odpowiednio `6.782`, `35.403` i `14.195 GiB`; swap użyty około
`0.002 GiB`.

## Walidacja tożsamości

`docs/recovery/R04_A3_INTEGRATION_SET.json` używa istniejącego
`NEXT_STABIL_COMPONENT_COMPATIBILITY_V1`. Wynik stagingu jest celowo
`UNVERIFIED`, bez mismatch, ponieważ Windows i Android nie zostały zbudowane
ani niezależnie zaobserwowane. Źródło backendu/Supervisora/gatewaya/workerów,
API/schema i Web mają osobne rodzaje tożsamości i dowody; Git SHA nie zastępuje
hasha buildu.

Na syntetycznej kopii ZIP zmieniono jeden bit przy zachowaniu oryginału.
Komparator zwrócił `MISMATCH` dla `web.identity`. Podstawienie Git SHA jako
`web.identity` zwróciło `UNVERIFIED`. Manifest jawnie zachowuje:

```text
normal_application_start_authorized=false
external_execution_authorized=false
external_export_authorized=false
privacy_r05=OPEN_NOT_VERIFIED
operational_use=BLOCKED_PENDING_REQUIRED_ACCEPTANCE_AND_OWNER_APPROVAL
```

## Skutki i pozostałe bramki

Utworzono i następnie usunięto wyłącznie własne syntetyczne kontenery
`next-stabil-r04-a3-20260911t091750z-postgres` i
`next-stabil-r04-a3-20260911t091750z-telemetry` oraz wewnętrzną sieć
`next-stabil-r04-a3-20260911t091750z-db-network`. Nie utworzono wolumenu i nie
pozostał listener. Zachowano lokalne logi, snapshoty testowe, WIP, source archive,
Web build i syntetyczną jednobajtowo zmienioną kopię.

Produkcja, main, rescue, R03/A2/A3/A4, modele, Qdrant, n8n, Gmail, Supervisor,
Temporary Chat, kolejki i dane firmy nie zostały zmienione ani uruchomione przez
R04-A3. Oryginalny worktree pozostał przy `72950657...`, staged `0` i 203
zinwentaryzowanych wpisach.

Otwarte pozostają: R03 escrow, pozostały build/runtime/release zakres R04,
privacy R05, pełny R06, C-004 (5 case + 3 KB + 4 supplemental Visual), W-02,
D-15/D-16 model/UX acceptance oraz Android. Następny krok to odbiór A3 przez
właściciela i osobna decyzja z istniejącej karty; ten raport nie otwiera R05 ani
deploymentu.
