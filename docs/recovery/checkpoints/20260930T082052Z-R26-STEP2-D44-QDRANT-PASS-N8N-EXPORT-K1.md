# R26 krok 2 — D-44 Qdrant PASS, RecoveryPointV2 zatrzymany na eksporcie n8n

- Operation ID: `R26-STEP2-D44-20260930T080137Z`
- Source HEAD: `38ea6da7e9f1f691fe756f0f6159eead23d41ad6`
- Product source: `67b867ee279fe0bf7617c05b7d61fff0b337cab3`
- OutputRoot: `C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-R26-STEP2-D44-20260930T080137Z`
- Planowany checkpoint backupu: `F:\dump\20260930T080500Z`
- Status: `R26_STEP2_IN_PROGRESS / FINAL_CONSOLIDATED_K1 / D44_RECOVERYPOINTV2_N8N_EXPORT_JSON_INVALID_NO_ARTIFACT`

## Source, testy i publikacja

Commit `38ea6da7e9f1f691fe756f0f6159eead23d41ad6` dodał strukturalny
capture HTTP Qdrant, rygorystyczną rekonsyliację operation-owned snapshotu po
HTTP 500 oraz zapis snapshotu i checksumy jako dwóch artefaktów manifestu.
Publiczny readback source i `local=tracking=remote` przeszły.

Windows PowerShell 5.1:

- HTTP/reconciliation: `56` assertions PASS;
- JSON inspect/helper diagnostics: `100` assertions PASS;
- PostgreSQL binary transport: `24` assertions PASS;
- collection selection: `7/7` PASS;
- helper contract: PASS.

LOCAL_ONLY operator miał `53710` B i SHA-256
`74ADE3221A084A05C9D093493214E9018DBCCFDF0D03C8D09EBF3F66C4D59E41`.
Alias/AST audit wykazał `20` funkcji, `60` poleceń, `0` kolizji aliasów,
`command_parameter_join_count=0` i `binary_join_operator_count=0`.
`D44_EXACT_OPERATOR_VALIDATE_ONLY_PASS` oraz rzeczywisty read-only preflight
przeszły bez mutacji.

## Jeden UAC i toolset

Jeden UAC D-44 został zaakceptowany. Podniesiony proces zakończył się kodem
`1`; drugiego UAC ani retry nie wykonano. Transakcja zachowała exact preimages,
ACL, owner i reparse state, a następnie atomowo zainstalowała:

- runner: `6CFFA1EC2CE8242EFD541B931B3E68790FD0FD36F3EC9F4871721356D6A542B6`
  -> `C1F7B3D80BBE45CB282763B7CD4018E822F09F9F8872F707B430E26BEBE05C40`;
- helper: `28B84E792C511C7EAC2BEEDAC52E013BD0A1115F239A7E4202BCFA708AAFCD06`
  -> `5E0EED95B096DFD3889782B6478167FD18BC9E4D60D36DB0BBD65B9B7851EDF6`.

Post-check parser/hash/ACL/reparse przeszedł. Zgodnie z D-44 toolset pozostaje
wdrożony po późniejszym niezależnym K1.

## Direct Qdrant proof

Direct proof przeszedł dla obu kolekcji. Każda miała dokładnie jeden POST;
oba POST-y zwróciły HTTP `500`, lecz niezależny kontrakt D-44 potwierdził po
jednym finalnym, stabilnym snapshotcie, checksumie, brak `.tmp`, lokalny hash
zgodny z Qdrant checksum, validator `valid=true`, helper ready, brak OOM/fatal,
API list `200`, helper/staging residue `0` i przywrócenie primary Qdrant.

| Kolekcja | Wynik | Bajty | Snapshot SHA-256 / Qdrant checksum | Checksum-file SHA-256 |
| --- | --- | ---: | --- | --- |
| `ai_lab_document_chunks` | `ARTIFACT_RECONCILED_AFTER_HTTP_500` | 348404224 | `eae49ff7d541cd2e0d697d54f5a44b02ab910db1f180c711f0fe7904510f11d9` | `e26225b137c0485ee16d5e0a79ffb24a643bed987a3a1d84c3d3696199bb6ec6` |
| `ai_lab_knowledge_base_chunks` | `ARTIFACT_RECONCILED_AFTER_HTTP_500` | 2449920 | `73bc88d946542f623d3ab5b52c63b2524efed42aebbdea4dc20137e45bf29bc2` | `e9304c4f90064420f546e31dcc72b70b656eb3356062da004538d161c84754e4` |

