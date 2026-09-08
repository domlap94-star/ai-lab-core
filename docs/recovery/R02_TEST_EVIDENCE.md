# R02 — dowody odtwarzalnych i izolowanych testów

## Zakres i tożsamość

- Sesja: `R02_20260907T232229Z`; wykonanie: `2026-09-07/08 UTC`.
- Source baseline: `main@483f9bf8b1a591ded8a42df5da87663c664ed5d4`.
- Kandydat oceniony osobno: `rescue@5cd8f86e63e1ab829692ca2601096fd0c0d9d53a`;
  nie został adoptowany ani połączony z recovery.
- Produkcyjny `backend/app` nie został zmieniony. Jedyna korekta istniejącego
  testu dotyczy `test_document_preparation_recovery_fencing.py`.
- Surowe logi i pełne snapshoty są `LOCAL_ONLY` pod
  `C:\ai-lab-core-staging\recovery\R02_20260907T232229Z`; ich manifest znajduje
  się w `R02_LOG_MANIFEST.csv`.

## Przypięte środowisko

- Obraz bazowy: lokalny tag `next-stabil-r02-base:6342b36f`, przed budową
  zweryfikowany jako
  `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`.
- Finalny obraz testowy:
  `next-stabil-r02-tests:pytest835-923dc559-fulltree`, image ID
  `sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651`.
- Python `3.12.13`; `pytest 8.3.5`; `pytest-asyncio 0.26.0`;
  `iniconfig 2.1.0`; `pluggy 1.5.0`. Hash locka:
  `923DC5599D84F4B359D1EDB567C5ECE79F520642C3C2A78E30442141BCB454FA`.
- Większość kampanii wykonano na pierwszym obrazie o identycznych zależnościach
  (`sha256:1c9974537fe4ef09c5f8f24692efc1ce4270404a341c88bc305438b8f5ae09d5`).
  Finalny obraz różni się wyłącznie metadanym `WORKDIR=/workspace/backend`;
  DOC-03 `19/19` oraz reprodukcje rescue `6/6` powtórzono na nim.
- PostgreSQL: lokalny image ID
  `sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685`;
  własny kontener `next-stabil-r02-pg-20260907t232229z`, bez publikowanego
  portu, w wewnętrznej sieci `next-stabil-r02-20260907t232229z-net`.
- Dwie oddzielne syntetyczne bazy: `ai_lab_isolated_r02` i
  `ai_lab_isolated_r02_rescue`. Obie zostały sprawdzone przez
  `SELECT current_database(), current_user, pg_is_in_recovery()` i mają head
  `followup_assistant_chat_history_20260829`.
- Pełne snapshoty utworzono przez `git archive` z dokładnych commitów. Hashy ZIP:
  main `6059D07FE119901453D146A6028C3B132488DF295273CB2AC41CCF44152BC64F`,
  rescue `3A4D55B0C266474A2EAB0E53FF5FF514BDC0FE006855CCE3E66D190BDD8E4487`.

Compose montuje pełny snapshot read-only pod `/workspace`, syntetyczne
`/tmp` i `/r02-data` jako `tmpfs`, nie publikuje PostgreSQL i używa sieci
`internal`. Ustawienia preparation, Assistant V2, Vision, Advanced, KB writer,
restore i retention delete są false; Ollama, Qdrant, n8n i Supervisory wskazują
niedostępny loopback. Testy bez DB miały `--network none`. Nie uruchamiano
lifespan aplikacji ani produkcyjnych dispatcherów. Ostrzeżenia klienta Qdrant
w istniejących pytestach oznaczają konstrukcję klienta; ruch był niemożliwy
przez `--network none`.

## FND-034 — fail-before i minimalna naprawa harnessu

Niezmieniony historyczny zestaw dawał `92/92 PASS`, co nie wykrywało zależności
od globalnej kolejki. Następnie realny `DocumentService` utworzył w syntetycznej
DB starszy, obcy queued job. Niezmieniony DOC-03 dał `17 PASS / 1 FAIL`:
`_claim()` otrzymał obcy rekord z realnego `DocumentPreparationService.claim_next()`.
To odtwarza FND-034 jako wadę izolacji testu, nie leasingu produktu.

