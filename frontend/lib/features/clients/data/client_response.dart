import '../domain/client.dart';
import 'industry_response.dart';

class ClientResponse {
  const ClientResponse({
    required this.id,
    required this.clientType,
    required this.name,
    required this.countryCode,
    required this.createdAt,
    required this.updatedAt,
    this.sourceRecordDate,
    this.legalName,
    this.taxId,
    this.registrationNumber,
    this.industryId,
    this.industry,
    this.website,
    this.primaryEmail,
    this.primaryPhone,
    this.street,
    this.buildingNumber,
    this.unitNumber,
    this.postalCode,
    this.city,
    this.notes,
    this.deletedAt,
  });

  final int id;
  final String clientType;
  final String name;
  final String? legalName;
  final String? taxId;
  final String? registrationNumber;
  final int? industryId;
  final IndustryResponse? industry;
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
  final DateTime createdAt;
  final DateTime updatedAt;
  final DateTime? sourceRecordDate;
  final DateTime? deletedAt;

  factory ClientResponse.fromJson(Map<String, dynamic> json) {
    final dynamic industryJson = json['industry'];

    return ClientResponse(
      id: _parseInt(json['id']),
      clientType: json['client_type']?.toString() ?? 'other',
      name: json['name']?.toString() ?? '',
      legalName: _parseNullableString(json['legal_name']),
      taxId: _parseNullableString(json['tax_id']),
      registrationNumber: _parseNullableString(json['registration_number']),
      industryId: _parseNullableInt(json['industry_id']),
      industry: industryJson is Map
          ? IndustryResponse.fromJson(Map<String, dynamic>.from(industryJson))
          : null,
      website: _parseNullableString(json['website']),
      primaryEmail: _parseNullableString(json['primary_email']),
      primaryPhone: _parseNullableString(json['primary_phone']),
      street: _parseNullableString(json['street']),
      buildingNumber: _parseNullableString(json['building_number']),
      unitNumber: _parseNullableString(json['unit_number']),
      postalCode: _parseNullableString(json['postal_code']),
      city: _parseNullableString(json['city']),
      countryCode: json['country_code']?.toString() ?? 'PL',
      notes: _parseNullableString(json['notes']),
      sourceRecordDate: _parseNullableDateTime(json['source_record_date']),
      createdAt: _parseDateTime(json['created_at']),
      updatedAt: _parseDateTime(json['updated_at']),
      deletedAt: _parseNullableDateTime(json['deleted_at']),
    );
  }

  Client toDomain() {
    return Client(
      id: id,
      clientType: ClientType.fromValue(clientType),
      name: name,
      legalName: legalName,
      taxId: taxId,
      registrationNumber: registrationNumber,
      industryId: industryId,
      industry: industry?.toDomain(),
      website: website,
      primaryEmail: primaryEmail,
      primaryPhone: primaryPhone,
      street: street,
      buildingNumber: buildingNumber,
      unitNumber: unitNumber,
      postalCode: postalCode,
      city: city,
      countryCode: countryCode,
      notes: notes,
      sourceRecordDate: sourceRecordDate,
      createdAt: createdAt,
      updatedAt: updatedAt,
      deletedAt: deletedAt,
    );
  }

  static int _parseInt(dynamic value) {
    if (value is int) {
      return value;
    }

    return int.tryParse(value?.toString() ?? '') ?? 0;
  }

  static int? _parseNullableInt(dynamic value) {
    if (value == null) {
      return null;
    }

    if (value is int) {
      return value;
    }

    return int.tryParse(value.toString());
  }

  static DateTime _parseDateTime(dynamic value) {
    final DateTime? parsed = DateTime.tryParse(value?.toString() ?? '');

    return parsed ?? DateTime.fromMillisecondsSinceEpoch(0);
  }

  static DateTime? _parseNullableDateTime(dynamic value) {
    if (value == null) {
      return null;
    }

    return DateTime.tryParse(value.toString());
  }

  static String? _parseNullableString(dynamic value) {
    final String? parsed = value?.toString().trim();

    if (parsed == null || parsed.isEmpty) {
      return null;
    }

    return parsed;
  }
}
