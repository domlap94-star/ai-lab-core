import '../data/auth_api.dart';
import '../data/login_request.dart';
import '../domain/auth_session.dart';
import '../domain/current_user.dart';

class AuthRepository {
  const AuthRepository(this._authApi);

  final AuthApi _authApi;

  Future<AuthSession> login({
    required String username,
    required String password,
  }) async {
    final response = await _authApi.login(
      LoginRequest(username: username.trim(), password: password),
    );

    final AuthSession session = response.toDomain();

    if (!session.isAuthenticated) {
      throw const FormatException(
        'Backend nie zwrócił poprawnego tokenu dostępu.',
      );
    }

    return session;
  }

  Future<CurrentUser> fetchCurrentUser(AuthSession session) async {
    final response = await _authApi.fetchCurrentUser(
      accessToken: session.accessToken,
      tokenType: session.tokenType,
    );

    return response.toDomain();
  }
}
