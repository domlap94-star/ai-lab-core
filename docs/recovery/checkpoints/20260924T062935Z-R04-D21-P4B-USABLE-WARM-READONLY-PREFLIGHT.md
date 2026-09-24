# R04 / D-21 / P4-B — USABLE-WARM consolidated read-only preflight

## Scope and preserved history

- Window: `R04-D21-P4B-USABLE-WARM-20260923T170936Z`.
- Entry/evidence HEAD: `32777ad5e3a6035fe60b25dded95dcee6b8a7094`.
- Recipe: `74E5664F50CCAE9E641BC076390CE17A769C2E6F1D6F109FB6990C80220B7D6D`.
- Historical package index remains unchanged: `10884` B,
  `6F379DC5330D902CEC30F72E5B4C2CD190FC923AF195B275FF9FF7BA56D64698`.
- The earlier `PACKAGE_STATUS_INVALID` result remains historical evidence; it
  was not rewritten into a retroactive PASS.
- Host22/NUP-01/02/03 and D-23 review `2/2` retain their accepted scopes.
  Installed run01 was not changed.

No UAC, `InstallAndWarm`, Host/task write or start, service/container start,
rollback, data change or Stage B occurred.

## Package contract correction

The original index top-level `status` was
`INACTIVE_PREFLIGHT_ONLY_MANIFEST_NOT_APPROVED`; the unchanged
`Test-P4BPackageIndex` contract requires
`PROPOSED_AWAITING_SEPARATE_OWNER_OPERATIONAL_APPROVAL`.

The LOCAL_ONLY derivative
`C:\Users\domai\AppData\Local\Temp\P4B-UW-01\package\package-index.verifyonly.json`
has `10892` B and SHA-256
`4A58DF7DB1FD100D341BE17633553272D490B9E34EC1C35F13A11B4F23B584DC`.
Semantic comparison after removing the top-level `status` was exact: no role,
path, hash, OperationId, payload or authorization field changed. The candidate
manifest remains `NOT_APPROVED`, and all mutation authorizations remain false.
The full existing package gate passed against the real package files.

## VerifyOnly

Exactly one new ordinary-token Windows PowerShell 5.1 `VerifyOnly` used the
derived index and output
`...\preflight\status01\verifyonly`:

- UTC: `2026-09-24T06:19:47.8514124Z`–`06:20:42.8099616Z`;
- exit `0`, elapsed `54958.549 ms`, no timeout;
- `VERIFIED_NO_MUTATION`, `mutation_started=false`,
  `pending_mutation=false`, empty `changed_roles` and `warm_runs`;
- journal `NOT_OPENED`, rollback `NOT_NEEDED`, dependency-task changes `0`,
  helper change `false`;
- `result.json`: `545` B, SHA-256
  `9A515673F4A10C076E57001891411FC3F5E2C0B8251D1A031680420F18BB53B4`.

## Current runtime readback

### Six pinned containers

The accepted parser/adapters performed one read-only campaign. All six exact
IDs were selected, all identity checks passed, all were `running`, PostgreSQL
was `healthy`, and no start was requested.

| Service | Exact container ID | Image ID | State / health | Result |
|---|---|---|---|---|
| backend | `686ac37663ad369f253eb91da4364aa2bd6c16c77b1205cc41d61c68d4d9c854` | `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702` | `running` / `NOT_CONFIGURED` | PASS |
| postgres | `240343ebff4fb299b239db2817efea1910ab59c29ed3ec9df3a8abde04e81226` | `sha256:a426e44bac0b759c95894d68e1a0ac03ecc20b619f498a91aae373bf06d8508d` | `running` / `healthy` | PASS |
| qdrant | `daa3b0b86b748aa3a52052dac08bfde499cf19ad61600a1325e09061a5451fae` | `sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286` | `running` / `NOT_CONFIGURED` | PASS |
| n8n | `a44e719ecfecf72a199b4f8b3ec9d7503548d2098601e767d5e9e6503d37081c` | `sha256:3c07c723326dd72e46a6969181c66a75260b7a204b9b77ba1ece6d594489c684` | `running` / `NOT_CONFIGURED` | PASS |
| open-webui | `9575ca068b8cc17d0b2ac72e0062867c5c74650c12619bf6ecc6b48d1ec54c39` | `sha256:a26effeb220e132482bf7e0560b3404843e7bc40d23051144e062960df8df6b0` | `running` / `healthy` | PASS |
| ollama | `7ff1c45ea12cb9a26df1540cdeb5993c30fe12ac1d9c199ea7ce776847aac083` | `sha256:ec24bcaa2a810eb74171ce7c517813ef4821ed678988845e8d76cf62467036d4` | `running` / `NOT_CONFIGURED` | PASS |

