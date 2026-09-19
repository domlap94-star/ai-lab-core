# R04 / D-21 / P4-B — rollback dependencies and pending mutations

UTC: `2026-09-19T08:25:27Z`

Parent recovery HEAD: `868339ab89b108e62bb3a9de1000f6573daee701`

Status: `ROLLBACK_DEPENDENCIES_AND_PENDING_MUTATIONS_READY_FOR_REVIEW /
OFFLINE_ONLY / NOT_INSTALLED`

## Zakres i wynik

Wykonano wyłącznie owner-authorized source/local-file/offline review. Na
zachowanym preimage recepty pełnej ścieżki odtworzono:

1. `RV-P4B-FULL-03B`: nierozliczony mutator mógł konkurować z rollbackiem i
   cleanupem zależnych plików;
2. `RV-P4B-FULL-02B`: bezczynny Host nie dowodził bezpiecznego stanu Compose
   używającego przywracanego legacy helpera;
3. `RV-P4B-FULL-02C`: rollback mógł wykonać `Register-ScheduledTask -Force`
   bez świeżej kontroli przypiętej lub operation-owned tożsamości.

Wynikowa recepta zapisuje stan mutatorów w kontekście próby. Niepewny handoff
kończy próbę jako `PARTIAL_PENDING_OPERATION_UNKNOWN` i blokuje automatyczny
retry, rollback oraz cleanup zależnych plików. Legacy helper wraca wyłącznie po
potwierdzeniu bezpiecznych konsumentów Host/Compose, a każdy rollbackowy zapis
taska ma wspólny gate tożsamości bezpośrednio przed zapisem.

## Przypięte artefakty LOCAL_ONLY

| Artefakt | Bajty | SHA-256 |
|---|---:|---|
| `invoke-p4b-resume-installer.rollback-safe.ps1` | 91,889 | `F6D3A8CC7AA57ED50244D773076700BCBE5771609762947B230E344C5C883F0E` |
| `rollback-safe-package-index.json` | 2,970 | `FDF9FE7AF55A8285FB51506E3CBFA5368F366353748DC68BBCCBBC37164A977F` |
| `test-input-bindings-rollback-safe.ps1` | 22,568 | `4753C26B1FB85CDA351A30B5E1FF1750398954D99CCA185399978894ADBC3C00` |
| `test-rollback-safe-orchestration.ps1` | 27,098 | `61C9C6FF8E083AFFAB3F2A84550ED0CC41558C800250285751F953994FEDFBEC` |
| `repro-preimage-rollback-dependencies.ps1` | 24,302 | `85D0A96DBA5A77EA8E6F9F2083EC0AC87557A044FE40EA1C9EF9E2C215B28E01` |
| review ZIP, 7 wpisów | 47,891 | `D2B3263BE6ECB20E139CF63E7559C0E53605CE8827183989E37979247965DA1C` |

ZIP przeszedł roundtrip listy wpisów i hashy; nie zawiera raw logów, danych
firmy, sekretów, 29 zewnętrznych wejść ani outputu operacyjnego.

## Wykonane testy

- Windows PowerShell `5.1.26100.8894`;
- preimage: exit `0`, `4/4` przypadki, `16` asercji, trzy uwagi `REPRODUCED`;
- input/index: exit `0`, `14/14` przypadków, `110` asercji, 29 ról, sześć
  baselines i argv `7/7`;
- orchestration/rollback: exit `0`, `15/15` przypadków, `96` asercji;
- workery: `437/437` rozliczone;
- parser czterech skryptów, JSON indeksu i ZIP roundtrip: `PASS`;
- real Docker/Task Scheduler/CIM/TCP/HTTP/UAC/mutacje produktu: `0`.

## Granica operacyjna i następny krok

Nie wykonano live preflightu, UAC, RunAs, instalacji, zmian tasków, warm runów
ani rollbacku hosta. Stan hosta pozostaje historyczny: `PARTIAL_SAFE_INACTIVE`,
wrapper w rollbacku, Host disabled/no-trigger, pięć tasków na preimage,
payload/manifest nieobecne, warm runs `0/2`. Globalny manifest pozostaje
`NOT_APPROVED_FOR_START`; Supervisor pozostaje `INTENTIONALLY_STOPPED` zgodnie
z polityką i nie był sondowany.

Jeden następny krok: niezależny review dokładnych bajtów recepty, indeksu i ZIP.
Każdy live odczyt, UAC, instalacja lub rollback wymaga nowej jednorazowej decyzji
właściciela. STOP przed P4/B execution, P5 i R06.
