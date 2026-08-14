import 'package:flutter/foundation.dart';

class ApiConfig {
  ApiConfig._();

  static const String _definedBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: '',
  );

  static String get baseUrl {
    final String defined = _normalizeBaseUrl(_definedBaseUrl);

    if (defined.isNotEmpty) {
      return defined;
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

  static String _normalizeBaseUrl(String value) {
    String normalized = value.trim();

    while (normalized.endsWith('/')) {
      normalized = normalized.substring(0, normalized.length - 1);
    }

    return normalized;
  }
}
