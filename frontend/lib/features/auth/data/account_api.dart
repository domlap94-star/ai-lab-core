import 'package:dio/dio.dart';

import '../domain/auth_session.dart';

class ManagedUser {
  const ManagedUser({
    required this.id,
    required this.username,
    required this.email,
    required this.isActive,
    required this.role,
    required this.mustChangePassword,
    required this.passwordResetRequested,
  });

  factory ManagedUser.fromJson(Map<String, dynamic> json) {
    return ManagedUser(
      id: json['id'] as int,
      username: json['username']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      isActive: json['is_active'] == true,
      role: json['role']?.toString() ?? '',
      mustChangePassword: json['must_change_password'] == true,
      passwordResetRequested: json['password_reset_requested'] == true,
    );
  }

  final int id;
  final String username;
  final String email;
  final bool isActive;
  final String role;
  final bool mustChangePassword;
  final bool passwordResetRequested;
}

class AccountApi {
  const AccountApi(this._dio);

  final Dio _dio;

  Options _authorizedOptions(AuthSession session) {
    return Options(
      headers: <String, Object>{
        'Authorization': '${session.tokenType} ${session.accessToken}',
        'Accept': 'application/json',
      },
    );
  }

  Future<void> changePassword({
    required AuthSession session,
    required String currentPassword,
    required String newPassword,
  }) async {
    await _dio.post<void>(
      '/api/v1/auth/change-password',
      data: <String, Object>{
        'current_password': currentPassword,
        'new_password': newPassword,
      },
      options: _authorizedOptions(session),
    );
  }

  Future<void> requestPasswordReset({required String identifier}) async {
    await _dio.post<void>(
      '/api/v1/auth/reset-password/request',
      data: <String, Object>{'identifier': identifier.trim()},
    );
  }

  Future<List<ManagedUser>> fetchUsers({required AuthSession session}) async {
    final Response<dynamic> response = await _dio.get<dynamic>(
      '/api/v1/admin/users',
      options: _authorizedOptions(session),
    );

    final dynamic data = response.data;

    if (data is! List) {
      throw const FormatException('Backend nie zwrócił listy użytkowników.');
    }

    return data
        .whereType<Map>()
        .map(
          (Map<dynamic, dynamic> value) => ManagedUser.fromJson(
            value.map(
              (dynamic key, dynamic item) => MapEntry(key.toString(), item),
            ),
          ),
        )
        .toList();
  }

  Future<void> createUser({
    required AuthSession session,
    required String username,
    required String email,
    required String role,
    required String temporaryPassword,
  }) async {
    await _dio.post<void>(
      '/api/v1/admin/users',
      data: <String, Object>{
        'username': username.trim(),
        'email': email.trim(),
        'role': role,
        'temporary_password': temporaryPassword,
        'must_change_password': true,
      },
      options: _authorizedOptions(session),
    );
  }

  Future<void> resetUserPassword({
    required AuthSession session,
    required int userId,
    required String temporaryPassword,
  }) async {
    await _dio.post<void>(
      '/api/v1/admin/users/$userId/reset-password',
      data: <String, Object>{'temporary_password': temporaryPassword},
      options: _authorizedOptions(session),
    );
  }
}
