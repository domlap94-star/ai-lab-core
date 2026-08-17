import '../domain/auth_session.dart';
import '../domain/current_user.dart';

class AuthState {
  const AuthState({required this.session, required this.user, this.notice});

  const AuthState.unauthenticated({this.notice}) : session = null, user = null;

  final AuthSession? session;
  final CurrentUser? user;
  final String? notice;

  bool get isAuthenticated {
    return session?.isAuthenticated == true && user != null;
  }

  AuthState copyWith({
    AuthSession? session,
    CurrentUser? user,
    bool clearSession = false,
    bool clearUser = false,
    String? notice,
    bool clearNotice = false,
  }) {
    return AuthState(
      session: clearSession ? null : session ?? this.session,
      user: clearUser ? null : user ?? this.user,
      notice: clearNotice ? null : notice ?? this.notice,
    );
  }
}
