import 'package:flutter_riverpod/flutter_riverpod.dart';

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

  @override
  Future<AuthState> build() async {
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

      return AuthState(session: session, user: user);
    } catch (_) {
      await _tokenStorage.clearSession();
      return const AuthState.unauthenticated();
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

      return AuthState(session: session, user: user);
    });
  }

  Future<void> logout() async {
    await _tokenStorage.clearSession();

    state = const AsyncData<AuthState>(AuthState.unauthenticated());
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
