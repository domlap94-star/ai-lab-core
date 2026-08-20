import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/auth/domain/current_user.dart';
import 'package:ai_lab/features/trash/application/trash_providers.dart';
import 'package:ai_lab/features/trash/data/trash_api.dart';
import 'package:ai_lab/features/trash/domain/trash_entry.dart';
import 'package:ai_lab/features/trash/presentation/admin_trash_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _session = AuthSession(accessToken: 'trash-token', tokenType: 'bearer');

class _AuthController extends AuthController {
  _AuthController(this.role);
  final String role;

  @override
  Future<AuthState> build() async => AuthState(
    session: _session,
    user: CurrentUser(
      id: 1,
      username: 'synthetic.admin',
      email: 'synthetic@example.invalid',
      role: role,
      isActive: true,
      mustChangePassword: false,
      passwordResetRequested: false,
    ),
  );
}

class _FakeTrashApi extends TrashApi {
  _FakeTrashApi() : super(Dio());
  int? restoredId;

  @override
  Future<TrashPageData> fetch({
    required AuthSession session,
    required TrashEntityType entityType,
  }) async => TrashPageData(
    items: <TrashEntry>[
      TrashEntry(
        id: 10 + entityType.index,
        entityType: entityType,
        entityId: 100 + entityType.index,
        state: 'trashed',
        safeDisplayLabel:
            'Bardzo długi bezpieczny techniczny opis elementu #100',
        trashedAt: DateTime(2026, 8, 21, 8),
        purgeAfter: DateTime.now().add(const Duration(days: 6)),
        trashedByUserId: 1,
        attemptCount: 0,
      ),
    ],
    total: 1,
  );

  @override
  Future<void> restore({
    required AuthSession session,
    required int entryId,
  }) async {
    restoredId = entryId;
  }
}

Widget _app(_FakeTrashApi api, {String role = 'Administrator'}) {
  return ProviderScope(
    overrides: [
      authControllerProvider.overrideWith(() => _AuthController(role)),
      trashApiProvider.overrideWithValue(api),
    ],
    child: const MaterialApp(home: AdminTrashPage()),
  );
}

void main() {
  for (final width in <double>[360, 390, 600, 1200]) {
    testWidgets('Kosz is responsive at ${width.toInt()}', (tester) async {
      final errors = <FlutterErrorDetails>[];
      final previous = FlutterError.onError;
      FlutterError.onError = errors.add;
      addTearDown(() => FlutterError.onError = previous);
      tester.view.physicalSize = Size(width, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(_app(_FakeTrashApi()));
      await tester.pumpAndSettle();

      expect(find.text('Kosz'), findsOneWidget);
      expect(find.text('Pliki'), findsOneWidget);
      expect(find.text('Klienci'), findsOneWidget);
      expect(find.text('Użytkownicy'), findsOneWidget);
      expect(find.text('Przywróć'), findsOneWidget);
      expect(
        errors.where((error) => error.exceptionAsString().contains('overflow')),
        isEmpty,
      );
    });
  }

  testWidgets('restore uses the selected Trash entry', (tester) async {
    final api = _FakeTrashApi();
    await tester.pumpWidget(_app(api));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Przywróć'));
    await tester.pumpAndSettle();
    expect(api.restoredId, 10);
    expect(find.text('Element został przywrócony.'), findsOneWidget);
  });

  testWidgets('normal User cannot open Trash content', (tester) async {
    await tester.pumpWidget(_app(_FakeTrashApi(), role: 'User'));
    await tester.pumpAndSettle();
    expect(find.text('Brak uprawnień administratora.'), findsOneWidget);
    expect(find.text('Pliki'), findsNothing);
  });
}
