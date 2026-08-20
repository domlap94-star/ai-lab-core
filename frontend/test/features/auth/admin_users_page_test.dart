import 'package:ai_lab/features/auth/application/account_providers.dart';
import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/data/account_api.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/auth/domain/current_user.dart';
import 'package:ai_lab/features/auth/presentation/admin_users_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const AuthSession _session = AuthSession(
  accessToken: 'lifecycle-test-token',
  tokenType: 'bearer',
);

const List<ManagedUser> _initialUsers = <ManagedUser>[
  ManagedUser(
    id: 1,
    username: 'admin.current',
    email: 'admin.current@example.invalid',
    isActive: true,
    role: 'Administrator',
    mustChangePassword: false,
    passwordResetRequested: false,
  ),
  ManagedUser(
    id: 2,
    username: 'user.target',
    email: 'user.target@example.invalid',
    isActive: true,
    role: 'User',
    mustChangePassword: false,
    passwordResetRequested: false,
  ),
  ManagedUser(
    id: 3,
    username: 'user.inactive',
    email: 'user.inactive@example.invalid',
    isActive: false,
    role: 'User',
    mustChangePassword: false,
    passwordResetRequested: false,
  ),
];

class _AdminAuthController extends AuthController {
  @override
  Future<AuthState> build() async {
    return const AuthState(
      session: _session,
      user: CurrentUser(
        id: 1,
        username: 'admin.current',
        email: 'admin.current@example.invalid',
        role: 'Administrator',
        isActive: true,
        mustChangePassword: false,
        passwordResetRequested: false,
      ),
    );
  }
}

class _FakeAccountApi extends AccountApi {
  _FakeAccountApi() : super(Dio());

  List<ManagedUser> users = List<ManagedUser>.of(_initialUsers);
  int fetchCount = 0;
  int? deactivatedUserId;
  int? resetUserId;
  int? updatedUserId;
  int updateCount = 0;
  DioException? deactivateError;

  @override
  Future<List<ManagedUser>> fetchUsers({required AuthSession session}) async {
    fetchCount += 1;
    return List<ManagedUser>.of(users);
  }

  @override
  Future<void> deactivateUser({
    required AuthSession session,
    required int userId,
  }) async {
    final DioException? error = deactivateError;
    if (error != null) {
      throw error;
    }
    deactivatedUserId = userId;
    users = users
        .map(
          (ManagedUser user) => user.id == userId
              ? ManagedUser(
                  id: user.id,
                  username: user.username,
                  email: user.email,
                  isActive: false,
                  role: user.role,
                  mustChangePassword: user.mustChangePassword,
                  passwordResetRequested: user.passwordResetRequested,
                )
              : user,
        )
        .toList();
  }

  @override
  Future<void> resetUserPassword({
    required AuthSession session,
    required int userId,
    required String temporaryPassword,
  }) async {
    resetUserId = userId;
  }

  @override
  Future<ManagedUser> updateUser({
    required AuthSession session,
    required int userId,
    required String username,
    required String email,
    required String role,
  }) async {
    updatedUserId = userId;
    updateCount += 1;
    final updated = ManagedUser(
      id: userId,
      username: username,
      email: email,
      isActive: true,
      role: role,
      mustChangePassword: false,
      passwordResetRequested: false,
    );
    users = users.map((user) => user.id == userId ? updated : user).toList();
    return updated;
  }
}

DioException _error(int statusCode, String detail) {
  final RequestOptions options = RequestOptions(path: '/deactivate');
  return DioException(
    requestOptions: options,
    response: Response<dynamic>(
      requestOptions: options,
      statusCode: statusCode,
      data: <String, Object>{'detail': detail},
    ),
  );
}

