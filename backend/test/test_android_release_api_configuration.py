from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_android_gradle_fails_closed_without_safe_release_api_url() -> None:
    source = (ROOT / "frontend/android/app/build.gradle.kts").read_text(
        encoding="utf-8"
    )
    assert 'gradleProperty("dart-defines")' in source
    assert 'decodedDartDefines()["API_BASE_URL"]' in source
    assert "ANDROID_RELEASE_API_CONFIGURATION_INVALID" in source
    assert 'host !in setOf("10.0.2.2", "127.0.0.1", "localhost", "::1")' in source


def test_canonical_release_script_supplies_api_and_optional_diagnostics() -> None:
    source = (ROOT / "frontend/scripts/build-release.ps1").read_text(
        encoding="utf-8"
    )
    assert '"--dart-define=API_BASE_URL=$ApiBaseUrl"' in source
    assert '"--dart-define=ANDROID_AUTH_DIAGNOSTICS=true"' in source
    assert 'throw "Release API URL must use HTTPS"' in source
    assert 'flutter build apk @commonArguments' in source
