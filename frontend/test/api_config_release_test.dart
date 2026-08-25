import 'package:ai_lab/core/config/api_config.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('canonical HTTPS API is valid for acceptance builds', () {
    expect(
      ApiConfig.isSafeReleaseBaseUrl('https://domai.tail1927bd.ts.net/'),
      isTrue,
    );
  });

  test('development and unsafe API values fail closed', () {
    for (final String value in <String>[
      '',
      'http://domai.tail1927bd.ts.net',
      'http://10.0.2.2:8000',
      'https://127.0.0.1:8000',
      'https://localhost:8000',
      'https://user:password@example.invalid',
      'not-a-url',
    ]) {
      expect(ApiConfig.isSafeReleaseBaseUrl(value), isFalse, reason: value);
    }
  });
}