Future<void> _pumpPage(
  WidgetTester tester,
  _FakeAccountApi api, {
  Size size = const Size(1200, 1800),
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final ProviderContainer container = ProviderContainer(
    overrides: [
      authControllerProvider.overrideWith(_AdminAuthController.new),
      accountApiProvider.overrideWithValue(api),
    ],
  );
  addTearDown(container.dispose);
  await container.read(authControllerProvider.future);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(home: AdminUsersPage()),
    ),
  );
  await tester.pumpAndSettle();
}

Finder _deactivateButton(int userId) {
  return find.descendant(
    of: find.byKey(Key('deactivate-user-$userId')),
    matching: find.byType(TextButton),
  );
}

Future<void> _openAndConfirm(
  WidgetTester tester, {
  String username = 'user.target',
}) async {
  await tester.tap(_deactivateButton(2));
  await tester.pumpAndSettle();
  await tester.enterText(
    find.byKey(const Key('deactivate-username-confirmation')),
    username,
  );
  await tester.pump();
  await tester.tap(find.byKey(const Key('confirm-user-deactivation')));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('lifecycle actions respect active, self and inactive state', (
    WidgetTester tester,
  ) async {
    final _FakeAccountApi api = _FakeAccountApi();
    await _pumpPage(tester, api);

    expect(find.text('Usuń użytkownika'), findsNWidgets(3));
    expect(tester.widget<TextButton>(_deactivateButton(1)).onPressed, isNull);
    expect(
      tester.widget<TextButton>(_deactivateButton(2)).onPressed,
      isNotNull,
    );
    expect(tester.widget<TextButton>(_deactivateButton(3)).onPressed, isNull);
    expect(
      tester
          .widget<IconButton>(find.byKey(const Key('reset-password-user-3')))
          .onPressed,
      isNull,
    );
    expect(find.textContaining('nieaktywny'), findsOneWidget);
  });

  testWidgets('confirmation requires exact username and refreshes state', (
    WidgetTester tester,
  ) async {
    final _FakeAccountApi api = _FakeAccountApi();
    await _pumpPage(tester, api);

    await tester.tap(_deactivateButton(2));
    await tester.pumpAndSettle();
    expect(
      find.text(
        'Konto zostanie dezaktywowane. Dane użytkownika i historia '
        'pozostaną w systemie.',
      ),
      findsOneWidget,
    );
    expect(find.textContaining('user.target'), findsWidgets);
    FilledButton confirm = tester.widget<FilledButton>(
      find.byKey(const Key('confirm-user-deactivation')),
    );
    expect(confirm.onPressed, isNull);

    await tester.enterText(
      find.byKey(const Key('deactivate-username-confirmation')),
      'User.Target',
    );
    await tester.pump();
    confirm = tester.widget<FilledButton>(
      find.byKey(const Key('confirm-user-deactivation')),
    );
    expect(confirm.onPressed, isNull);

    await tester.enterText(
      find.byKey(const Key('deactivate-username-confirmation')),
      'user.target',
    );
    await tester.pump();
    confirm = tester.widget<FilledButton>(
      find.byKey(const Key('confirm-user-deactivation')),
    );
    expect(confirm.onPressed, isNotNull);
    await tester.tap(find.byKey(const Key('confirm-user-deactivation')));
    await tester.pumpAndSettle();

    expect(api.deactivatedUserId, 2);
    expect(api.fetchCount, 2);
    expect(tester.widget<TextButton>(_deactivateButton(2)).onPressed, isNull);
    expect(
      find.text('Konto użytkownika zostało dezaktywowane.'),
      findsOneWidget,
    );
  });

  for (final (int, String, String) testCase in <(int, String, String)>[
    (403, 'Administrator role required', 'Brak uprawnień administratora.'),
    (
      409,
      'Administrator cannot deactivate own account',
      'Nie możesz usunąć własnego konta.',
    ),
    (
      409,
      'Cannot deactivate the last active Administrator',
      'Nie można usunąć ostatniego aktywnego Administratora.',
    ),
    (409, 'User is already inactive', 'Konto użytkownika jest już nieaktywne.'),
  ]) {
    testWidgets('maps lifecycle error ${testCase.$1}: ${testCase.$2}', (
      WidgetTester tester,
    ) async {
      final _FakeAccountApi api = _FakeAccountApi()
        ..deactivateError = _error(testCase.$1, testCase.$2);
      await _pumpPage(tester, api);
      await _openAndConfirm(tester);
      expect(find.text(testCase.$3), findsOneWidget);
    });
  }

  testWidgets('active password reset flow remains available', (
    WidgetTester tester,
  ) async {
    final _FakeAccountApi api = _FakeAccountApi();
    await _pumpPage(tester, api);
    await tester.tap(find.byKey(const Key('reset-password-user-2')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byType(TextField).last,
      'Temporary-Password-2026',
    );
    await tester.pump();
    await tester.tap(find.byKey(const Key('confirm-password-reset')));
    await tester.pumpAndSettle();
    expect(api.resetUserId, 2);
  });

  testWidgets('create user form remains available', (
    WidgetTester tester,
  ) async {
    final _FakeAccountApi api = _FakeAccountApi();
    await _pumpPage(tester, api);
    expect(find.text('Dodaj użytkownika'), findsWidgets);
    expect(find.text('Nazwa użytkownika'), findsOneWidget);
    expect(find.text('E-mail'), findsOneWidget);
    expect(find.text('Hasło tymczasowe'), findsOneWidget);
  });

  for (final width in <double>[360, 390, 600, 1200]) {
    testWidgets('user rows remain readable at width ${width.toInt()}', (
      WidgetTester tester,
    ) async {
      final api = _FakeAccountApi()
        ..users = <ManagedUser>[
          const ManagedUser(
            id: 2,
            username: 'very.long.synthetic.username.for.mobile',
            email: 'very.long.synthetic.email.address@example.invalid',
            isActive: true,
            role: 'Administrator',
            mustChangePassword: false,
            passwordResetRequested: false,
          ),
        ];
      await _pumpPage(tester, api, size: Size(width, 1400));
      await tester.ensureVisible(find.byKey(const Key('edit-user-2')));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(
        find.byKey(const Key('user-identity-2')),
        width <= 600 ? findsOneWidget : findsNothing,
      );
      expect(find.byKey(const Key('edit-user-2')), findsOneWidget);
      expect(find.byKey(const Key('reset-password-user-2')), findsOneWidget);
      expect(find.byKey(const Key('deactivate-user-2')), findsOneWidget);
      if (width <= 600) {
        final identityWidth = tester
            .getSize(find.byKey(const Key('user-identity-2')))
            .width;
        expect(identityWidth, greaterThan(180));
      }
    });
  }

  testWidgets('edit cancel performs zero writes and password stays separate', (
    WidgetTester tester,
  ) async {
    final api = _FakeAccountApi();
    await _pumpPage(tester, api);
    await tester.tap(find.byKey(const Key('edit-user-2')));
    await tester.pumpAndSettle();
    expect(find.text('Edytuj użytkownika'), findsOneWidget);
    expect(find.textContaining('hasło', findRichText: true), findsNothing);
    await tester.tap(find.text('Anuluj').last);
    await tester.pumpAndSettle();
    expect(api.updateCount, 0);
    expect(find.byKey(const Key('reset-password-user-2')), findsOneWidget);
  });

  testWidgets('successful edit refreshes the list', (
    WidgetTester tester,
  ) async {
    final api = _FakeAccountApi();
    await _pumpPage(tester, api);
    await tester.tap(find.byKey(const Key('edit-user-2')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('edit-user-username')),
      'user.edited',
    );
    await tester.enterText(
      find.byKey(const Key('edit-user-email')),
      'user.edited@example.invalid',
    );
    await tester.tap(find.byKey(const Key('save-user-edit')));
    await tester.pumpAndSettle();
    expect(api.updatedUserId, 2);
    expect(api.updateCount, 1);
    expect(api.fetchCount, 2);
    expect(find.text('user.edited'), findsOneWidget);
  });
}