Backend mounts remained `/app=C:/ai-lab-core/backend:ro` and
`/data=C:/ai-lab-core/data:rw`. The campaign preserved 22 bounded native
response envelopes. Its first formatter field incorrectly retained
`native_reads=0`; this was corrected only in the summary from the already
stored 22 envelopes, without another Engine read.

### Host services, HTTP and resources

- Windows PowerShell `5.1.26100.8894` exact observer: Public Gateway
  `PRESENT`, Private Gateway `ABSENT`, Supervisor `ABSENT`; `3/3` complete,
  workers settled, starts/writes/retries `0`.
- HTTP: backend `/health` `200`, `/version` `200`, Public Gateway
  `/gateway-health` `200`, public `/control` `404`, public `/control/health`
  `404`; `5/5` PASS.
- Windows resource gate: available physical memory `5252493312` B, free
  virtual memory `36178493440` B, C: free `617138397184` B, D: free
  `917804883968` B; all configured thresholds passed.
- Docker/WSL available pool and current swap usage remain
  `UNKNOWN_NOT_MEASURED`. This is disclosed for the owner decision and is not
  rewritten as PASS.

Two wrapper launches ended at `OUTPUT_ROOT_MISSING` before any host read, and
one container-collector launch ended before any native read because a local
variable name was overwritten by dot-sourcing. They are preserved as tooling
history. The successful campaigns above are the only actual host-service and
Docker read campaigns; no read was repeated to repair formatting.

The sanitized LOCAL_ONLY consolidated summary is `11302` B, SHA-256
`1486F0840D2DC604329385363B374A2BE3752F1761D8C1C1A7454BFD250D75B5`.

## Result and next decision

The live read-only layers passed, but a final exact-byte execution check found
a material Stage-B blocker in the frozen package. The candidate manifest has
`approval.status=NOT_APPROVED`, `installation_authorized=false` and
`startup_authorized=false`. The unchanged runtime validator adds
`START_NOT_APPROVED` unless the status is exactly `APPROVED_FOR_START`.
`InstallAndWarm` copies this exact manifest before the recorder-backed Host
attempts; it does not perform an approval transition. Therefore an unchanged
Stage B would install bytes that the launcher must refuse, and cannot be
presented for owner confirmation as a viable warm window.

Status:
`P4B_USABLE_WARM_CONSOLIDATED_READ_ONLY_PREFLIGHT_PASS_WITH_DECLARED_UNKNOWNS /
VERIFYONLY_VERIFIED_NO_MUTATION /
STAGE_B_BLOCKED_EXACT_APPROVED_MANIFEST_BINDING_NOT_PREPARED_NOT_AUTHORIZED`.

The intended operation remains four files plus the existing Host task, two
recorder-backed warm runs with Private `1 -> 0`, and logon only after both
complete successes. Before that operation can be offered for confirmation, a
separate owner-authorized LOCAL_ONLY derivation must create exact
`APPROVED_FOR_START` manifest bytes, rebind their hash in a derivative index,
and pass the unchanged manifest/package guards. This checkpoint does not
authorize that derivation, UAC, installation or Stage B. The reserved
`C:\Users\domai\AppData\Local\Temp\P4B-UW-01\apply` remains absent.

## ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT

Przed oceną i kolejnym promptem przeczytaj [roadmapę §0,
ANTI_EXCESSIVE_WORK oraz aktywną kartę R04](../../../NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md)
na pełnym opublikowanym SHA oraz ten checkpoint. Zachowaj odbiory i D-23
`2/2`; nie szukaj K2/K3. K0/K1: `K1 — zamrożony manifest ma NOT_APPROVED, a
niezmieniony runtime zwraca START_NOT_APPROVED; niezmienione Stage B nie może
osiągnąć warm runs`. Następny krok: jedna decyzja właściciela o minimalnym
LOCAL_ONLY przygotowaniu dokładnych approved-manifest bytes i derivative-index
binding; nadal bez UAC, instalacji, Host startu, warm runs i task writes.
