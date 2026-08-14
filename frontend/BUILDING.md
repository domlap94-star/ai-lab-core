# AI-Lab multi-platform builds

The Flutter client supports one compile-time API endpoint:

`API_BASE_URL`

This makes the same codebase usable as:

- Windows desktop
- Android
- Web/PWA
- iOS

## Development defaults

Without `API_BASE_URL`:

- Windows/Web/iOS: `http://127.0.0.1:8000`
- Android emulator: `http://10.0.2.2:8000`

Android debug explicitly allows cleartext HTTP for the emulator.

Release Android has INTERNET permission but does not explicitly enable
cleartext traffic. Remote production builds should therefore use HTTPS.

## Windows / Android / Web release

From the `frontend` directory:

```powershell
.\scripts\build-release.ps1 `
    -ApiBaseUrl "https://YOUR-AI-LAB-HOST" `
    -Platform all `
    -Version "1.0.0" `
    -BuildNumber 1
```

Individual builds:

```powershell
.\scripts\build-release.ps1 `
    -ApiBaseUrl "https://YOUR-AI-LAB-HOST" `
    -Platform windows

.\scripts\build-release.ps1 `
    -ApiBaseUrl "https://YOUR-AI-LAB-HOST" `
    -Platform android

.\scripts\build-release.ps1 `
    -ApiBaseUrl "https://YOUR-AI-LAB-HOST" `
    -Platform web
```

Outputs:

- Windows: `build/windows/x64/runner/Release`
- Android APK: `build/app/outputs/flutter-apk/app-release.apk`
- Web: `build/web`

## iOS

iOS cannot be compiled or signed on Windows.

The Flutter iOS project and launcher icons are prepared in this repository.
On a Mac with Flutter and Xcode:

```bash
./scripts/build-ios.sh \
  "https://YOUR-AI-LAB-HOST" \
  "1.0.0" \
  "1"
```

Then open `ios/Runner.xcworkspace` in Xcode for signing/archive.

## Remote access target

Production remote clients should use one HTTPS address shared by all builds.

Planned topology:

Client device
-> private encrypted network
-> HTTPS host
-> AI-Lab frontend/API
-> backend services remain private

Do not expose PostgreSQL, Qdrant, Ollama or n8n directly to the Internet.
