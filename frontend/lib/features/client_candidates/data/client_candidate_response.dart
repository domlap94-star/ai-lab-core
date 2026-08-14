import '../domain/client_candidate.dart';

class ClientCandidateResponse {
  const ClientCandidateResponse({
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

  factory ClientCandidateResponse.fromJson(Map<String, dynamic> json) {
    return ClientCandidateResponse(
      id: json['id'] as int,
      clientType: json['client_type']?.toString() ?? 'other',
      name: json['name']?.toString() ?? '',
      legalName: json['legal_name']?.toString(),
      taxId: json['tax_id']?.toString(),
      primaryEmail: json['primary_email']?.toString(),
      primaryPhone: json['primary_phone']?.toString(),
      city: json['city']?.toString(),
      countryCode: json['country_code']?.toString() ?? 'PL',
      status: json['status']?.toString() ?? 'pending',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
      matchedClientId: json['matched_client_id'] as int?,
      sourceSummary: json['source_summary']?.toString(),
    );
  }

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

  ClientCandidate toDomain() {
    return ClientCandidate(
      id: id,
      clientType: clientType,
      name: name,
      legalName: legalName,
      taxId: taxId,
      primaryEmail: primaryEmail,
      primaryPhone: primaryPhone,
      city: city,
      countryCode: countryCode,
      status: status,
      confidence: confidence,
      matchedClientId: matchedClientId,
      sourceSummary: sourceSummary,
    );
  }
}
