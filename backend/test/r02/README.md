# R02 — izolowane środowisko testowe

Ten katalog opisuje małe, przypięte środowisko testowe R02. Nie jest to
konfiguracja produkcyjna. Źródłem testu jest pełny snapshot wskazanego commita,
montowany read-only pod `/workspace`. PostgreSQL nie publikuje portu hosta,
używa własnego `tmpfs`, a sieć Compose jest `internal`.

## Tożsamości zamrożone przez R02

| Element | Wartość |
|---|---|
| main | `483f9bf8b1a591ded8a42df5da87663c664ed5d4` |
| rescue | `5cd8f86e63e1ab829692ca2601096fd0c0d9d53a` |
| backend base image ID | `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702` |
| final test image ID | `sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651` |
| PostgreSQL 16 Alpine image ID | `sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685` |
| dependency lock SHA-256 | `923DC5599D84F4B359D1EDB567C5ECE79F520642C3C2A78E30442141BCB454FA` |

Lokalny tag nie jest niezmiennym identyfikatorem. Przed użyciem porównaj ID:

```powershell
$ExpectedBase = 'sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702'
$ExpectedTests = 'sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651'
$ExpectedPostgres = 'sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685'
if ((docker image inspect next-stabil-r02-base:6342b36f --format '{{.Id}}') -ne $ExpectedBase) { throw 'R02 base image mismatch' }
if ((docker image inspect next-stabil-r02-tests:pytest835-923dc559-fulltree --format '{{.Id}}') -ne $ExpectedTests) { throw 'R02 test image mismatch' }
if ((docker image inspect postgres:16-alpine --format '{{.Id}}') -ne $ExpectedPostgres) { throw 'R02 PostgreSQL image mismatch' }
```

Jeżeli oczekiwany obraz bazowy istnieje tylko pod pełnym ID, najpierw sprawdź
ten obiekt po ID, a lokalny tag nadaj dopiero po tej kontroli:

```powershell
if ((docker image inspect $ExpectedBase --format '{{.Id}}') -ne $ExpectedBase) { throw 'R02 base image ID mismatch' }
docker image tag $ExpectedBase next-stabil-r02-base:6342b36f
if ((docker image inspect next-stabil-r02-base:6342b36f --format '{{.Id}}') -ne $ExpectedBase) { throw 'R02 base tag mismatch' }
```

Brak któregoś przypiętego obrazu oznacza `LOCAL_ONLY`/blokadę przekazania; nie
wolno w jego miejsce użyć obrazu produkcyjnego o niezweryfikowanej tożsamości.

## Świeże snapshoty i nakładka DOC-03

Wykonaj w nowym katalogu poza repo i runtime. Nie używaj starego katalogu
stagingowego jako wejścia:

```powershell
$Recovery = 'C:\ai-lab-core-recovery'
$SessionRoot = 'C:\ai-lab-core-staging\recovery\R02_REPLAY_<UTC>'
$MainSha = '483f9bf8b1a591ded8a42df5da87663c664ed5d4'
$RescueSha = '5cd8f86e63e1ab829692ca2601096fd0c0d9d53a'
if (Test-Path -LiteralPath $SessionRoot) { throw 'R02 replay root already exists' }
New-Item -ItemType Directory -Path $SessionRoot, "$SessionRoot\snapshots", "$SessionRoot\raw", "$SessionRoot\env" | Out-Null
git -C $Recovery archive --format=zip --output="$SessionRoot\snapshots\main.zip" $MainSha
git -C $Recovery archive --format=zip --output="$SessionRoot\snapshots\rescue.zip" $RescueSha
Expand-Archive -LiteralPath "$SessionRoot\snapshots\main.zip" -DestinationPath "$SessionRoot\snapshots\main"
Expand-Archive -LiteralPath "$SessionRoot\snapshots\rescue.zip" -DestinationPath "$SessionRoot\snapshots\rescue"
if ((Get-FileHash "$SessionRoot\snapshots\main.zip" -Algorithm SHA256).Hash -ne '6059D07FE119901453D146A6028C3B132488DF295273CB2AC41CCF44152BC64F') { throw 'main archive mismatch' }
if ((Get-FileHash "$SessionRoot\snapshots\rescue.zip" -Algorithm SHA256).Hash -ne '3A4D55B0C266474A2EAB0E53FF5FF514BDC0FE006855CCE3E66D190BDD8E4487') { throw 'rescue archive mismatch' }

$Overlay = "$Recovery\backend\test\r02\overlays\doc03-isolation.patch"
foreach ($Snapshot in @("$SessionRoot\snapshots\main", "$SessionRoot\snapshots\rescue")) {
  Push-Location $Snapshot
  try {
    git apply --check --unidiff-zero --whitespace=nowarn $Overlay
    git apply --unidiff-zero --whitespace=nowarn $Overlay
  } finally { Pop-Location }
}
```

