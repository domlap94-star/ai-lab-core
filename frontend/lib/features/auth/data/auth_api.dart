import 'package:dio/dio.dart';

import 'current_user_response.dart';
import 'login_request.dart';
import 'login_response.dart';

class AuthApi {
  const AuthApi(this._dio);

  final Dio _dio;

  static const String _loginPath = '/api/v1/auth/login';
  static const String _currentUserPath = '/api/v1/auth/me';

  Future<LoginResponse> login(LoginRequest request) async {
    final Response<Map<String, dynamic>> response = await _dio
        .post<Map<String, dynamic>>(
          _loginPath,
          data: request.toFormData(),
          options: Options(contentType: Headers.formUrlEncodedContentType),
        );

    final Map<String, dynamic>? data = response.data;

    if (data == null) {
      throw const FormatException(
        'Endpoint logowania zwrócił pustą odpowiedź.',
      );
    }

    return LoginResponse.fromJson(data);
  }

  Future<CurrentUserResponse> fetchCurrentUser({
    required String accessToken,
    required String tokenType,
  }) async {
    final String normalizedTokenType = tokenType.trim().isEmpty
        ? 'Bearer'
        : _capitalize(tokenType.trim());

    final Response<Map<String, dynamic>> response = await _dio
        .get<Map<String, dynamic>>(
          _currentUserPath,
          options: Options(
            headers: <String, Object>{
              'Authorization': '$normalizedTokenType $accessToken',
            },
          ),
        );

    final Map<String, dynamic>? data = response.data;

    if (data == null) {
      throw const FormatException(
        'Endpoint użytkownika zwrócił pustą odpowiedź.',
      );
    }

    return CurrentUserResponse.fromJson(data);
  }

  String _capitalize(String value) {
    if (value.isEmpty) {
      return value;
    }

    return '${value[0].toUpperCase()}${value.substring(1).toLowerCase()}';
  }
}
