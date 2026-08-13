class ClientCandidate {
  const ClientCandidate({
    required this.id,
    required this.clientType,
    required this.name,
    required this.legalName,
    required this.taxId,
    required this.primaryEmail,
    required this.primaryPhone,
    required this.city,
    required this.countryCode,
    required this.status,
    required this.confidence,
    required this.matchedClientId,
    required this.sourceSummary,
  });

  final int id;
  final String clientType;
  final String name;
  final String? legalName;
  final String? taxId;
  final String? primaryEmail;
  final String? primaryPhone;
  final String? city;
  final String countryCode;
  final String status;
  final double confidence;
  final int? matchedClientId;
  final String? sourceSummary;

  String get displayName {
    final String trimmed = name.trim();

    if (trimmed.isNotEmpty) {
      return trimmed;
    }

    return primaryEmail ?? 'Kandydat #$id';
  }
}
