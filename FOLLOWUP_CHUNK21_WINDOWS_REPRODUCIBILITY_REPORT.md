# FOLLOW-UP CHUNK 21 — Windows Build Reproducibility

Date: 2026-08-23
Source HEAD audited: `b59b1209f0d324515e2319a091f23c9bd509a0ca`
Stable release: NEXT Stabil `1.0.2+29` (unchanged)
Status: **COMPLETE — ISOLATED REPRODUCIBILITY ACCEPTANCE PASS**

## Owner-approved portable NSIS delivery

The owner approved only the official SourceForge NSIS 3.12 portable ZIP, with
no installer, PATH, registry, package-manager or system-wide integration. The
first request used SourceForge's HTML `/download` landing endpoint and was saved
only to the approved per-user Downloads directory:

`C:\Users\domai\AppData\Local\NEXT Stabil\Tools\Downloads\nsis-3.12.zip`

The response did **not** match the approved artifact:

- expected bytes: `2,362,938`;
- actual bytes: `141,109`;
- expected SHA-256:
  `56581F90DB321581C5381193D796FFFCF2D24B2F8FED2160A6C6A3BAA67F2C4F`;
- actual SHA-256:
  `EE8B270F7EF03227D806DF1759C3C3DA20831C77938A3AD9F99316A049DFA6F1`;
- expected ZIP magic: `50 4B`;
- actual prefix: `<!doctype html><html class="no-j...`;
- Zone.Identifier: absent on the downloaded response.

This was correctly reclassified as `SOURCEFORGE_DOWNLOAD_LANDING_HTML`, not as
a changed or malicious NSIS archive. It was never extracted or executed and is
preserved as `nsis-3.12-sourceforge-landing.html`.

The owner-approved retry used Windows `curl.exe` with TLS verification, HTTP
failure handling, redirect following and bounded retries against the exact file
delivery endpoint:

`https://downloads.sourceforge.net/project/nsis/NSIS%203/3.12/nsis-3.12.zip`

The redirect remained HTTPS and terminated at SourceForge mirror host
`altushost-net.dl.sourceforge.net`. The delivered file is 2,362,938 bytes,
starts with ZIP magic `50 4B 03 04`, opens with a valid central directory,
contains 441 entries including `nsis-3.12/makensis.exe`, and has SHA-256
`56581F90DB321581C5381193D796FFFCF2D24B2F8FED2160A6C6A3BAA67F2C4F`.
That exactly matches the previously audited consistency value. It is not a
publisher-signed digest.

The ZIP was traversal-checked and extracted only to
`C:\Users\domai\AppData\Local\NEXT Stabil\Tools\NSIS\3.12`. The directory is
protected for `domai`, Administrators and SYSTEM without broad Users or
Authenticated Users write access. No installer, PATH, registry, package
manager or machine-wide integration was used. Root `makensis.exe` reports
`v3.12`, is 2,560 bytes, has SHA-256
`B043E554AFEFBFC56315669D0B4779793AEAE67F0F2A7A790E2EA91F05298EFF`,
and is not Authenticode-signed.

## Scope and safety result

This audit covers the Flutter Windows payload, native plug-ins, NSIS installer,
version metadata, WDAC evidence, build provenance, and update trust boundaries.
It installed only the approved portable per-user NSIS tree, produced two
isolated non-public builds, and performed raw and installed user-scope smokes.
It did not publish an artifact, write the stable manifest, weaken Code Integrity,
or mutate production data. CHUNK 22 and Release F were not started.

The repository now has a fail-closed, PowerShell 5.1-compatible staging build
script, an input-driven NSIS definition, a machine-readable manifest for the two
WDAC-accepted pinned DLLs, and a deterministic tooling test. The canonical
installer proof passed with portable NSIS 3.12 invoked by absolute path.

## Reproducibility classification

| Boundary | Result | Evidence / limitation |
| --- | --- | --- |
| Source checkout | PASS | Git HEAD and `pubspec.lock` identify source and plug-in packages. |
| Toolchain inventory | PASS | Exact installed paths/versions are recorded below. |
| Flutter compile | PASS | Two isolated builds from the same HEAD/config produced identical frontend, Dart AOT and asset bytes. |
| Native payload | PARTIAL | Fresh permission/geolocator relinks vary by PE/debug timestamps; all other fresh payload files were identical. |
| WDAC-accepted payload | PASS (hash identity) | Both accepted DLLs are pinned and verified by SHA-256 before staging. Their acceptance mechanism is not proven to be portable to another host/policy. |
| NSIS installer | PASS | NSIS 3.12 produced byte-identical installers from the two identical normalized payloads. |
| Version metadata | PASS | `pubspec` is validated; installer ProductVersion is 1.0.2 and FileVersion is 1.0.2.29. |
| Build hash manifest | PASS | Both builds emitted source/toolchain/fresh payload/normalized payload/installer metadata without secret values. |
| Functional reproducibility | PASS | Raw login/Dashboard and installed session-restored Dashboard passed; Bad Image absent and no new relevant WDAC block occurred. |
| Byte-for-byte reproducibility | PASS for this two-build normalized proof; not a universal guarantee | The two normalized payloads and installers were byte-identical. Fresh relinked plug-ins were not. |
| Publisher trust reproducibility | BLOCKED BY SEPARATE TRUST DECISION | Current Windows artifacts are not Authenticode-signed. |