Minimalna korekta tworzy kontrolny obcy sentinel, a osobna sesja każdego testu
blokuje wszystkie zastane `queued/running` rekordy przez PostgreSQL
`SELECT ... FOR UPDATE`. Produkcyjny `claim_next()` i `recover_expired()` nadal
wykonują rzeczywiste zapytania z `SKIP LOCKED`; nie są mockowane. Sentinel musi
pozostać queued, attempt `0`, bez lease. Nie dodano sleep, retry-do-skutku,
skip/xfail ani osłabienia asercji fencing. Teardown usuwa tylko własny sentinel
i flushuje FK przed własnym dokumentem.

Nakładka testowa main ma SHA-256
`89E7772A95318D6480C398CEC64358E9FA09C9FC0BD5D8AD809EC7D2E8B90F39`.
Rescue zachowuje własny test `complete_visual_handoff`; osobna nakładka
`LOCAL_ONLY` powstała z pełnego rescue i ma SHA-256
`A1D8628E87535DBF6198DBF2878599CABC7AE1E2AF9FD46EF75AA54FB6ECCE6A`.

## Wyniki testów

| Wersja / przebieg | Polecenie skrócone (dokładne moduły) | Wynik |
|---|---|---|
| fail-before | `python -m unittest -v test.test_document_preparation_recovery_fencing` po obcym starszym jobie | `17 PASS / 1 FAIL`, oczekiwany dowód |
| DOC-03 sam | ten sam moduł z poprawionym harness | `19/19 PASS` |
| kolejność A | `document_ingestion_vision_containment`, `document_office_archive_safety`, `document_intelligence_resource_wait`, `document_preparation_pipeline`, `document_metadata_unicode_safety`, `document_preparation_recovery_fencing` | `92/92 PASS` |
| kolejność B, seed `20260908` | `document_metadata_unicode_safety`, `document_preparation_pipeline`, `document_ingestion_vision_containment`, `document_intelligence_resource_wait`, `document_preparation_recovery_fencing`, `document_office_archive_safety` | `92/92 PASS` |
| main DOC-03, pełny snapshot + jawna nakładka | `python -m unittest -v test.test_document_preparation_recovery_fencing` | `19/19 PASS` |
| main pytest-only | pięć modułów: resource coordinator, contract sync, implementation, KB grounding, document content | `199/199 PASS` |
| main Assistant baseline | Pipeline V2, chat source contract i Assistant visual branch | `34/34 PASS` |
| main scope + Temporary Chat contract | dwa moduły pytest na pełnym drzewie | `16/16 PASS` |
| main chat integration | `RUN_ASSISTANT_CHAT_HISTORY_INTEGRATION=1 python -m test.test_assistant_chat_history` | `PASS`; list/detail queries `1/4`, max `3.278/5.746 ms` |
| rescue Visual/resource | `pytest test_visual_v2_service.py test_local_model_resource_coordinator.py` | `51/51 PASS` |
| rescue visual/chat source | `unittest test_assistant_visual_branch test_assistant_chat_history` na pełnym drzewie | `30/30 PASS` |
| rescue chat integration | jak main, na osobnej bazie rescue | `PASS`; obejmuje dwa połączenia delete/publication i stale ORM; max `5.583/7.626 ms` |
| rescue pytest-only | te same pięć modułów co main | `201/201 PASS` |
| rescue combined | Pipeline V2, ingestion containment, intelligence resource wait | `31/31 PASS` |
| rescue scope + Temporary Chat contract | dwa moduły pytest na pełnym drzewie | `16/16 PASS` |
| compile | dwa zmienione pliki Python, cache w `/tmp` | `2/2 PASS` |

Pierwsza próba rescue unit (`024`) błędnie montowała tylko backend i nie dawała
testowi dostępu do frontendu tego samego snapshota. To błąd uruchomienia R02,
nie source failure; pełne drzewo (`025`) daje `30/30 PASS`. Analogicznie `021`
użyło ścieżki skryptu zamiast modułu; właściwy `022` przeszedł.

## REP-001–004 i dodatkowy test KB + Visual

Reprodukcje importują realny `UnifiedAssistantService` badanego snapshota:

- REP-001: `Czy możesz przeanalizować ten dokument?` z wybranym dokumentem
  daje `SYSTEM_META` na main i rescue — hipoteza potwierdzona.
- REP-002: pytanie techniczne daje KB `true`, ale dodanie `podaj adres klienta`
  daje `false` na main i rescue — hipoteza potwierdzona.