Nakładka jest różnicą test-only od main do zaakceptowanego harnessu R02. Ten sam
patch stosuje się do rescue bez nadpisania jego zmian. Format `-U0` usuwa
spacje wymagane przez puste linie kontekstu z pliku-patcha; `--unidiff-zero`
jest dlatego jawne. `--whitespace=nowarn` dotyczy wyłącznie poprawnych pustych
linii dodawanych na końcu hunków bez kontekstu. Dokładne wynikowe Git clean
bloby poniżej pozostają bramką treści. Kontrola:

```powershell
$Relative = 'backend/test/test_document_preparation_recovery_fencing.py'
$MainTest = "$SessionRoot\snapshots\main\backend\test\test_document_preparation_recovery_fencing.py"
$RescueTest = "$SessionRoot\snapshots\rescue\backend\test\test_document_preparation_recovery_fencing.py"
if ((git -C $Recovery hash-object --path=$Relative $MainTest) -ne '63d25d6f05d2410391ffc8c84c9b035e0bf5d8ba') { throw 'main DOC-03 overlay mismatch' }
if ((git -C $Recovery hash-object --path=$Relative $RescueTest) -ne '15df78f2c719e58a881af839fd0059ec87e9f302') { throw 'rescue DOC-03 overlay mismatch' }
if (-not (Select-String -LiteralPath $RescueTest -Pattern 'complete_visual_handoff' -Quiet)) { throw 'rescue handoff test lost' }
```

`hash-object --path` stosuje reguły clean Git i jest odporny na sposób checkoutu
zakończeń linii. W referencyjnym replayu Windows surowe SHA-256 wyniosły
`3813BE9F3BBD0048CFC1BF2658A6299C23F19D9AEA687A563072B4990B12D30B`
(main) i `0B96DCF5ECF30A1B37BF11608819C2E2F59E09142FB3747301C3E353714E30E0`
(rescue). Wcześniejsze surowe hashe dotyczyły równoważnej treści z innym układem
CRLF/LF; Git clean blob jest kanoniczną kontrolą recepty.

## Syntetyczne wartości środowiska

Utwórz osobny plik env dla każdego wariantu. Wszystkie hasła/klucze muszą być
nowymi wartościami syntetycznymi. Nie kopiuj produkcyjnego `.env`.

Wymagane nazwy:

- `R02_BASE_IMAGE` — pełny ID obrazu bazowego;
- `R02_TEST_IMAGE` — lokalny tag obrazu testowego, wcześniej związany z
  oczekiwanym ID;
- `R02_POSTGRES_IMAGE` — pełny lokalny ID PostgreSQL;
- `R02_DATABASE_NAME`, `R02_DATABASE_USER`, `R02_DATABASE_PASSWORD`;
- `R02_SECRET_KEY`, `R02_ADMIN_PASSWORD`, `R02_N8N_INGEST_API_KEY`;
- `R02_SOURCE_ROOT` — pełny właściwy snapshot po nakładce;
- `R02_HARNESS_ROOT` — `C:/ai-lab-core-recovery/backend/test/r02`;
- `R02_SNAPSHOT` — dokładnie `main` albo `rescue` zgodnie z
  `R02_SOURCE_ROOT`.

