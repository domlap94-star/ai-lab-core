# Checkpoint R04 / D-21 / P3 — owner window and final drift check

- UTC: `2026-09-17T16:37:42Z`
- parent local/tracking/remote: `78bcf70edc7ed787b377e38461e84c1b4149a29f`
- OP_ID: `R04-D21-P3-CORE-SWITCH-20260917T141404Z`
- selected source: `0ee0ea50943578e6e552aae23ce1688595ddc262`
- payload aggregate: `7A65EDFC8E18B4B1B592A5DDEB1EBFA5C2CA85762260299157E7132AEE48B055`
- override SHA-256: `F99BABA92A72DFA366367470181AB1BF9DEC19D71ADBD2CBF1632F0B74DE4E86`
- operation plan SHA-256: `8F5691A5504FE01213C97502D20B2517FF172A641092629413FD08F64FE31E78`
- state at checkpoint: `OWNER_WINDOW_APPROVED / FINAL_DRIFT_CHECK_PASS / BEFORE_FIRST_OPERATIONAL_MUTATION`

## Bieżąca decyzja właściciela

Właściciel zatwierdził jedno przełączenie wyłącznie backendu dla dokładnego
OP_ID, source, payloadu i override wskazanych powyżej. Przyjął przerwę,
ograniczenia punktu rollbacku, `DELTA_NOT_FULLY_OBSERVED`, zastane pending
`18/16/1` oraz ryzyko legacy rollbacku. W przypadku niepowodzenia zgoda obejmuje
co najwyżej jeden opisany powrót do poprzedniego kodu/config bez restore danych.
Supervisor, migracje, relokacja danych i P4/P5 pozostają poza zgodą.

## Finalny drift check

- Recovery jest clean; local/tracking wskazują ten sam parent. `origin/main` i
  przypięty rescue są niezmienione.
- Payload: `592/592` plików, 5,061,238 B, brak missing/mismatch/extra.
- Bieżący `C:\ai-lab-core\backend`: `1473/1473` plików, 24,624,213 B,
  brak missing/mismatch/extra; brak zewnętrznego procesu używającego ścieżki.
- Backend nadal ma pełne ID `9d9b46c530412e48562b5427a0586b08c1e919ff293ec2cbd1489faffc98615a`,
  image `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`,
  `/app=C:/ai-lab-core/build/deploy-main-483f9bf8/backend`, niezmienione
  `/data`, port, sieć i restart policy. Pozostałe pięć pełnych ID jest zgodnych.
- Junction pozostaje `C:\ai-lab-core\data -> D:\ai-lab-data`; Supervisor i
  Private Gateway są nieobecne, Public Gateway pozostaje przy PID `41784`.
- PostgreSQL READ ONLY: schema oczekiwana, Administrator `1/1`, brak aktywnego
  backup/import/restore w projekcji, pending `18/16/1`; pełna delta pozostaje
  `DELTA_NOT_FULLY_OBSERVED`.
- Zasoby: Windows available 7,826,960,384 B; commit reserve 39,678,619,648 B;
  Docker/WSL available 15,823,597,568 B; swap used 0 B; D: free
  917,942,194,176 B.
- Najbliższy task NEXT Stabil jest zaplanowany na `2026-09-17T19:00:00Z`;
  żaden task nie wskazuje `C:\ai-lab-core\backend`. Nie ma kolizji z oknem.

Pierwsza mutacja instalacji nie została jeszcze wykonana w chwili zapisu tego
checkpointu. Dalszy krok to dokładnie jedna kontrolowana operacja fazy B zgodna
z planem; przy nieznanym stanie nie wolno jej automatycznie ponowić.