## Current toolchain inventory

- Windows registry reports Windows 10 Pro, DisplayVersion `25H2`, build
  `26200.8894`. The build number is authoritative; the legacy product-name value
  is recorded without inferring a different edition label.
- Windows PowerShell: `5.1.26100.8894` at
  `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`.
- Flutter SDK: `C:\FlutterSDK-New\flutter`; SDK metadata records Flutter
  `3.44.8` stable, framework revision
  `058e0af2c2b57e369d905a03ac9748b0ebf543c6`, engine
  `0cd610717bde95fd88343c64f81c11ba4e5c0010`, Dart `3.12.2`.
- Visual Studio Community 2022: `17.14.37`, installation version
  `17.14.37516.0`, at
  `C:\Program Files\Microsoft Visual Studio\2022\Community`.
- MSVC toolsets present: `14.29.30133` and `14.44.35207`; the existing Windows
  build cache selected the x64 linker from `14.44.35207` (file version
  `14.44.35228.0`).
- Windows SDKs present include `10.0.22621.0` and `10.0.26100.0`. A future build
  manifest records the selected/latest discovered SDK; the current CMake cache
  does not preserve a conclusive target-platform version value.
- CMake: `3.31.6-msvc6`, Visual Studio bundled path.
- Ninja: `1.12.1`, Visual Studio bundled path.
- Git: `2.55.0.windows.3` at `C:\Program Files\Git\cmd\git.exe`.
- NSIS: portable `3.12` at
  `C:\Users\domai\AppData\Local\NEXT Stabil\Tools\NSIS\3.12\makensis.exe`;
  explicitly invoked, not on PATH and not registered system-wide.

`flutter.bat.lock` and `lockfile` were zero-byte, stale, exclusively openable,
and had no Flutter/Dart/Java/Gradle/CMake/Ninja owner. Those exact two files were
removed; no other cache content and no build output was cleaned. A remaining
sandbox-only lock denial was resolved by running the canonical Flutter command
with normal host permissions. `flutter --version` and Windows/VS/network doctor
checks then passed; the only doctor warning was an absent Chrome executable,
which is irrelevant to the Windows build.

## Portable NSIS acceptance

Gate `FOLLOWUP_HOST_TOOL_INSTALL_APPROVAL_REQUIRED` was consumed only for this
exact portable scope and passed delivery, structure, hash, extraction, ACL and
version verification.

- Version: NSIS `3.12`, released 2026-04-19. This is the current official stable
  release and contains a security fix for elevated installer temporary-directory
  handling.
- Publisher/source: NSIS project, official SourceForge distribution.
- Artifact: portable `nsis-3.12.zip`, 2,362,938 bytes.
- File endpoint:
  `https://downloads.sourceforge.net/project/nsis/NSIS%203/3.12/nsis-3.12.zip`
- Expected SHA-256:
  `56581F90DB321581C5381193D796FFFCF2D24B2F8FED2160A6C6A3BAA67F2C4F`.
- Signature: the official release page does not publish a detached signature
  for the Windows ZIP. The archive hash must be verified before extraction;
  this is integrity verification, not publisher signing.
- Installation: extracted only after hash verification to
  `C:\Users\domai\AppData\Local\NEXT Stabil\Tools\NSIS\3.12` and invoke
  `makensis.exe` by explicit absolute path.
- PATH impact: none. No Chocolatey, Winget, registry, service, or machine-wide
  installation is proposed.
- Rollback: remove only that versioned tool directory after confirming no build
  process uses it. No system uninstall or PATH rollback is needed.
- Selection rationale: official current stable release, security-relevant fix,
  portable/versioned deployment, and compatibility with the repository's
  standard MUI2/LZMA NSIS script.

No global toolchain state was changed. The prior landing-page response remains
diagnostic evidence rather than a binary artifact.

## Canonical Windows build inputs and script

