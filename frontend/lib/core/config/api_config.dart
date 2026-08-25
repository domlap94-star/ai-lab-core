import 'package:flutter/foundation.dart';

class ApiConfig {
  ApiConfig._();

  static const String _definedBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: '',
  );

  static const bool diagnosticsEnabled = bool.fromEnvironment(
    'ANDROID_AUTH_DIAGNOSTICS',
    defaultValue: false,
  );

  static String get baseUrl {
    final String defined = _normalizeBaseUrl(_definedBaseUrl);

    if (defined.isNotEmpty) {
      if ((kReleaseMode || kProfileMode) && !isSafeReleaseBaseUrl(defined)) {
        throw StateError(
          'ANDROID_RELEASE_API_CONFIGURATION_INVALID: API_BASE_URL must use '
          'HTTPS and must not target a development host.',
        );
      }
      return defined;
    }

    if (kReleaseMode || kProfileMode) {
      throw StateError(
        'ANDROID_RELEASE_API_CONFIGURATION_MISSING: API_BASE_URL is required '
        'for release/profile artifacts.',
      );
    }

    if (kIsWeb) {
      return 'http://127.0.0.1:8000';
    }

    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return 'http://10.0.2.2:8000';
      case TargetPlatform.windows:
      case TargetPlatform.linux:
      case TargetPlatform.macOS:
        return 'http://127.0.0.1:8000';
      case TargetPlatform.iOS:
        return 'http://127.0.0.1:8000';
      case TargetPlatform.fuchsia:
        return 'http://127.0.0.1:8000';
    }
  }

  static bool get usesExplicitBaseUrl {
    return _normalizeBaseUrl(_definedBaseUrl).isNotEmpty;
  }

  static String get sourceDescription {
    if (usesExplicitBaseUrl) {
      return 'API_BASE_URL';
    }

    if (kIsWeb) {
      return 'web default';
    }

    return '${defaultTargetPlatform.name} default';
  }

  static String get buildMode {
    if (kReleaseMode) return 'release';
    if (kProfileMode) return 'profile';
    return 'debug';
  }

  static bool isSafeReleaseBaseUrl(String value) {
    final String normalized = _normalizeBaseUrl(value);
    final Uri? uri = Uri.tryParse(normalized);
    if (uri == null ||
        uri.scheme.toLowerCase() != 'https' ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty ||
        uri.query.isNotEmpty ||
        uri.fragment.isNotEmpty) {
      return false;
    }
    return !const <String>{
      '10.0.2.2',
      '127.0.0.1',
      'localhost',
      '::1',
    }.contains(uri.host.toLowerCase());
  }

  static String _normalizeBaseUrl(String value) {
    String normalized = value.trim();

    while (normalized.endsWith('/')) {
      normalized = normalized.substring(0, normalized.length - 1);
    }

    return normalized;
  }
}
