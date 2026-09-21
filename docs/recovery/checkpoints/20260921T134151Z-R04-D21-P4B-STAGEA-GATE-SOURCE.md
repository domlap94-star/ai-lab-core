# R04 / D-21 / P4-B — P4B-STAGEA-GATE source/offline handoff

UTC: `2026-09-21T13:41:51.4974567Z`

Status: `P4B_STAGEA_GATE_NORMALIZATION_SOURCE_READY_FOR_REVIEW / OFFLINE_TESTS_PASS / NOT_DEPLOYED / STAGE_B_BLOCKED_NOT_AUTHORIZED`

## Preserved state

- Evidence base: `17b81b5f46850ebf585c40724ab457a52cfce5c4`.
- Source commit: `e8ad5e27bc8515e6536b5fc8696608b3d9c6e7de`.
- D-23 review remains `2/2`; Host22 and NUP-01/02/03 limited acceptances are preserved.
- Installed run01 is unchanged: historical launcher/runtime/helper/manifest bytes remain installed, Host is `Disabled/no-trigger`, warm runs `0/2`, Private starts `0`, Supervisor `INTENTIONALLY_STOPPED`.
- The historical Stage-A VerifyOnly still has exit `22`; this checkpoint does not relabel it PASS.

## One authorized four-task capture

Exactly one non-elevated read-only capture ran for Docker Desktop, Public
Gateway, Private Gateway and Supervisor during
`2026-09-21T13:17:28.4962441Z`–`2026-09-21T13:17:32.5441094Z`.

- `4/4 OBSERVED`, `4/4 NORMALIZED_MATCH`, workers `4/4` accounted;
- safe result: `9994` B, SHA-256
  `5D9906509E5F54D6D92EE44682EAC887659F9CA9A63F0AE724C1A2946B410028`;
- task writes/starts: `0`;
- raw XML and complete action projections remain LOCAL_ONLY.

Docker Desktop differs from its pinned XML only in EOL/final separator after
comparable normalization. The three service actions use the same approved
scripts as quoted absolute paths under exact `C:\ai-lab-core`; the manifest
uses relative paths. Exact executable, CWD, token count, non-code arguments,
script identity and root boundaries still apply.

## Source/offline result

- candidate launcher: `78681` B,
  `B4143A6934E6723E3293A6D5A4806A4F01D34CB53037C6417B16830BD4EC7892`;
- candidate runtime: `83488` B,
  `959768E297BCB93FF1AF3D7EE5A174313F9DC053707EDE8C45D3A84D024B0732`;
- derived recipe: `62583` B,
  `E4D0FA45D29C5B199DF225C41B508E97239A4FFD6AD7785BFB2847BF2873241A`;
- package index: `8628` B,
  `F74BD6286FCAFB4591378A09C4E6E7B0FA7D9714A9E2C660A20BE99E3DEA5BD2`;
- review index: `9558` B,
  `F21EE086C2801D3BC895EA0116AE635292E17947B89B8ABA2429B368348CEB04`;
- review ZIP: `150237` B,
  `F9850E9BC3CBA376ABE509955E83831AE986536C76134322713BF005E4619A3B`;
- ZIP roundtrip: `40/40` files, `39/39` indexed files verified; index self is
  deliberately excluded from its own list.

Final Windows PowerShell 5.1 results on the final source bytes:

- focused Stage-A gate: `41` assertions, four collector cases, children `4/4`, production boundaries `0`;
- `test-start-host-services.ps1`: `57` assertions PASS;
- `test-startup-real-adapters.ps1`: `51` assertions PASS;
- `test-startup-data-junction.ps1`: `44` assertions PASS;
- `test-p4-startup-package.ps1`: `41` assertions PASS;
- derived NUP orchestration: `75` assertions / `20` scenarios PASS, production boundaries `0`, owned processes `1/1` settled.

These overlapping sets are not a count of unique application tests. PS 5.1
parsing, package JSON/CSV, payload bindings, roundtrip hashes, diff and secret
checks are required before publication.

## Boundaries and next step

`HTTP = NOT_RUN`, `fresh six-container preflight = NOT_RUN`, `live VerifyOnly =
NOT_RUN`, `Stage B = BLOCKED / NOT_AUTHORIZED`. No Docker/HTTP/CIM/TCP/SQL
read, UAC, installation, Host retry, task write/start, rollback or data change
was performed by the source/offline test campaign. The only live boundary was
the explicitly authorized four-task read-only capture above.

The one next step is owner review of this exact source diff and the four saved
task definitions. A later single VerifyOnly requires a separate decision; this
checkpoint does not request Stage B.

> **ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT**
>
> Przed oceną tej zwrotki i kolejnym promptem przeczytaj
> `NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md`: §0, `ANTI_EXCESSIVE_WORK`, aktywną
> kartę i ten checkpoint na pełnym opublikowanym SHA.
>
> Zachowaj odbiory Host22 i NUP-01/02/03; review pozostaje `2/2`. Nie dodawaj
> K2/K3. K0/K1 blokujący zależny krok: `P4B-STAGEA-GATE` — nowe bajty są
> niezweryfikowane live i niewdrożone. Efekt: cztery różnice reprezentacji mają
> ograniczony source/offline guard i dowód `4/4`; następny krok to wyłącznie
> właścicielski review tego diffu przed osobną decyzją o jednym VerifyOnly.
