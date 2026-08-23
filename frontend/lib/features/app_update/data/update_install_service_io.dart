import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:open_filex/open_filex.dart';

import '../domain/app_update.dart';

class UpdateInstallDelegate {
  UpdateInstallDelegate(this._dio);

  final Dio _dio;

  Future<String> downloadAndVerify(
    UpdateCheckResult result, {
    void Function(int received, int total)? onProgress,
    void Function()? onVerifying,
  }) async {
    final UpdatePlatformRelease? release = result.release;

    if (release == null || !release.available) {
      throw StateError('No update release is available for this platform.');
    }

    final String expectedSha = (release.sha256 ?? '').trim().toUpperCase();

    if (!RegExp(r'^[0-9A-F]{64}$').hasMatch(expectedSha)) {
      throw const FormatException(
        'Update manifest contains an invalid SHA256 value.',
      );
    }

    final Uri uri = validateStableUpdateUrl(
      platform: result.platform,
      url: release.url,
    );

    if (uri.pathSegments.isEmpty) {
      throw const FormatException('Update URL does not contain a file name.');
    }

    final String fileName = uri.pathSegments.last.trim();

    if (fileName.isEmpty) {
      throw const FormatException('Update file name is empty.');
    }

    _validateInstallerExtension(platform: result.platform, fileName: fileName);

    final Directory tempDirectory = await Directory.systemTemp.createTemp(
      'next_stabil_update_',
    );

    final String filePath =
        '${tempDirectory.path}${Platform.pathSeparator}$fileName';

    try {
      await _dio.download(
        release.url,
        filePath,
        deleteOnError: true,
        onReceiveProgress: onProgress,
        options: Options(
          followRedirects: true,
          receiveTimeout: const Duration(minutes: 10),
        ),
      );

      final File file = File(filePath);

      if (!await file.exists()) {
        throw StateError('Downloaded update file does not exist.');
      }

      onVerifying?.call();

      await verifyFileSha256(filePath, expectedSha);

      return filePath;
    } catch (_) {
      try {
        if (await tempDirectory.exists()) {
          await tempDirectory.delete(recursive: true);
        }
      } catch (_) {
        // Best-effort cleanup only.
      }

      rethrow;
    }
  }

  Future<void> launchInstaller(String filePath) async {
    final File file = File(filePath);

    if (!await file.exists()) {
      throw StateError('Update installer file no longer exists.');
    }

    if (Platform.isWindows) {
      final Process process = await Process.start(
        filePath,
        const <String>[],
        mode: ProcessStartMode.detached,
      );

      if (process.pid <= 0) {
        throw StateError('Windows installer could not be started.');
      }

      await Future<void>.delayed(const Duration(milliseconds: 700));

      exit(0);
    }

    if (Platform.isAndroid) {
      final OpenResult result = await OpenFilex.open(
        filePath,
        type: 'application/vnd.android.package-archive',
      );

      if (result.type != ResultType.done) {
        throw StateError(
          'Android installer could not be opened: ${result.message}',
        );
      }

      return;
    }

    throw UnsupportedError(
      'Native update installation is supported only on Windows and Android.',
    );
  }
}

Uri validateStableUpdateUrl({
  required AppUpdatePlatform platform,
  required String url,
}) {
  final Uri uri = Uri.parse(url.trim());
  final String requiredPrefix = switch (platform) {
    AppUpdatePlatform.windows => '/updates/stable/windows/',
    AppUpdatePlatform.android => '/updates/stable/android/',
    AppUpdatePlatform.web || AppUpdatePlatform.unsupported =>
      throw UnsupportedError('Native update URL is not supported.'),
  };

  if (uri.hasScheme ||
      uri.hasAuthority ||
      uri.hasQuery ||
      uri.hasFragment ||
      !uri.path.startsWith(requiredPrefix) ||
      uri.pathSegments.any((String segment) => segment == '..')) {
    throw const FormatException(
      'Update URL must be a canonical stable-channel relative path.',
    );
  }

  return uri;
}

Future<String> calculateFileSha256(String filePath) async {
  final File file = File(filePath);

  if (!await file.exists()) {
    throw StateError('File does not exist: $filePath');
  }

  final Digest digest = await sha256.bind(file.openRead()).first;

  return digest.toString().toUpperCase();
}

Future<void> verifyFileSha256(String filePath, String expectedSha256) async {
  final String expected = expectedSha256.trim().toUpperCase();

  if (!RegExp(r'^[0-9A-F]{64}$').hasMatch(expected)) {
    throw const FormatException('Expected SHA256 value is invalid.');
  }

  final String actual = await calculateFileSha256(filePath);

  if (actual != expected) {
    throw StateError(
      'SHA256 verification failed. Expected $expected but received $actual.',
    );
  }
}

void _validateInstallerExtension({
  required AppUpdatePlatform platform,
  required String fileName,
}) {
  final String lower = fileName.toLowerCase();

  switch (platform) {
    case AppUpdatePlatform.windows:
      if (!lower.endsWith('.exe')) {
        throw const FormatException(
          'Windows update file must use the .exe extension.',
        );
      }
      return;

    case AppUpdatePlatform.android:
      if (!lower.endsWith('.apk')) {
        throw const FormatException(
          'Android update file must use the .apk extension.',
        );
      }
      return;

    case AppUpdatePlatform.web:
    case AppUpdatePlatform.unsupported:
      throw UnsupportedError(
        'Native installer is not available for this platform.',
      );
  }
}
