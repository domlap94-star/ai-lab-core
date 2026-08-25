# P0 Windows Bad Image / WDAC hotfix audit

Date: 2026-08-25

Source HEAD: `a747f0d9225199af3c76fa9f71ccba0eb98dfc71`

Stable: NEXT Stabil `1.0.2+29` (unchanged)

Status: **RESOLVED — installed-current-source trust PASS; stable +29 restored**

## Observed failure and preserved evidence

The owner reported Bad Image status `0xc0e90002` while launching
`frontend/build/windows/x64/runner/Release/frontend.exe`. The exact failing
`geolocator_windows_plugin.dll` was captured before any rebuild:

- bytes: 151,040;
- SHA-256: `6C6B2B8FF8079CCB23DB375E5BEF561F7A3F8A3C4DFC54730BEEAC1AFF405898`;
- PE timestamp: `2026-08-22T09:04:05Z`;
- created: `2026-08-17T12:42:10.9640028Z`;
- last written: `2026-08-22T09:04:04Z`;
- file/product version: absent;
- Authenticode: not signed;
- Zone.Identifier: absent.

The adjacent `permission_handler_windows_plugin.dll` was 120,320 bytes with
SHA-256 `5CC6D938143C687690A3B697C05EC7A50B76C0156D34E2439BD0C90AFE3CDA2A`,
PE timestamp `2026-08-22T09:04:12Z`, no version, no signature and no
Zone.Identifier. Both hashes exactly match the CHUNK21 accepted-native
manifest.

Code Integrity Operational events at `2026-08-25T00:24:22+02:00` prove the
geolocator denial:

- 3033 record 51044: requested signing level 2, validated level 1;
- 3077 record 51046: status `0xc0e90002`, flat SHA-256 equal to the pinned
  value, policy `VerifiedAndReputableDesktop`, GUID
  `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`, policy ID
  `27555.1000.240208` and policy hash
  `2668895A5B233A80432D00D67251D7B7F52686A3FB13780F4B242C5A1F937A01`.

No WDAC, Code Integrity or antivirus setting was changed.

## Root cause

Classification: **E plus B — current WDAC policy state changed after the
historical smoke, and canonical staging normalization never established raw
execution trust.**

CHUNK21 built and smoked on 2026-08-23 before Code Integrity event 3099 at
`2026-08-23T20:50:05+02:00` refreshed and activated the relevant policy. The
Unified Assistant work then ran a direct `flutter build windows`, copied the
two pinned DLLs into the repository Release directory, and called the smoke a
pass because the process stayed alive. It did not inspect a Bad Image dialog or
query Code Integrity afterward. A later Flutter build could also overwrite
that directory because normalization was manual rather than canonical.

The installed +29 copies have the same native hashes but additionally carry
`$KERNEL.SMARTLOCKER.ORIGINCLAIM` and
`$KERNEL.PURGE.SMARTLOCKER.VALID`, tied to the CHUNK21 NSIS installer. The raw
repository copy has only a Code Integrity evaluation cache entry. A bounded
installed +29 launch loaded both native modules and produced zero new relevant
3033/3077 events. This proves the current distinction is installation trust,
not DLL content or a changed plugin dependency.

The Unified Assistant source range `9794932d..a747f0d` changed no pubspec,
pubspec lock, Windows CMake/plugin registration or native Windows source.
Plugin versions remain geolocator_windows 0.2.5 and
permission_handler_windows 0.2.2.

## Hardened build and acceptance rule

The repository now enforces one Windows release route:

- `frontend/scripts/build-release.ps1` delegates Windows work to
  `operations/installer/windows/build-windows-release.ps1` and requires an
  explicit accepted-native root and isolated staging root;
- direct Flutter output is not reported as a release artifact;
- build manifests explicitly record `INSTALLER_REQUIRED` and
  `raw_payload_launch_supported=false`;
- `assert-windows-acceptance-ready.ps1` rejects the repository build tree,
  non-installed staging, wrong native hashes and missing Managed Installer
  evidence;
- a successful pre-launch gate never replaces the mandatory post-launch
  3033/3077 audit.

The gate returns `WINDOWS_NATIVE_PAYLOAD_NOT_NORMALIZED` for hash mismatches
and `WINDOWS_NATIVE_PAYLOAD_NOT_INSTALLER_TRUSTED` for raw/staging paths or
missing installation trust. Unknown native DLLs are not normalized.

## Hardened two-build proof

Two fresh isolated builds C and D used the same source HEAD, Flutter inputs,
portable NSIS 3.12 and canonical script after hardening:

