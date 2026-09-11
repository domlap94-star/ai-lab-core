# R05-A2 — dowód lokalnej granicy uploadu

## Wynik

R05-A2 osiągnęło `OFFLINE_UPLOAD_BOUNDARY_READY_FOR_REVIEW / NOT_DEPLOYED`
na source `dc075426c233ac204cec144be04cb66e74349702`. Test nie uruchamiał
przeglądarki, profilu, sieci ani rzeczywistego workera CLI. `fake upload`
oznacza wyłącznie argument przekazany przez kod workera do atrapionego
`setInputFiles`; nie dowodzi wysłania do Temporary Chat.

R05-A1 pozostaje odebrane przez właściciela na source
`d31e105427acd40733e91c4d4b46f0412b0f95ad` i evidence
`05995ab2c87438c5786a9f874793e95d2bf5b296` jako
`SOURCE_AND_SYNTHETIC_TESTS_ACCEPTED / NOT_DEPLOYED`.

## Łańcuch i minimalna zmiana

| Etap | Faktyczna implementacja i kontrola |
|---|---|
| Backend | `VisualV2Service` wykonał realne `ensure → advance(block) → approval_candidate → approve_export → advance/submit`. Request zawierał `request_key` oraz wyłącznie dozwolone deskryptory `source_ref`, syntetyczny `document_id`, `page_number`, `asset_id`, `sha256`, `incoming_relative_path`. Backend source nie został zmieniony. |
| `VisionQueue` | Realne `create()` odczytuje incoming jeden raz do bufora, sprawdza SHA-256 i zapisuje dokładnie ten bufor do `job/input`; potem zapisuje niezmieniony manifest `NEXT_STABIL_VISION_JOB_V1`. |
| Worker | `loadVerifiedInputs()` waliduje manifest, zwykły plik i root, odczytuje raz bajty, sprawdza limit i SHA-256 oraz tworzy bezpieczny Playwright `FilePayload` (`name`, `mimeType`, `buffer`). CLI `run()` używa tej samej funkcji. |
| Ostatnia granica | Bezpośrednio przed `setInputFiles` worker zapisuje atomowy `NEXT_STABIL_VISION_UPLOAD_HANDOFF_V1` ze stanem `contact_may_have_started`; po potwierdzeniu załączników zapisuje `upload_confirmed`. Marker zawiera tylko job/source ref, hash i rozmiar. |
| Restart/retry | Błąd albo restart po markerze daje `UPLOAD_UNCERTAIN` i `next_retry_at=null`; także etykieta `UI_CHANGED` nie przywraca retry. Exit 0 bez potwierdzonego markera nie daje `COMPLETE`. Historyczny manifest joba nie jest przepisywany ani automatycznie uznawany za nowo zatwierdzony. |

Nie dodano drugiej polityki approval, nowego pipeline ani nowej wersji
manifestu joba. Rozszerzenie dotyczy lokalnego, oddzielnego markera skutku
workera. Rollback source to odwrócenie commita A2, ale przed przyszłym
wdrożeniem trzeba skoordynować kolejkę i worker; powrót do automatycznego retry
po niepewnym uploadzie nie jest bezpiecznym zachowaniem operacyjnym.

## Fail-before i pass-after

Fail-before na preimage uruchomił prawdziwe `vision-job.js` z atrapionym
Playwright. Po poprawnym hash checku fake launch podmienił plik przed
`setInputFiles`. Ostatnia granica dostała SHA-256
`B8D0474304BB781400E66B3678824B5482A75C04A1A5D554E495B4D3F555E61B`
zamiast zatwierdzonego
`A75D6618A79655B27EBB7DF595DC7BFE2FF8AC1880BEDB442DED279EC2B4CAD5`.
Wynik: `FAIL_BEFORE_TOCTOU_REPRODUCED`, exit `1`.

Pass-after użył dwóch requestów wygenerowanych przez prawdziwą bramkę A1:

| Przypadek | Hash zatwierdzonego finalnego rastra | Hash bajtów fake upload | Wynik |
|---|---|---|---|
| `public_safe` | `3956F8ED4074E3AB3531A9A821159A65A8A12441E6E5328021D6A09914DD3206` | taki sam | PASS |
| `locally_redacted` | `7A89CB69AE2D29BDB1F8F2311177CB128B877B75F00C6B2A94B33661631B431C` | taki sam; różny od sztucznego niedopuszczonego oryginału | PASS |

Request backendu był bez zmian kopiowany do realnej kolejki. Queue wygenerowała
job ID i manifest, worker odczytał job, a fake granica niezależnie policzyła
hash otrzymanego bufora. Oba zadania miały różne `request_key` i `job_id`.
Finalne rastry miały puste EXIF, a obiekt przekazany do granicy zawierał tylko
`buffer`, bezpieczną nazwę `S1.jpg` i MIME `image/jpeg`; żadnej ścieżki,
oryginalnej nazwy lub metadanych klienta.

