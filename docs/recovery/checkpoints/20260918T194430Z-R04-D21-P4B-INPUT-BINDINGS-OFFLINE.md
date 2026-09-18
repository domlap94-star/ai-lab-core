# R04 / D-21 / P4-B — input bindings offline handoff

Checkpoint ID: `R04-20260918T194430Z-D21-P4B-INPUT-BINDINGS-OFFLINE`

UTC: `2026-09-18T19:44:30.6190658Z`

Entry HEAD: `102c65277c2143986f81109b759ff837cf23a7bc`

## Wynik

`P4B RECIPE_INPUT_BINDINGS_AND_OFFLINE_PREFLIGHT_PASS /
EXACT_PACKAGE_READY_FOR_REVIEW / NOT_INSTALLED`

Zachowana recepta `5F310C64...1FD67` odtworzyła fail-before rzeczywistego
`Assert-ContainersUnchanged`: szukała baseline pod rootem recepty i kończyła
się przed fake Docker/mutacją. Nowa LOCAL_ONLY recepta wiąże 29 ról z exact
input index po ścieżce, rozmiarze i SHA-256, parsuje sześć baseline z tych
samych zweryfikowanych buforów i przekazuje je do rzeczywistego guarda.

## Frozen LOCAL_ONLY package

- recipe: 55,623 B, SHA-256
  `733AA23F15EF9CC1E8A87F1A1B38EF523464F09160EDACF50300F00957D05B6A`;
- package index: 4,156 B, SHA-256
  `ED05FE269F89BE881474CA9B2C00D62589720FD0AE1959547D55A4032B54875C`;
- old input index: 10,977 B, SHA-256
  `ED8826F7CFAB1A33B84C5FCF3BDA1E57FB48E9598100B3826C0CDDDCC3131CDA`;
- final safe summary: 4,573 B, SHA-256
  `AA50F637E3763DC3482EA169EA5807E7E00D2CDA1C9F45BE7449107A49CE2784`.

Stara recepta, jej indeks, XML, payload, manifest, rollback wrapper, P3 override
i historyczne baseline pozostały bez zmiany bajtów. Pełne lokalne ścieżki i
surowe logi pozostają poza Git w chronionym stagingu P4/B.

## Testy

Windows PowerShell `5.1.26100.8894`, exit `0`: 14/14 przypadków, 119 asercji.
Pokrycie: fail-before; 29/29 resolver; 6/6 baseline; rzeczywisty guard z sześcioma
historycznymi fake odpowiedziami; odmowy missing/hash/size/duplicate/service/
JSON/root escape/reparse/decoy/output collision oraz ID/image/mount drift;
package/System32/Unicode CWD; exact argv 7/7; nonzero/timeout; frozen package
index. Własny timeout PID 48296 zakończony, syntetyczny junction usunięty.

Real Docker/WSL/CIM/TCP/HTTP/Task Scheduler/RunAs/UAC/SQL = `0`.
Installed-file/task/trigger/mount/data changes = `0`; warm runs = `0`; rollback
= `0`; host mutations = `0`. Future output
`execution-output\exact-resume-attempt-1` pozostaje nieutworzony.

## Stan i STOP

Instalacja pozostaje historycznie `PARTIAL_SAFE_INACTIVE`: wrapper w rollbacku,
Host disabled/no-trigger/never-run, pięć tasków na preimage, launcher/runtime/
manifest niezainstalowane, helper legacy, warm `0/2`, Supervisor
`INTENTIONALLY_STOPPED`. Tego stanu nie odczytywano na żywo w tym zakresie.

Globalny manifest pozostaje `NOT_APPROVED_FOR_START`. Następny krok: exact-byte
review recepty i package indexu. Dopiero osobna bieżąca decyzja może dopuścić
fresh bounded drift check, jeden UAC i okno operacyjne. STOP przed P4/B live,
P5 i R06.
