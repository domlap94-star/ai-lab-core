import 'dart:async';

import 'package:ai_lab/app/app.dart';
import 'package:ai_lab/features/app_update/application/update_provider.dart';
import 'package:ai_lab/features/app_version/application/app_version_provider.dart';
import 'package:ai_lab/features/app_version/domain/app_version_info.dart';
import 'package:ai_lab/features/auth/application/auth_providers.dart';
import 'package:ai_lab/features/auth/application/auth_repository.dart';
import 'package:ai_lab/features/auth/data/auth_api.dart';
import 'package:ai_lab/features/auth/data/auth_token_storage.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/auth/domain/current_user.dart';
import 'package:ai_lab/features/system_status/application/system_status_provider.dart';
import 'package:ai_lab/features/system_status/domain/backend_status.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('valid login validates, persists, and stays on Dashboard', (
    WidgetTester tester,
  ) async {
    final _MemoryTokenStorage storage = _MemoryTokenStorage();
    final _LoginRepository repository = _LoginRepository();
    await _pumpLogin(tester, storage: storage, repository: repository);

    await tester.enterText(find.byType(TextFormField).at(0), 'user');
    await tester.enterText(find.byType(TextFormField).at(1), 'valid');
    await tester.tap(find.text('Zaloguj się'));
    await tester.pump();

    expect(find.text('Sprawdzanie sesji...'), findsNothing);
    expect(find.text('Logowanie...'), findsOneWidget);
    repository.releaseLogin();
    await tester.pumpAndSettle();

    expect(find.text('Dashboard'), findsWidgets);
    expect(storage.session, _session);
    expect(storage.readCount, greaterThanOrEqualTo(2));
    await tester.pump(const Duration(seconds: 1));
    expect(find.text('Dashboard'), findsWidgets);
  });

  testWidgets('invalid credentials stay on form and show friendly error', (
    WidgetTester tester,
  ) async {
    final _LoginRepository repository = _LoginRepository(loginStatus: 401);
    await _pumpLogin(
      tester,
      storage: _MemoryTokenStorage(),
      repository: repository,
    );

    await tester.enterText(find.byType(TextFormField).at(0), 'user');
    await tester.enterText(find.byType(TextFormField).at(1), 'wrong');
    await tester.tap(find.text('Zaloguj się'));
    repository.releaseLogin();
    await tester.pumpAndSettle();

    expect(
      find.text('Nieprawidłowa nazwa użytkownika lub hasło.'),
      findsOneWidget,
    );
    expect(find.text('Zaloguj się'), findsOneWidget);
    expect(find.textContaining('DioException'), findsNothing);
  });

  testWidgets('session-check network error is not shown as bad credentials', (
    WidgetTester tester,
  ) async {
    final _LoginRepository repository = _LoginRepository(
      fetchNetworkError: true,
    );
    final _MemoryTokenStorage storage = _MemoryTokenStorage();
    await _pumpLogin(tester, storage: storage, repository: repository);

    await tester.enterText(find.byType(TextFormField).at(0), 'user');
    await tester.enterText(find.byType(TextFormField).at(1), 'valid');
    await tester.tap(find.text('Zaloguj się'));
    repository.releaseLogin();
    await tester.pumpAndSettle();

    expect(
      find.text(
        'Nie udało się sprawdzić sesji. Sprawdź połączenie i spróbuj ponownie.',
      ),
      findsOneWidget,
    );
    expect(
      find.text('Nieprawidłowa nazwa użytkownika lub hasło.'),
      findsNothing,
    );
    expect(storage.session, isNull);
  });

  testWidgets('login connection error is identified as connectivity failure', (
    WidgetTester tester,
  ) async {
    final _LoginRepository repository = _LoginRepository(
      loginError: DioException.connectionError(
        requestOptions: RequestOptions(path: '/api/v1/auth/login'),
        reason: 'synthetic offline',
      ),
    );
    await _pumpLogin(
      tester,
      storage: _MemoryTokenStorage(),
      repository: repository,
    );
    await tester.enterText(find.byType(TextFormField).at(0), 'user');
    await tester.enterText(find.byType(TextFormField).at(1), 'valid');
    await tester.tap(find.text('Zaloguj się'));
    repository.releaseLogin();
    await tester.pumpAndSettle();
    expect(
      find.text('Nie można połączyć się z serwerem NEXT Stabil.'),
      findsOneWidget,
    );
  });

  testWidgets('login backend 500 is identified as an HTTP response', (
    WidgetTester tester,
  ) async {
    final _LoginRepository repository = _LoginRepository(loginStatus: 500);
    await _pumpLogin(
      tester,
      storage: _MemoryTokenStorage(),
      repository: repository,
    );
    await tester.enterText(find.byType(TextFormField).at(0), 'user');
    await tester.enterText(find.byType(TextFormField).at(1), 'valid');
    await tester.tap(find.text('Zaloguj się'));
    repository.releaseLogin();
    await tester.pumpAndSettle();
    expect(find.text('Serwer zwrócił błąd HTTP 500.'), findsOneWidget);
  });

  testWidgets('malformed login response reports schema failure', (
    WidgetTester tester,
  ) async {
    final _LoginRepository repository = _LoginRepository(
      loginError: const FormatException('Niepoprawna odpowiedź logowania.'),
    );
    await _pumpLogin(
      tester,
      storage: _MemoryTokenStorage(),
      repository: repository,
    );
    await tester.enterText(find.byType(TextFormField).at(0), 'user');
    await tester.enterText(find.byType(TextFormField).at(1), 'valid');
    await tester.tap(find.text('Zaloguj się'));
    repository.releaseLogin();
    await tester.pumpAndSettle();
    expect(find.text('Niepoprawna odpowiedź logowania.'), findsOneWidget);
  });

  testWidgets('unknown Dio socket failure maps to connectivity message', (
    WidgetTester tester,
  ) async {
    final _LoginRepository repository = _LoginRepository(
      loginError: DioException(
        requestOptions: RequestOptions(path: '/api/v1/auth/login'),
        type: DioExceptionType.unknown,
        error: const _SyntheticSocketException(),
      ),
    );
    await _pumpLogin(
      tester,
      storage: _MemoryTokenStorage(),
      repository: repository,
    );
    await tester.enterText(find.byType(TextFormField).at(0), 'user');
    await tester.enterText(find.byType(TextFormField).at(1), 'valid');
    await tester.tap(find.text('Zaloguj się'));
    repository.releaseLogin();
    await tester.pumpAndSettle();
    expect(
      find.text('Nie można połączyć się z serwerem NEXT Stabil.'),
      findsOneWidget,
    );
    expect(find.textContaining('nieznany błąd'), findsNothing);
  });

  testWidgets('non-Dio client failure uses bounded generic message', (
    WidgetTester tester,
  ) async {
    final _LoginRepository repository = _LoginRepository(
      loginError: StateError('synthetic private detail'),
    );
    await _pumpLogin(
      tester,
      storage: _MemoryTokenStorage(),
      repository: repository,
    );
    await tester.enterText(find.byType(TextFormField).at(0), 'user');
    await tester.enterText(find.byType(TextFormField).at(1), 'valid');
    await tester.tap(find.text('Zaloguj się'));
    repository.releaseLogin();
    await tester.pumpAndSettle();
    expect(
      find.text('Nie udało się zalogować. Spróbuj ponownie.'),
      findsOneWidget,
    );
    expect(find.textContaining('synthetic private detail'), findsNothing);
  });
}

