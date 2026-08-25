# NEXT Stabil public ingress

`public-ingress-manifest.json` is the non-secret source of truth for the
historically approved public boundary:

- public HTTPS `https://domai.tail1927bd.ts.net` is Tailscale Funnel on port
  443 and proxies only to `http://127.0.0.1:8789`;
- the public gateway must return 404 for `/control` and `/control/`;
- backend `127.0.0.1:8000`, Supervisor `127.0.0.1:8787`, and the private
  gateway `127.0.0.1:8788` remain loopback-only;
- the historical tailnet-only Serve mapping on port 8443 is documented but is
  deliberately outside public reconciliation.

Run `check-public-ingress.ps1` from an elevated PowerShell 5.1 process for a
read-only drift and boundary check. `reconcile-public-ingress.ps1` is
idempotent: an exact mapping is a no-op; a completely absent public mapping is
restored to the single approved target; any conflicting or unexpected public
mapping fails closed. It never calls `serve reset` or `funnel reset`.

`register-public-ingress-reconciliation.ps1` installs the owned, elevated,
logon-triggered `NEXT Stabil - Public Ingress Reconcile` task. Elevation is
required because the local Tailscale API pipe is administrator-protected on
this host. The existing limited Docker startup task must not be promoted just
to gain that access.
