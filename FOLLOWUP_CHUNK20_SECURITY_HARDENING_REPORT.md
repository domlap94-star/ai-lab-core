# FOLLOW-UP CHUNK 20 — SECURITY HARDENING V2

Audit date: 2026-08-23

Source baseline: `e7fef2793f0d68ec12bb6baddabb403bd075420d`

Stable release: NEXT Stabil `1.0.2+29`

Production DB: `followup_contact_person_20260822`

## Outcome

The current local/private architecture has no P0 finding. Bounded,
backward-compatible P1 source fixes passed, but CHUNK 20 remains in progress
because live ACL remediation, public security headers, login throttling and
publisher-signing trust require explicit owner decisions. No firewall,
Tailscale, WDAC, Scheduled Task, credential, production schema or business-data
change was made.

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
- Login has no IP/account-aware rate limit. The local/private deployment lowers
  exposure, but the public auth path makes this P1 defense-in-depth work. It
  requires `FOLLOWUP_LOGIN_RATE_LIMITING_APPROVAL_REQUIRED` because proxy
  attribution, anti-enumeration, cooldown and lockout-DoS behavior must be
  agreed together.
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
- `Authenticated Users` currently have Modify on the repo, Supervisor and
  gateway scripts, Vision/analysis spools, release channel, backup root,
  `.env` and Android key properties. This is P1.
- Supervisor/public/private gateway and backup tasks run as `domai`, limited.
  Trash Purge runs as `domai`, S4U, Highest, and loads a PowerShell script from
  the writable repo. No task or ACL was changed. Correcting principals,
  ownership, inheritance and operational write paths requires
  `FOLLOWUP_RUNTIME_ACL_HARDENING_APPROVAL_REQUIRED` with rollback and service
  restart checks.

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

### P1 owner-gated

1. Writable runtime/secret/release/task paths:
   `FOLLOWUP_RUNTIME_ACL_HARDENING_APPROVAL_REQUIRED`.
2. Staged public headers/CSP compatibility:
   `FOLLOWUP_PUBLIC_SECURITY_HEADERS_APPROVAL_REQUIRED`.
3. Proxy-aware, anti-enumeration login throttling:
   `FOLLOWUP_LOGIN_RATE_LIMITING_APPROVAL_REQUIRED`.
4. Manifest/Windows publisher authenticity:
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
- Flutter analyze: PASS; focused auth/update `40/40`; full Flutter `289/289`.
- Android debug build: PASS. No release build or release was performed.
- Production DB head and Qdrant counts are unchanged.

## Decision

`CHUNK20_OWNER_GATE_REQUIRED`. CHUNK 21 remains NOT STARTED. Release F was not
performed.
