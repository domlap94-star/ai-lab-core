import 'dart:async';

import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/auth/domain/current_user.dart';
import 'package:ai_lab/features/shared_clients/application/client_access_providers.dart';
import 'package:ai_lab/features/shared_clients/data/client_access_repository.dart';
import 'package:ai_lab/features/shared_clients/presentation/client_share_action.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _RoleAuthController extends AuthController {
  _RoleAuthController(this.role, {this.authenticated = true});

  final String role;
  final bool authenticated;

  @override
  Future<AuthState> build() async {
    if (!authenticated) return const AuthState.unauthenticated();
    return AuthState(
      session: const AuthSession(
        accessToken: 'test',
        tokenType: 'Bearer',
      ),
      user: CurrentUser(
        id: 1,
        username: 'synthetic-user',
        email: 'synthetic@example.invalid',
        role: role,
        isActive: true,
        mustChangePassword: false,
        passwordResetRequested: false,
      ),
    );
  }
}

class _FakeClientAccessRepository extends ClientAccessRepository {
  _FakeClientAccessRepository() : super(Dio());

  int grantCalls = 0;
  int? clientId;
  int? externalUserId;
  Completer<void>? pendingGrant;
  int? failureStatus;

  @override
  Future<void> grant({
    required AuthSession session,
    required int clientId,
    required int externalUserId,
  }) async {
    grantCalls += 1;
    this.clientId = clientId;
    this.externalUserId = externalUserId;
    if (failureStatus != null) {
      throw DioException(
        requestOptions: RequestOptions(path: '/synthetic'),
        response: Response<void>(
          requestOptions: RequestOptions(path: '/synthetic'),
          statusCode: failureStatus,
        ),
      );
    }
    await (pendingGrant?.future ?? Future<void>.value());
  }
}

