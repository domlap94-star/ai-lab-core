# R26 krok 2 — D-45 n8n/RecoveryPointV2 PASS, częściowy deployment produktu

- Operation ID: `R26-STEP2-D45-20260930T162000Z`
- N8n runner source: `02502854d93a4cd773febb27a995f2f52ce65ceb`
- Product source: `67b867ee279fe0bf7617c05b7d61fff0b337cab3`
- OutputRoot: `C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-R26-STEP2-D45-20260930T162000Z`
- N8n proof checkpoint: `F:\dump\20260930T162100Z` — validated, then removed
- Full backup checkpoint: `F:\dump\20260930T162200Z` — retained, validated
- Status: `R26_STEP2_IN_PROGRESS / FINAL_CONSOLIDATED_K1 / D45_BACKUP_PASS_MIGRATION_APPLIED_PRODUCT_DEPLOYMENT_PARTIAL_ALEMBIC_STDERR`

## Source, testy i publikacja

Potwierdzona przyczyna D-44 była zgodna z source n8n 2.31.6: bez `--output`
eksport przechodzi przez logger, więc stdout nie jest kanonicznym plikiem JSON.
Source `02502854d93a4cd773febb27a995f2f52ce65ceb` używa dla workflow i
credentials dokładnie jednego argumentu `--output=/tmp/next-stabil-...json`,
nie używa `--decrypted`, zachowuje stdout/stderr wyłącznie jako bounded
diagnostykę, kopiuje plik do hostowego `.partial`, waliduje JSON i semantykę,
oblicza hash i dopiero wtedy atomowo promuje artefakt.

Windows PowerShell 5.1:

- n8n file-output contract: `72` assertions PASS;
- Qdrant HTTP/reconciliation: `56` assertions PASS;
- Qdrant JSON inspect/helper diagnostics: `100` assertions PASS;
- PostgreSQL binary transport: `24` assertions PASS;
- collection selection: `7/7` PASS;
- helper contract: PASS.

Secret/business-content scan, `git diff --check`, publiczny push i zdalny
readback source przeszły. Source runnera ma SHA-256
`866AA9B7E18AB20022405C3D7D9318F04EDFB566AD1ED15A66F6D0F45C2E9406`.

LOCAL_ONLY operator ma `58896` B i SHA-256
`62F5A1C7C8AE9B4EC607217CEC655D7D4AEF2C65F401B2F7FCA8C3649A4DDC92`.
Alias/AST audit: `22` funkcje, `62` polecenia, `0` kolizji, oba liczniki
niepoprawnego `-join` równe `0`. `D45_EXACT_OPERATOR_VALIDATE_ONLY_PASS` oraz
actual read-only preflight przeszły. Dokładne bajty operatora zachowano w
OutputRoot.

## Jeden UAC i runner-only update

Jedyny UAC D-45 uruchomił elevated PID `3848`; proces zakończył się exit `1`
na późniejszym K1. Drugiego UAC, retry ani alternatywnego elevation nie użyto.

Runner został atomowo zmieniony:

- przed: `C1F7B3D80BBE45CB282763B7CD4018E822F09F9F8872F707B430E26BEBE05C40`;
- po: `866AA9B7E18AB20022405C3D7D9318F04EDFB566AD1ED15A66F6D0F45C2E9406`.

Preimage, bytes, ACL, owner i reparse state zostały zachowane. Parser, exact
hash, ACL/owner/reparse i brak staging residue przeszły. Qdrant helper nie był
kopiowany i pozostał exact
`5E0EED95B096DFD3889782B6478167FD18BC9E4D60D36DB0BBD65B9B7851EDF6`.

## N8n-only proof

Proof przez exact installed runner, `Scope=n8n_config` i `LegacyV1` przeszedł:

| Artefakt | Exit | Count | Bajty | SHA-256 |
| --- | ---: | ---: | ---: | --- |
| workflow | 0 | 4 | 106047 | `66e92464d613ecf929a9f79515d58f2902f796cbe0a8ca01bf6dfd5f951ef716` |
| credentials | 0 | 4 | 4612 | `0f8b9362efe0f3555b4caab8eaf360d2807bc680f1bb34a11f5e21216a477d27` |

Credentials miały `credential_data_encrypted=true`; workflow i credential ID
list hashes zachowano bez ujawniania ID/nazw/treści. Manifest proof miał
SHA-256 `6EB9AD99397C1E2C2E4E6759A2C71F790FFC03EE83AA4041C2C2E7DD839F8ED4`.
Oba exact `/tmp` są absent, brak operation-owned wpisów w active data root,
n8n zachował ID
`a44e719ecfecf72a199b4f8b3ec9d7503548d2098601e767d5e9e6503d37081c`,
restart `0`, wersję `2.31.6` i readiness `200`. Po pełnej walidacji usunięto
wyłącznie operation-owned proof checkpoint i potwierdzono jego brak.

