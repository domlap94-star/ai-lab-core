# R04 / D-21 / P3 — current DB i rollback evidence

UTC: `2026-09-16T20:06:09Z`

## Zakres i punkt wejścia

- start local/tracking/remote: `c52f453513dc96bd750dd9e6c0a0a836f134d7e6`;
- owner-accepted guard source: `0ee0ea50943578e6e552aae23ce1688595ddc262`;
- guard tree: `4ccbc8922051401da1422be0d08f271476c3bab6`;
- status guarda: `BASE_START_GUARD_SOURCE_AND_SYNTHETIC_TESTS_ACCEPTED / NOT_DEPLOYED`;
- dozwolony zakres: ograniczony odczyt runtime, jedna sesja PostgreSQL READ ONLY,
  przegląd istniejących dowodów rollbacku i dokumentacja;
- bez startu/stopu/restartu, zmiany config/data/mount/task/flag/queue,
  backupu, restore, cutoveru, P4/P5 lub R06.

Recovery było czyste, staged `0`; oryginalny worktree zachował 203 wpisy
(`6 modified + 197 untracked`, staged `0`).

## Bieżący runtime — obserwacja odczytowa

- Docker Server `29.8.0`;
- backend full ID
  `9d9b46c530412e48562b5427a0586b08c1e919ff293ec2cbd1489faffc98615a`;
- backend image
  `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`;
- PostgreSQL full ID
  `240343ebff4fb299b239db2817efea1910ab59c29ed3ec9df3a8abde04e81226`;
- PostgreSQL image
  `sha256:a426e44bac0b759c95894d68e1a0ac03ecc20b619f498a91aae373bf06d8508d`;
- PostgreSQL bind:
  `C:\ai-lab-core\data\postgres -> /var/lib/postgresql/data`, RW;
- backend/PostgreSQL host, DB i user były zgodne bez utrwalenia wartości;
- backend health `200`, Public Gateway health `200`, public `/control` `404`;
- junction `C:\ai-lab-core\data -> D:\ai-lab-data` nie został zmieniony;
- Supervisor pozostał `INTENTIONALLY_STOPPED`.

## Jedyna sesja PostgreSQL READ ONLY

Sesja użyła `psql -X`, `ON_ERROR_STOP=1`,
`default_transaction_read_only=on`, `BEGIN READ ONLY`,
`statement_timeout=5s`, `lock_timeout=1s`, ograniczonego
`idle_in_transaction_session_timeout` i jawnego `ROLLBACK`. Exit `0`, czas
1424 ms, bez retry i bez pozostawionego procesu.

Wynik:

- PostgreSQL `17.10`, database/user `ai_lab`;
- `transaction_read_only=on`;
- revision `followup_assistant_chat_history_20260829` — zgodny z kandydatem;
- rola `Administrator`: `1`; skonfigurowany aktywny, nieusunięty admin: `1`;
- `data_directory=/var/lib/postgresql/data`, `log_directory=log`;
- `pg_wal` i `pg_tblspc` są zwykłymi katalogami pod PGDATA;
- external tablespaces: `0`; DB size: `743765683` B;
- backup active `0`, restore rows `0`, import rows `0`, KB active `0`,
  backup sync pending `0`;
- zastany pending work: document preparation `18 queued/queued`, analysis
  `16 advanced_queued`, Assistant `1 waiting/analyzing_local`.

Nie odczytywano payloadów, dokumentów, treści poczty, haseł, adresów e-mail,
wierszy użytkowników ani SQL innych sesji. Żądane zapisy danych biznesowych:
brak. Nie jest to twierdzenie o globalnym zerze technicznego I/O.

## Rollback evidence

- accepted full point: `E:\ai-lab-backup\20260908T210559Z`, manifest SHA-256
  `8F20A7845473097EE74019966583EC3F121139C4B562265F9A7391FAFAF6BE4B`,
  `9/9` artefaktów obecnych i zgodnych rozmiarem; R03-A4 ma historyczny odbiór
  restore dla dokładnego manifestu;
- latest DB point: `F:\ai-lab-system-backup\20260911T230006Z`, manifest
  `769583D1CD2CCDDA3C83786AC05B4C9E53015870C5AA23C0A0B84DEEECEB2382`,
  `1/1`, bez bieżącego restore proof;
- latest n8n point: `F:\ai-lab-system-backup\20260911T233006Z`, manifest
  `F8005856EF68F1AF88B5CD70DC19452B4DA8FDCE689371E397131081F71539AA`,
  `3/3`;
- bieżące wyniki tasków `267014/1/1` nie potwierdzają świeżej kopii po tych
  punktach; nie uruchomiono backupu, restore ani ponownego haszowania dużych
  artefaktów.

Klasyfikacja: `REVIEW_READY / DATA_FRESHNESS_OWNER_DECISION_REQUIRED`.

## Dowody lokalne

Chroniony katalog `LOCAL_ONLY`:
`C:\ai-lab-core-staging\recovery\R04_D21_P2_20260915T212340Z\active-data-junction-20260916T055951Z\p3-preparation-20260916T133633Z\current-db-read-20260916T195239Z`.

- sanitowany stdout SQL: 10 219 B, SHA-256
  `EA575FADD1537B2BFDAC813F23766E838536CA366DB361869A5DA818FA9B704E`;
- sanitowane podsumowanie: 2 936 B, SHA-256
  `F9E9F3B5D1F5CDC71683328D46AB72E88B32356AAF29ADB401E8B65669BADE07`;
- preflight: SHA-256
  `471DEC4B83F28B564C064AE359282FF6179D574504144E773A8341D20B6F643A`;
- relacja backend/PostgreSQL: SHA-256
  `87D4A83079232425B2035CB33779C83CE3B4E5B15FC83AE6E85E024894210B4`.

## Handoff

Status: `R04 D21-P3 PREPARATION_PARTIAL / CURRENT_DB_METADATA_OBSERVED_READ_ONLY /
ROLLBACK_EVIDENCE_REVIEW_READY / NO_CUTOVER`.

Testy aplikacji, Flutter, Web build, migracje i runtime smoke kandydata:
`NOT_RUN`. Produkcyjny manifest: `NOT_APPROVED_FOR_START`. Cutover, relokacja,
task install i cleanup: `NOT_RUN`. R04/R05 pozostają `IN_PROGRESS`; R03
`WAITING_APPROVAL / WAITING_ESCROW_DECISION`.

Jedyna następna decyzja właściciela: czy przyszły P3 może użyć accepted full
pointu z 2026-09-08 razem z DB/n8n z 2026-09-11 mimo nieobjętych zmian do
2026-09-16 i niezerowych wyników ostatnich tasków, czy przed cutoverem wymagany
jest nowy, zweryfikowany punkt rollbacku.
