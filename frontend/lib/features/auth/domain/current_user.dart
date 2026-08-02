class CurrentUser {
  const CurrentUser({
    required this.id,
    required this.username,
    required this.email,
    required this.role,
    required this.isActive,
  });

  final int id;
  final String username;
  final String email;
  final String role;
  final bool isActive;
}
