# FOLLOW-UP CHUNK 20 — SECURITY HARDENING V2

Audit date: 2026-08-23

Source baseline: `e7fef2793f0d68ec12bb6baddabb403bd075420d`

Owner-gated remediation baseline: `319d01b2c04ccacbdfc82a08abdc4fdd1046c8e0`

Stable release: NEXT Stabil `1.0.2+29`

Production DB: `followup_contact_person_20260822`

## Outcome

The current local/private architecture has no P0 finding. Bounded,
backward-compatible P1 source fixes passed. The owner subsequently approved
runtime ACL remediation, staged public security headers and proxy-aware login
throttling; publisher-signing trust was deferred to CHUNK 21. Headers, login
throttling and final ACL acceptance pass. ACL rollback safety has complete
current-state coverage and the approved elevated apply protected all 22
canonical targets without owner/group/SACL changes. No firewall, Tailscale, WDAC,
credential, production schema or business-data change was made.

## Threat model

The relevant attackers are an unauthenticated caller reaching the Tailscale
HTTPS/public gateway, an authenticated normal User attempting Administrator
operations, malicious document/file metadata, untrusted document evidence sent
through the AI pipeline, a local unprivileged Windows user, and a party able to
tamper with update artifacts or the stable manifest. A Docker/host
Administrator remains trusted because that principal can already inspect
container environments and runtime storage.

## Network and CORS

- Backend `127.0.0.1:8000`, Postgres `127.0.0.1:5432`, Qdrant
  `127.0.0.1:6333-6334`, n8n `127.0.0.1:5678`, Ollama
  `127.0.0.1:11434`, Open WebUI `127.0.0.1:3000`, Supervisor
  `127.0.0.1:8787`, private gateway `127.0.0.1:8788` and public gateway
  `127.0.0.1:8789` are loopback-bound.
- Existing Tailscale listeners are intentional; no application container has
  an unexpected `0.0.0.0` host publication.
- Public `/control` is `404`; only the private gateway references Supervisor.
- CORS allows exact `http://127.0.0.1:8789` with credentials. An arbitrary LAN
  origin returns `400` without allow-origin. Wildcard origins are absent.
- Public responses still lack `nosniff`, referrer, framing and CSP headers.
  Their staged compatibility proposal remains behind
  `FOLLOWUP_PUBLIC_SECURITY_HEADERS_APPROVAL_REQUIRED`.

## Authentication and authorization

- Passwords use bcrypt through Passlib. Access JWTs are HS256, bounded to 60
  minutes, and bind issuer, type, `jti`, `iat`, `nbf`, `exp`, live User state,
  role and `auth_version`.
- Login uses a uniform `401` for missing, disabled and invalid identities.
  Password-reset request is anti-enumeration. No bootstrap/default credential
  value is tracked.
- Release +29 recovery remains correct: expired startup token is cleared before
  fresh login, `/auth/login` carries no stale Authorization header, and known
  connection/HTTP/schema errors map to bounded UI messages.
- Unauthenticated access is rejected for Clients/Documents/search/AI and every
  audited Administrator surface. A normal User receives `403` for User
  Management, Knowledge Base, Backup/Restore, Trash and Change History.
- Client, Contact Person, Document, Work Item and project edits intentionally
  share the authenticated User product boundary. Administrator-only controls
  remain admin-only.
- Login now uses a bounded in-process limiter keyed by the normalized socket
  peer and a SHA-256 account key. Untrusted forwarded headers are ignored.
  Five failures in 60 seconds yield a 60-second cooldown; the source-wide
  ceiling is 30. Valid credentials reset/bypass the failure bucket, preventing
  a trivial attacker-created permanent account lockout. Invalid, missing and
  disabled accounts retain the same bounded response shape.
- Password change does not revoke other access tokens immediately; exposure is
  bounded by the 60-minute token lifetime. A compatible re-issue/revocation UX
  is deferred rather than breaking stable clients.

## Supervisor and advanced analysis

- Supervisor binds loopback only. Vision, advanced analysis and backup use
  purpose-separated HMAC-derived bridge keys with timing-safe comparison.
