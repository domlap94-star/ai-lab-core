import 'package:ai_lab/core/network/api_client.dart';
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

    await container
        .read(sessionExpirationCoordinatorProvider)
        .handleUnauthorized(_sessionA.accessToken);

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

    await container
        .read(sessionExpirationCoordinatorProvider)
        .handleUnauthorized(_sessionA.accessToken);
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
  _MemoryTokenStorage(this.session) : super(const FlutterSecureStorage());

  AuthSession? session;
  int clearCount = 0;

  @override
  Future<void> saveSession(AuthSession value) async {
    session = value;
  }

  @override
  Future<AuthSession?> readSession() async => session;

  @override
  Future<void> clearSession() async {
    clearCount++;
    session = null;
  }
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
