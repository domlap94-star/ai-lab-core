import '../domain/current_user.dart';

class CurrentUserResponse {
  const CurrentUserResponse({
    required this.id,
    required this.username,
    required this.email,
    required this.role,
    required this.isActive,
    required this.mustChangePassword,
    required this.passwordResetRequested,
  });

  final int id;
  final String username;
  final String email;
  final String role;
  final bool isActive;
  final bool mustChangePassword;
  final bool passwordResetRequested;

  factory CurrentUserResponse.fromJson(Map<String, dynamic> json) {
    return CurrentUserResponse(
      id: _parseInt(json['id']),
      username: json['username']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      role: json['role']?.toString() ?? '',
      isActive: _parseBool(json['is_active'] ?? json['active']),
      mustChangePassword: _parseBool(json['must_change_password']),
      passwordResetRequested: _parseBool(json['password_reset_requested']),
    );
  }

  CurrentUser toDomain() {
    return CurrentUser(
      id: id,
      username: username,
      email: email,
      role: role,
      isActive: isActive,
      mustChangePassword: mustChangePassword,
      passwordResetRequested: passwordResetRequested,
    );
  }

  static int _parseInt(dynamic value) {
    if (value is int) {
      return value;
    }

    return int.tryParse(value?.toString() ?? '') ?? 0;
  }

  static bool _parseBool(dynamic value) {
    if (value is bool) {
      return value;
    }

    return value?.toString().toLowerCase() == 'true';
  }
}