- Analysis package hash, analysis ID/type, source hashes, result manifest and
  terminal-job identity are strictly bound. Vision and analysis share one
  browser arbiter. `AUTH_REQUIRED`, `UI_CHANGED`, retry and restart behavior
  remain fail-closed.
- Static bridge keys do not add a timestamp/nonce replay layer. Given loopback
  isolation and immutable package/result binding this is P2, not a reason to
  change the live protocol in this chunk.
- Production advanced analysis remains enabled and local-first. Only
  `public_reference` and sanitizer-passed `customer_sanitizable` can escalate;
  `internal_non_sensitive` remains local/review and
  `restricted_never_external` is blocked. PHONE/privacy, source allowlist,
  post-validation and no-normal-Chat contracts pass. No real customer job ran.

## Backup, restore and destructive operations

- Backup destinations must be outside repo/data, checkpoint joins are bounded,
  manifests bind size/SHA-256, Qdrant snapshots receive structural and isolated
  restore checks, and the global operation lock is retained.
- Production restore remains disabled behind
  `FOLLOWUP_PRODUCTION_RESTORE_APPROVAL_REQUIRED`; no restore was attempted.
- Trash restore/purge, KB archive, Contact Person lifecycle and exact Qdrant
  deletion are authenticated, bounded, audited and ownership-checked. Vector
  purge fails closed on foreign or untracked points.

## Files, paths and uploads

- Canonical document reads resolve both root and target, require an existing
  regular file, and reject escape from `data_dir`. Synthetic slash, backslash,
  absolute, UNC, encoded and missing-path cases pass.
- Filenames are reduced to a basename, normalized to a bounded safe character
  set and cannot inject path or response-header separators. KB upload adds a
  strict extension/MIME allowlist, size bound and checksum dedupe.
- General authenticated/import-key Document upload accepts arbitrary bytes up
  to 250 MiB. Content is stored under a generated name and never executed, but
  type/rate/storage abuse remains P2. A future allowlist must account for the
  existing PDF/Office/media/mail/archive compatibility contract.

## SQL and Qdrant

- Search, filters, sort orders, Change History and backup metadata use ORM
  expressions or bound SQL parameters. Global Mail assembles only constant SQL
  fragments; every caller value remains bound.
- Mutating vector tests require an explicit isolated endpoint and an
  `ai_lab_test_*` collection. Both production collection names and production
  endpoints fail closed. Exact deletes validate point ID and payload ownership.
- Production collections remained customer `57`, KB `0`, both green,
  `1024/Cosine`; no write, delete, index or backfill occurred.

## Secrets, logging and errors

- No `.env`, key properties, keystore, private key or certificate container is
  tracked. Runtime secrets exist only in untracked environment/container
  configuration; values were never printed.
- The tracked literal Postgres password was removed. Compose now requires
  `POSTGRES_PASSWORD` from the untracked runtime environment and fails closed
  when absent. Because the former literal remains in Git history, rotation and
  escrow remain operational owner work under CHUNK 23.
- Synthetic password/JWT/Authorization/path/email/phone markers were absent
  from bounded backend/Supervisor log scans. Advanced-analysis logs retain
  metadata only.
- Generic AI/RAG `500` responses no longer return arbitrary exception text;
  injected synthetic secret/path markers are withheld. Domain error codes stay
  bounded and client-facing auth errors reveal no stack, path or token.

## Windows trust, ACLs and Scheduled Tasks

- Release +29 retains the Code-Integrity-accepted permission plugin SHA-256
  `5CC6D938143C687690A3B697C05EC7A50B76C0156D34E2439BD0C90AFE3CDA2A`
  and geolocator plugin SHA-256
  `6C6B2B8FF8079CCB23DB375E5BEF561F7A3F8A3C4DFC54730BEEAC1AFF405898`.
  They and the Windows installer are not Authenticode-signed. WDAC was not
  weakened. This is both a reproducibility issue (CHUNK 21) and a publisher
  trust limitation.
- Before remediation, `Authenticated Users` had Modify on the repo, Supervisor
  and gateway scripts, Vision/analysis spools, release channel, backup root,
  `.env` and Android key properties. This was P1.