## Pełny RecoveryPointV2

Checkpoint `F:\dump\20260930T162200Z` jest kompletny. Manifest:

- SHA-256: `7DF3D0DD1BDB3D508A48DC670468882FFC7CB8D729D886EBCC29E1DD25F394BA`;
- schema `NEXT_STABIL_BACKUP_V2`;
- capture/scope `COMPLETE`;
- artifact hash verified `true`;
- `11/11` artefaktów ma zgodne rozmiary i SHA-256;
- partial/tmp: `0`.

PostgreSQL: `pg_dump exit=0`, stderr pusty, `490291084` B, SHA-256
`fde74afae6168759feb33c90a8a32f723d8a3a94c7381e904504cc50a5cacbfc`,
`pg_restore --list` exit `0`, pełny read do `/dev/null` exit `0`.

Qdrant zachował primary ID
`daa3b0b86b748aa3a52052dac08bfde499cf19ad61600a1325e09061a5451fae`,
readiness `200`, restart `0`, kolekcje `57/157`, aliases `0/0`, helper i staging
residue `0`. Snapshoty:

| Kolekcja | Bajty | Snapshot SHA-256 / Qdrant checksum | Checksum-file SHA-256 |
| --- | ---: | --- | --- |
| `ai_lab_document_chunks` | 348404224 | `80d1ec9dbda747f746923571c03be4b1a41d36c6ff17f02fa11be60fededcc52` | `6b2d5047614d9aa709f479439f608157281621fe3a1ef7fc5987660b8e10a769` |
| `ai_lab_knowledge_base_chunks` | 2449920 | `3eba3087a8a1cdcdc24c5a72e7df0b290233d8cbca0a57656e994087d55721e5` | `d9981da5f9168dabcd033a140d668ee00acc8dbcb77b044c3ff299b0fd2a6d28` |

Finalny manifest zawiera oba n8n artefakty z tymi samymi hashami co proof.
Duże artefakty powstały na `F:`; active backup po operacji wynosi `0`.

## Nowy materialny K1 i rzeczywisty stan skutków

Po backup PASS operator rozpoczął fazę produktu, zachował startup/stable
preimages i podmienił 16 hostowych plików backendu na exact product source.
Następnie wykonał `alembic upgrade head`. PowerShell z
`$ErrorActionPreference=Stop` potraktował pierwszy informacyjny wiersz stderr

`INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.`

jako terminating `NativeCommandError`, zanim wrapper mógł ocenić faktyczny
exit code. Bounded readback wykazał, że migracja rzeczywiście zakończyła się:

- DB revision `r26_step2_20260928`;
- `scheduled_date` istnieje jako addytywna kolumna;
- 16/16 hostowych plików backendu odpowiada source;
- backend container ID pozostał
  `2e6e9e04aac2728ac84fed38078cb6e5628620525b83c848f850332b6b879e42`;
- backend `/health=200`, publiczne `/control=404`;
- live `/version` nadal raportuje R25 source/schema, ponieważ backend nie został
  zastąpiony;
- startup/stable/Web/Windows/Android pozostają exact +42 preimage;
- live smoke R26S2 i fixture nie zostały uruchomione; końcowe fixture residue `0`;
- active backup `0`, Supervisor `0/0`, Qdrant/n8n ready i bez residue.

Startup manifest nadal ma hash
`A86582B48A854D963F61327F139A27160057B1004AFB1B394613D0DC28E39AE8` i status
`APPROVED_FOR_START`, lecz bounded walidacja zwraca siedem
`FILE_HASH_MISMATCH` dla podmienionych hostowych plików backendu. Oznacza to
rozliczony, częściowy deployment z `pending_mutation=true`; nie wolno ogłaszać
runtime +43 ani uruchamiać Host jako ścieżki naprawy.

Zgodnie z D-45 po nowym materialnym K1 nie wykonano poprawki operatora, retry,
drugiego UAC, backend replacement, manifest update ani klientów +43. Następne
wykonanie wymaga nowej decyzji obejmującej dokładnie rozliczony forward-only
resume z obecnego DB/host-file state; nie może ponawiać backupu ani migracji.

Canonical footer: R26 krok 1 `ACCEPTED / OWNER_CONFIRMED`; R26 krok 2
`IN_PROGRESS / FINAL_CONSOLIDATED_K1`; R25 `ACCEPTED`; R04 `IN_PROGRESS /
WSTRZYMANE`; D-22 `NOT_RUN`.
