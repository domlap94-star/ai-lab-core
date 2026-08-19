import 'package:ai_lab/features/app_update/domain/app_update.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('UpdateDecisionEngine', () {
    test('reports current when version and build match', () {
      final UpdateCheckResult result = UpdateDecisionEngine.evaluate(
        currentVersion: '1.0.0',
        currentBuildNumber: 2,
        manifest: _manifest(
          version: '1.0.0',
          buildNumber: 2,
          minimumVersion: '1.0.0',
        ),
        platform: AppUpdatePlatform.windows,
      );

      expect(result.state, AppUpdateState.current);
      expect(result.latestDisplayVersion, '1.0.0+2');
    });

    test('reports available when build number is newer', () {
      final UpdateCheckResult result = UpdateDecisionEngine.evaluate(
        currentVersion: '1.0.0',
        currentBuildNumber: 2,
        manifest: _manifest(
          version: '1.0.0',
          buildNumber: 3,
          minimumVersion: '1.0.0',
        ),
        platform: AppUpdatePlatform.windows,
      );

      expect(result.state, AppUpdateState.available);
    });

    test('reports available when semantic version is newer', () {
      final UpdateCheckResult result = UpdateDecisionEngine.evaluate(
        currentVersion: '1.2.0',
        currentBuildNumber: 50,
        manifest: _manifest(
          version: '1.10.0',
          buildNumber: 1,
          minimumVersion: '1.0.0',
        ),
        platform: AppUpdatePlatform.windows,
      );

      expect(result.state, AppUpdateState.available);
    });

    test('reports required below minimum supported version', () {
      final UpdateCheckResult result = UpdateDecisionEngine.evaluate(
        currentVersion: '0.9.9',
        currentBuildNumber: 99,
        manifest: _manifest(
          version: '1.0.0',
          buildNumber: 2,
          minimumVersion: '1.0.0',
        ),
        platform: AppUpdatePlatform.windows,
      );

      expect(result.state, AppUpdateState.required);
    });

    test('reports unsupported for unsupported native platform', () {
      final UpdateCheckResult result = UpdateDecisionEngine.evaluate(
        currentVersion: '1.0.0',
        currentBuildNumber: 2,
        manifest: _manifest(
          version: '1.0.0',
          buildNumber: 2,
          minimumVersion: '1.0.0',
        ),
        platform: AppUpdatePlatform.unsupported,
      );

      expect(result.state, AppUpdateState.unsupported);
    });

    test('parses production manifest shape', () {
      final UpdateManifest manifest = UpdateManifest.fromJson(<String, dynamic>{
        'channel': 'stable',
        'version': '1.0.0',
        'build_number': 2,
        'minimum_version': '1.0.0',
        'published_at': '2026-08-14T12:26:32Z',
        'platforms': <String, dynamic>{
          'web': <String, dynamic>{'available': true, 'url': '/'},
          'windows': <String, dynamic>{
            'available': true,
            'url': '/updates/stable/windows/app.exe',
            'sha256': 'ABC',
          },
          'android': <String, dynamic>{
            'available': true,
            'url': '/updates/stable/android/app.apk',
            'sha256': 'DEF',
          },
        },
      });

      expect(manifest.channel, 'stable');
      expect(manifest.buildNumber, 2);
      expect(manifest.releaseFor(AppUpdatePlatform.windows)?.available, isTrue);
    });

    test('rejects malformed manifest newer minimum version', () {
      expect(
        () => UpdateManifest.fromJson(<String, dynamic>{
          'channel': 'stable',
          'version': '1.0.2',
          'build_number': 21,
          'minimum_version': '2.0.0',
          'published_at': '2026-08-19T05:00:00Z',
          'platforms': <String, dynamic>{
            'web': <String, dynamic>{'available': true, 'url': '/'},
          },
        }),
        throwsFormatException,
      );
    });

    test('rejects malformed manifest build type', () {
      expect(
        () => UpdateManifest.fromJson(<String, dynamic>{
          'channel': 'stable',
          'version': '1.0.2',
          'build_number': '21',
          'minimum_version': '1.0.0',
          'published_at': '2026-08-19T05:00:00Z',
          'platforms': <String, dynamic>{
            'web': <String, dynamic>{'available': true, 'url': '/'},
          },
        }),
        throwsFormatException,
      );
    });
  });
}

UpdateManifest _manifest({
  required String version,
  required int buildNumber,
  required String minimumVersion,
}) {
  return UpdateManifest(
    channel: 'stable',
    version: version,
    buildNumber: buildNumber,
    minimumVersion: minimumVersion,
    publishedAt: DateTime.utc(2026, 8, 14),
    platforms: const <AppUpdatePlatform, UpdatePlatformRelease>{
      AppUpdatePlatform.windows: UpdatePlatformRelease(
        available: true,
        url: '/updates/windows/app.exe',
        sha256: 'ABC',
      ),
      AppUpdatePlatform.android: UpdatePlatformRelease(
        available: true,
        url: '/updates/android/app.apk',
        sha256: 'DEF',
      ),
      AppUpdatePlatform.web: UpdatePlatformRelease(
        available: true,
        url: '/',
        sha256: null,
      ),
    },
  );
}
