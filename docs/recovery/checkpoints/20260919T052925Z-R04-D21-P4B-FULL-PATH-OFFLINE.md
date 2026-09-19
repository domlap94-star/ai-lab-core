# R04 / D-21 / P4-B — full error path and SAFE_INACTIVE rollback

UTC: `2026-09-19T05:29:25Z`

Parent recovery HEAD: `38610e4b0fad6ceaed787b3787db824cacbdbca6`

Status: `FULL_ERROR_AND_SAFE_INACTIVE_ROLLBACK_PATH_READY_FOR_REVIEW /
OFFLINE_ONLY / NOT_INSTALLED`

## Zakres i wynik

Wykonano wyłącznie owner-authorized source/local-file/offline review. Zachowany
preimage recepty input-binding potwierdził `RV-P4B-FULL-01–04`:

1. kolizję read-only `$Host` i błędne `-Status (if (...))`;
2. możliwość destrukcyjnego rollbacku dla nieznanego stanu taska;
3. synchroniczną dolną granicę poza wspólnym deadline;
4. test tekstowy, który nie wykonywał rzeczywistego catch/finalization.

Wynikowa LOCAL_ONLY recepta domyka zamknięty katalog bounded host operations,
zachowuje pierwotny błąd przy awarii logowania i wymaga pozytywnego dowodu
SAFE_INACTIVE przed usuwaniem własnych plików. UNKNOWN, timeout, denial, obca
tożsamość lub aktywna/zakolejkowana instancja blokują destrukcyjny rollback.

## Przypięte artefakty LOCAL_ONLY

| Artefakt | Bajty | SHA-256 |
|---|---:|---|
| `invoke-p4b-resume-installer.full-path.ps1` | 77,031 | `16A35C328A091801A4713A7F282A72C7E143BE489BF847A1AEE15599F70C4DC8` |
| `test-input-bindings-full-path.ps1` | 22,518 | `36F4284FA3766D2172707C95B4B31E9FE39B9E95B8D0312C7FAD570EEBAC93F6` |
| `test-full-path-orchestration.ps1` | 18,569 | `2BAEFCF4EA4DEDA1EB337B796197C93DB737344E26C299E27D7B6B91DCBFEB3E` |
| `preimage-full-path-repro.ps1` | 2,875 | `C6A31E63EE8AEA2FB631477D312B233BDFEE4013924DBE3C9542405CAD7C7784` |
| `full-path-package-index.json` | 3,775 | `1355EF0878C31202145E4E324C40A5D07E343FB78B0C6C7D029E2E932C43E3BF` |
| review ZIP, 8 wpisów | 37,305 | `DE8483568A17E27E80F3EE1C222C9E4BAC8EC6D78BA4C4CDC6DC48E2A86CFAEC` |

ZIP przeszedł roundtrip listy wpisów i nie zawiera raw logów, danych firmy,
sekretów ani runtime payloadu.

## Wykonane testy

- Windows PowerShell `5.1.26100.8894`;
- preimage: exit `0`, wszystkie cztery uwagi `REPRODUCED`;
- input/index harness: exit `0`, 14 przypadków, 110 asercji, 29/29 ról,
  6/6 baseline, argv 7/7;
- execution harness: exit `0`, 10 przypadków, 67 asercji;
- success, pre-mutation failure, post-mutation SAFE_INACTIVE, first-warm
  failure, unsafe rollback refusal, logging failure preserving original,
  foreign task/helper/file and hanging lower boundary: PASS;
- własne workery: 9 startów / 9 rozliczonych zakończeń;
- parser finalnej recepty: PASS;
- real Docker/Task Scheduler/CIM/TCP/HTTP/UAC/host mutations: `0`.

Trzy celowe komunikaty `STAGE_WRITE_FAILED` należały do scenariusza awarii
logowania; test potwierdził zachowanie pierwotnego błędu. Zarezerwowany katalog
`execution-output\exact-full-path-attempt-1` nie powstał.

## Granica operacyjna i następny krok

Nie wykonano live preflightu, UAC, instalacji, zmian tasków, warm runów ani
rollbacku hosta. Stan hosta pozostaje historyczny: `PARTIAL_SAFE_INACTIVE`,
wrapper w rollbacku, Host disabled/no-trigger, pięć tasków na preimage,
payload/manifest nieobecne, warm runs `0/2`. Globalny manifest pozostaje
`NOT_APPROVED_FOR_START`; Supervisor pozostaje `INTENTIONALLY_STOPPED` według
obowiązującej polityki i nie był sondowany.

Jeden następny krok: owner review dokładnych bajtów recepty, indeksu i ZIP.
Każde fresh drift check, UAC lub wznowienie instalacji wymaga osobnej,
jednorazowej decyzji. STOP przed P4/B execution, P5 i R06.
