# R26 krok 2 — D-46 backend/manifest PASS, Web ACL K1

- Operation ID: `R26-STEP2-D46-20261001T193854Z`
- Entry source HEAD: `9afa840a393cc2d7b75093761017fd8644922e93`
- Product source: `67b867ee279fe0bf7617c05b7d61fff0b337cab3`
- OutputRoot: `C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-R26-STEP2-D46-20261001T193854Z`
- Status: `R26_STEP2_IN_PROGRESS / FINAL_CONSOLIDATED_K1 / D46_BACKEND_AND_MANIFEST_PASS_WEB_PATH_ACCESS_DENIED`

## Zachowany stan D-45

ValidateOnly pod Windows PowerShell 5.1 potwierdził bez ponawiania operacji:

- RecoveryPointV2 `F:\dump\20260930T162200Z`, manifest SHA-256
  `7DF3D0DD1BDB3D508A48DC670468882FFC7CB8D729D886EBCC29E1DD25F394BA`,
  schema `NEXT_STABIL_BACKUP_V2`, capture/scope `COMPLETE`, artefakty `11/11`,
  partial/tmp `0`;
- DB revision `r26_step2_20260928`, `scheduled_date` typu `date`, właściwy indeks,
  zachowane `scheduled_at` i `started_at`, unresolved backfill `0`;
- `16/16` hostowych plików backendu odpowiada product source;
- sześć kontenerów było running, PostgreSQL healthy, Qdrant/n8n ready;
- startup manifest miał dokładnie siedem znanych `FILE_HASH_MISMATCH` i żadnego
  dodatkowego błędu;
- stable/Web/Windows/Android pozostawały `1.0.2+42`, fixture i active backup `0`,
  Supervisor `0/0`.

Nie uruchomiono backupu, n8n proofu, dumpu PostgreSQL, snapshotu Qdrant,
Alembic, migracji, buildów ani kopiowania 16 plików.

## Operator i jeden UAC

LOCAL_ONLY operator miał `45734` B i SHA-256
`6FC7244474CB86582F8AD80A0DE1D9F59E78C21963B2E27D357F85FE24AB4B38`.
Parser, alias audit `0`, AST join audit `0/0` oraz pięć kontraktów procesu
natywnego przeszły. Informacyjny stderr przy exit `0`, stderr przy exit `7`,
równoległy stdout/stderr, timeout oraz dokładny wiersz Alembic z D-45 zostały
rozliczone przez osobne strumienie i jawny exit code.

Jedyny UAC D-46 uruchomił elevated PID `3104` i zakończył się exit `1`.
Drugiego UAC, retry ani alternatywnego elevation nie wykonano.

## Backend-only replacement i startup manifest — PASS

Kontrolowany `compose up -d --no-deps --force-recreate backend` użył tego samego
przypiętego image ID, bez build/pull. Zachowano mounty, porty, network/aliases,
restart policy, command/entrypoint, semantyczne labels, nazwy zmiennych i dziewięć
flag `false`. Pozostałe pięć container IDs nie zmieniło się.

- backend przed: `2e6e9e04aac2728ac84fed38078cb6e5628620525b83c848f850332b6b879e42`;
- backend po: `eae23207c36e7e9eeb623869bb68387b6d48c5be7deea3fcbb7761f246e5f44c`;
- image: `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`;
- override: `0B54ED87D926BAEF7CE7FEB3AC90D83E845D10664BDDCC3966992CFF1535F219`;
- `/version`: `1.0.2`, minimum/latest `1.0.0/1.0.2`, production,
  `debug=false`, runtime `SAFE`, source `67b867...`, schema
  `r26_step2_20260928`, release `NEXT-STABIL-R26-step2-67b867ee279fe0bf`;
- publiczne `/control`, `/control/health`, `/control/status`: `404`;
- R26 bulk revoke i inspections endpoint są obecne w live OpenAPI.

Startup manifest został atomowo związany z faktycznym backend ID, override i
wszystkimi 16 plikami R26. Ma SHA-256
`0B2AD50C46ADC43C3FA8A4122C1778114AA8349E5411935CEFAF4B11648A71BD`,
status `APPROVED_FOR_START`, walidacja `valid=true`, błędy `0`.

## Materialny K1 i stan końcowy

Pierwsza czynność fazy `STABLE_WEB` — zachowanie katalogowego preimage przez
kopię bieżącego Web — zakończyła się:

`Odmowa dostępu do ścieżki „C:\ai-lab-core\frontend\build\web”.`

Nie rozpoczęto przełączenia Web ani zapisu stable manifestu. Końcowy readback:

- stable manifest pozostał exact +42:
  `F65CC51573D583C408413CCAAAA62BBED84C9862FA8BB2109F223C48461135E5`;
- Web pozostał exact +42:
  `44A53C0BF821D31279294D017D4D12673A822AAFFBAAF301B8C90900E4A115EE`;
- Windows pozostał exact +42:
  `C0DE8E94FF2BF4280ACDC2C1FA0B65701CB3A19D3269226F6C2BDB664C134CD5`;
- Android nie był aktualizowany i pozostał +42;
- live smoke i fixture nie rozpoczęły się, więc fixture residue wynosi `0`;
- active backup `0`, Supervisor `0/0`;
- zdrowy nowy backend i ważny startup manifest zostały zachowane zgodnie z
  forward-only zasadami;
- `pending_mutation=true`, ponieważ klienci +43 i live smoke są niedokończone.

Nie wykonano destrukcyjnego rollbacku, downgrade migracji, przywrócenia starych
plików backendu ani cofnięcia zdrowego backendu/manifestu. R26 krok 2 nie jest
`READY_FOR_OWNER_REVIEW` ani `ACCEPTED`.

Canonical footer: R26 krok 1 `ACCEPTED / OWNER_CONFIRMED`; R26 krok 2
`IN_PROGRESS / FINAL_CONSOLIDATED_K1`; R25 `ACCEPTED`; R04 `IN_PROGRESS /
WSTRZYMANE`; D-22 `NOT_RUN`.
