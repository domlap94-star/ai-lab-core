# R04 / D-21 / P4-B — replacement read-only preflight partial

UTC checkpoint: `2026-09-19T10:52:24Z`

## Przypięcia

- entry HEAD: `94f81f952a12de437fc8b6480953793260b81927`
- branch: `recovery/next-stabil-repair-completion`
- campaign: `R04-D21-P4B-PF01-20260919T104840Z`
- exact recipe: `F6D3A8CC7AA57ED50244D773076700BCBE5771609762947B230E344C5C883F0E`
- exact package index: `FDF9FE7AF55A8285FB51506E3CBFA5368F366353748DC68BBCCBBC37164A977F`
- evidence root: `C:\ai-lab-core-staging\recovery\P4B-PF-01` (`LOCAL_ONLY`)

## Krótka ścieżka i I/O

Root nie istniał przed kampanią, nie jest reparse pointem i nie otrzymał
dodatkowego principalu `Allow` względem rodzica. Dwa lokalne błędy wzorca
parsera ścieżki recepty wystąpiły przed probe i przed odczytami systemowymi;
root pozostał wtedy pusty. Poprawiony wzorzec został najpierw potwierdzony w
pamięci, a dopiero potem wykonano właściwy probe.

- UTF-8 XML roundtrip: `PASS`;
- UTF-8 JSON temp-to-rename roundtrip: `PASS`;
- pliki próbne usunięte po dokładnych ścieżkach;
- najdłuższa planowana ścieżka: `90`, budżet `220`;
- recipe package root / reserved execution root / event path: `205/252/275`;
- reserved execution output: `ABSENT`;
- installer output write compatibility: `NOT_VERIFIED_NO_IO_PERFORMED`.

Meta SHA-256: `E59271A8BB46F49D021D1EACECFFCC9002B30D20C3AEBF5276468808B6336109`.
I/O SHA-256: `32AC16C3A4B730C4C1CD574A35279BF68A78F3E29B040CC31C507F0EA2FA55C7`.
Map SHA-256: `E16E2ED2316D9F175476C21D64265F4D1A4513C0A886691C05D6F0360F51D99D`.

## Jednokrotny odczyt host/task

Collector działał w osobnym procesie `78188`, zakończył się po `4550 ms`,
`exit 1`, bez timeoutu i bez pozostawienia własnego procesu. Utrwalono sześć
XML-i tasków. Pięć dokładnych tasków ma surowe hashe identyczne z preimage:

| Task | SHA-256 |
|---|---|
| Docker Desktop | `A09342576E3FADE1439D67429535ED609868D749C0458C450D43FA090586FBAA` |
| Docker Compose | `7A5E6BDF2E8214B8DF8395A0BE9CA8733A70CDFD90C5EE89ED38CF697282B97D` |
| Public Gateway | `0CAFE89B7236BF81EA061F66C60B7308DB2B36A7189360B313BF8DFC28335494` |
| Private Gateway | `0409BC50A4DA30ADF461D00B8D47700C1DF29C729AFA2B7EB548F0438D5184BC` |
| Supervisor | `BE930B183EA61C61E1BF625997B40F7570A4D84FB1B320AEB0B809B463C77238` |

Host XML SHA-256 to
`0EBD4DA250ADB2D033FCACF04B8ED41166FAA5DFF76A83C4C61A6C0120CDB702`.
Statyczna semantyka odpowiada disabled/no-trigger, InteractiveToken,
LeastPrivilege, IgnoreNew, PT15M i dokładnej akcji po normalizacji `domai` do
przypiętego SID oraz pominiętego w eksporcie `RunLevel` do domyślnego
`LeastPrivilege`. Dynamiczny stan i `LastRunTime` nie zostały zapisane.

Collector przerwał budowę projekcji na
`HOST_TRIGGER_CIMCLASS_PROPERTY_NOT_FOUND`. Nie wykonano ponownego odczytu.
`h.err` SHA-256:
`0EFE271DA14787344C928C6E11F3ACB0DFF55D3335DEFF9DC673280AFF45D42B`.

## Lokalne kontrole i zakres niewykonany

- Startup wrapper: `ABSENT`;
- rollback wrapper: `PRESENT`, hash zgodny;
- launcher/runtime/manifest: `ABSENT`;
- legacy helper:
  `445AFFC04CF916602A30FDC9BBE0C8557E31AC670E8C5D389636BAB11E6DECC5`;
- P3 override:
  `F99BABA92A72DFA366367470181AB1BF9DEC19D71ADBD2CBF1632F0B74DE4E86`;
- reserved execution output: `ABSENT`.

Z powodu nieutrwalonej projekcji dynamicznej zatrzymano kampanię. Nie wykonano
pozostałych gałęzi host/resources, Docker ani HTTP. Nie wykonano UAC, Install,
warm runs, rollbacku, zmian tasków/triggerów, mutacji instalacji ani danych
biznesowych.

Result SHA-256:
`58B876CFA386B11D868FDA1D569A6E6F6ABE291CC39CCB4D0509DE615FA73B8A`.
Index SHA-256:
`40A9DA4636B40FBF9F0CB3E4FB99E26EF509B6E2D28E48A18E24709DFA1C1A02`.

## Status i STOP

`P4B REPLACEMENT_READ_ONLY_PREFLIGHT_PARTIAL /
HOST_TASK_FORMATTER_CIMCLASS_FAILURE / CURRENT_TASK_XML_AND_LOCAL_FILE_EVIDENCE /
NO_UAC / NOT_INSTALLED`.

Exact recipe pozostaje zaakceptowana wyłącznie w zakresie source/offline.
Globalny manifest pozostaje `NOT_APPROVED_FOR_START`, Supervisor
`INTENTIONALLY_STOPPED`, warm runs `0/2`. Następny live preflight wymaga nowej
decyzji po review minimalnej poprawki read-only projekcji triggera. Ten
checkpoint nie zezwala na UAC, Install, aktywację, warm run ani rollback.