Odpowiedzi Qdrant wskazywały błąd po utworzeniu finalnego pliku: próba budowy
`SnapshotDescription` odczytywała metadata spod ścieżki nested, której Qdrant
już nie widział (`No such file or directory (os error 2)`). Jest to runtime
cause odpowiedzi 500; niezależna integralność artefaktów została potwierdzona,
więc nie oznaczono HTTP POST jako sukcesu, lecz artefakty jako reconciled.
Bounded response body, headers, status/reason, duration, exception, helper logs
i helper state zachowano w OutputRoot. Proof artefacts zostały następnie
usunięte zgodnie z decyzją.

## Pełny RecoveryPointV2 i nowy K1

Drugi i ostatni dozwolony cykl Qdrant w pełnym backupie również przeszedł dla
obu kolekcji:

| Kolekcja | Wynik | Bajty | Snapshot SHA-256 / Qdrant checksum | Checksum-file SHA-256 |
| --- | --- | ---: | --- | --- |
| `ai_lab_document_chunks` | `ARTIFACT_RECONCILED_AFTER_HTTP_500` | 348404224 | `6924c27fb759fb640909befefa2fc3723da8e354167f674c75f4b6c07e2fbe6b` | `bc9dfd5c2a9b735432d56b2a14788a105200bf71fef358be2284909ba39d020f` |
| `ai_lab_knowledge_base_chunks` | `ARTIFACT_RECONCILED_AFTER_HTTP_500` | 2449920 | `8c8b2f5fefafb7f93c17a2064813a2864295571d6f1cdd0f3a442a856ddea346` | `86a6e42e0da0bd175fb96e984b8601511a79a93750b730df35257fed0e0399f5` |

PostgreSQL dump i jego list/full-read validation oraz document-storage capture
zostały wykonane na `F:`. Backup doszedł następnie do etapu `n8n` i zakończył
się dokładnym błędem `n8n_export_json_invalid`. Finalny
`backup-manifest.json` nie powstał, więc operator usunął jednoznacznie
niekompletny checkpoint `F:\dump\20260930T080500Z`. Nie ma artefaktu backupu,
a RecoveryPointV2 nie jest PASS. Raw niepoprawny eksport n8n nie został
zachowany poza usuniętym niekompletnym checkpointem, dlatego bez nowej decyzji
nie wolno zgadywać jego treści ani uruchamiać eksportu ponownie.

## Rozliczenie skutków

- `pending_mutation=false`, `product_mutation_started=false`;
- Qdrant: ten sam ID `daa3b0b86b748aa3a52052dac08bfde499cf19ad61600a1325e09061a5451fae`,
  running/readiness `200`, restart count `0`, volume `qdrant_storage`;
- kolekcje `57/157`, indexed `0/0`, aliases `0/0`;
- helper residue `0`, staging residue `0`;
- active backup `0`, fixture `0`, Supervisor `0/0`;
- DB `r25_external_scope_20260927`, `scheduled_date` absent;
- backend/startup/Web/Windows/Android pozostają R25 / `1.0.2+42`;
- startup manifest nadal
  `A86582B48A854D963F61327F139A27160057B1004AFB1B394613D0DC28E39AE8`;
- migracja, backend/startup update, Web/Windows/Android `+43` i live smoke są
  `NOT_RUN`.

## Materialny K1 i następny krok

Jedyny materialny blocker to
`D44_RECOVERYPOINTV2_N8N_EXPORT_JSON_INVALID_NO_ARTIFACT`: produkcyjna ścieżka
backup runnera zapisuje stdout `n8n export:*` jako plik, lecz bieżący wynik nie
przechodzi `ConvertFrom-Json`; brak finalnego manifestu i artefaktu uniemożliwia
deployment produktu. Następny krok wymaga nowej decyzji na zachowanie bounded
diagnostyki eksportu n8n, ustalenie konkretnej domieszki/formatu oraz minimalny
fix i nowy pełny proof. D-44 i jej jeden UAC są skonsumowane.

Canonical footer: R26 krok 1 `ACCEPTED / OWNER_CONFIRMED`; R26 krok 2
`IN_PROGRESS / FINAL_CONSOLIDATED_K1`; R25 `ACCEPTED`; R04 `IN_PROGRESS /
WSTRZYMANE`; D-22 `NOT_RUN`.