`docker compose --env-file` służy interpolacji Compose. Dopiero jawne pole
`R02_SNAPSHOT` w `services.tests.environment` przekazuje wartość do kontenera.
Natomiast `docker run --env-file` przekazuje tylko wpisy obecne w podanym pliku;
dla bezpośredniego `docker run` użyj jawnego `--env R02_SNAPSHOT=main` albo
`--env R02_SNAPSHOT=rescue`. Guard w teście nie ma wartości domyślnej.

Przykład niesekretnej części main env:

```text
R02_BASE_IMAGE=sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702
R02_TEST_IMAGE=next-stabil-r02-tests:pytest835-923dc559-fulltree
R02_POSTGRES_IMAGE=sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685
R02_DATABASE_NAME=ai_lab_isolated_r02_replay_main
R02_DATABASE_USER=r02_replay_main
R02_SOURCE_ROOT=C:/ai-lab-core-staging/recovery/R02_REPLAY_<UTC>/snapshots/main
R02_HARNESS_ROOT=C:/ai-lab-core-recovery/backend/test/r02
R02_SNAPSHOT=main
```

Rescue używa osobnej nazwy DB/projektu, ścieżki `snapshots/rescue` oraz
`R02_SNAPSHOT=rescue`.

## Mały replay przekazania

Z `backend/test/r02` użyj różnych nazw projektów dla main i rescue:

```powershell
docker compose -p next-stabil-r02-replay-main --env-file <main-env> config --quiet
docker compose -p next-stabil-r02-replay-main --env-file <main-env> run --rm --no-deps --entrypoint python tests -c "import hashlib,os,pathlib; expected='B37EF374FBA6F188B046960A06CE5DD198EB24B9ECAD875C46CA6CFB1A56A20A'; actual=hashlib.sha256(pathlib.Path('/workspace/backend/app/services/unified_assistant_service.py').read_bytes()).hexdigest().upper(); assert os.environ['R02_SNAPSHOT']=='main'; assert actual==expected; print('R02_SNAPSHOT=main'); print('SERVICE_SHA256='+actual)"
docker compose -p next-stabil-r02-replay-main --env-file <main-env> run --rm --no-deps --entrypoint python tests -m pytest -c /r02-harness/pytest.ini -q -s /r02-harness/test_audit_reproductions.py

docker compose -p next-stabil-r02-replay-rescue --env-file <rescue-env> config --quiet
docker compose -p next-stabil-r02-replay-rescue --env-file <rescue-env> run --rm --no-deps --entrypoint python tests -c "import hashlib,os,pathlib; expected='833969661E0B4F6FE7A7B2E618AAC63885EA5621003E6F24DAAFBE5A3F2F2122'; actual=hashlib.sha256(pathlib.Path('/workspace/backend/app/services/unified_assistant_service.py').read_bytes()).hexdigest().upper(); assert os.environ['R02_SNAPSHOT']=='rescue'; assert actual==expected; print('R02_SNAPSHOT=rescue'); print('SERVICE_SHA256='+actual)"
docker compose -p next-stabil-r02-replay-rescue --env-file <rescue-env> run --rm --no-deps --entrypoint python tests -m pytest -c /r02-harness/pytest.ini -q -s /r02-harness/test_audit_reproductions.py
```

Przed DOC-03 uruchom własny PostgreSQL, odtwórz istniejący schemat i sprawdź
faktyczne połączenie. Samo `R02_DATABASE_NAME` nie jest dowodem izolacji:

```powershell
docker compose -p next-stabil-r02-replay-main --env-file <main-env> up -d postgres
$MainDbUser = 'r02_replay_main'
$MainDbName = 'ai_lab_isolated_r02_replay_main'
docker compose -p next-stabil-r02-replay-main --env-file <main-env> exec -T postgres psql -U $MainDbUser -d $MainDbName -Atc 'SELECT current_database(), current_user, pg_is_in_recovery()'
docker compose -p next-stabil-r02-replay-main --env-file <main-env> run --rm --entrypoint python tests -m alembic upgrade followup_assistant_chat_history_20260829
docker compose -p next-stabil-r02-replay-main --env-file <main-env> run --rm --entrypoint python tests -m unittest -v test.test_document_preparation_recovery_fencing
```

