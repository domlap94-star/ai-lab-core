import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../../core/network/session_expiration_coordinator.dart';
import '../data/auth_token_storage.dart';
import '../domain/auth_session.dart';
import '../domain/current_user.dart';
import 'auth_providers.dart';
import 'auth_repository.dart';
import 'auth_state.dart';

final authControllerProvider = AsyncNotifierProvider<AuthController, AuthState>(
  AuthController.new,
);

class AuthController extends AsyncNotifier<AuthState> {
  late final AuthRepository _repository;
  late final AuthTokenStorage _tokenStorage;
  late final SessionExpirationCoordinator _sessionExpirationCoordinator;
  late final SessionExpiredHandler _sessionExpiredHandler;

  @override
  Future<AuthState> build() async {
    _sessionExpirationCoordinator = ref.read(
      sessionExpirationCoordinatorProvider,
    );
    _sessionExpiredHandler = _expireSession;
    _sessionExpirationCoordinator.registerHandler(_sessionExpiredHandler);
    ref.onDispose(() {
      _sessionExpirationCoordinator.unregisterHandler(_sessionExpiredHandler);
    });
    _repository = ref.read(authRepositoryProvider);
    _tokenStorage = ref.read(authTokenStorageProvider);

    return _restoreSession();
  }

  Future<AuthState> _restoreSession() async {
    final AuthSession? session = await _tokenStorage.readSession();

    if (session == null || !session.isAuthenticated) {
      return const AuthState.unauthenticated();
    }

    try {
      final CurrentUser user = await _repository.fetchCurrentUser(session);

      if (!user.isActive) {
        await _tokenStorage.clearSession();
        return const AuthState.unauthenticated();
      }

      _sessionExpirationCoordinator.markSessionActive(session.accessToken);
      return AuthState(session: session, user: user);
    } on DioException catch (error) {
      if (error.response?.statusCode != 401) {
        rethrow;
      }
      await _tokenStorage.clearSession();
      return const AuthState.unauthenticated(
        notice: 'Sesja wygasła. Zaloguj się ponownie.',
      );
    }
  }

  Future<void> login({
    required String username,
    required String password,
  }) async {
    state = const AsyncLoading<AuthState>();

    state = await AsyncValue.guard<AuthState>(() async {
      final AuthSession session = await _repository.login(
        username: username,
        password: password,
      );

      final CurrentUser user = await _repository.fetchCurrentUser(session);

      if (!user.isActive) {
        throw const AuthException('Konto użytkownika jest nieaktywne.');
      }

      await _tokenStorage.saveSession(session);
      _sessionExpirationCoordinator.markSessionActive(session.accessToken);

      return AuthState(session: session, user: user);
    });
  }

  Future<void> logout() async {
    await _tokenStorage.clearSession();

    state = const AsyncData<AuthState>(AuthState.unauthenticated());
  }

  Future<void> _expireSession(String rejectedAccessToken) async {
    final AuthSession? currentSession = state.value?.session;
    if (currentSession == null ||
        currentSession.accessToken != rejectedAccessToken) {
      return;
    }

    try {
      await _tokenStorage.clearSession();
    } finally {
      state = const AsyncData<AuthState>(
        AuthState.unauthenticated(
          notice: 'Sesja wygasła. Zaloguj się ponownie.',
        ),
      );
    }
  }

  Future<void> refreshCurrentUser() async {
    final AuthState? currentState = state.value;
    final AuthSession? session = currentState?.session;

    if (session == null || !session.isAuthenticated) {
      state = const AsyncData<AuthState>(AuthState.unauthenticated());
      return;
    }

    state = await AsyncValue.guard<AuthState>(() async {
      final CurrentUser user = await _repository.fetchCurrentUser(session);

      return AuthState(session: session, user: user);
    });
  }
}

class AuthException implements Exception {
  const AuthException(this.message);

  final String message;

  @override
  String toString() => message;
}