| Evidence | Build C | Build D |
| --- | --- | --- |
| fresh geolocator | `E340B771243AF19C3CA7AC30BBC247110A444DA5E4A2879A1B855AAEE222F151` | `AE79E6DA75C09A4F9B5B735A928140494D55C20BEC093E2D769352DD96B906E7` |
| fresh permission | `41C80CCA8EA5D0458AD9EAC8660886B859D3A66E52E32DD2CDD109A1CF5A2EF9` | `18DFF0085BC991DE9FBF9216ED1DA2F5005D3373A7830334CC682C8920372440` |
| normalized geolocator | pinned value | pinned value |
| normalized permission | pinned value | pinned value |
| frontend.exe | `4051916E19AE5B094F09F4FACB00AA10566E0337BC5FD1ED81D482E8B1D65F8D` | same |
| data/app.so | `DD07157F75D719703D7C1D7709208046DDF4A35873B5B285DA472367D6EEC919` | same |
| normalized 21-file payload | byte-identical | byte-identical |
| installer | `0BAD067CC4FC0DCF4BE11CA9BFED7CF69F54EEB6997E0AA1F1738DFB2DEFA9EA` | same |
| installer bytes | 13,448,553 | 13,448,553 |
| launch readiness | INSTALLER_REQUIRED | INSTALLER_REQUIRED |

An attempted launch of isolated normalized staging was itself blocked by
Application Control before process creation. The current installed +29 gate
and native-module smoke pass, but that payload predates Unified Assistant.

## Owner-approved installed trust cycle

The owner explicitly authorized one diagnostic overwrite with mandatory
rollback. Before mutation the retained stable installer was independently
verified at 13,432,883 bytes, SHA-256
`46E8A4CD6D0A9A2B99A6C942990546AE8DC58A5DB8381EE056504EF8322E043D`,
ProductVersion `1.0.2` and FileVersion `1.0.2.29`. A recursive 22-file installed
hash manifest, NEXT Stabil uninstall metadata, shortcut targets and Managed
Installer attribute names were captured outside the repository. No uninstall
or data clear was performed.

The hardened build-D diagnostic installer then installed over the existing
user-scope location and exited 0. The installed payload matched source
`a747f0d9225199af3c76fa9f71ccba0eb98dfc71`:

- `frontend.exe`: `4051916E19AE5B094F09F4FACB00AA10566E0337BC5FD1ED81D482E8B1D65F8D`;
- `data/app.so`: `DD07157F75D719703D7C1D7709208046DDF4A35873B5B285DA472367D6EEC919`;
- geolocator and permission DLLs: exact pinned hashes.

The frontend and both native DLLs received SmartLocker origin/valid evidence.
The installed-root gate passed. The process remained alive after 12 seconds,
opened a normal `NEXT Stabil` window and loaded both native modules. No new
installed-path 3033/3077 event occurred after the exact boundaries (3033 record
51099; 3077 record 51051). Classification: **A — INSTALLED TRUST PASS**.

The trust-only automation did not enter credentials or click authenticated
pages. Dashboard, Clients, Assistant Sources, Backup, System Control, Mail and
Documents are therefore supported by unchanged source/API regressions, not
misreported as separately navigated during this cycle.

## Mandatory rollback

The stable installer ran from `finally` and exited 0. Final installed state is
the retained canonical public +29 payload:

- visible version: `NEXT Stabil 1.0.2+29`;
- `frontend.exe`: `5BD959A30CE176D5E484D41EF1B5BF51D0D9FD38F5F99F7219AA07446BDB0865`;
- `data/app.so`: `3928FDBA4031C22887D34C8D19211555CE9EC89F621697B8945C7E70E530332B`;
- both pinned native hashes: exact match;
- Managed Installer gate and both native module loads: PASS;
- new installed-path 3033/3077 events: 0.

The pre-cycle app.so came from the earlier CHUNK21 reproduction and was not
byte-identical to the retained public installer. Rollback intentionally
restored the retained canonical artifact. The final visible UI was the +29
login screen; no password was requested or logged.

Production safety: DB migrations 0; business writes 0; Qdrant writes/deletes
0/0; Gmail 0; n8n 0; model changes 0; backup deletion 0; WDAC changes 0; stable
publication 0. Android +33 source/artifact was not changed.

The Windows tooling regression test passes. Both canonical Windows builds
compiled the unchanged Unified Assistant source successfully. A separate
focused Flutter widget-test invocation produced no output because the existing
Flutter SDK lock was held/stale-looking; it was interrupted without deleting
the lock or modifying the cache. The previously committed Unified Assistant
backend/Flutter results remain historical evidence only and are not promoted
to a current Windows physical PASS.

Decision: `P0_WINDOWS_INSTALLED_TRUST_RESOLVED`.
