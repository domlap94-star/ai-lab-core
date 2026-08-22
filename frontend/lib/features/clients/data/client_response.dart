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
    required this.effectiveAddedDate,
    this.workflowStatus = 'untouched',
    this.workflowStatusLabel = 'Brak modyfikacji',
    this.workflowEffectiveDate,
    this.sourceRecordDate,
    this.clientAddedAt,
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
    this.emails = const <Map<String, dynamic>>[],
    this.phones = const <Map<String, dynamic>>[],
    this.addresses = const <Map<String, dynamic>>[],
    this.contactPersons = const <Map<String, dynamic>>[],
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
  final String workflowStatus;
  final String workflowStatusLabel;
  final DateTime? workflowEffectiveDate;
  final DateTime? sourceRecordDate;
  final DateTime? clientAddedAt;
  final DateTime effectiveAddedDate;
  final DateTime? deletedAt;
  final List<Map<String, dynamic>> emails;
  final List<Map<String, dynamic>> phones;
  final List<Map<String, dynamic>> addresses;
  final List<Map<String, dynamic>> contactPersons;

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
      clientAddedAt: _parseNullableDateTime(json['client_added_at']),
      effectiveAddedDate: _parseDateTime(json['effective_added_date']),
      createdAt: _parseDateTime(json['created_at']),
      updatedAt: _parseDateTime(json['updated_at']),
      workflowStatus: json['workflow_status']?.toString() ?? 'untouched',
      workflowStatusLabel:
          json['workflow_status_label']?.toString() ?? 'Brak modyfikacji',
      workflowEffectiveDate: _parseNullableDateTime(
        json['workflow_effective_date'],
      ),
      deletedAt: _parseNullableDateTime(json['deleted_at']),
      emails: _parseContacts(json['emails']),
      phones: _parseContacts(json['phones']),
      addresses: _parseContacts(json['addresses']),
      contactPersons: _parseContacts(json['contact_persons']),
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
      clientAddedAt: clientAddedAt,
      effectiveAddedDate: effectiveAddedDate,
      createdAt: createdAt,
      updatedAt: updatedAt,
      workflowStatus: workflowStatus,
      workflowStatusLabel: workflowStatusLabel,
      workflowEffectiveDate: workflowEffectiveDate,
      deletedAt: deletedAt,
      emails: emails
          .map(
            (item) => ClientContactPoint(
              id: _parseInt(item['id']),
              value: item['value']?.toString() ?? '',
              isPrimary: item['is_primary'] == true,
              origin: item['origin']?.toString() ?? 'manual',
              sourceType: _parseNullableString(item['source_type']),
              sourceId: _parseNullableInt(item['source_id']),
              contactPersonId: _parseNullableInt(item['contact_person_id']),
            ),
          )
          .toList(growable: false),
      phones: phones
          .map(
            (item) => ClientContactPoint(
              id: _parseInt(item['id']),
              value: item['value']?.toString() ?? '',
              isPrimary: item['is_primary'] == true,
              origin: item['origin']?.toString() ?? 'manual',
              sourceType: _parseNullableString(item['source_type']),
              sourceId: _parseNullableInt(item['source_id']),
              contactPersonId: _parseNullableInt(item['contact_person_id']),
            ),
          )
          .toList(growable: false),
      addresses: addresses
          .map(
            (item) => ClientAddress(
              id: _parseInt(item['id']),
              label: item['label']?.toString() ?? 'Adres',
              street: _parseNullableString(item['street']),
              buildingNumber: _parseNullableString(item['building_number']),
              unitNumber: _parseNullableString(item['unit_number']),
              postalCode: _parseNullableString(item['postal_code']),
              city: _parseNullableString(item['city']),
              countryCode: item['country_code']?.toString() ?? 'PL',
              isPrimary: item['is_primary'] == true,
              origin: item['origin']?.toString() ?? 'manual',
              sourceType: _parseNullableString(item['source_type']),
              sourceId: _parseNullableInt(item['source_id']),
            ),
          )
          .toList(growable: false),
      contactPersons: contactPersons
          .map<ContactPerson>(_parseContactPerson)
          .toList(growable: false),
    );
  }

  static ContactPerson _parseContactPerson(Map<String, dynamic> item) {
    final List<ClientContactPoint> points =
        _parseContacts(item['contact_points'])
            .map<ClientContactPoint>(
              (point) => ClientContactPoint(
                id: _parseInt(point['id']),
                value: point['value']?.toString() ?? '',
                isPrimary: point['is_primary'] == true,
                origin: point['origin']?.toString() ?? 'manual',
                sourceType: _parseNullableString(point['source_type']),
                sourceId: _parseNullableInt(point['source_id']),
                contactPersonId: _parseNullableInt(point['contact_person_id']),
              ),
            )
            .toList(growable: false);
    return ContactPerson(
      id: _parseInt(item['id']),
      clientId: _parseInt(item['client_id']),
      displayName: item['display_name']?.toString() ?? '',
      role: _parseNullableString(item['role']),
      isPreferred: item['is_preferred'] == true,
      isDecisionMaker: item['is_decision_maker'] == true,
      notes: _parseNullableString(item['notes']),
      position: _parseInt(item['position']),
      origin: item['origin']?.toString() ?? 'manual',
      sourceType: _parseNullableString(item['source_type']),
      sourceId: _parseNullableInt(item['source_id']),
      createdAt: _parseDateTime(item['created_at']),
      updatedAt: _parseDateTime(item['updated_at']),
      contactPoints: points,
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

  static List<Map<String, dynamic>> _parseContacts(dynamic value) =>
      value is List
      ? value
            .whereType<Map>()
            .map((item) => Map<String, dynamic>.from(item))
            .toList()
      : const <Map<String, dynamic>>[];
}
