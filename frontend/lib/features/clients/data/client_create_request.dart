import '../domain/client.dart';

class ClientCreateRequest {
  const ClientCreateRequest({
    required this.clientType,
    required this.name,
    required this.countryCode,
    this.legalName,
    this.taxId,
    this.registrationNumber,
    this.industryId,
    this.website,
    this.primaryEmail,
    this.primaryPhone,
    this.street,
    this.buildingNumber,
    this.unitNumber,
    this.postalCode,
    this.city,
    this.notes,
  });

  final ClientType clientType;
  final String name;
  final String? legalName;
  final String? taxId;
  final String? registrationNumber;
  final int? industryId;
  final String? website;
  final String? primaryEmail;
  final String? primaryPhone;
  final String? street;
  final String? buildingNumber;
  final String? unitNumber;
  final String? postalCode;
  final String? city;
  final String countryCode;
  final String? notes;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'client_type': clientType.value,
      'name': name.trim(),
      'legal_name': _normalize(legalName),
      'tax_id': _normalize(taxId),
      'registration_number': _normalize(registrationNumber),
      'industry_id': industryId,
      'website': _normalize(website),
      'primary_email': _normalize(primaryEmail),
      'primary_phone': _normalize(primaryPhone),
      'street': _normalize(street),
      'building_number': _normalize(buildingNumber),
      'unit_number': _normalize(unitNumber),
      'postal_code': _normalize(postalCode),
      'city': _normalize(city),
      'country_code': countryCode.trim().toUpperCase(),
      'notes': _normalize(notes),
    };
  }

  String? _normalize(String? value) {
    final String? normalized = value?.trim();

    if (normalized == null || normalized.isEmpty) {
      return null;
    }

    return normalized;
  }
}
