# R04 / D-21 / P4-B — NUP-03 Host completion (SOURCE/OFFLINE)

UTC evidence window: `2026-09-21T06:14:10Z`
Scope: `SOURCE / LOCAL FILE READ / OFFLINE TEST ONLY`
Runtime effect: `NONE`
Status: `D23_MATERIAL_IMPACT_RULE_RECORDED / NUP03_HOST_COMPLETION_SOURCE_FIX_READY_FOR_VERIFICATION / OFFLINE_PASS / NOT_DEPLOYED`

## Preserved state and chronology

- Repository entry HEAD: `0293adde13c415358f92a07ea35f33c4c8936a41`.
- Recorder source remains `d3435afcfb89d02d91f2db3d1eb55be17fd790bd`.
- D-23 review `2/2` is complete. NUP-01 and NUP-02 remain PASS in the reviewed
  scope; the owner authorized completion of the sole remaining material K1 in
  NUP-03. The counter was not reset.
- Installed run01 was not read or changed: historical Host `Disabled/no-trigger`,
  warm `0/2`, Supervisor `INTENTIONALLY_STOPPED`. D-22 remains `NOT_RUN`.

## K1 evidence and minimal change

Fail-before on exact recipe preimage
`0B051C2F54125E25ED6DDEDEDC63A33A738604B8AAECE713B13C473FA83FB9EF`
reproduced `first_warm_status=SUCCESS` while the exact Host model remained
`Running` with one active instance. The second required warm step was then
blocked (`WARM_RUN_FAILED:2:START_FAILED`).

The derivative changes only `Invoke-P4BWarmAttempt` and its LOCAL_ONLY harness.
After all existing evidence checks pass, a fresh bounded observation must prove
the expected Host semantic hash and zero running/queued instances. Running or
Queued continues inside the same deadline; Unknown, foreign or deadline expiry
remains incomplete and cannot authorize the second warm start or logon.

## Offline verification

- Windows PowerShell `5.1.26100.8894` parser: `0` errors for recipe, harness and
  unchanged recorder.
- Actual recipe + unchanged recorder + lower leaf fakes: `70` assertions / `20`
  scenarios, exit `0`.
- Successful order: Host starts `2`, each `Running -> Queued -> Ready`; Private
  starts `1 -> 0`; container/Supervisor/five dependency-task writes `0`.
- Never-idle, immediate-idle, unknown/foreign Host and existing evidence/rollback
  negatives passed. Owned processes `1`, unsettled `0`.
- Production Docker/Task Scheduler/CIM/TCP/HTTP/WSL/UAC/Host boundaries: `0`.
- JSON/CSV/XML, exact payload hashes, review-index binding, secret scan and ZIP
  roundtrip: PASS; `34/34` ZIP files, `0` mismatches.

## Exact LOCAL_ONLY package

- Recipe: `59 194 B`, SHA-256
  `DC1295C3A82943C938521C404CD1F23302C4252FFDF25DB189A602BA14BC4A0A`.
- Unchanged recorder: `17 192 B`, SHA-256
  `D21A3E6B5D49E68711C5584138C47C2201B861A80DD4A4F89F173DC57217452A`.
- Package index: `7 283 B`, SHA-256
  `B3B50FD3AE711EF817640B6E7B89A8A30B003A36C8708760C3720F9E84607919`.
- Review index: `14 594 B`, SHA-256
  `FB46215644B2960E68F49C27438B61F5ADF1A98B1B6E307617E697F4A3B063BE`.
- Review ZIP: `125 383 B`, SHA-256
  `3ED49CB38370F8044DE76E596957CF07BAB92912ABB5BAFA37B6C3818BEFA09D`.
- Path:
  `C:\Users\domai\AppData\Local\Temp\R04-D21-P4B-HOST22-NUP03-END-REVIEW-20260921T061410Z.zip`.
- Launcher/runtime payload, proposed manifest and all Host XML bytes are unchanged.

## Decision boundary and next step

The new recipe is not self-accepted and conveys no operational approval. The
only next step is independent verification of this Host-completion diff and its
direct regressions. At PASS, recommend package acceptance; do not open another
K2/K3 search. No live preflight, UAC, installation, Host retry, task write,
rollback, P5, R06 or D-22 execution is authorized.

> **ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT**
>
> Przed oceną i kolejnym promptem przeczytaj §0, `ANTI_EXCESSIVE_WORK`, aktywną
> kartę i ten checkpoint na pełnym SHA raportu. Zachowaj odbiory. Naprawiać tylko
> wykazany istotny wpływ; K2/K3 nie ruszać, nie blokować nimi odbioru i nie
> tworzyć automatycznych zadań naprawczych.
>
> K0/K1: `NUP03_HOST_SETTLED_COMPLETION` — preimage oznaczał warm SUCCESS przy
> nadal Running Host; dowód i skutek opisano wyżej. Nowe bajty mają OFFLINE PASS,
> lecz czekają na weryfikację diffu.
>
> Efekt: dwa warm runs i logon nie wyprzedzają zakończenia właściwego Host.
> Cykl: review `2/2` zakończony; właścicielsko zatwierdzone domknięcie NUP-03,
> licznik niezerowany. Następny krok: tylko weryfikacja tego uzupełnienia i odbiór
> przy PASS; brak zgody na operacje hosta.