Powtórz te cztery polecenia z projektem i env rescue. Moduł rescue zawiera
`test_t08_stale_vision_result_cannot_advance_job`, który wywołuje rzeczywisty
`complete_visual_handoff`; pełny wynik DOC-03 potwierdza zachowanie tego testu.

## Dokładne historyczne suite

Poniższe nazwy pochodzą z logów R02. Są komendami odtworzenia historycznych
zestawów, nie deklaracją ich ponownego wykonania w każdym handoffie. Uruchamiaj
je po starcie własnego PostgreSQL i migracji. Dla badanego wariantu ustaw
`$Project` i `$EnvFile` na tę samą nazwę projektu i ten sam plik env, których
użyto do kontroli snapshotu powyżej:

```powershell
$Project = 'next-stabil-r02-replay-main' # albo osobny projekt rescue
$EnvFile = '<main-env>'                  # albo odpowiadający mu <rescue-env>

# DOC-03 kolejność A
docker compose -p $Project --env-file $EnvFile run --rm --entrypoint python tests -m unittest -v test.test_document_ingestion_vision_containment test.test_document_office_archive_safety test.test_document_intelligence_resource_wait test.test_document_preparation_pipeline test.test_document_metadata_unicode_safety test.test_document_preparation_recovery_fencing

# DOC-03 kolejność B, zapisany seed/permutacja 20260908
docker compose -p $Project --env-file $EnvFile run --rm --entrypoint python tests -m unittest -v test.test_document_metadata_unicode_safety test.test_document_preparation_pipeline test.test_document_ingestion_vision_containment test.test_document_intelligence_resource_wait test.test_document_preparation_recovery_fencing test.test_document_office_archive_safety

# pytest-only main/rescue
docker compose -p $Project --env-file $EnvFile run --rm --entrypoint python tests -m pytest -c /r02-harness/pytest.ini -v test/test_local_model_resource_coordinator.py test/test_unified_assistant_contract_sync.py test/test_unified_assistant_implementation.py test/test_unified_assistant_kb_grounding.py test/test_unified_document_content_service.py

# Assistant baseline main
docker compose -p $Project --env-file $EnvFile run --rm --entrypoint python tests -m unittest -v test.test_assistant_pipeline_v2_implementation test.test_assistant_chat_history test.test_assistant_visual_branch

# Visual/resource rescue
docker compose -p $Project --env-file $EnvFile run --rm --entrypoint python tests -m pytest -c /r02-harness/pytest.ini -v test/test_visual_v2_service.py test/test_local_model_resource_coordinator.py

# Visual/chat rescue
docker compose -p $Project --env-file $EnvFile run --rm --entrypoint python tests -m unittest -v test.test_assistant_visual_branch test.test_assistant_chat_history

# Combined rescue
docker compose -p $Project --env-file $EnvFile run --rm --entrypoint python tests -m unittest -v test.test_assistant_pipeline_v2_implementation test.test_document_ingestion_vision_containment test.test_document_intelligence_resource_wait

# Scope + Temporary Chat contract main/rescue
docker compose -p $Project --env-file $EnvFile run --rm --entrypoint python tests -m pytest -c /r02-harness/pytest.ini -v test/test_unified_assistant_scope_boundary.py test/test_temp_chat_v2_scope_estimation_semantics.py

# Chat-history integration main/rescue, wyłącznie w syntetycznej DB
docker compose -p $Project --env-file $EnvFile run --rm -e RUN_ASSISTANT_CHAT_HISTORY_INTEGRATION=1 --entrypoint python tests -m test.test_assistant_chat_history
```

Surowe logi, env, pełne snapshoty i obrazy nie należą do Git. W Git trafiają
wyłącznie mała nakładka testowa, sanityzowany manifest hashy i podsumowanie.