- Supervisor/public/private gateway and backup tasks run as `domai`, limited.
  Trash Purge runs as `domai`, S4U, Highest, and loads a PowerShell script from
  the writable repo. After approval, protected ACLs were applied to the repo
  root, backend, compose, hardening task scripts, Vision/analysis spools,
  backup root and `.env`; these no longer grant `Authenticated Users`/`Users`
  write access. The original partial pre-change record is retained as bounded
  historical evidence only; the repaired rollback model is documented below.
  The approved elevated apply subsequently protected the Administrator-owned
  gateway/Supervisor/Windows paths, release-channel and Android signing
  properties. The Highest Trash and backup task load paths remain protected.

### ACL rollback safety micro-fix

The original record
`%LOCALAPPDATA%\Temp\next-stabil-chunk20-acl-before.json` remains unchanged.
Its byte-identical copy is explicitly named
`%LOCALAPPDATA%\NEXT Stabil\Security\chunk20-acl-partial-pre-hardening-evidence.json`.
It is historical evidence for its 10 listed targets only: coverage is `10/22`
and no pre-CHUNK20 state is claimed for the missing targets.

The canonical inventory is defined once by `Get-Chunk20AclTargets` in
`operations/hardening/acl-hardening-core.ps1`; both apply and acceptance consume
it. Classification from preserved evidence, earlier apply output and current
read-only ACL inspection is:

| # | Target | Type | Elevation | Earlier mutation | Evidence class |
|---:|---|---|---:|---:|---|
| 1 | `C:\ai-lab-core` | directory | no | yes | A |
| 2 | `C:\ai-lab-core\backend` | directory | no | yes | A |
| 3 | `C:\ai-lab-core\compose` | directory | no | yes | A |
| 4 | `C:\ai-lab-core\operations` | directory | yes | no | A |
| 5 | `C:\ai-lab-core\operations\hardening` | directory | no | yes | B |
| 6 | `C:\ai-lab-core\operations\gateway` | directory | yes | no | C |
| 7 | `C:\ai-lab-core\operations\supervisor` | directory | yes | no | C |
| 8 | `C:\ai-lab-core\operations\windows` | directory | yes | no | C |
| 9 | `C:\ai-lab-core\release-channel` | directory | yes | no | A |
| 10 | `C:\ai-lab-core\operations\hardening\run-trash-purge.ps1` | file | no | yes | B |
| 11 | `C:\ai-lab-core\operations\hardening\run-backup-schedule.ps1` | file | no | yes | B |
| 12 | `C:\ai-lab-core\operations\hardening\backup-production.ps1` | file | no | yes | B |
| 13 | `C:\ai-lab-core\operations\gateway\public_web_server.cjs` | file | yes | no | C |
| 14 | `C:\ai-lab-core\operations\gateway\web_server.cjs` | file | yes | no | C |
| 15 | `C:\ai-lab-core\operations\supervisor\server.js` | file | yes | no | C |
| 16 | `C:\ai-lab-core\operations\windows\start-compose-after-docker.ps1` | file | yes | no | C |
| 17 | `C:\ai-lab-core\release-channel\stable\manifest.json` | file | yes | no | C |
| 18 | `C:\ai-lab-core\data\vision-spool` | directory | no | yes | A |
| 19 | `C:\ai-lab-core\data\analysis-spool` | directory | no | yes | A |
| 20 | `C:\ai-lab-core-backups` | directory | no | yes | A |
| 21 | `C:\ai-lab-core\.env` | file | no | yes | A |
| 22 | `C:\ai-lab-core\frontend\android\key.properties` | file | yes | no | A |

Class A means trustworthy historical SDDL exists; B means already changed and
historical SDDL is unavailable; C means not yet changed; D would mean unknown.
Counts are A=`10`, B=`4`, C=`8`, D=`0`; `11` targets were partially hardened
and `11` required elevation before the final apply.

The new canonical record is
`%LOCALAPPDATA%\NEXT Stabil\Security\chunk20-acl-current-baseline-v3.json`.
It is explicitly `CURRENT_PRE_FINALIZATION_BASELINE`, not historical evidence,
and captures 22/22 current owner, group and DACL values without file contents.
Schema is `NEXT_STABIL_ACL_BASELINE_V3`; source HEAD is
`319d01b2c04ccacbdfc82a08abdc4fdd1046c8e0`; target-list SHA-256 is
`d69b3025a4f81ad4bd7d9bc3eb6c6b598dac01dfcb6609514fd24aea2289b05f`.
The per-user record directory and record expose no broad Users/Authenticated
Users write grant.

