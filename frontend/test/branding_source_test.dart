import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('production UI sources use NEXT Stabil branding', () {
    final List<File> files = <File>[
      ...Directory('lib')
          .listSync(recursive: true)
          .whereType<File>()
          .where((File file) => file.path.endsWith('.dart')),
      File('android/app/src/main/AndroidManifest.xml'),
      File('web/index.html'),
      File('web/manifest.json'),
      File('pubspec.yaml'),
    ];
    final RegExp oldBrand = RegExp(r'AI[- ]Lab', caseSensitive: false);

    for (final File file in files) {
      final String source = file.readAsStringSync();
      expect(
        oldBrand.hasMatch(source),
        isFalse,
        reason: 'Old user-facing brand remains in ${file.path}',
      );
    }

    final String androidManifest = File(
      'android/app/src/main/AndroidManifest.xml',
    ).readAsStringSync();
    expect(androidManifest, contains('android:label="NEXT Stabil"'));

    final String settings = File(
      'lib/features/settings/presentation/settings_page.dart',
    ).readAsStringSync();
    expect(settings, contains(r'NEXT Stabil ${value.displayVersion}'));
    expect(settings, contains(r'NEXT Stabil Backend ${value.version}'));
  });
}
