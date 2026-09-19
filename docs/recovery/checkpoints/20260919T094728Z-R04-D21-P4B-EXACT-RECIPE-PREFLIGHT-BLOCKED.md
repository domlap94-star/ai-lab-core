# R04 / D-21 / P4-B — exact recipe accepted, preflight blocked

UTC: `2026-09-19T09:47:28Z`

## Stan wejściowy

- branch: `recovery/next-stabil-repair-completion`
- local/tracking/remote przed pracą: `ea825a6b237999bcb3bc3b77ab4c2623a334930c`
- product launcher source: `8756314f51a76091a483cfc9b677a05c7f67f315`
- accepted backend P3 source: `0ee0ea50943578e6e552aae23ce1688595ddc262`
- original operation: `R04-D21-P4B-WINDOW-20260918T084652Z`
- external resume: `R04-D21-P4B-EXACT-RESUME-20260919T094244Z`

## Dokładny pakiet

| Element | Bajty | SHA-256 | Wynik |
|---|---:|---|---|
| `invoke-p4b-resume-installer.rollback-safe.ps1` | 91889 | `F6D3A8CC7AA57ED50244D773076700BCBE5771609762947B230E344C5C883F0E` | MATCH |
| `rollback-safe-package-index.json` | 2970 | `FDF9FE7AF55A8285FB51506E3CBFA5368F366353748DC68BBCCBBC37164A977F` | MATCH |
| review ZIP | 47891 | `D2B3263BE6ECB20E139CF63E7559C0E53605CE8827183989E37979247965DA1C` | MATCH; 7/7 wpisów |
| external `resume-input-index.json` | 10977 | `ED8826F7CFAB1A33B84C5FCF3BDA1E57FB48E9598100B3826C0CDDDCC3131CDA` | MATCH; 29/29 wejść |

Sześć wpisów package index odpowiada dokładnym bajtom. Recepta uruchomiona
zwykłym tokenem w trybie `VerifyInputsOnly` zakończyła się exit `0`; zgłosiła
29 wejść i sześć baseline records oraz zero Docker/task/HTTP/UAC/mutations.
Zarezerwowany output
`execution-output\exact-rollback-safe-attempt-1` nie istniał przed ani po tej
kontroli.

Wynik odbioru narzędzia:
`P4B EXACT_ROLLBACK_SAFE_RECIPE_ACCEPTED / SOURCE_AND_OFFLINE_SCOPE /
NOT_INSTALLED`.

## Świeży preflight

Do jednego read-only preflightu wybrano zachowany collector P4/B. Utworzono
osobny katalog dowodowy obok pakietu, bez zajęcia outputu instalatora. Collector
doszedł do pierwszego dokładnego taska (`NEXT Stabil - Docker Desktop`) i jego
eksportu, lecz zapis XML zakończył się `DirectoryNotFoundException`, ponieważ
pełna ścieżka zagnieżdżonego pliku przekroczyła praktyczny limit Windows.
Proces collector zakończył się exit `1`. Katalog preflight pozostał pusty;
bezpieczna projekcja taska nie została utrwalona.

Zgodnie z zakazem ponawiania wykonanej operacji po błędzie loggera/formatera nie
uruchomiono tego odczytu ponownie pod krótszą ścieżką. Nie rozpoczęto kolejnych
gałęzi Task Scheduler, Docker, HTTP ani zasobów. Nie wywołano UAC, `Install`,
warm runs lub rollbacku. Host mutations: `0`. Reserved execution output nadal
nie istnieje.

## Status i następny krok

`P4B PRE_UAC_BLOCKED / PREFLIGHT_EVIDENCE_NOT_PERSISTED_PATH_LENGTH /
NO_MUTATION`.

Stan hosta z wcześniejszych dowodów pozostaje historyczny. Nie potwierdzono
fresh task/container/health/resource drift gate. Globalny manifest pozostaje
`NOT_APPROVED_FOR_START`, Supervisor `INTENTIONALLY_STOPPED`, warm runs `0/2`.

Jeden następny krok: właściciel może osobno zatwierdzić jedną zastępczą,
ograniczoną kampanię read-only z wcześniej wyznaczonym krótkim katalogiem
dowodowym. Dopiero jej pełny PASS pozwoli wrócić do oddzielnej bieżącej bramki
UAC/Install. Ten checkpoint nie udziela żadnej z tych zgód.
