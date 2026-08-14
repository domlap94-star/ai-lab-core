import '../domain/auth_session.dart';

class LoginResponse {
  const LoginResponse({required this.accessToken, required this.tokenType});

  final String accessToken;
  final String tokenType;

  factory LoginResponse.fromJson(Map<String, dynamic> json) {
    return LoginResponse(
      accessToken: json['access_token']?.toString() ?? '',
      tokenType: json['token_type']?.toString() ?? 'bearer',
    );
  }

  AuthSession toDomain() {
    return AuthSession(accessToken: accessToken, tokenType: tokenType);
  }
}