`operations/installer/windows/build-windows-release.ps1` is the canonical
staging entry point. It:

1. requires version/build/API/Supervisor inputs and validates the exact
   `pubspec.yaml` version;
2. requires explicit Flutter, NSIS, accepted-native, and fresh staging paths;
3. rejects development API hosts for release builds;
4. runs `flutter pub get` and `flutter build windows --release` with explicit
   build name/number and the two named Dart defines;
5. copies the raw payload to a non-stable staging directory;
6. verifies each accepted native DLL before and after explicit substitution;
7. invokes NSIS with explicit version, payload, and output definitions;
8. emits `NEXT_STABIL_WINDOWS_BUILD_MANIFEST_V1` containing source HEAD,
   version, UTC, Flutter/Dart/VS/MSVC/SDK/CMake/Ninja/NSIS data, top-level
   payload hashes, and installer hash.

The script uses `throw` and `$LASTEXITCODE`, is PowerShell 5.1 compatible, and
does not invoke `flutter clean`. Dart-define **names**, but not values, enter the
build manifest. The stable release directory is never an implicit output.

`next-stabil.nsi` now fails compilation unless `APP_VERSION`, `APP_BUILD`,
`APP_FILE_VERSION`, `BUILD_PAYLOAD_DIR`, and `OUTPUT_FILE` are supplied. The
previous absolute `C:\ai-lab-core` input/output paths and hard-coded build 29
metadata are removed. Installer behavior (per-user installation, MUI, Unicode,
solid LZMA, shortcuts, uninstall registration) is otherwise unchanged.

One canonical version is still repeated in published runtime metadata
(`pubspec`, backend release configuration, and stable manifest). CHUNK 21 does
not alter stable version state. The new build script makes the Windows side
fail closed on mismatch; a phase-boundary release remains responsible for
updating the other canonical published-release fields.

## Native plug-in provenance and binary comparison

### permission_handler_windows_plugin.dll

- Direct dependency: `permission_handler 12.0.3`.
- Windows implementation: `permission_handler_windows 0.2.2`, pub lock
  checksum
  `caeae01858a0a7d2df67a445ac98e1ad95e55a0e77c73044f4e9b1c8c2289cbd`.
- Architecture: x64 PE.
- Accepted +29 SHA-256:
  `5CC6D938143C687690A3B697C05EC7A50B76C0156D34E2439BD0C90AFE3CDA2A`.
- Known WDAC-blocked relink SHA-256 flat hash:
  `D450D4D0DA34F887CDA1D09FAE40DBAD3440441AFECCA4AB79E21164DC6AA856`.
- Final acceptance build's fresh relink SHA-256:
  `5B0C389FC3A2E5D053B689BE98D9838DCAE108CF2E4F3F5379DF59971956516B`.
- Authenticode: not signed.
- Imports include Flutter Windows, MSVC runtime, CRT, KERNEL32, OLE32, and
  OLEAUT32.

### geolocator_windows_plugin.dll

- Direct dependency: `geolocator 14.0.3` (constraint `^14.0.2`).
- Windows implementation: `geolocator_windows 0.2.5`, pub lock checksum
  `175435404d20278ffd220de83c2ca293b73db95eafbdc8131fe8609be1421eb6`.
- Architecture: x64 PE.
- Accepted +29 SHA-256:
  `6C6B2B8FF8079CCB23DB375E5BEF561F7A3F8A3C4DFC54730BEEAC1AFF405898`.
- Final acceptance build's fresh relink SHA-256:
  `0117EDDABB83B06460C6A0660D462B3E4AE6CD8C0F2E11FC291B8C0626408F7D`.
- Authenticode: not signed.

Both accepted and current relinked DLL pairs have the same x64 architecture,
file/image sizes, linker version 14.44, imports, exports, section layout,
load-configuration security flags, and no Authenticode signature. For each
pair, byte comparison found only six changed bytes in two ranges: the COFF PE
timestamp and debug-directory timestamp. This proves why the **current** relink
hash differs from the accepted hash; it does not prove why the historical
`D450...` file was denied, because those exact historical bytes are no longer
available for full binary comparison.

Other top-level native payload files are `flutter_windows.dll`,
`file_selector_windows_plugin.dll`, `flutter_secure_storage_windows_plugin.dll`,
`speech_to_text_windows_plugin.dll`, `url_launcher_windows_plugin.dll`, and
`dartjni.dll`. The future build manifest records every top-level payload file's
size and SHA. No inspected +29 EXE/DLL/installer has an Authenticode signature.

