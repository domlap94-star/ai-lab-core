class Industry {
  const Industry({
    required this.id,
    required this.code,
    required this.name,
    required this.isActive,
    this.description,
  });

  final int id;
  final String code;
  final String name;
  final String? description;
  final bool isActive;
}
