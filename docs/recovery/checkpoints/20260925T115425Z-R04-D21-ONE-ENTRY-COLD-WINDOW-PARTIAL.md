# R04 / D-21 — ONE-ENTRY-COLD window partial

Status: `PRE_REBOOT_INSTALL_FAILED_VALIDATION_MANIFEST_PARAMETER_COLLISION / SAFE_INACTIVE_COMPLETE / UAC_CONSUMED`.

## Scope and pinned input

- window: `R04-D21-ONE-ENTRY-COLD-WINDOW-20260925T110738Z`;
- entry SHA: `cf535cfab7a67e35c3a66b09c1619a0f40599175`;
- package index: `9C1A60AA50965E4419C9B6021A8C4F60EA8FEF67C685F37D026CCAF60EBBB06C`;
- review ZIP: `B8D33DD14CEF2491160A50F241EE58B7679729D3DAE304810729565295C48876`;
- operational manifest/index: `6219F891E8C1CB50088C8E2262E7935E329A9B0198E0179815BBA23001A90BBA` / `F2905BD6BD014B3F7E3BC4FD17A69CE91EEBD709B091E3EB07314066B5242535`.

The owner confirmed presence at NEXT Stabil/RustDesk and recovery access after
restart. One UAC and one limited rollback were authorized. The UAC was used once;
no restart was reached.

## Preflight

The final bounded preflight evidence is
`730C0CA118529A435FD91C5C293561F91C2868EBFB02580EE11DE8A4375EA7D5`.
It passed package, installed preimages, entry/client, Host, maintenance, 6/6
pinned containers, host services and HTTP `200/200/200/404/404`. PostgreSQL was
healthy; Public and Private Gateway were present; Supervisor was absent.
Docker/WSL pool availability and swap usage remain approved UNKNOWN for this
limited window, not PASS.

## Execution and exact failure

- elevated PID: `52112`;
- submitted: `2026-09-25T11:54:21.8524340Z`;
- finished: `2026-09-25T11:54:25.6349037Z`;
- exit: `22`;
- exact error: `Cannot bind argument to parameter 'ManifestPath' because it is an empty string.`;
- mutation started: `true`; pending mutation: `false`;
- four file writes occurred before validation failed;
- shortcut writes, task writes, Host starts, service starts and container starts: `0`.

The LOCAL_ONLY operator's validation child accepted a parameter named
`ManifestPath`; dot-sourcing the launcher reset that same name to its default
empty value. This is a material K1 because it blocks installation and therefore
manual-entry/cold validation. It is not evidence of a product runtime failure.

## Rollback and final state

The one authorized rollback completed `SAFE_INACTIVE_COMPLETE`. Exact final
readback confirmed:

- launcher `686F4EC877AADC93D46D2B67858864BF9C728B00093037A266B257099BA14B66`;
- runtime `959768E297BCB93FF1AF3D7EE5A174313F9DC053707EDE8C45D3A84D024B0732`;
- recorder `D21A3E6B5D49E68711C5584138C47C2201B861A80DD4A4F89F173DC57217452A`;
- installed manifest `38D7C529FD7CE37E25E32A58CC9CF46075FF5E97D7E60F3618D088653C492BDE`;
- desktop shortcut `8B46D106A8AD2DB3AC39E57A6E879104C77BA7C8D7AEEC9008577E1F9BA9FBDD`.

Host remained Ready/enabled with the existing one logon trigger, LastResult 0
and unchanged last-run time. Manual entry/repeat, reboot/logon, cold start and
CRM/Web were not run. Six containers and running gateways were not mutated;
Supervisor remains `INTENTIONALLY_STOPPED`. USABLE-WARM remains
`ACCEPTED / LIMITED_RUNTIME_SCOPE`.

## Decision boundary

The window and its UAC/rollback authorization are consumed. There is no retry
or second UAC. The single next decision is whether to authorize a new exact
window after minimal offline verification of a non-colliding validation
parameter. R04 remains `IN_PROGRESS`; D-23 remains 2/2 and D-22 remains
`NOT_RUN`.
