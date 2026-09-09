# R04-A1 — version identity i compatibility evidence

## Zakres i wynik

R04-A1 usuwa źródłowy brak z FND-015: dotychczas `/version`, stable manifest i
`pubspec` opisywały różne aspekty zestawu, lecz nie istniał wspólny walidator
tożsamości komponentów. Różne numery backend/API/schema/klienta są dozwolone.
Pierwotny wynik A1: `SOURCE_READY_FOR_REVIEW / NOT_DEPLOYED` na
`ec102a8dacac529c3ac5f6715c08e4dd3ac35020`. Ograniczona poprawka review
wiążąca `identity_kind` z rolą komponentu zachowuje ten sam zakres i kończy się
`IDENTITY_KIND_FIX_READY_FOR_REVIEW / NOT_DEPLOYED`; SHA publikacji należy
odczytać z historii Git tego pliku.

Nie zamyka to runtime części FND-013/FND-014/FND-015. Nie zmieniono stable
manifestu, minimum aplikacji, buildów, routingu, rescue ani konfiguracji live.

## Rzeczywiste wejścia i minimalna zmiana

| Wejście/konsument | Stan przed A1 | Zmiana A1 |
|---|---|---|
| `backend/app/main.py::version` | legacy fields: backend/app/API/environment/debug/minimum/latest | wszystkie legacy fields i typy zachowane; addytywne `component_identity` |
| `backend/app/core/config.py::Settings` | brak deklarowanych pól release/source/image/schema | cztery opcjonalne, domyślnie nieudawane (`None` → `UNKNOWN`) identyfikatory |
| stable/update manifest + `UpdateManifest.fromJson` | kanoniczna polityka stable/minimum/build | bez zmiany pliku i parsera; starszy parser ignoruje addytywne metadata |
| `version_identity_service` | brak | jeden czysty walidator dziesięciu składników; wynik `VERIFIED`, `UNVERIFIED` albo `MISMATCH` bez zwracania wartości hashy |

Wymagane komponenty walidatora: backend, API, DB schema, Web, Windows,
Android, Supervisor, gateway, analysis worker i vision worker. Identyfikatory
mają jawny rodzaj (`git_sha`, `sha256`, `repo_digest`, `schema_revision` albo
`contract_version`). `VERIFIED` wymaga kompletnego i zgodnego zestawu; nieznane
lub nieprawidłowe dane nie przechodzą jako PASS.

Publiczna projekcja jest allowlistą. Nie zawiera ścieżek, command lines,
host inventory, zmiennych środowiskowych ani sekretów. Jest samopisem runtime,
więc ma `verification=UNVERIFIED` do czasu zewnętrznego porównania. Dla
`environment != production` lub `debug=true` zwraca
`runtime_configuration=REVIEW_REQUIRED`; nie ukrywa debug przez stałe `false`.

## Fail-before i pass-after

Środowisko: lokalny przypięty obraz
`next-stabil-r02-tests:pytest835-923dc559-fulltree`, image ID
`sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651`,
read-only source mount, `--network none`, tmpfs `/tmp` i `/r02-data`, wyłącznie
syntetyczne wartości wymaganych zmiennych.

Wspólne parametry izolacji użyte dla testów backendu:

```text
--label next-stabil.owner=R04-A1 --network none --read-only
--tmpfs /tmp --tmpfs /r02-data
--mount type=bind,source=C:\ai-lab-core-recovery,target=/workspace,readonly
-w /workspace/backend
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=9 QDRANT_HOST=127.0.0.1 QDRANT_PORT=9
OLLAMA_URL=http://127.0.0.1:9 N8N_URL=http://127.0.0.1:9
BACKUP_SUPERVISOR_URL=http://127.0.0.1:9 VISION_SUPERVISOR_URL=http://127.0.0.1:9
DOCUMENT_PREPARATION_ENABLED=false ASSISTANT_PIPELINE_V2_ENABLED=false
VISION_AUTOMATION_ENABLED=false ADVANCED_ANALYSIS_ENABLED=false
KNOWLEDGE_BASE_PROCESSING_ENABLED=false KNOWLEDGE_BASE_VECTOR_WRITES_ENABLED=false
```

Pierwsza komenda omyłkowo podała `python` jako argument obrazu, którego
entrypoint już jest Pythonem; zakończyła się `can't open file .../python`, exit
`2`, i nie jest dowodem produktu. Po jawnym `--entrypoint python`:

```powershell
docker run --rm --name next-stabil-r04-a1-f-before <parametry-izolacji> --entrypoint python next-stabil-r02-tests:pytest835-923dc559-fulltree -m pytest -q test/test_r04_version_identity.py
```

- Before: `ModuleNotFoundError: app.services.version_identity_service` podczas
  collection; pytest exit `2`. To potwierdza brak realnego mechanizmu, nie błąd
  fixture.
- After, ta sama granica i test: `10 passed`, exit `0`.

Końcowa regresja:

```powershell
docker run --rm --name next-stabil-r04-a1-final-regression <parametry-izolacji> --entrypoint python next-stabil-r02-tests:pytest835-923dc559-fulltree -m pytest -q test/test_r04_version_identity.py test/test_followup_chunk22_system_status.py test/test_android_release_api_configuration.py
```

- `21 passed`, exit `0`; ostrzeżenia dotyczyły deprecations zależności i
  niemożności zapisu `.pytest_cache` na read-only source.

Pozostałe komendy:

```powershell
docker run --rm --name next-stabil-r04-a1-public-boundary2 <parametry-izolacji> --entrypoint python next-stabil-r02-tests:pytest835-923dc559-fulltree -m test.test_public_gateway_cors
docker run --rm --name next-stabil-r04-a1-final-compile --network none --read-only --tmpfs /tmp --mount type=bind,source=C:\ai-lab-core-recovery,target=/workspace,readonly -w /workspace/backend -e PYTHONPYCACHEPREFIX=/tmp/pycache --entrypoint python next-stabil-r02-tests:pytest835-923dc559-fulltree -m py_compile app/core/config.py app/main.py app/services/version_identity_service.py test/test_r04_version_identity.py
C:\FlutterSDK-New\flutter\bin\flutter.bat test test/update_decision_engine_test.dart
C:\FlutterSDK-New\flutter\bin\flutter.bat analyze
git diff --check
```

Wyniki: gateway CORS `PASS`, compile `4/4`, Flutter test `10/10`, Flutter
analyze `No issues found`, diff check `PASS`. Pierwsza próba testu gateway jako
ścieżki pliku nie miała backendu na `sys.path` i dała `ModuleNotFoundError`;
uruchomienie istniejącego testu jako modułu jest właściwą komendą i przeszło.

Flutter wykonał resolution zależności istniejącego locka i wypisał
`Downloading packages`; nie zmieniono SDK, `pubspec.yaml`, lockfile ani wersji
zależności. Generated registrants zostały dotknięte, lecz każdy z sześciu
znormalizowanych blobów był identyczny z HEAD; staged/committed paths: `0`.

## Ograniczona poprawka review: rodzaj tożsamości komponentu

Ta reprodukcja jest odrębna od wcześniejszego fail-before z brakującym modułem.
Na niezmienionym module z commita bazowego (SHA-256 bajtów
`99D634E7F357D4949118834B40918F083C8982BB99C97A21FDBAA79E111E8F2F`)
rzeczywista funkcja `evaluate_component_compatibility()` błędnie przyjmowała
zgodne etykiety niewłaściwego rodzaju jako dowód tożsamości:

- poprawny pełny fixture: `VERIFIED`;
- brak `vision_worker`: `UNVERIFIED`;
- różne prawidłowe SHA-256 Windows: `MISMATCH`;
- oba manifesty z `vision_worker.identity_kind=contract_version`, identity `1`:
  błędnie `VERIFIED`;
- oba manifesty z `web.identity_kind=schema_revision`, identity `same-label`:
  błędnie `VERIFIED`.

Po dodaniu nowych testów, ale przed zmianą implementacji, uruchomienie realnego
modułu w tym samym przypiętym obrazie R02 zakończyło się `12 failed, 11 passed`,
pytest exit `1`. Wszystkie 12 porażek dotyczyło nowej, skończonej reguły
komponent → dozwolony rodzaj tożsamości.

Minimalna zmiana dopuszcza:

- `api`: wyłącznie `contract_version`;
- `database`: wyłącznie `schema_revision`;
- `web`, `windows`, `android`: właściwy hash artefaktu `sha256`;
- `backend`, `supervisor`, `gateway`, `analysis_worker`, `vision_worker`:
  `git_sha`, `sha256` lub `repo_digest`.

`contract_version` i `schema_revision` nie mogą zastępować tożsamości kodu,
workera albo buildu. Niewłaściwy rodzaj po stronie expected, observed lub obu
stron daje `UNVERIFIED`. Niezależna, prawidłowo wykazana różnica zachowuje
priorytet `MISMATCH` i równocześnie raportuje pole `unverified`.

Komendy po poprawce używały tych samych parametrów izolacji opisanych wyżej:

```powershell
docker run --rm --name next-stabil-r04-a1-kind-test-after <parametry-izolacji> --entrypoint python next-stabil-r02-tests:pytest835-923dc559-fulltree -m pytest -q test/test_r04_version_identity.py
docker run --rm --name next-stabil-r04-a1-kind-combined <parametry-izolacji> --entrypoint python next-stabil-r02-tests:pytest835-923dc559-fulltree -m pytest -q test/test_r04_version_identity.py test/test_followup_chunk22_system_status.py test/test_android_release_api_configuration.py
docker run --rm --name next-stabil-r04-a1-kind-compile --network none --read-only --tmpfs /tmp --mount type=bind,source=C:\ai-lab-core-recovery,target=/workspace,readonly -w /workspace/backend -e PYTHONPYCACHEPREFIX=/tmp/pycache --entrypoint python next-stabil-r02-tests:pytest835-923dc559-fulltree -m py_compile app/services/version_identity_service.py test/test_r04_version_identity.py
```