Negatywna macierz sprawdziła: zły hash incoming i input, niewłaściwe
`source_ref ↔ relative_input_path`, traversal, junction/symlink input root,
podmianę incoming po odczycie kolejki, podmianę input po odczycie workera,
cancel przed granicą, brak potwierdzenia temporary mode, `AUTH_REQUIRED`,
`UI_CHANGED`, brak markera przy exit 0 oraz crash/restart po markerze. Wszystkie
przypadki pozostały bez niedopuszczonych bajtów na fake upload albo zachowały
wcześniej zatwierdzony bufor; po możliwym kontakcie nie powstał automatyczny
drugi upload.

## Polecenia i wyniki

- Obraz Python: `sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651`,
  Python 3.12, pytest 8.3.5; `docker run --rm --network none --read-only`,
  source `/workspace` read-only, `/tmp` jako tmpfs, tylko syntetyczne wartości
  inicjalizacyjne. Polecenie:
  `python -m pytest -p no:cacheprovider -q test/test_visual_v2_service.py test/test_r05_visual_export_api.py`.
  Wynik: `76 passed`, exit `0`.
- Node `v24.18.0`: kolejno `node operations/vision-worker/test_contract.js`,
  `node operations/vision-worker/test_upload_boundary.js --chain-root <synthetic-chain>`,
  `node operations/supervisor/test_vision_queue.js`,
  `node operations/supervisor/test_analysis_queue.js`. Wszystkie cztery exit
  `0`; procesy browser/network/spawnWorker były podstawione przed konstrukcją.
- `python -m compileall` dla dotkniętego testu/backend dependency: exit `0`.
  Pięć `node --check`: `0,0,0,0,0`.

Pierwszy kontener pytest zatrzymał się przy kolekcji, ponieważ brakowało ośmiu
syntetycznych wymaganych ustawień (`DOCKER_EXIT_CODE=4`); nie utworzył fixture.
Jedno ponowienie z wartościami generowanymi w procesie przeszło. Osobna próba
agregacji logu Node miała błąd parametru PowerShell `Tee-Object -Append`; wyniki
z niej nie są używane jako finalny dowód. Oba zdarzenia zachowano w manifeście,
nie przypisano ich produktowi.

## Tożsamość i skutki

| Element | Identyfikator |
|---|---|
| parent source | `a09e461bae2c7296e02e92f69864c8fb1a00f976` |
| source A2 | `dc075426c233ac204cec144be04cb66e74349702` |
| `vision_queue.js` blob | `996ab39f7b5e55f46e6f11665d7500840856c340` |
| `vision-job.js` blob | `8908d2dea455d2e1a401168b46d16b0f970bc56c` |
| `vision_contract.js` blob | `393a00dd840c5a484b2c58c48f2bf437cc824ca9` |
| test upload boundary blob | `65d9795394d4d04e167561448576d25b0e08bae1` |
| backend chain test blob | `81f7ea5b11a3780bcae8d56115213b6a823475b2` |

Powstały wyłącznie efemeryczne kontenery `docker run --rm`, tmpfs/SQLite oraz
syntetyczne pliki w chronionym katalogu dowodowym. Nie utworzono named volume,
sieci Docker ani portu hosta. Końcowa kontrola obrazu pokazała tylko dwa stare,
zatrzymane kontenery R04-A2; nie należały do tej sesji i nie zostały zmienione.
Nie pozostał własny proces Node. Produkcyjne DB/storage/spool, aplikacja,
Supervisor HTTP, realny worker, przeglądarka, modele, Temporary Chat, Qdrant,
Gmail i n8n: `NOT_RUN`; real export: `0`.

Surowe logi i syntetyczne rastry/requesty pozostają `LOCAL_ONLY` pod
`C:\ai-lab-core-staging\recovery\R05_A2_UPLOAD_BOUNDARY_20260911T215159Z`.
Ich mały indeks znajduje się w
`docs/recovery/R05_A2_LOCAL_EVIDENCE_MANIFEST.csv`.

## Granica dowodu i następny krok

Dowód kończy się na lokalnym wywołaniu atrapionego `setInputFiles`. Nie
zweryfikowano realnego Playwright/Edge, profilu, faktycznego uploadu,
Temporary Chat, worker rootu runtime, UI decyzji operatora ani end-to-end.
Source jest `NOT_DEPLOYED`; zewnętrzna kopia workera nie została podmieniona.

Następny bezpieczny krok: właściciel przegląda i przyjmuje albo odrzuca A2.
Każdy realny browser/upload smoke, skoordynowany rollout kolejki/workera albo
rozpoczęcie R06 wymaga oddzielnej zgody.
