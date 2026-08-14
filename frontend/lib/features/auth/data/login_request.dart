class LoginRequest {
  const LoginRequest({required this.username, required this.password});

  final String username;
  final String password;

  Map<String, dynamic> toFormData() {
    return <String, dynamic>{'username': username, 'password': password};
  }
}
