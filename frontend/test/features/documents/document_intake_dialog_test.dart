import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/documents/application/documents_repository.dart';
import 'package:ai_lab/features/documents/presentation/document_intake_dialog.dart';

class _Repository extends DocumentsRepository {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  const session = AuthSession(accessToken: 'token', tokenType: 'Bearer');

  testWidgets('camera action is Android-only and intake is responsive', (
    tester,
  ) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: DocumentIntakeDialog(
            repository: _Repository(),
            session: session,
            clientId: 7,
          ),
        ),
      ),
    );
    expect(find.text('Dodaj pliki'), findsOneWidget);
    expect(find.text('Dodaj zdjęcie'), findsOneWidget);
    expect(find.text('Zrób zdjęcie'), findsOneWidget);
    expect(find.textContaining('odmowa nie blokuje'), findsOneWidget);
    expect(tester.takeException(), isNull);
    debugDefaultTargetPlatformOverride = null;
  });
}
