# R04 / D-21 / P4-B — input binding evidence

Status: `RECIPE_INPUT_BINDINGS_AND_OFFLINE_PREFLIGHT_PASS /
EXACT_PACKAGE_READY_FOR_REVIEW / NOT_INSTALLED`

Package ID: `R04-D21-P4B-INPUT-BINDINGS-20260918T192258Z`

Entry HEAD: `102c65277c2143986f81109b759ff837cf23a7bc`

Original OP_ID: `R04-D21-P4B-WINDOW-20260918T084652Z`

## Zakres i skutek

Była to praca `SOURCE / LOCAL FILE READ / OFFLINE TEST ONLY`. Nie wykonano
Docker/WSL/CIM/TCP/HTTP/Task Scheduler/RunAs/UAC/SQL, instalacji, warm runu ani
rollbacku. Stan hosta (`PARTIAL_SAFE_INACTIVE`, warm `0/2`) pochodzi z
poprzedniego checkpointu i nie był odczytywany na nowo.

Stara recepta 45,009 B, SHA-256
`5F310C64DFB21F55B4403E9A738B80344EB9CEC38536EE4FD2081F6422F1FD67`
została zachowana bez zmiany. Minimalny fail-before wywołał jej rzeczywiste
`Assert-ContainersUnchanged`: funkcja szukała pierwszego baseline pod rootem
recepty, zgłosiła brak pliku i wykonała 0 fake Docker calls oraz 0 mutacji.

## Oczyszczony diff wykonawczy

Istotna zmiana jest ograniczona do resolvera i jego wywołań:

```diff
- $baselineRecord = Get-Content (Join-Path $resumeRoot "docker-container-$service-pass2-command.json")
- $baseline = $baselineRecord.stdout | ConvertFrom-Json
- $live = Get-LiveContainerProjection -Service $service -ContainerId $baseline.id
+ $resolvedInputs = Assert-InputIndex
+ $entry = $resolvedInputs.baselines[$service]
+ $baseline = $entry.baseline       # parsed from the already hashed byte buffer
+ $live = & $ContainerProjectionReader $service ([string]$baseline.id)
```

`Resolve-InstallerInputs`:

1. odczytuje i hashuje przypięty input index;
2. wymaga dokładnie 29 unikalnych ról;
3. dla każdej roli rozstrzyga exact path, odczytuje bufor raz i sprawdza
   `bytes` oraz SHA-256;
4. dla sześciu `resume_container_*` wymaga exact service, filename, direct
   child zatwierdzonego input rootu, bez reparse/root escape;
5. parsuje baseline z tego samego zweryfikowanego bufora;
6. przekazuje jeden obiekt `$resolvedInputs` do preflightu, dwóch warm-run
   guardów i guarda końcowego.

Wszystkie XML, payload, manifest, rollback wrapper i P3 override są pobierane
przez `Get-ResolvedInputPath` według istniejącej roli indeksu. Output ma osobny,
exact i exclusive root; `VerifyInputsOnly` kończy się przed tokenem, Dockerem,
taskami, HTTP i mutacją.

## Sześć baseline

| Service | Indexed role | Bytes | SHA-256 | Wynik |
|---|---|---:|---|---|
| backend | `resume_container_backend` | 1420 | `55C4250C34C89C8545C2DF3F29C9A9D5673BBB065BEF48CB26EC6FE904DEAF2F` | indexed path = read path, PASS |
| postgres | `resume_container_postgres` | 1358 | `2BFBBB37FD1FB5E02B4786CDC10E107766629FB578DE90958CFFE8F8498E3289` | indexed path = read path, PASS |
| qdrant | `resume_container_qdrant` | 1494 | `3534EB5AA13CD7F40547AA24E66673B27713AFFAD305740F6AFE2B013E871C55` | indexed path = read path, PASS |
| n8n | `resume_container_n8n` | 1342 | `B25B289BB1EAECD67CCE57B187E0437794B5C938BD0D91DADE6F57E179797055` | indexed path = read path, PASS |
| open-webui | `resume_container_open-webui` | 1377 | `EF5E3CF0F922FC9F7ABD244BF7F7D2C4927739E9BCD4D5BCBAAC139FD8971677` | indexed path = read path, PASS |
| ollama | `resume_container_ollama` | 1342 | `39551CA0F6DC8EC1F0642D818EBF6F569EA0E6BCED826CB69CD2240D1D5EF78E` | indexed path = read path, PASS |

