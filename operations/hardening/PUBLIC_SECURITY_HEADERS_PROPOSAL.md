# Public security-header proposal (audit only)

No public header, Tailscale, gateway, CORS, firewall or port setting was changed
during the CHUNK 17 operational gates. The live HTTPS root currently returns
`Cache-Control`, `Date`, `Content-Length` and `Content-Type`, but not HSTS,
`X-Content-Type-Options`, `Referrer-Policy`, framing protection or CSP.

## Staged proposal

| Header | Proposed first stage | Risk / compatibility |
| --- | --- | --- |
| `X-Content-Type-Options` | `nosniff` | Low risk. Verify JS, WASM, fonts, APK and EXE MIME responses before rollout. |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Low risk. Cross-origin diagnostics lose path/query details by design. |
| Framing | `Content-Security-Policy: frame-ancestors 'none'` (or `X-Frame-Options: DENY` as a legacy fallback) | Medium risk if any approved embedding exists. Test login, dialogs and all Flutter routes; do not send conflicting policies. |
| HSTS | Start with `max-age=86400`, without `preload`; extend only after validation | Medium risk because browsers cache it. Confirm the public hostname and every affected subdomain remain HTTPS-only before considering `includeSubDomains`. |
| CSP | Report-only policy first; enforcement only after browser matrix PASS | Highest compatibility risk for Flutter Web scripts, service workers, WASM/CanvasKit, workers, fonts, `blob:`/`data:` assets and production API connections. |

## Compatibility test plan

Test the exact live Flutter Web build at widths 360, 390, 600 and 1200 in Edge
and Chrome. Cover login/session refresh, document upload/download, Vision state,
Agent, service-worker update, CanvasKit/WASM rendering, fonts/assets, deep links
and browser Back. Capture report-only CSP violations without customer content.
The Tailscale HTTPS proxy must be checked because headers originate at the
gateway but HSTS is cached against the public hostname.

## Rollback

Keep a copy of the prior gateway source and task configuration. Revert only the
header change, restart the public gateway task, verify Web/API/update hashes and
repeat the browser smoke. HSTS cannot be instantly removed from browsers that
already cached a non-zero `max-age`; the short first-stage lifetime limits this
risk. Do not use `preload` in the first stage.

The missing headers are defense-in-depth findings in the current loopback plus
Tailscale deployment. They still warrant a separately approved staged change,
especially framing protection, but this audit found no evidence requiring an
unreviewed emergency public-configuration mutation.