Future apply requires exactly 22 unique normalized paths, zero missing/extra/
duplicate entries, matching target hash, matching current DACL/owner/group and
an elevated token before mutation. Each touched target is tracked. Any error
restores the current invocation's touched DACLs in reverse order and verifies
DACL plus unchanged owner/group. Audit/SACL state is deliberately not modified.
Temporary file/directory tests pass baseline restoration, target-three failure
rollback, untouched later targets and repeated-apply idempotency. A
non-elevated real-target invocation fails before mutation. No production ACL
was changed by this micro-fix.

### Final elevated ACL acceptance

The UAC-authorized final invocation used the complete current-state baseline
`%LOCALAPPDATA%\NEXT Stabil\Security\chunk20-acl-current-baseline-v3.json`.
Its preflight, source-HEAD check, target-list hash, complete-coverage check and
current-state drift gate passed. All 22 targets were evaluated successfully;
automatic rollback was not needed. Post-apply inspection found zero
`Authenticated Users` or ordinary `Users` write grants, zero owner/group
changes and zero SACL changes across the canonical inventory. Administrators,
SYSTEM and the `domai` operator retain the rights defined by each target's
access class.

The acceptance suite confirms protected task-loaded scripts, public/private
gateway and Supervisor sources, release-channel manifest/artifacts, `.env`,
Android `key.properties` and backup integrity paths. Bounded structural
negative-write probes report access-denied semantics without altering real
content. Safe create/delete probes prove the required operator can still write
Vision spool, analysis spool and backup output. Existing Supervisor, gateway,
backup and Trash tasks retain their run-as identities and privilege modes and
remain healthy. The invocation baseline retained for transactional recovery is
`%LOCALAPPDATA%\NEXT Stabil\Security\chunk20-acl-invocation-20260823T120842415Z.json`.

## Public security headers and CORS

- The canonical public gateway emits `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`
  and Flutter-compatible `Content-Security-Policy-Report-Only` on Web, API and
  update responses. HSTS is not enabled because HTTP loopback remains a
  supported local path.
- Local and public HTTPS responses include the headers; HTML, main bundle and
  service-worker MIME types remain correct. Exact loopback CORS is allowed and
  arbitrary LAN origin remains rejected. The owner completed normal sign-in;
  the authenticated +29 Dashboard loaded with no console/runtime error. Main
  assets, service worker, stable manifest and immutable artifact HEAD/download
  paths remain available.

## Update channel

- The stable manifest is `1.0.2+29`, minimum `1.0.0`, advertises neither +27
  nor +28, and retains +25/+26 rollback artifacts plus +27 forensic bytes.
- Clients verify SHA-256 and monotonic version/build decisions. Native update
  URLs are now restricted to same-origin relative
  `/updates/stable/windows/` or `/updates/stable/android/` paths, without
  authority, query, fragment or traversal.
- Hashes prove byte consistency only after trusting the manifest; they do not
  prove publisher identity. Android has APK v2 signing with the established
  certificate; Windows artifacts/manifest have no publisher signature. A
  durable signing/certificate design requires
  `FOLLOWUP_UPDATE_SIGNING_TRUST_APPROVAL_REQUIRED`.

## Web and Android

- Flutter renders untrusted values as text; no raw `innerHtml` renderer or open
  redirect was found. External map/tel targets are constructed through `Uri`.
  Web document download uses a local Blob and sanitized filename.
- Web auth uses `flutter_secure_storage`; XSS defense still depends on the
  gated public-header/CSP rollout.
- Stable +29 is non-debuggable and defaults to cleartext disabled. Its main
  launcher and widget receiver are intentionally exported; other providers and
  services are non-exported. APK v2 signer is
  `5e223da2da7c893d089d7333e99aaeee8d98c9cdf72be80609020967368fe018`.
- Source for the next release now explicitly disables cleartext, application
  backup and full backup. Debug cleartext remains an explicit debug-only
  manifest override. Physical +29 auth acceptance remains PASS.