The tracked `wdac-accepted-native-payload.json` contains metadata only. It calls
the files “WDAC-accepted pinned binaries,” not signed or universally trusted
binaries. Binaries remain outside Git. The build requires an explicit
operator-controlled native root, verifies its hashes, copies to isolated
staging, and re-verifies. A missing/mismatched file hard-fails; silent manual
substitution is eliminated.

## WDAC evidence

Observed enterprise policy GUID:
`{0283ac0f-fff1-49ae-ada1-8a933130cad6}` (`VerifiedAndReputableDesktop`).

Code Integrity event 3077 (record 48856, 2026-08-22 21:46 local) records:

- process: `frontend.exe`;
- blocked path: the Release runner's
  `permission_handler_windows_plugin.dll`;
- status: `0xc0e90002`;
- requested signing level 2, validated signing level 1;
- SHA-256 flat hash: the known `D450...` value;
- policy GUID matching the value above.

Associated 3033/3077 evidence confirms a Code Integrity denial. The logs do not
prove whether the accepted pinned bytes succeed due to reputation, catalog,
managed-installer state, hash policy, or another mechanism; the accepted
mechanism is therefore **UNKNOWN**. A read-only query after the final accepted
payload launch found zero later relevant block events. No WDAC/security policy
was changed.

## Isolated two-build and smoke acceptance

Both builds used source HEAD `b59b1209f0d324515e2319a091f23c9bd509a0ca`,
Flutter 3.44.8 / Dart 3.12.2, explicit production define names, portable NSIS
3.12, and per-user isolated staging outside the CHUNK20-protected release
channel. The stable manifest and retained release artifacts were not written.

| Evidence | Build 1 | Build 2 |
| --- | --- | --- |
| `frontend.exe` SHA-256 | `5BD959A30CE176D5E484D41EF1B5BF51D0D9FD38F5F99F7219AA07446BDB0865` | same |
| fresh permission DLL | `9A5D142291C7C51FAAB489B3127D5EAAC010E1B27375A8761C78E95462C4F842` | `5B0C389FC3A2E5D053B689BE98D9838DCAE108CF2E4F3F5379DF59971956516B` |
| fresh geolocator DLL | `4271D24FA934D9F6704AF29CE49E60AFEA56C6497584D2FB8DCEC602841EB1AE` | `0117EDDABB83B06460C6A0660D462B3E4AE6CD8C0F2E11FC291B8C0626408F7D` |
| normalized permission DLL | `5CC6D938143C687690A3B697C05EC7A50B76C0156D34E2439BD0C90AFE3CDA2A` | same |
| normalized geolocator DLL | `6C6B2B8FF8079CCB23DB375E5BEF561F7A3F8A3C4DFC54730BEEAC1AFF405898` | same |
| installer bytes | 13,430,801 | 13,430,801 |
| installer SHA-256 | `4E3F7DFF43DCEA64775B44388573F8F097A328258FBEDCFFC59565739D2B853B` | same |

The complete 21-file normalized payloads were byte-identical. Before
normalization, only the two freshly relinked plug-ins differed. Comparing the
current fresh files to the accepted files found exactly six byte changes per
DLL: the COFF timestamp and matching debug-directory timestamp. This explains
the current relink variance without claiming the historical WDAC policy reason.

The generated fresh and final JSON manifests include source HEAD, version,
UTC, Flutter/Dart/VS/MSVC/Windows SDK/CMake/Ninja/NSIS data, define names only,
all recursive payload sizes/hashes, accepted-native manifest binding and final
installer hash. No secret values are present. The two manifest files themselves
differ in their truthful build UTC and fresh native hashes; the normalized
payload and installer bytes do not.

The raw normalized application launched, showed version `1.0.2+29`, accepted
manual owner login and reached Dashboard. The isolated installer exited 0,
reported ProductVersion `1.0.2` and FileVersion `1.0.2.29`, installed to the
existing user-scope location, restored the authenticated session and reached
Dashboard. Its 21 installed payload files exactly matched the normalized
staging payload; the expected additional file was `Uninstall.exe`. Bad Image
was absent and new relevant Code Integrity events 3077/3033 were zero.

Compared with retained public +29, 20 of 21 application payload files match;
the two accepted native DLL hashes and version metadata match. `data/app.so`
differs because the retained public artifact was produced from the earlier
Release E source/build state. The retained public installer is 13,432,883 bytes
with SHA-256
`46E8A4CD6D0A9A2B99A6C942990546AE8DC58A5DB8381EE056504EF8322E043D`;
the reproduced installer is therefore not byte-identical to public +29, while
its normalized payload, install behavior and WDAC result are reproducible for
the current audited source/toolchain.

## Update and signing trust design

The current trust boundaries are separate:

