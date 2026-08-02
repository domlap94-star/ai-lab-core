class AuthSession {
  const AuthSession({required this.accessToken, required this.tokenType});

  final String accessToken;
  final String tokenType;

  bool get isAuthenticated => accessToken.isNotEmpty;
}