## Docker, dependencies and abuse controls

- No app container is privileged; no `cap_add`, Docker socket or host network
  mount exists. Images are digest-pinned where externally sourced.
- Backend/Postgres/Qdrant/Open WebUI/Ollama run as root/default and several
  code/data mounts are writable. Least-privilege/read-only redesign is P2 and
  needs staged compatibility proof.
- Python requirements are version-pinned (with only a bounded `xlrd` range),
  `pip check` reports no broken dependency, Flutter uses `pubspec.lock`, and
  Supervisor/gateways use Node built-ins/local modules. No mass upgrade or
  online advisory claim was made. Flutter reports a future Kotlin plugin
  migration warning for `speech_to_text`; defer to normal dependency work.
- Login throttling is the only current P1 abuse-control gap. Search/upload,
  processing, Vision, analysis, backup and restore already have authentication,
  size, concurrency, queue or human gates; generic throttling would add little
  value without measured abuse.

## Findings and fixes

### P0

- None.

### P1 fixed in source

1. Removed tracked Postgres password literal; runtime value is mandatory.
2. Replaced arbitrary AI/RAG exception disclosure with stable public errors.
3. Disabled Android release backup/full-backup and made cleartext denial
   explicit.
4. Restricted native updater URLs to canonical same-origin stable paths.
5. Added deterministic path, filename, admin-negative, error-leak, tracked
   secret, Android policy and public-Supervisor boundary tests.

### P1 approved remediation

1. Runtime ACL hardening: final elevated 22-target apply and acceptance PASS.
2. Staged public headers/CSP compatibility: implemented and verified.
3. Proxy-aware, anti-enumeration login throttling: implemented and verified.
4. Manifest/Windows publisher authenticity: DEFERRED TO CHUNK 21 under
   `FOLLOWUP_UPDATE_SIGNING_TRUST_APPROVAL_REQUIRED`.

### P2 / defer

- Supervisor nonce/replay layer, immediate password-change token revocation,
  general Document upload allowlist, Docker least privilege/read-only mounts,
  n8n settings-file permissions, online dependency advisory scan, and the
  CHUNK 21 Windows reproducibility/toolchain remediation.

## Verification

- Focused CHUNK 20 source/path/auth/error tests: PASS.
- Unauthenticated admin matrix: PASS; normal User admin matrix: PASS.
- Android auth regression and current active-user lifecycle: PASS.
- Trash, backup/restore and KB isolated suites: PASS; production restore gate
  PASS; production Qdrant writes `0`.
- Advanced analysis: privacy PASS, calculations `30/30` and `36/36`, adapters
  `7/7`; Supervisor idempotency/recovery/AUTH/UI and Vision contracts PASS.
- Qdrant safety and public CORS/LAN rejection: PASS.
- Public security headers local/HTTPS and gateway source tests: PASS.
- Login limiter unit/E2E, proxy spoofing, anti-enumeration, successful-login
  reset/bypass and bounded-storage tests: PASS.
- ACL parser, canonical inventory `22/22`, current baseline `22/22`, missing/
  duplicate/extra fail-closed, transactional rollback, target-three partial
  failure, idempotency and apply/test parity: PASS. Non-elevated apply fails
  before mutation. Elevated apply, complete protected-path verification,
  DACL-only invariants, negative-write semantics and positive operational
  writes: PASS.
- Flutter analyze: PASS; focused current auth tests `27/27`; full Flutter was
  not rerun because Flutter source did not change (latest baseline `289/289`).
- Android debug build: PASS. No release build or release was performed.
- Production DB head and Qdrant counts are unchanged.

## Decision

`CHUNK20_COMPLETE_CHUNK21_NEXT`: bounded source controls, public headers,
proxy-aware login limiting, repaired transactional rollback, final 22-target
ACL acceptance and authenticated +29 Web Dashboard smoke pass. The historical
pre-hardening evidence remains truthfully limited to 10/22 targets; no complete
historical rollback is claimed. Update signing trust is DEFERRED TO CHUNK 21
under `FOLLOWUP_UPDATE_SIGNING_TRUST_APPROVAL_REQUIRED`. CHUNK 21 is NEXT / NOT
STARTED. Release F was not performed.
