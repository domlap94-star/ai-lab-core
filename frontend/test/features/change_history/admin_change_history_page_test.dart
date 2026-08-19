import 'package:ai_lab/features/auth/application/account_providers.dart';
import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/data/account_api.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/auth/domain/current_user.dart';
import 'package:ai_lab/features/change_history/data/change_history_api.dart';
import 'package:ai_lab/features/change_history/domain/change_history.dart';
import 'package:ai_lab/features/change_history/presentation/admin_change_history_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const AuthSession _session = AuthSession(
  accessToken: 'change-history-test-token',
  tokenType: 'bearer',
);

class _AuthController extends AuthController {
  _AuthController(this.role);
  final String role;

  @override
  Future<AuthState> build() async => AuthState(
    session: _session,
    user: CurrentUser(
      id: 1,
      username: 'admin.current',
      email: 'admin@example.invalid',
      role: role,
      isActive: true,
      mustChangePassword: false,
      passwordResetRequested: false,
    ),
  );
}

class _FakeAccountApi extends AccountApi {
  _FakeAccountApi() : super(Dio());

  @override
  Future<List<ManagedUser>> fetchUsers({required AuthSession session}) async {
    return const <ManagedUser>[
      ManagedUser(
        id: 1,
        username: 'admin.current',
        email: 'admin@example.invalid',
        isActive: true,
        role: 'Administrator',
        mustChangePassword: false,
        passwordResetRequested: false,
      ),
    ];
  }
}

class _FakeHistoryApi extends ChangeHistoryApi {
  _FakeHistoryApi({this.failure}) : super(Dio());
  final DioException? failure;
  int calls = 0;
  String? entityType;

  @override
  Future<ChangeHistoryPageData> fetch({
    required AuthSession session,
    String? entityType,
    int? actorUserId,
    String? action,
    DateTime? dateFrom,
    DateTime? dateTo,
    int skip = 0,
    int limit = 50,
  }) async {
    calls += 1;
    this.entityType = entityType;
    if (failure != null) throw failure!;
    return ChangeHistoryPageData(
      total: 51,
      items: <ChangeHistoryItem>[
        ChangeHistoryItem(
          stableKey: 'change-1-$skip',
          createdAt: DateTime.utc(2026, 8, 19, 14, 25),
          actorUserId: 1,
          actorDisplayName: 'admin.current',
          entityType: 'client',
          entityId: 123,
          entityLabel: 'Klient #123',
          action: 'updated',
          changedFields: const <String>['primary_phone', 'notes'],
          beforeValues: const <String, dynamic>{
            'primary_phone': <String, String>{
              'masked': '***1234',
              'sha256': 'hidden-old-digest',
            },
            'notes': <String, dynamic>{'length': 1234, 'sha256': 'hidden'},
          },
          afterValues: const <String, dynamic>{
            'primary_phone': <String, String>{
              'masked': '***5678',
              'sha256': 'hidden-new-digest',
            },
            'notes': <String, dynamic>{'length': 1260, 'sha256': 'hidden'},
          },
          deepLink: '/clients/123',
        ),
      ],
    );
  }
}

Future<void> _pump(
  WidgetTester tester,
  _FakeHistoryApi api, {
  String role = 'Administrator',
  double width = 1200,
}) async {
  tester.view.physicalSize = Size(width, 1600);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final ProviderContainer container = ProviderContainer(
    overrides: [
      authControllerProvider.overrideWith(() => _AuthController(role)),
      accountApiProvider.overrideWithValue(_FakeAccountApi()),
      changeHistoryApiProvider.overrideWithValue(api),
    ],
  );
  addTearDown(container.dispose);
  await container.read(authControllerProvider.future);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(home: AdminChangeHistoryPage()),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('admin sees bounded masked history and expandable diff', (
    WidgetTester tester,
  ) async {
    final _FakeHistoryApi api = _FakeHistoryApi();
    await _pump(tester, api);
    expect(find.text('Historia zmian'), findsOneWidget);
    expect(find.textContaining('Zmieniono · Klient #123'), findsOneWidget);
    await tester.tap(find.byKey(const Key('history-change-1-0')));
    await tester.pumpAndSettle();
    expect(find.text('***1234'), findsOneWidget);
    expect(find.text('***5678'), findsOneWidget);
    expect(find.text('1234 znaków'), findsOneWidget);
    expect(find.text('1260 znaków'), findsOneWidget);
    expect(find.textContaining('hidden'), findsNothing);
    expect(find.byKey(const Key('history-load-more')), findsOneWidget);
  });

  testWidgets('normal user is denied without requesting history', (
    WidgetTester tester,
  ) async {
    final _FakeHistoryApi api = _FakeHistoryApi();
    await _pump(tester, api, role: 'User');
    expect(find.text('Brak uprawnień administratora.'), findsOneWidget);
    expect(api.calls, 0);
  });

  testWidgets('403 is rendered as a bounded administrator error', (
    WidgetTester tester,
  ) async {
    final RequestOptions options = RequestOptions(path: '/history');
    final _FakeHistoryApi api = _FakeHistoryApi(
      failure: DioException(
        requestOptions: options,
        response: Response<dynamic>(requestOptions: options, statusCode: 403),
      ),
    );
    await _pump(tester, api);
    expect(find.text('Brak uprawnień administratora.'), findsOneWidget);
  });

  for (final double width in <double>[360, 390, 600, 1200]) {
    testWidgets('history is responsive at ${width.toInt()} px', (
      WidgetTester tester,
    ) async {
      await _pump(tester, _FakeHistoryApi(), width: width);
      expect(tester.takeException(), isNull);
      expect(find.byKey(const Key('history-entity-filter')), findsOneWidget);
    });
  }
}