Wyniki po poprawce:

- bezpośrednia reprodukcja: prawidłowy fixture `VERIFIED`, brak workera
  `UNVERIFIED`, różny poprawny SHA Windows `MISMATCH`, zły rodzaj workera/Web
  `UNVERIFIED`; exit `0`;
- focused: `23 passed`, exit `0`;
- combined: `34 passed`, exit `0`;
- compile zmienionych plików: `2/2`, exit `0`;
- właściwe rodzaje API/DB nadal przechodzą, a ich zamiana na przeciwny rodzaj
  daje `UNVERIFIED`;
- testy wywołują rzeczywisty moduł; decyzja walidatora nie jest mockowana;
- wejściowe manifesty nie są mutowane, publiczna allowlista i dotychczasowe pola
  `/version` pozostają objęte istniejącymi testami.

Komparator nadal wyłącznie porównuje dostarczone, prawidłowo opisane dowody. Nie
obserwuje sam plików, procesów ani runtime i nie stanowi odbioru wdrożenia.

## Observed / source / candidate

| Warstwa | Tożsamość i dowód | Stan |
|---|---|---|
| source baseline | `origin/main@483f9bf8b1a591ded8a42df5da87663c664ed5d4` | legacy `/version`; bez A1 |
| candidate | source/test A1 `ec102a8dacac529c3ac5f6715c08e4dd3ac35020` + bieżący atomowy microfix identity-kind, którego SHA odczytuje się z Git | `IDENTITY_KIND_FIX_READY_FOR_REVIEW / NOT_DEPLOYED` |
| observed backend | container `9d9b46c53041`, image ID `sha256:6342b36f...`, `/app=C:/ai-lab-core/build/deploy-main-483f9bf8/backend` | stary live source, bez A1 |
| observed public API | version `1.0.0`, API `1`, environment `development`, `debug=true`, minimum/latest `1.0.0`; brak `component_identity` | `REVIEW_REQUIRED`, A1 not deployed |
| stable client policy | `release-channel/stable/manifest.json`, blob `b15d7aa3f7cd8e9eda2b4ebcf8bebfe4d97c7dcd`, SHA-256 `FA9EEAB55397B8C34C8EBC15FC4708962E8923D1D3D86D0F5F7E91322E7D699A`; source client `pubspec.yaml`, blob `b14ea2505d4a9198f5c2edf948a79bffd9d10a5c` | niezmienione przez A1 |
| DB schema | A4 historycznie: `followup_assistant_chat_history_20260829`; w R04-A1 nie odczytywano DB | candidate wymaga jawnego dowodu, obecnie `UNVERIFIED` |
| Web/Windows/Android/gateway/Supervisor/workers | pełna struktura wymagana i przetestowana syntetycznie | konkretne build/runtime identity nadal `UNVERIFIED` do następnego zatwierdzonego integration/build/deploy |

Nie podstawiono SHA dokumentacji jako tożsamości buildu. Rescue
`5cd8f86e63e1ab829692ca2601096fd0c0d9d53a` nie zostało adoptowane.

## Hash źródła/testu A1

| Plik | SHA-256 |
|---|---|
| `backend/app/core/config.py` | `D031A6130C5CDAE64AF6837EFE78BD0141D3E37031A38EA966B970266AA9292E` |
| `backend/app/main.py` | `5173D3AA1AC89B577A62FD5BE1E2AF3A3EC609023FD398610BDF031612270829` |
| `backend/app/services/version_identity_service.py` | `E417345C4821C94CBD47F0FB2A5823C14340BA4CD7ECF8BF291080D7188792EA` |
| `backend/test/test_r04_version_identity.py` | `9879BFB41745EADDB504E3B2EB6B4B4391CF6C60DA30D08533EFFDFF3BF42835` |
| `frontend/test/update_decision_engine_test.dart` | `09E1BC5DF1C3FFA90C6A2670C2212A1BA36081D43DCB1686DC41EF7CC78CEEA1` |

## Pozostałe bramki i rollback

- Nie wykonano buildów Windows/Android/Web, podpisu, stable publish, deploy,
  restartu, migracji, DB write, model call, kolejki ani zewnętrznego workera.
- R03 pozostaje `WAITING_APPROVAL / WAITING_ESCROW_DECISION`; R04 jako całość
  pozostaje `IN_PROGRESS`.
- Runtime identity wszystkich składników oraz privacy/deploy acceptance wymaga
  osobnej, zatwierdzonej integracji i obserwacji.
- Rollback samego microfixu: odwrócić wyłącznie commit zawierający bieżący
  checkpoint identity-kind, identyfikowany z Git. Rollback całego source A1
  pozostaje osobnym odwróceniem `ec102a8d...`; legacy top-level `/version` i
  stable manifest są zachowane, więc nie ma migracji danych ani
  minimum-version rollbacku.

Następna bezpieczna czynność: odbiór R04-A1 przez właściciela, potem osobna
zgoda na następny podetap istniejącej karty R04.