Pełne ścieżki pozostają w chronionym indeksie LOCAL_ONLY. Każda wskazuje plik
pod `r04-d21-p4b-resume-20260918t112015z`; żaden baseline nie został skopiowany
obok nowej recepty.

## Frozen package

| Artefakt LOCAL_ONLY | Bytes | SHA-256 |
|---|---:|---|
| `invoke-p4b-resume-installer.input-bound.ps1` | 55623 | `733AA23F15EF9CC1E8A87F1A1B38EF523464F09160EDACF50300F00957D05B6A` |
| `input-binding-package-index.json` | 4156 | `ED05FE269F89BE881474CA9B2C00D62589720FD0AE1959547D55A4032B54875C` |
| `test-input-bindings-offline.ps1` | 21793 | `6864765550C368FBDF28B27C7C82668512065B51D3EFDDE55C692DA2FD6CFBD7` |
| final safe summary | 4573 | `AA50F637E3763DC3482EA169EA5807E7E00D2CDA1C9F45BE7449107A49CE2784` |

Input index pozostał 10,977 B, SHA-256
`ED8826F7CFAB1A33B84C5FCF3BDA1E57FB48E9598100B3826C0CDDDCC3131CDA`.
Stary transport recipe index pozostał `43F285C2...A2A9`.

Przyszłe wywołanie jest jawne, lecz `NOT_EXECUTED`; z dowolnego CWD:

```text
Windows PowerShell 5.1 -File <exact recipe> -Mode Install -ExecutionOutputRoot <reserved exact root> -ExternalResumeId <new owner-approved external ID>
```

Nadanie external ID nie zmienia bajtów recepty. Install wymaga canonical recipe
path, owner SID i elevation; `VerifyInputsOnly` nie może przejść do tych skutków.

## Końcowa kampania offline

Polecenie finalne zakończyło się exit `0` na Windows PowerShell
`5.1.26100.8894`: 14/14 przypadków i 119 asercji. Pokrycie obejmowało:

- real old-guard fail-before;
- resolver 29/29 i sześć actual baseline paths;
- rzeczywisty `Assert-ContainersUnchanged` z sześcioma historycznymi fake
  odpowiedziami oraz odmowy ID/image/mount drift;
- missing/hash/size/duplicate role/wrong service/bad JSON/index mismatch/root
  escape/reparse/decoy basename/output collision;
- identyczne bindingi z package CWD, `C:\Windows\System32` i byte-identical
  copy path ze spacją/Unicode;
- finalny bounded runner: exact argv 7/7, nonzero i timeout; własny timeout PID
  48296 został zakończony;
- zachowanie kolejności, brak drugiego move/create i tylko dwa planowane warm
  run calls w kodzie, bez ich wykonania;
- frozen package index entries zgodne po rozmiarze i SHA-256.

Zsyntetyzowany junction został usunięty. Future output
`execution-output\exact-resume-attempt-1` pozostaje nieutworzony. Wynik nie jest
fresh runtime drift checkiem i nie potwierdza bieżącego stanu sześciu usług.

## Następny krok i STOP

Następny krok to review dokładnej LOCAL_ONLY recepty i package indexu. Dopiero
osobna, bieżąca decyzja może dopuścić fresh bounded drift check, jeden UAC i
okno operacyjne. Globalny manifest pozostaje `NOT_APPROVED_FOR_START`; P4/B nie
jest `ACCEPTED` ani `COMPLETE`.
