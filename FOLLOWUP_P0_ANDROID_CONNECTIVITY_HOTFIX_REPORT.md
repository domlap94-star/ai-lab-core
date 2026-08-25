# P0 Android release connectivity hotfix

Date: 2026-08-25

## Owner evidence and scope

On the same physical Android phone, the browser returned HTTP 200 with
`{"status":"ok"}` from `https://domai.tail1927bd.ts.net/health`, while the
installed non-stable +33 application reported a startup-session transport
failure and could not log in. This proves phone-to-public-backend reachability
and leaves the application transport/configuration boundary as the P0 blocker.
PRE-CHUNK23 physical acceptance remains blocked; CHUNK23 was not started.

## +33 provenance audit

The exact +33 APK is 67,316,719 bytes with SHA-256
`C70E6EF82C8847DED6911F3E57FFE11D0A4D6581249A1C5A420C5F7F78F08725`.
Its package is `pl.ailab.app`, version is `1.0.2+33`, signer is the canonical
NEXT Stabil certificate, v2 signing verifies, `debuggable` is false/absent and
cleartext is disabled.

The exact command which created +33 was not durably recorded, so canonical
script use cannot be claimed. Binary inspection nevertheless proves that the
canonical HTTPS API URL is compiled into +33. Both +32 and +33 contain that URL
and the development fallback string; the latter remains in AOT because the
debug fallback code is part of the program and is not evidence that it was the
selected runtime value. The source diff from the +32 build HEAD to the +33
Unified Assistant HEAD changes no API, auth, Android manifest, network-security,
dependency or release-script source; only application routing changed in the
transport-relevant slice. Their Android permission/manifests match apart from
version/build output.

Consequently, the proposed simple explanation “+33 omitted API_BASE_URL and
used 10.0.2.2” is not supported by the artifact. The exact low-level +33 Dio
exception is unavailable because the stable-safe diagnostic removed after +28
was not present. The remaining runtime cause is therefore bounded to an
application transport failure (socket/TLS/timeout/HTTP/schema) that +33 cannot
classify. This mirrors the earlier transient +27 incident and must be resolved
by physical +34 diagnostics rather than by guessing.

`SUPERVISOR_BASE_URL` is still supplied by the canonical build for compatibility,
but current Android auth/session traffic uses the public API Dio client and does
not contact Supervisor directly.

## Fail-closed fix and safe diagnostics

Release/profile API configuration now fails closed in two layers:

1. Android Gradle decodes `dart-defines` and rejects a missing, non-HTTPS,
   credential-bearing or development-host `API_BASE_URL` before compilation.
2. `ApiConfig` independently rejects the same invalid state at runtime; debug
   builds retain the emulator/loopback development fallbacks.

A direct Gradle negative control without `API_BASE_URL` failed during project
configuration with `ANDROID_RELEASE_API_CONFIGURATION_INVALID`. The canonical
HTTPS value passes unit validation.

The previous proven diagnostic design was restored behind the non-stable-only
`ANDROID_AUTH_DIAGNOSTICS` compile flag. It shows the effective complete API
base URL, configuration source and build mode, and can issue `/health` through
the same Dio instance used by auth. Startup session and fresh login record only
bounded path/status/Dio/transport/result classifications. It never renders
credentials, tokens, request headers, response bodies or low-level error text.

The canonical Android script now requires HTTPS, supports the explicit
diagnostic flag, and always copies the completed APK into `staging/android`
with a source/copy SHA-256 equality check. Direct unaudited `flutter build apk`
output is documented as non-acceptance evidence.

## +34 candidate

Canonical command inputs:

- platform: `android`
- API: `https://domai.tail1927bd.ts.net`
- Supervisor compatibility URL:
  `https://domai.tail1927bd.ts.net:8443/control`
- version/build: `1.0.2+34`
- diagnostics: enabled

Owner-facing artifact:

`C:\ai-lab-core\staging\android\NEXT-Stabil-1.0.2+34-android-auth-hotfix-candidate.apk`

- bytes: 67,398,751
- SHA-256:
  `9453C7B072BA967F45CB228ED923BE6B65417771648D6426D286E1E23CC00CD5`
- application ID: `pl.ailab.app`
- versionName/versionCode: `1.0.2` / `34`
- signer SHA-256:
  `5e223da2da7c893d089d7333e99aaeee8d98c9cdf72be80609020967368fe018`
- v2 signature: verified
- debuggable: false/absent
- cleartext: false
- canonical API URL in arm64 AOT: yes
- diagnostics marker in arm64 AOT: yes
- published: no

## Verification and current disposition

- Flutter analyze: PASS, no issues.
- Focused config/auth/session regression: 17/17 PASS.
- Full Flutter suite: 302/302 PASS.
- Isolated network-disabled backend-image source contract: PASS.
- Gradle missing-define negative control: PASS (rejected as designed).
- Canonical signed +34 build and SHA-verified staging copy: PASS.
- Current public `/health`: HTTP 200.
- Current unauthenticated `/api/v1/auth/me`: HTTP 401, as expected.
- ADB device: unavailable; +34 physical result: pending owner install over +33.

No DB/business/Qdrant/Gmail/n8n/model/backup-delete/network configuration or
stable publication change occurred. VersionCode 34 is consumed by this
non-stable candidate.

## Owner physical +34 result — 2026-08-25

The owner installed +34 on the same physical Android device and observed the
explicit canonical API URL, application `/health` HTTP 200, retained
`/api/v1/auth/me` HTTP 401, and a successful fresh login/Dashboard. The old
token was expired; phone-to-backend transport was functional. The +33 generic
connection message was therefore misleading rather than evidence of a lasting
network outage.

`P0 ANDROID CONNECTIVITY = RESOLVED`. Low-level details remain compile-time
gated to non-stable diagnostics. No token, response body, credential, or raw
transport secret is exposed.
