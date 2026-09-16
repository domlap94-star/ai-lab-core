# Checkpoint R04 / D-21 / P3 startup guard — 2026-09-16T16:14:20Z

## Stan

- branch: `recovery/next-stabil-repair-completion`;
- start local/tracking/remote:
  `ab44ad9a19c81d93fa924c54fe6a5adc9fefe724`;
- accepted source pozostaje:
  `cb6e22506a0fecc440400566293524536847b9b0`;
- wynik: `P3 PREPARATION_PARTIAL / BASE_START_GUARD_SOURCE_PARTIAL /
  LOCAL_ONLY / TESTS_NOT_RUN / NO_CUTOVER`;
- P1/P2/DATA_ONLY i R05-A1–A4 zachowują wcześniejsze wąskie odbiory;
- produkcyjny manifest pozostaje `NOT_APPROVED_FOR_START`;
- Supervisor pozostaje `INTENTIONALLY_STOPPED`.

## Ograniczona diagnoza

1. Zachowany log Docker Desktop dla okna
   `2026-09-16T13:38:16Z–13:43:51Z` zawiera odpowiedzi `/time` oraz
   anulowane event streams/EOF, ale nie pasujący `containers/json` ani exact
   backend `inspect`. Nie rozstrzyga przyczyny poprzednich timeoutów.
2. Log VM `init.log` z tego okna został zrotowany. Ograniczone dzienniki
   Application/System nie zawierają pasujących zdarzeń Docker/WSL.
3. Brak nowego dowodu odzyskania resource reads oznaczał STOP przed
   warunkowym inspectem, SQL, sprawdzeniem obrazu i testowym kontenerem.
4. Taski backupu nadal mają wyniki `267014/1/1`. `267014` sklasyfikowano jako
   `0x41306 / SCHED_S_TASK_TERMINATED`, bez przypisywania aktora/przyczyny.
   Runner nie przekierowuje stdout/stderr, a brak pasujących zdarzeń Task
   Scheduler oznacza, że przyczyna wyników `1` pozostaje nierozstrzygnięta.
5. Punkt R03 `E:\ai-lab-backup\20260908T210559Z` istnieje, a jego manifest ma
   SHA-256 `8F20A7845473097EE74019966583EC3F121139C4B562265F9A7391FAFAF6BE4B`.
   Jest to historyczny punkt z accepted restore drill, nie dowód dzisiejszej
   świeżości ani zgoda escrow.

## WIP źródłowy

Przygotowano, lecz nie opublikowano jako source-ready:

- `backend/app/core/config.py`;
- `backend/app/database/init_db.py`;
- `backend/app/main.py`;
- `backend/app/services/backup_plan_reconciler.py`;
- `backend/test/test_d21_p3_startup_guard.py`.

Kontrakt WIP zachowuje domyślne `true`. Przy jawnym `false` seed jest
zastąpiony fail-closed odczytem `READ ONLY` istniejącej rewizji/roli/admina,
a reconciler nie tworzy tasku ani sesji. Lifespan obsługuje `None`; pozostałe
automaty zachowują swoje istniejące flagi.

Preimage/output SHA-256:

| Ścieżka | Preimage | WIP |
|---|---|---|
| `backend/app/core/config.py` | `74CCBC5542368AD58C121FEF593EDA77EA94AF4548B6E82490C5D3AC505C45BB` | `F07A13EF54F3E24FF9D6CAE7FBC235659DAE954CEC54E62ACE4FCD16DADFC52C` |
| `backend/app/main.py` | `81A8723875A1ACECB1BDA4FBFF34B60B1B4E9CBDA98BF493A65E1E5204997E14` | `5C6C039934639856F384EF67346A80311738C2B824FD9375393B145E3506A404` |
| `backend/app/database/init_db.py` | `83714C7ACF739A41465CED95CF8EF8626DEBAA072668DD879FEC4C9D7A6604A2` | `2072F3657A115ABB67F56E82B498FFC2CDC32765135BF2315C813D17A8284BDE` |
| `backend/app/services/backup_plan_reconciler.py` | `6E3CBA07EA96FE56A166965059C0EDD3232EBC7C30F976DFEC3CFADA59D8B9C6` | `743B5D1EC337A606BD8EE11CA09548B7A0F5CB1EB9086694C40D0ED9EF86A372` |
| `backend/test/test_d21_p3_startup_guard.py` | `ABSENT` | `1D07A38E35BFC32E7726FD4FC8EA1A3E8B171C2518CEA7EBFCA11573B9F01362` |

Lokalne zabezpieczenie pod istniejącym chronionym rootem P2:

- tracked patch `E043325F662D7A443534CC884C23B95EEA340348EA0823E348DEAB27F64EC0E3`;
- test patch `78A8394E1B5E4B80AAEED3E3B7FAFFC773112DAD33BECD62E3C2ED6EB013A4DA`;
- diagnosis summary `275D637CCD09F1CE4D59E24E2E8714AC1E1C49EC60EE690EE3032EB35DC3399B`.

## Testy i skutki

- `git diff --check`: PASS dla WIP;
- pytest/compileall/auth/`/version`/A4 API: `NOT_RUN`;
- testowy obraz R02 i zasoby: `NOT_QUERIED`, bo resource-read gate nie
  przeszedł;
- Docker inspect/SQL/normalny lifespan/uvicorn: `NOT_RUN`;
- produkcyjne start/restart/stop/move/migration/export/backup/restore: `0`;
- żaden własny proces lub testowy kontener nie pozostał.

## Następny krok

Po rzeczywistej, niezależnie potwierdzonej zmianie stanu resource reads wykonać
dozwolony exact backend inspect z deadline 20 s. Jeżeli odczyt, przypięty obraz
i bramki zasobów przejdą, uruchomić dokładnie jedną izolowaną kampanię guarda.
Bez cutoveru, P4/P5 lub R06.
