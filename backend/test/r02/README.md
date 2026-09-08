# R02 — izolowane środowisko testowe

Ten katalog opisuje małe, przypięte środowisko testowe dla R02. Nie jest to
konfiguracja produkcyjna. Obraz testowy dziedziczy po niezmiennym obrazie
backendu wskazanym pełnym identyfikatorem i dodaje wyłącznie zależności z
`requirements.lock`. PostgreSQL nie publikuje portu hosta, używa własnego
`tmpfs`, a sieć Compose jest `internal`.

## Wymagane wartości

Ustaw jawnie w powłoce uruchamiającej:

- `R02_BASE_IMAGE` — pełny immutable image ID obrazu backendu;
- `R02_TEST_IMAGE` — jednoznaczna lokalna nazwa obrazu R02;
- `R02_DATABASE_NAME` — zatwierdzona syntetyczna baza, np.
  `ai_lab_isolated_r02`;
- `R02_DATABASE_USER` i jednorazowe syntetyczne hasło;
- `R02_SECRET_KEY`, `R02_ADMIN_PASSWORD` i `R02_N8N_INGEST_API_KEY` —
  jednorazowe syntetyczne wartości wymagane przez walidację konfiguracji;
- `R02_SOURCE_ROOT` — pełne drzewo ocenianego snapshota (nie tylko backend),
  montowane read-only pod `/workspace`;
- `R02_HARNESS_ROOT` — katalog zawierający testy/reprodukcje R02.

Nigdy nie pobieraj tych wartości z produkcyjnego `.env`.

## Odtworzenie

Z `backend/test/r02`:

```powershell
docker compose -p next-stabil-r02 --env-file <synthetic-r02-env> build tests
docker compose -p next-stabil-r02 --env-file <synthetic-r02-env> up -d postgres
docker compose -p next-stabil-r02 --env-file <synthetic-r02-env> run --rm tests -m alembic upgrade followup_assistant_chat_history_20260829
docker compose -p next-stabil-r02 --env-file <synthetic-r02-env> run --rm --entrypoint python tests -m unittest -v test.test_document_preparation_recovery_fencing
docker compose -p next-stabil-r02 --env-file <synthetic-r02-env> run --rm --entrypoint python tests -m pytest -c /r02-harness/pytest.ini -v /r02-harness/test_audit_reproductions.py
```

Przed importem aplikacji sprawdź `SELECT current_database(), current_user,
pg_is_in_recovery()` wewnątrz własnego kontenera PostgreSQL. `DATABASE_URL`
oraz `TEST_DATABASE_NAME` muszą wskazywać tę samą bazę. Flagi dispatcherów i
wysyłek pozostają wyłączone, adresy zewnętrznych usług wskazują niedostępny
loopback, a montowane źródło jest tylko do odczytu.

Surowe logi i pełne kopie snapshotów nie należą do Git. W Git trafia wyłącznie
sanityzowany manifest hashy i zwięzłe wyniki.
