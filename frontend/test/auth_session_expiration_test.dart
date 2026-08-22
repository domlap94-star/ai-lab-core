import 'dart:convert';
import 'dart:typed_data';

import 'package:ai_lab/core/network/api_client.dart';
import 'package:ai_lab/core/network/session_expiration_coordinator.dart';
import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_providers.dart';
import 'package:ai_lab/features/auth/application/auth_repository.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/data/auth_api.dart';
import 'package:ai_lab/features/auth/data/auth_token_storage.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/auth/domain/current_user.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('expired token clears session and allows a clean next login', () async {
    final _MemoryTokenStorage storage = _MemoryTokenStorage(_sessionA);
    final _AuthRepository repository = _AuthRepository();
    final ProviderContainer container = ProviderContainer(
      overrides: [
        authTokenStorageProvider.overrideWithValue(storage),
        authRepositoryProvider.overrideWithValue(repository),
      ],
    );
    addTearDown(container.dispose);

    final AuthState initial = await container.read(
      authControllerProvider.future,
    );
    expect(initial.user?.username, 'user-a');

    final coordinator = container.read(sessionExpirationCoordinatorProvider);
    await coordinator.handleUnauthorized(
      _sessionA.accessToken,
      requestGeneration: coordinator.captureGeneration(_sessionA.accessToken),
    );

    final AuthState expired = container
        .read(authControllerProvider)
        .requireValue;
    expect(expired.isAuthenticated, isFalse);
    expect(expired.notice, 'Sesja wygasła. Zaloguj się ponownie.');
    expect(storage.clearCount, 1);
    expect(storage.session, isNull);

    await container
        .read(authControllerProvider.notifier)
        .login(username: 'user-b', password: 'valid');

    final AuthState relogged = container
        .read(authControllerProvider)
        .requireValue;
    expect(relogged.user?.username, 'user-b');
    expect(relogged.session?.accessToken, _sessionB.accessToken);
    expect(relogged.notice, isNull);

    await coordinator.handleUnauthorized(
      _sessionA.accessToken,
      requestGeneration: coordinator.captureGeneration(_sessionA.accessToken),
    );
    expect(
      container.read(authControllerProvider).requireValue.user?.username,
      'user-b',
    );
  });

  test('401 during restore clears the rejected stored session', () async {
    final _MemoryTokenStorage storage = _MemoryTokenStorage(_sessionA);
    final _AuthRepository repository = _AuthRepository(
      fetchError: DioException.badResponse(
        statusCode: 401,
        requestOptions: RequestOptions(path: '/api/v1/auth/me'),
        response: Response<void>(
          requestOptions: RequestOptions(path: '/api/v1/auth/me'),
          statusCode: 401,
        ),
      ),
    );
    final ProviderContainer container = ProviderContainer(
      overrides: [
        authTokenStorageProvider.overrideWithValue(storage),
        authRepositoryProvider.overrideWithValue(repository),
      ],
    );
    addTearDown(container.dispose);

    final AuthState state = await container.read(authControllerProvider.future);
    expect(state.isAuthenticated, isFalse);
    expect(state.notice, 'Sesja wygasła. Zaloguj się ponownie.');
    expect(storage.clearCount, 1);
    expect(storage.session, isNull);
  });

  test(
    'expired stored token is cleared before fresh login and never reaches login header',
    () async {
      final List<String> events = <String>[];
      final _MemoryTokenStorage storage = _MemoryTokenStorage(
        _sessionA,
        events: events,
      );
      final _ExpiredThenFreshAdapter adapter = _ExpiredThenFreshAdapter(events);
      final SessionExpirationCoordinator coordinator =
          SessionExpirationCoordinator();
      final Dio dio = Dio(BaseOptions(baseUrl: 'https://example.invalid'))
        ..httpClientAdapter = adapter;
      installSessionExpirationInterceptor(dio, coordinator);
      final ProviderContainer container = ProviderContainer(
        overrides: [
          authTokenStorageProvider.overrideWithValue(storage),
          dioProvider.overrideWithValue(dio),
          sessionExpirationCoordinatorProvider.overrideWithValue(coordinator),
        ],
      );
      addTearDown(container.dispose);

      final AuthState expired = await container.read(
        authControllerProvider.future,
      );
      expect(expired.isAuthenticated, isFalse);
      expect(expired.notice, 'Sesja wygasła. Zaloguj się ponownie.');
      expect(storage.session, isNull);
      expect(events, <String>[
        'GET /api/v1/auth/me authorization=Bearer token-a',
        'storage.clear',
      ]);

      await container
          .read(authControllerProvider.notifier)
          .login(username: 'user-b', password: 'valid');

      final AuthState authenticated = container
          .read(authControllerProvider)
          .requireValue;
      expect(authenticated.user?.username, 'user-b');
      expect(authenticated.session?.accessToken, _sessionB.accessToken);
      expect(storage.session?.accessToken, _sessionB.accessToken);
      expect(storage.session?.tokenType, _sessionB.tokenType);
      expect(events, <String>[
        'GET /api/v1/auth/me authorization=Bearer token-a',
        'storage.clear',
        'POST /api/v1/auth/login authorization=none',
        'GET /api/v1/auth/me authorization=Bearer token-b',
        'storage.save',
      ]);
    },
  );

  test(
    'network failure during restore preserves token with clear notice',
    () async {
      final _MemoryTokenStorage storage = _MemoryTokenStorage(_sessionA);
      final _AuthRepository repository = _AuthRepository(
        fetchError: DioException.connectionError(
          requestOptions: RequestOptions(path: '/api/v1/auth/me'),
          reason: 'offline',
        ),
      );
      final ProviderContainer container = ProviderContainer(
        overrides: [
          authTokenStorageProvider.overrideWithValue(storage),
          authRepositoryProvider.overrideWithValue(repository),
        ],
      );
      addTearDown(container.dispose);

      final AuthState state = await container.read(
        authControllerProvider.future,
      );
      expect(state.isAuthenticated, isFalse);
      expect(
        state.notice,
        'Nie udało się sprawdzić sesji. Sprawdź połączenie i spróbuj ponownie.',
      );
      expect(storage.clearCount, 0);
      expect(storage.session, _sessionA);
    },
  );

  test(
    'malformed session response preserves token with clear notice',
    () async {
      final _MemoryTokenStorage storage = _MemoryTokenStorage(_sessionA);
      final _AuthRepository repository = _AuthRepository(
        fetchError: const FormatException('synthetic malformed response'),
      );
      final ProviderContainer container = ProviderContainer(
        overrides: [
          authTokenStorageProvider.overrideWithValue(storage),
          authRepositoryProvider.overrideWithValue(repository),
        ],
      );
      addTearDown(container.dispose);

      final AuthState state = await container.read(
        authControllerProvider.future,
      );
      expect(state.isAuthenticated, isFalse);
      expect(
        state.notice,
        'Nie udało się sprawdzić sesji. Sprawdź połączenie i spróbuj ponownie.',
      );
      expect(storage.clearCount, 0);
      expect(storage.session, _sessionA);
    },
  );
}