- HTTPS/Tailscale protects transport to the configured endpoint.
- The stable manifest is not cryptographically authenticated independently of
  that transport.
- Manifest SHA-256 values prove downloaded-byte consistency only after the
  manifest itself is trusted.
- Android has package signer identity and platform-enforced update continuity.
- Windows +29 installer, `frontend.exe`, and native plug-ins have no
  Authenticode publisher identity.
- WDAC acceptance is an enterprise-policy decision and is not equivalent to
  Authenticode, HTTPS, or a manifest hash.

Options:

| Option | WDAC / publisher result | Operational consequence |
| --- | --- | --- |
| Commercial code-signing certificate | Strong public publisher identity; likely better SmartScreen reputation, but WDAC still needs a compatible publisher/reputation rule | Recurring cost, protected private-key custody, timestamping, rotation/revocation and recovery procedure |
| Enterprise/internal PKI certificate | Best fit for a controlled enterprise WDAC publisher rule; no public SmartScreen reputation outside managed devices | Enterprise CA/policy deployment, protected key, timestamping, renewal and offline recovery |
| Self-signed local certificate | No public publisher trust; works only after explicit trust/policy deployment | High per-device policy burden; not equivalent to public signing and not recommended as a shortcut |
| No signing / hash-only | Current model; integrity after trusting manifest, no publisher identity | Every changed binary hash may need reputation/policy acceptance; poor provenance and recovery characteristics |

Recommendation: use an enterprise/internal-PKI code-signing certificate if the
fleet remains policy-managed, with a WDAC publisher rule explicitly reviewed by
the owner/security administrator. Use a commercial code-signing certificate if
distribution must extend beyond the managed fleet. Sign the installer and
`frontend.exe`; treat third-party native DLL signing separately because
re-signing vendor-derived binaries changes their identity and provenance.

For manifest authenticity, use canonical JSON serialization plus a detached
signature, key ID/version, and a verification public key pinned in clients.
Clients must verify the signature before trusting URLs or SHA-256 values. Keep
the signing private key outside the repository, define offline escrow, rotation,
revocation, and dual-key transition. This is design only: no key, certificate,
certificate-store, timestamping, client verification, or manifest-signature
implementation occurred. Implementation still requires
`FOLLOWUP_UPDATE_SIGNING_TRUST_APPROVAL_REQUIRED`.

## Tests and acceptance

Passed:

- PowerShell 5.1 parser for the canonical script;
- fail-closed script/NSIS/static contract test;
- absolute workstation path rejection;
- native manifest schema/unique names/SHA format/trust wording;
- no `flutter clean` and no `exit N` in the shared build script;
- stable manifest remained build 29;
- SourceForge size/magic/central-directory/entry/SHA validation;
- portable NSIS version, hash, no-PATH/no-registry and protected ACL checks;
- two isolated Flutter Windows builds and two NSIS builds;
- full normalized payload and installer byte-identity across those builds;
- raw manual login/Dashboard smoke;
- installed session-restored Dashboard smoke;
- installed payload hash match and zero new relevant Code Integrity events;
- post-acceptance relevant Code Integrity block query returned zero events;
- `git diff --check` passed (line-ending warning only).

CHUNK20 ACL controls remain intact. The proposed build writes only to an
explicit pre-existing staging root and reads the explicit native source; it does
not require stable-channel writes or broad ACL rollback.

## Production safety verification

The canonical read-only health check passed after running with the required
Docker access: backend, Supervisor, Qdrant, Ollama, n8n, Open WebUI and Vision
are healthy; Vision is `READY` with zero queued/active jobs; the production DB
head is `followup_contact_person_20260822`; operational lock/stale-job checks are
zero; and the latest backup checkpoint remains fresh. Qdrant remains green at
57 customer points and 0 Knowledge Base points.

The stable manifest remains `1.0.2+29`, minimum `1.0.0`, SHA-256
`B45D01BE9DBEB077564A67F5521C0AB98BF3BF6AB19DD5AA3F522AA4F633F781`.
There were zero stable-manifest writes, business writes, migrations, Qdrant
writes/deletes, Gmail or n8n mutations, Vision production jobs, or real-customer
Temporary Chat jobs attributable to CHUNK 21.

## Owner gates

1. `FOLLOWUP_HOST_TOOL_INSTALL_APPROVAL_REQUIRED`: consumed only for the exact
   portable NSIS 3.12 scope and accepted.
2. **Not consumed:** `FOLLOWUP_UPDATE_SIGNING_TRUST_APPROVAL_REQUIRED` for
   certificate/key/manifest-signature implementation. Signing design is not
   required for the completed reproducibility proof and remains an explicit
   future trust decision.