void main() {
  test('share role policy is normalized and fail-closed', () {
    for (final String role in <String>[
      'User',
      ' user ',
      'Admin',
      'Administrator',
    ]) {
      expect(canManageClientAccess(role), isTrue, reason: role);
    }
    for (final String? role in <String?>[
      'External',
      'unknown',
      '',
      '  ',
      null,
    ]) {
      expect(canManageClientAccess(role), isFalse, reason: '$role');
    }
  });

  test(
    'available users exclude active, retain revoked and sort names',
    () async {
      final ProviderContainer container = ProviderContainer(
        overrides: [
          clientAccessManagerOptionsProvider.overrideWith((Ref ref) async {
            return <String, List<Map<String, dynamic>>>{
              'clients': <Map<String, dynamic>>[],
              'external_users': <Map<String, dynamic>>[
                <String, dynamic>{'id': 3, 'username': 'External Zeta'},
                <String, dynamic>{'id': 2, 'username': 'External Beta'},
                <String, dynamic>{'id': 1, 'username': 'External Alpha'},
              ],
            };
          }),
          clientGrantHistoryProvider.overrideWith((Ref ref) async {
            return <Map<String, dynamic>>[
              <String, dynamic>{
                'client_id': 7,
                'external_user_id': 2,
                'active': true,
              },
              <String, dynamic>{
                'client_id': 7,
                'external_user_id': 3,
                'active': false,
              },
            ];
          }),
        ],
      );
      addTearDown(container.dispose);

      final List<ClientShareUser> users = await container.read(
        availableClientShareUsersProvider(7).future,
      );

      expect(users.map((ClientShareUser user) => user.displayName), <String>[
        'External Alpha',
        'External Zeta',
      ]);
    },
  );

  for (final MapEntry<String, bool> entry in <String, bool>{
    'User': true,
    'Admin': true,
    'Administrator': true,
    'External': false,
    'unknown': false,
    '': false,
  }.entries) {
    testWidgets('share action visibility for ${entry.key}', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            authControllerProvider.overrideWith(
              () => _RoleAuthController(entry.key),
            ),
            availableClientShareUsersProvider.overrideWith(
              (Ref ref, int clientId) async => const <ClientShareUser>[],
            ),
          ],
          child: const MaterialApp(
            home: Scaffold(
              body: ClientShareAction(
                clientId: 7,
                clientDisplayName: 'Klient testowy A',
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        find.byKey(const ValueKey<String>('client-share-7')),
        entry.value ? findsOneWidget : findsNothing,
      );
    });
  }

  testWidgets('unauthenticated session hides share action', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider.overrideWith(
            () => _RoleAuthController('', authenticated: false),
          ),
        ],
        child: const MaterialApp(
          home: Scaffold(
            body: ClientShareAction(
              clientId: 7,
              clientDisplayName: 'Klient testowy A',
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey<String>('client-share-7')), findsNothing);
  });

  testWidgets(
    'selection is read-only, cancel is zero POST, confirm is one POST',
    (WidgetTester tester) async {
      final _FakeClientAccessRepository repository =
          _FakeClientAccessRepository()..pendingGrant = Completer<void>();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            authControllerProvider.overrideWith(
              () => _RoleAuthController('User'),
            ),
            clientAccessRepositoryProvider.overrideWithValue(repository),
            availableClientShareUsersProvider.overrideWith(
              (Ref ref, int clientId) async => const <ClientShareUser>[
                ClientShareUser(id: 11, displayName: 'External Alpha'),
              ],
            ),
          ],
          child: const MaterialApp(
            home: Scaffold(
              body: ClientShareAction(
                clientId: 7,
                clientDisplayName: 'Klient testowy A',
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const ValueKey<String>('client-share-7')));
      await tester.pumpAndSettle();
      expect(find.text('External Alpha'), findsOneWidget);
      expect(repository.grantCalls, 0);

      await tester.tap(find.text('External Alpha'));
      await tester.pumpAndSettle();
      expect(find.text('Udostępnić klienta?'), findsOneWidget);
      expect(find.textContaining('Klient testowy A'), findsOneWidget);
      expect(repository.grantCalls, 0);
      await tester.tap(find.text('Anuluj'));
      await tester.pumpAndSettle();
      expect(repository.grantCalls, 0);

      await tester.tap(find.byKey(const ValueKey<String>('client-share-7')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('External Alpha'));
      await tester.pumpAndSettle();
      final Finder confirm = find.byKey(const Key('client-share-confirm'));
      await tester.tap(confirm);
      await tester.tap(confirm);
      await tester.pump();
      expect(repository.grantCalls, 1);
      expect(repository.clientId, 7);
      expect(repository.externalUserId, 11);

      repository.pendingGrant!.complete();
      await tester.pumpAndSettle();
      expect(
        find.text('Udostępniono klienta użytkownikowi External Alpha.'),
        findsOneWidget,
      );
    },
  );

  testWidgets('duplicate race is bounded and does not show success', (
    WidgetTester tester,
  ) async {
    final _FakeClientAccessRepository repository = _FakeClientAccessRepository()
      ..failureStatus = 409;
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider.overrideWith(
            () => _RoleAuthController('Admin'),
          ),
          clientAccessRepositoryProvider.overrideWithValue(repository),
          availableClientShareUsersProvider.overrideWith(
            (Ref ref, int clientId) async => const <ClientShareUser>[
              ClientShareUser(id: 11, displayName: 'External Alpha'),
            ],
          ),
        ],
        child: const MaterialApp(
          home: Scaffold(
            body: ClientShareAction(
              clientId: 7,
              clientDisplayName: 'Klient testowy A',
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey<String>('client-share-7')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('External Alpha'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('client-share-confirm')));
    await tester.pumpAndSettle();

    expect(repository.grantCalls, 1);
    expect(
      find.text('Ten użytkownik ma już dostęp do klienta.'),
      findsOneWidget,
    );
    expect(find.textContaining('Udostępniono klienta'), findsNothing);
  });
}