const AuthSession _sessionA = AuthSession(
  accessToken: 'token-a',
  tokenType: 'bearer',
);
const AuthSession _sessionB = AuthSession(
  accessToken: 'token-b',
  tokenType: 'bearer',
);

class _MemoryTokenStorage extends AuthTokenStorage {
  _MemoryTokenStorage(this.session, {this.events})
    : super(const FlutterSecureStorage());

  AuthSession? session;
  final List<String>? events;
  int clearCount = 0;

  @override
  Future<void> saveSession(AuthSession value) async {
    events?.add('storage.save');
    session = value;
  }

  @override
  Future<AuthSession?> readSession() async => session;

  @override
  Future<void> clearSession() async {
    events?.add('storage.clear');
    clearCount++;
    session = null;
  }
}

class _ExpiredThenFreshAdapter implements HttpClientAdapter {
  _ExpiredThenFreshAdapter(this.events);

  final List<String> events;
  int currentUserCalls = 0;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final Object? authorization = options.headers.entries
        .where(
          (MapEntry<String, dynamic> entry) =>
              entry.key.toLowerCase() == 'authorization',
        )
        .map((MapEntry<String, dynamic> entry) => entry.value)
        .firstOrNull;
    events.add(
      '${options.method} ${options.path} '
      'authorization=${authorization ?? 'none'}',
    );

    if (options.method == 'POST' && options.path == '/api/v1/auth/login') {
      return _jsonResponse(200, const <String, Object>{
        'access_token': 'token-b',
        'token_type': 'bearer',
      });
    }
    if (options.method == 'GET' && options.path == '/api/v1/auth/me') {
      currentUserCalls++;
      if (currentUserCalls == 1) {
        return _jsonResponse(401, const <String, Object>{'detail': 'expired'});
      }
      return _jsonResponse(200, const <String, Object>{
        'id': 2,
        'username': 'user-b',
        'email': 'b@example.invalid',
        'role': 'user',
        'is_active': true,
        'must_change_password': false,
        'password_reset_requested': false,
      });
    }
    throw StateError('Unexpected request: ${options.method} ${options.path}');
  }

  ResponseBody _jsonResponse(int status, Map<String, Object> body) {
    return ResponseBody.fromBytes(
      utf8.encode(jsonEncode(body)),
      status,
      headers: <String, List<String>>{
        Headers.contentTypeHeader: <String>['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

class _AuthRepository extends AuthRepository {
  _AuthRepository({this.fetchError}) : super(AuthApi(Dio()));

  final Object? fetchError;

  @override
  Future<AuthSession> login({
    required String username,
    required String password,
  }) async {
    expect(username, 'user-b');
    expect(password, 'valid');
    return _sessionB;
  }

  @override
  Future<CurrentUser> fetchCurrentUser(AuthSession session) async {
    if (fetchError case final Object error) {
      throw error;
    }
    return CurrentUser(
      id: session == _sessionA ? 1 : 2,
      username: session == _sessionA ? 'user-a' : 'user-b',
      email: session == _sessionA ? 'a@example.invalid' : 'b@example.invalid',
      role: 'user',
      isActive: true,
      mustChangePassword: false,
      passwordResetRequested: false,
    );
  }
}