- REP-003: poprawny payload ze zwykłym `S235` lub `S355` daje
  `user_output_internal_leak` na main i rescue — hipoteza potwierdzona.
- REP-004: wyjątek wyszukiwania KB i prawdziwy brak dopasowania zwracają
  identyczny `_Collected` na main i rescue — hipoteza potwierdzona.
- KB + supplemental Visual: main nie ma tej ścieżki (`NOT_APPLICABLE`). Rescue
  rozpoczyna od 5 syntetycznych źródeł sprawy i 3 KB, następnie dodaje 4 Visual.
  Rzeczywisty `_collect()` oraz `_prompt()` kończą z `4 case / 0 KB / 4 visual`.
  FND-019 jest potwierdzone dla rescue i pozostaje otwartym błędem produktu
  właściwego późniejszego pakietu; R02 go nie naprawia.

Mockowane są wyłącznie granice zewnętrzne reprodukcji: konstrukcja document/
vector readera, wywołanie rejestru narzędzi oraz KB retrieval. Dane zwracane z
tych granic są syntetyczne. `_query_mode`, `_should_retrieve_kb`, `_validate`,
`_collect` i `_prompt` są rzeczywistymi metodami każdego snapshota. Testy
Visual V2 używają prawdziwego service z syntetycznym SQLite/storage oraz fake
Supervisor; nie wykonują Temporary Chat. DOC-03 używa prawdziwego PostgreSQL,
`DocumentService`, claim/recovery i fencing.

## Komendy odtworzenia

Po ustawieniu jednorazowego syntetycznego env opisanego w
`backend/test/r02/README.md`:

```powershell
docker compose -p next-stabil-r02 --env-file <synthetic-r02-env> -f backend/test/r02/compose.yaml build tests
docker compose -p next-stabil-r02 --env-file <synthetic-r02-env> -f backend/test/r02/compose.yaml up -d postgres
docker compose -p next-stabil-r02 --env-file <synthetic-r02-env> -f backend/test/r02/compose.yaml run --rm tests -m alembic upgrade followup_assistant_chat_history_20260829
docker compose -p next-stabil-r02 --env-file <synthetic-r02-env> -f backend/test/r02/compose.yaml run --rm --entrypoint python tests -m unittest -v test.test_document_preparation_recovery_fencing
docker run --rm --network none --env-file <synthetic-snapshot-env> --mount "type=bind,source=<full-snapshot>,target=/workspace,readonly" --mount "type=bind,source=<r02-harness>,target=/r02-harness,readonly" --tmpfs /tmp --tmpfs /r02-data --workdir /workspace/backend --entrypoint python next-stabil-r02-tests:pytest835-923dc559-fulltree -m pytest -c /r02-harness/pytest.ini -q -s /r02-harness/test_audit_reproductions.py
```

Przed testem mutującym trzeba niezależnie sprawdzić nazwę połączenia przez
`SELECT current_database()`; sama nazwa env nie jest dowodem izolacji.

## Skutki i ograniczenia

Własne syntetyczne skutki po kampanii: main `223 documents / 223 preparation
jobs / 10 assistant runs / 61 conversations / 216 messages / 0 analysis jobs`;
rescue `42 / 42 / 12 / 63 / 218 / 0`. Po zachowaniu dowodów usunięto wyłącznie
jednoznacznie oznaczone własne zasoby: kontener PostgreSQL, sieć internal oraz
trzy tymczasowe pliki env R02. Finalny obraz testowy
`sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651`
pozostaje lokalnie jako odtwarzalny artefakt; snapshoty, nakładka rescue i 41
surowych logów są `LOCAL_ONLY`.

Nie wykonano testów Flutter/Android, realnego 9B, Temporary Chat ani E2E
produkcji (`NOT_RUN`, poza R02). Nie było dostępu ani zapisów do produkcyjnej
DB/storage, restartów, migracji produkcyjnych, kolejki produkcyjnej, Qdrant,
Gmail, Calendar, Supervisorów ani modeli. R02 poprawia wiarygodność harnessu;
jawne REP source failures pozostają otwarte dla R07/R08 i nie są maskowane.

## Domknięcie procedury przekazania — 2026-09-08

Review potwierdzono w opublikowanym drzewie `5ae1f62aa4da74895e11710849866ba46fd939a2`:

1. `test_audit_reproductions.py` wymagał `R02_SNAPSHOT`, ale README go nie
   wymieniało, a Compose nie przekazywał go do kontenera. `--env-file` Compose
   sam nie eksportuje wszystkich wpisów do usługi.
2. Czyste snapshoty main/rescue nie zawierały testowej izolacji DOC-03, a
   wcześniejsza nakładka rescue była tylko `LOCAL_ONLY`, bez kompletnej recepty.
3. Dodatkowo literalny digest PostgreSQL w Compose nie był rozwiązywalny;
   istniejący lokalny `postgres:16-alpine` miał inny, zweryfikowany image ID.

Przed korektą dokładna opublikowana komenda Compose zakończyła się `exit 1`
przy próbie rozwiązania błędnego obrazu PostgreSQL (`R02-L043`). Ten sam test
uruchomiony diagnostycznie z `--no-deps`, bez ręcznego przekazania brakującej
zmiennej, zakończył collection `exit 2` z guardem
`R02_SNAPSHOT must be exactly 'main' or 'rescue'` (`R02-L044`). Oba wyniki są
błędem procedury, nie produktu.

Minimalna korekta:

- Compose przekazuje wymagane `R02_SNAPSHOT` i wymaga jawnego pełnego
  `R02_POSTGRES_IMAGE`;
- README rozróżnia interpolację `docker compose --env-file` od przekazywania
  `docker run --env-file`, zawiera komendy main/rescue oraz kontrolę kodu
  wewnątrz kontenera;
- `backend/test/r02/overlays/doc03-isolation.patch` jest jedną małą nakładką
  test-only. Powstała jako diff main `3d0091e...` → harness R02 `63d25d6...`;
  stosuje się kontekstowo także do rescue i zachowuje jego
  `complete_visual_handoff`.

Świeży replay nie używał poprzedniego stagingowego env ani nakładki. Snapshoty
utworzono ponownie przez `git archive`; archiwa zachowały hashe
`6059D07F...` (main) i `3A4D55B0...` (rescue). Replay testów użył równoważnego
pełnokontekstowego zapisu patcha `63E07EFF...`. Przed publikacją ten sam diff
znormalizowano do formatu `-U0`, aby sam artefakt przechodził
`git diff --check`; finalny patch SHA-256 to
`AE68005DF750D139C6B9CC9D491458450C16EC2E2F6C6CE731AC1E1E48BCE018`.
Finalny patch ponownie zastosowano z `--unidiff-zero` osobno do czystego main i
rescue, uzyskując te same bloby wynikowe; testów nie powtarzano, bo treść
wynikowych drzew nie zmieniła się.
Po zastosowaniu Git clean blob testu to `63d25d6f05d2410391ffc8c84c9b035e0bf5d8ba`
dla main i `15df78f2c719e58a881af839fd0059ec87e9f302` dla rescue. Surowe Windows
SHA-256 to odpowiednio `3813BE9F...` i `0B96DCF5...`; różnica względem starych
hashy wynika wyłącznie z CRLF/LF, przy identycznej znormalizowanej treści.

| Powtórzony test | Wynik bieżącego replayu |
|---|---|
| main: env + hash zamontowanego `UnifiedAssistantService` | PASS |
| rescue: env + hash zamontowanego `UnifiedAssistantService` | PASS |
| REP-001–004 + main brak supplemental Visual | `6/6 PASS` |
| REP-001–004 + rescue KB/supplemental Visual | `6/6 PASS`; `4 case / 0 KB / 4 visual` |
| main: `current_database()` + istniejąca migracja | PASS |
| rescue: `current_database()` + istniejąca migracja | PASS |
| DOC-03 main z nakładką | `19/19 PASS` |
| DOC-03 rescue z nakładką | `19/19 PASS`; T08 `complete_visual_handoff` PASS |

Nowe surowe logi `R02-L043`–`R02-L058` są `LOCAL_ONLY` pod
`C:\ai-lab-core-staging\recovery\R02_HANDOFF_20260908T063527Z\raw` i mają
hashe w rozszerzonym `R02_LOG_MANIFEST.csv`. Po replayu usunięto wyłącznie dwa
własne kontenery PostgreSQL, dwie sieci internal i dwa pliki env z syntetycznymi
sekretami. Pozostały snapshoty, logi i przypięty obraz testowy. Historycznych
199/201 ani 92/92 nie powtarzano i nie datowano ponownie.