class _SyntheticSocketException implements Exception {
  const _SyntheticSocketException();
}

Future<void> _pumpLogin(
  WidgetTester tester, {
  required _MemoryTokenStorage storage,
  required _LoginRepository repository,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authTokenStorageProvider.overrideWithValue(storage),
        authRepositoryProvider.overrideWithValue(repository),
        appVersionProvider.overrideWith(
          (Ref ref) async =>
              const AppVersionInfo(version: '1.0.2', buildNumber: '20'),
        ),
        updateCheckProvider.overrideWith(
          (Ref ref) async => throw StateError('offline in login test'),
        ),
        backendStatusProvider.overrideWith((Ref ref) async {
          return const BackendStatus(
            isOnline: true,
            application: 'AI-Lab',
            version: 'test',
            environment: 'test',
            debug: false,
            latencyMilliseconds: 1,
            baseUrl: 'https://example.invalid',
          );
        }),
      ],
      child: const App(),
    ),
  );
  await tester.pumpAndSettle();
}

const AuthSession _session = AuthSession(
  accessToken: 'fresh-token',
  tokenType: 'bearer',
);

class _MemoryTokenStorage extends AuthTokenStorage {
  _MemoryTokenStorage() : super(const FlutterSecureStorage());

  AuthSession? session;
  int readCount = 0;

  @override
  Future<AuthSession?> readSession() async {
    readCount++;
    return session;
  }

  @override
  Future<void> saveSession(AuthSession value) async {
    session = value;
  }

  @override
  Future<void> clearSession() async {
    session = null;
  }
}

class _LoginRepository extends AuthRepository {
  _LoginRepository({
    this.loginStatus,
    this.loginError,
    this.fetchNetworkError = false,
  }) : super(AuthApi(Dio()));

  final int? loginStatus;
  final Object? loginError;
  final bool fetchNetworkError;
  final Completer<void> _loginGate = Completer<void>();

  void releaseLogin() {
    if (!_loginGate.isCompleted) _loginGate.complete();
  }

  @override
  Future<AuthSession> login({
    required String username,
    required String password,
  }) async {
    await _loginGate.future;
    if (loginError case final Object error) {
      throw error;
    }
    if (loginStatus case final int status) {
      final RequestOptions request = RequestOptions(path: '/api/v1/auth/login');
      throw DioException.badResponse(
        statusCode: status,
        requestOptions: request,
        response: Response<void>(requestOptions: request, statusCode: status),
      );
    }
    return _session;
  }

  @override
  Future<CurrentUser> fetchCurrentUser(AuthSession session) async {
    if (fetchNetworkError) {
      throw DioException.connectionError(
        requestOptions: RequestOptions(path: '/api/v1/auth/me'),
        reason: 'offline',
      );
    }
    return const CurrentUser(
      id: 1,
      username: 'user',
      email: 'user@example.invalid',
      role: 'user',
      isActive: true,
      mustChangePassword: false,
      passwordResetRequested: false,
    );
  }
}
