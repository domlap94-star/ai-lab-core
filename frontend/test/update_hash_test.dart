import 'dart:convert';
import 'dart:io';

import 'package:ai_lab/features/app_update/data/update_install_service_io.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('calculates and verifies SHA256 for downloaded update file', () async {
    final Directory directory = await Directory.systemTemp.createTemp(
      'next_stabil_hash_test_',
    );

    addTearDown(() async {
      if (await directory.exists()) {
        await directory.delete(recursive: true);
      }
    });

    final File file = File(
      '${directory.path}${Platform.pathSeparator}update.bin',
    );

    await file.writeAsBytes(utf8.encode('NEXT Stabil'), flush: true);

    const String expected =
        'A1693190A9A8E5F3649CAE8B77A0EDA46CF31A2AB70207A480D739FB2C8888CD';

    expect(await calculateFileSha256(file.path), expected);

    await verifyFileSha256(file.path, expected);
  });

  test('rejects file when SHA256 does not match', () async {
    final Directory directory = await Directory.systemTemp.createTemp(
      'next_stabil_hash_test_',
    );

    addTearDown(() async {
      if (await directory.exists()) {
        await directory.delete(recursive: true);
      }
    });

    final File file = File(
      '${directory.path}${Platform.pathSeparator}update.bin',
    );

    await file.writeAsBytes(utf8.encode('NEXT Stabil'), flush: true);

    const String wrong =
        '0000000000000000000000000000000000000000000000000000000000000000';

    await expectLater(
      verifyFileSha256(file.path, wrong),
      throwsA(isA<StateError>()),
    );
  });
}
