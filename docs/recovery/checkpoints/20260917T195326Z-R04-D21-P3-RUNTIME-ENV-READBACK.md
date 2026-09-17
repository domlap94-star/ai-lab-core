# R04 / D-21 / P3 — runtime environment readback

## Status

`P3 BACKEND_STARTUP_ENVIRONMENT_READBACK_PASS / CURRENT_READ_ONLY_EVIDENCE`

`CORE_BACKEND_SOURCE_SWITCH_READY_FOR_REVIEW / LIMITED_RUNTIME_VERIFIED`

Nie jest to `ACCEPTED`, ponowienie przełączenia ani zgoda na dalszą mutację
runtime. Globalny manifest zwykłego startu pozostaje
`NOT_APPROVED_FOR_START`.

## Tożsamość i okno

- dokumentacyjny parent: `d792eb3886cacfeb80aa08d8cf03b872319d4b8b`;
- OP_ID: `R04-D21-P3-CORE-SWITCH-20260917T141404Z`;
- source: `0ee0ea50943578e6e552aae23ce1688595ddc262`;
- backend ID: `686ac37663ad369f253eb91da4364aa2bd6c16c77b1205cc41d61c68d4d9c854`;
- image: `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`;
- `/app=C:/ai-lab-core/backend:ro`, `/data=C:/ai-lab-core/data:rw`;
- `StartedAt=2026-09-17T16:41:59.852578882Z`, `RestartCount=0` przed i po;
- okno UTC: `2026-09-17T19:53:26.3159410Z–2026-09-17T19:53:27.4036434Z`;
- ta sama instancja przez całe okno: `true`.

## Dwie niezależne warstwy wejść

| Klucz | Config.Env | istniejący proces backendu | Wynik |
|---|---:|---:|---|
| `SOURCE_REVISION` | `0ee0ea50943578e6e552aae23ce1688595ddc262` | `0ee0ea50943578e6e552aae23ce1688595ddc262` | MATCH |
| `DATABASE_SCHEMA_REVISION` | `followup_assistant_chat_history_20260829` | `followup_assistant_chat_history_20260829` | MATCH |
| `DATABASE_STARTUP_SEED_ENABLED` | `false` | `false` | MATCH |
| `BACKUP_PLAN_RECONCILER_ENABLED` | `false` | `false` | MATCH |
| `VISION_AUTOMATION_ENABLED` | `false` | `false` | MATCH |
| `VISUAL_V2_ENABLED` | `false` | `false` | MATCH |
| `ADVANCED_ANALYSIS_ENABLED` | `false` | `false` | MATCH |
| `KNOWLEDGE_BASE_PROCESSING_ENABLED` | `false` | `false` | MATCH |
| `KNOWLEDGE_BASE_VECTOR_WRITES_ENABLED` | `false` | `false` | MATCH |
| `DOCUMENT_PREPARATION_ENABLED` | `false` | `false` | MATCH |
| `ASSISTANT_PIPELINE_V2_ENABLED` | `false` | `false` | MATCH |

Podsumowanie: `CONTAINER_ENV_OBSERVED 11/11 MATCH`,
`BACKEND_PROCESS_ENV_OBSERVED 11/11 MATCH`, `9/9` przełączników ma wartość
`false`. Proces backendu został jednoznacznie dopasowany jako PID 1 do
udokumentowanego exec-form uruchomienia.

Jedyny proces kontrolny użył istniejącego `python -I -S -B`, standardowej
biblioteki i bezpiecznej projekcji allowlisty z `/proc/1/environ`. Zakończył
się `exit 0`; nie importował aplikacji, nie zapisywał plików i nie wykonywał
połączeń.

## Bieżąca gotowość

| GET | HTTP | Bezpieczny wynik |
|---|---:|---|
| `http://127.0.0.1:8000/health` | 200 | backend odpowiada |
| `http://127.0.0.1:8000/version` | 200 | source i schema zgodne |
| `http://127.0.0.1:8789/gateway-health` | 200 | Public Gateway odpowiada |
| `http://127.0.0.1:8789/control` | 404 | publiczna granica zachowana |

## Dowód i skutki

Bezpieczna projekcja LOCAL_ONLY:

`C:\ai-lab-core-staging\recovery\R04_D21_P2_20260915T212340Z\p3-core-switch-20260917T141404Z\runtime-readback-20260917T195326Z\runtime-environment-readback.safe.json`

- rozmiar: `5 249 B`;
- SHA-256: `126E78F1A9009DDA463C9C7C517BDB25AB4769015DB75CD6C55ED982A5B4E1F3`;
- nie zawiera pełnego env, sekretów ani danych firmy.

Rzeczywiste skutki tej sesji: dwa celowane inspecty, jeden krótki `docker
exec` i cztery bezpieczne GET. Start/stop/restart usług, recreate, zapis
runtime, SQL, rollback, Supervisor i mutacje danych: `0`.

## Ograniczenia i następny krok

To dowód bieżących wejść środowiskowych uruchomionego procesu powiązany z
przypiętym `config.py` i wcześniejszym porównaniem bajtów `592/592`. Nie jest
bezpośrednim odczytem obiektu Settings w pamięci, nie dowodzi każdego
historycznego cyklu dispatchera ani globalnego braku wcześniejszych zapisów.
Historyczny handoff fazy B prawidłowo pozostaje opisany jako bez zachowanego
readbacku w swoim pierwotnym oknie.

Następny krok: właścicielski review ograniczonego wyniku switch wraz z tym
readbackiem. P4/P5 i każda kolejna mutacja runtime wymagają osobnej zgody.
