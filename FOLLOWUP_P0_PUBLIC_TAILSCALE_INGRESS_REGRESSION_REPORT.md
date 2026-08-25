# P0 Public Tailscale Ingress Regression Report

Date: 2026-08-25

Source baseline: `f3d30081c9ba83ccdfb8ab05ad9536b14ebd92ba`

Stable: `NEXT Stabil 1.0.2+29`

Decision: `P0_PUBLIC_TAILSCALE_INGRESS_RESTORED_PHYSICAL_RETEST_REQUIRED`

## Owner evidence and boundary

The owner observed `DNS_PROBE_POSSIBLE` for
`https://domai.tail1927bd.ts.net/health` on the same Android phone that had
previously reached the endpoint without a Tailscale client. Android +37 used
that exact HTTPS API and classified `/health` as a socket-level transport
failure. PRE-CHUNK23 therefore remains blocked on physical acceptance and
CHUNK23 was not started.

No Android endpoint, APK, firewall, router/NAT, backend bind, Supervisor bind,
DNS provider, or security policy was changed in this execution.

## Git reconstruction

Git proves the following timeline:

- `45fa212bc66659656f7bc18955e84ec5f4792345`, 2026-08-14 13:06 +02:00,
  introduced the combined loopback gateway and stable update channel.
- `b2067179612b3a02633ab1431f0e0df80d8288a0`, 2026-08-14 18:04 +02:00,
  renamed that runtime to `web_server.cjs` for host compatibility.
- `7ea151438a410f460630e4beead6fa2c4e8ee01f`, 2026-08-14 21:09 +02:00,
  added the dedicated public `127.0.0.1:8789` gateway, made public `/control`
  return 404, and retained the private `127.0.0.1:8788` gateway.
- `FINAL_SYSTEM_AUDIT.md` records the accepted runtime mapping as public
  Funnel `https://domai.tail1927bd.ts.net` to `127.0.0.1:8789` and a
  tailnet-only Serve route `:8443` to `127.0.0.1:8788`.

Git contains no historical `tailscale funnel`/`tailscale serve` command,
declarative Serve configuration, startup reconciliation, or reset command.
The mapping syntax used to establish the original state is therefore unknown;
the accepted mapping and boundary are proven, while the original mutation
command is not.

## Local and Tailscale runtime audit

Before any Tailscale mutation:

- backend `http://127.0.0.1:8000/health`: HTTP 200;
- public gateway `http://127.0.0.1:8789/gateway-health`: HTTP 200;
- public gateway backend proxy `http://127.0.0.1:8789/health`: HTTP 200;
- public gateway PID 8844, Node command
  `operations/gateway/public_web_server.cjs`, started with the host on
  2026-08-23 20:50:19, listening only on `127.0.0.1:8789`;
- Supervisor remained private on `127.0.0.1:8787`.

Tailscale 1.102.2 was online as node `domai.tail1927bd.ts.net`. Its protected
Serve/Funnel JSON already contained the exact accepted state:

- HTTPS TCP 443;
- Web `domai.tail1927bd.ts.net:443` `/` proxy to
  `http://127.0.0.1:8789`;
- `AllowFunnel[domai.tail1927bd.ts.net:443] = true`;
- tailnet-only HTTPS 8443 proxy to `http://127.0.0.1:8788`, with no Funnel
  permission for 8443.

The configuration was therefore not missing when inspected. The exact
reconciler correctly returned NO-OP; no Tailscale mapping mutation was made.
Port 8443 was neither restored nor changed.

## DNS and public proof

During the audit, both Cloudflare `1.1.1.1` and Google `8.8.8.8` returned the
public Tailscale Funnel A/AAAA addresses. The Windows system resolver returned
the node's MagicDNS address, which was recorded separately and was not used as
public acceptance proof.

A no-proxy HTTPS request through ordinary public DNS returned:

- `/health`: HTTP 200;
- `/gateway-health`: HTTP 200;
- `/control`: HTTP 404;
- unauthenticated `/api/v1/auth/me`: HTTP 401.

TLS completed successfully. Supervisor and backend remained loopback-only.
The Codex sandbox's default HTTP proxy points at `127.0.0.1:9`; its initial
connection refusal was excluded from the result by the explicitly no-proxy
control.

## Regression window and root-cause confidence

The last durable known-good proof is the 2026-08-25 contract-sync acceptance,
which returned the current-shaped SYSTEM_META request through the public HTTPS
gateway. The first known-bad proof is the owner's later same-day phone DNS and
Android socket evidence. No tracked startup, backend reload, Supervisor reload,
WDAC workflow, or CHUNK22 script contains a Tailscale Serve/Funnel reset or
mutation. The Tailscale service and exact mapping were present when audited,
and public DNS/HTTPS had recovered before any mutation.

Consequently, the exact disappearing trigger cannot be proven. The observed
incident is classified as a transient public publication/node/control-plane or
resolver availability regression that self-recovered before runtime audit.
The durable product defect proven by Git is missing ingress drift detection
and reconciliation from the host startup design. It is not classified as a
deleted mapping, because runtime evidence contradicts that claim.

## Durability guard

Tracked, non-secret controls now provide:

- `operations/gateway/public-ingress-manifest.json`: exact public origin,
  port, loopback target, forbidden public control, and private-service
  boundary;
- `operations/gateway/check-public-ingress.ps1`: PowerShell 5.1-safe,
  read-only exact-map, local/public health, unexpected-Funnel, and public
  `/control` checks;
- `operations/gateway/reconcile-public-ingress.ps1`: exact-state NO-OP,
  restoration only when no public mapping/conflict exists, and fail-closed
  operator review for any conflict; it never uses `serve reset` or
  `funnel reset`;
- a source registration helper for the owned
  `NEXT Stabil - Public Ingress Reconcile` elevated logon task;
- a static contract regression and operator documentation.

The live exact check and reconciler NO-OP both pass. Automatic task
registration was not performed: the host security boundary rejected creating
a persistent elevated logon task without a separate exact authorization for
that privilege mechanism. The existing Docker startup task is limited and
cannot read the administrator-protected Tailscale LocalAPI pipe; it was not
privilege-expanded. A requested bounded Tailscale service restart was also
not executed because the current process could not open the protected service
control handle. No workaround was attempted.

Thus source-level reconciliation is ready and current ingress drift is
detectable, while live automatic startup registration and service-restart
proof remain explicit operational gates. No host reboot was performed.

## Safety and disposition

- Tailscale mapping changes: 0 (exact accepted state already present);
- public ports added: 0;
- firewall/router/NAT changes: 0;
- Supervisor/public backend exposure changes: 0;
- DB migrations/writes and business writes: 0;
- Qdrant writes/deletes, Gmail, n8n, model, backup-delete, WDAC changes: 0;
- Android rebuild/versionCode 38/stable publication: 0.

Android +37 remains the candidate at the unchanged canonical endpoint. Owner
must now repeat browser `/health` and application connectivity on the same
phone without Tailscale before Unified Assistant physical acceptance resumes.
