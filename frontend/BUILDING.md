# AI-Lab multi-platform builds

The Flutter client supports one compile-time API endpoint:

`API_BASE_URL`

This makes the same codebase usable as:

- Windows desktop
- Android
- Web/PWA

## Development defaults

Without `API_BASE_URL`:

- Windows/Web/iOS: `http://127.0.0.1:8000`
- Android emulator: `http://10.0.2.2:8000`

Android debug explicitly allows cleartext HTTP for the emulator.

These defaults are development-only. Android release/profile builds fail during
Gradle configuration unless `API_BASE_URL` is explicitly supplied as a safe
HTTPS URL. `localhost`, `127.0.0.1`, `::1`, and `10.0.2.2` are rejected. A
direct `flutter build apk` without the audited dart defines is therefore not an
acceptance artifact.

Release Android has INTERNET permission but does not explicitly enable
cleartext traffic. Remote production builds should therefore use HTTPS.

## Windows / Android / Web release

From the `frontend` directory:

```powershell
.\scripts\build-release.ps1 `
    -ApiBaseUrl "https://YOUR-AI-LAB-HOST" `
    -SupervisorBaseUrl "https://YOUR-PRIVATE-AI-LAB-HOST" `
    -Platform all `
    -Version "1.0.0" `
    -BuildNumber 1
```

Individual builds:

```powershell
.\scripts\build-release.ps1 `
    -ApiBaseUrl "https://YOUR-AI-LAB-HOST" `
    -SupervisorBaseUrl "https://YOUR-PRIVATE-AI-LAB-HOST" `
    -Platform windows `
    -Version "1.0.2" `
    -BuildNumber 29 `
    -AcceptedNativeRoot "C:\OPERATOR-CONTROLLED\accepted-native" `
    -WindowsStagingRoot "C:\ISOLATED\windows-staging"

.\scripts\build-release.ps1 `
    -ApiBaseUrl "https://YOUR-AI-LAB-HOST" `
    -SupervisorBaseUrl "https://YOUR-PRIVATE-AI-LAB-HOST" `
    -Platform android `
    -Version "1.0.2" `
    -BuildNumber 34 `
    -AndroidCandidateLabel "candidate"

.\scripts\build-release.ps1 `
    -ApiBaseUrl "https://YOUR-AI-LAB-HOST" `
    -SupervisorBaseUrl "https://YOUR-PRIVATE-AI-LAB-HOST" `
    -Platform web
```

Outputs:

- Windows: versioned installer and manifests below the explicit isolated
  `WindowsStagingRoot`
- Android compiler output: `build/app/outputs/flutter-apk/app-release.apk`
- Android owner-facing, SHA-verified candidate copy:
  `..\staging\android\NEXT-Stabil-<version>+<build>-<label>.apk`
- Web: `build/web`

## Windows WDAC acceptance boundary

`flutter build windows` still produces compiler output at
`build/windows/x64/runner/Release`, but that directory is **not** a release or
acceptance artifact on the WDAC-managed host. Hash-normalizing the two pinned
native plug-ins does not establish execution trust. Do not launch its
`frontend.exe` as a Windows acceptance smoke.

The only supported Windows release path is:

1. `operations/installer/windows/build-windows-release.ps1` compiles Flutter,
   records the fresh payload, verifies and stages the two accepted native
   hashes, and builds the NSIS installer.
2. Install the resulting artifact through the approved user-scope installation
   path.
3. Run `operations/installer/windows/assert-windows-acceptance-ready.ps1`
   against the registered installed root. The gate fails closed if native
   hashes differ or Managed Installer evidence is absent.
4. Launch only that installed payload and audit Code Integrity events 3033 and
   3077 after the smoke.

The pre-launch gate is necessary but not sufficient: absence of a Bad Image
dialog and absence of new relevant Code Integrity events are both required.

## Remote access target

Production remote clients should use one HTTPS address shared by all builds.

Planned topology:

Client device
-> private encrypted network
-> HTTPS host
-> AI-Lab frontend/API
-> backend services remain private

Do not expose PostgreSQL, Qdrant, Ollama or n8n directly to the Internet.

## Android acceptance diagnostics

For a bounded, non-stable Android transport diagnostic, add
`-AndroidAuthDiagnostics` to an Android-only canonical build. The login surface
then shows only the effective API URL, configuration source, build mode and
bounded `/health`/auth classifications. It never renders credentials, tokens,
headers or response bodies. Do not enable this flag for a stable publication.
