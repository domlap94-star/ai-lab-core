import '../domain/industry.dart';

class IndustryResponse {
  const IndustryResponse({
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

  factory IndustryResponse.fromJson(Map<String, dynamic> json) {
    return IndustryResponse(
      id: _parseInt(json['id']),
      code: json['code']?.toString().trim() ?? '',
      name: json['name']?.toString().trim() ?? '',
      description: _parseNullableString(json['description']),
      isActive: _parseBool(json['is_active']),
    );
  }

  Industry toDomain() {
    return Industry(
      id: id,
      code: code,
      name: name,
      description: description,
      isActive: isActive,
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

  static String? _parseNullableString(dynamic value) {
    final String? parsed = value?.toString().trim();

    if (parsed == null || parsed.isEmpty) {
      return null;
    }

    return parsed;
  }
}
