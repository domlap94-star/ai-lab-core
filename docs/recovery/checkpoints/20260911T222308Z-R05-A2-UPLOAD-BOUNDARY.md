# R05-A2 — checkpoint lokalnej granicy uploadu

- Checkpoint ID: `R05-20260911T222308Z-A2-UPLOAD-BOUNDARY`
- UTC: `2026-09-11T22:23:08Z`
- Repo / branch / worktree: `domlap94-star/ai-lab-core` / `recovery/next-stabil-repair-completion` / `C:\ai-lab-core-recovery`
- Wejście A2: `05995ab2c87438c5786a9f874793e95d2bf5b296`
- Checkpoint start: `a09e461bae2c7296e02e92f69864c8fb1a00f976`
- Source objęte testem: `dc075426c233ac204cec144be04cb66e74349702`
- Poprzedni checkpoint: `docs/recovery/checkpoints/20260911T215344Z-R05-A2-START.md`

## Faktycznie zakończono

- Zachowano odbiór R05-A1: source `d31e105427acd40733e91c4d4b46f0412b0f95ad`, evidence `05995ab2c87438c5786a9f874793e95d2bf5b296`, `SOURCE_AND_SYNTHETIC_TESTS_ACCEPTED / NOT_DEPLOYED`.
- Odtworzono błąd TOCTOU istniejącego workera: po poprawnym sprawdzeniu hasha podmiana pliku przed `setInputFiles` przekazała inne bajty. Wynik `FAIL_BEFORE_TOCTOU_REPRODUCED`, exit `1`; log SHA-256 `0C33EC33EC0B620581C02ED2F5778E8EFF4D9E3DF864186A9659200F63AA3BC9`.
- Kolejka odczytuje incoming raz, sprawdza jego SHA-256 i zapisuje dokładnie ten bufor. Worker po sprawdzeniu manifestu, zwykłego pliku, rootu, rozmiaru i SHA-256 przekazuje ten sam bufor do atrapionego `setInputFiles`.
- Przed ostatnią granicą worker zapisuje odrębny marker `contact_may_have_started`; po możliwym kontakcie błąd/restart nie otrzymuje automatycznego retry. Potwierdzony marker `upload_confirmed` jest wymagany do `COMPLETE`.
- Dwa requesty wygenerowane przez realną ścieżkę A1 (`public_safe`, `locally_redacted`) przeszły przez rzeczywistą lokalną kolejkę i kod workera; fake upload otrzymał dokładnie zatwierdzone finalne bajty. Nie uruchomiono przeglądarki ani sieci.

## Kontrole

| Kontrola | Wynik | Dowód |
|---|---|---|
| Backend `test_visual_v2_service.py` + `test_r05_visual_export_api.py` | PASS, `76 passed`, exit `0` | log SHA-256 `C22A96553E5060741A152A3213507B0C55323C6A6138B48C354684611AD3D090` |
| Worker contract + upload boundary + VisionQueue + AnalysisQueue | PASS, cztery procesy Node exit `0` | log SHA-256 `0F3232681C2AD5110303409691A7B7D9EC52632ADCDFC6A6D80EAF828A7AFEB3` |
| `compileall` i pięć `node --check` | PASS, exit `0` | bieżąca sesja A2 |
| Exact-byte positive cases | PASS | `public_safe` SHA-256 `3956F8ED4074E3AB3531A9A821159A65A8A12441E6E5328021D6A09914DD3206`; `locally_redacted` SHA-256 `7A89CB69AE2D29BDB1F8F2311177CB128B877B75F00C6B2A94B33661631B431C` |
| Browser / real Playwright / Temporary Chat / external upload | NOT_RUN / NOT_VERIFIED | poza zakresem zgody A2 |
| Testy aplikacyjne Flutter/Web/Android | NOT_RUN | frontend niezmieniony; Android nadal `DEFERRED_BY_OWNER / NOT_TESTED` |

Pierwszy kontener testowy bez ośmiu wymaganych syntetycznych ustawień zakończył kolekcję kodem `4`; nie utworzył fixture. Powtórzenie po jawnym ustawieniu wyłącznie syntetycznych wartości przeszło. Jedna próba agregacji logu Node miała błąd wrappera PowerShell i nie jest używana jako dowód finalny. Oba zdarzenia pozostały jawne w indeksie.

## Skutki i odtwarzalność

- Source A2 opublikowano w osobnym commicie `dc075426c233ac204cec144be04cb66e74349702`.
- Dowody lokalne: `C:\ai-lab-core-staging\recovery\R05_A2_UPLOAD_BOUNDARY_20260911T215159Z`; szczegółowy indeks z hashami: `docs/recovery/R05_A2_LOCAL_EVIDENCE_MANIFEST.csv`.
- Utworzono tylko efemeryczne kontenery `docker run --rm`, tmpfs/SQLite i syntetyczne pliki. Nie utworzono named volumes, sieci ani host ports; nie pozostał własny proces Node.
- Nie uruchomiono normalnej aplikacji, dispatchera, Supervisor HTTP, worker CLI, browsera, Temporary Chat, modeli, Qdrant, Gmaila, n8n ani realnego eksportu. Produkcyjne DB/storage/spool i chronione zasoby R03/R04 pozostają nietknięte.
- Oryginalny worktree pozostaje zachowany: 203 wpisy manifestu/statusu i staged `0`; main i rescue nie zostały zmienione ani adoptowane.
- SHA commita zawierającego ten checkpoint odczytuje się z Git po publikacji; nie jest wpisywane do własnej treści.

## Stan i STOP

- R05-A1: `SOURCE_AND_SYNTHETIC_TESTS_ACCEPTED / NOT_DEPLOYED`.
- R05-A2: `OFFLINE_UPLOAD_BOUNDARY_READY_FOR_REVIEW / NOT_DEPLOYED`.
- R05: `IN_PROGRESS`; `REAL_BROWSER_UPLOAD_AND_EXTERNAL_END_TO_END_NOT_VERIFIED`.
- R04: `IN_PROGRESS`.
- R03: `WAITING_APPROVAL / WAITING_ESCROW_DECISION`.
- R06–R24: nieuruchomione przez ten podetap.

Następny bezpieczny krok: właściciel przegląda i przyjmuje albo odrzuca ograniczony wynik R05-A2. Realny browser/upload smoke, rollout kolejki/workera i R06 wymagają osobnej zgody. STOP.
