import '../domain/auth_session.dart';
import '../domain/current_user.dart';

class AuthState {
  const AuthState({required this.session, required this.user});

  const AuthState.unauthenticated() : session = null, user = null;

  final AuthSession? session;
  final CurrentUser? user;

  bool get isAuthenticated {
    return session?.isAuthenticated == true && user != null;
  }

  AuthState copyWith({
    AuthSession? session,
    CurrentUser? user,
    bool clearSession = false,
    bool clearUser = false,
  }) {
    return AuthState(
      session: clearSession ? null : session ?? this.session,
      user: clearUser ? null : user ?? this.user,
    );
  }
}
