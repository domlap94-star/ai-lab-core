import 'industry.dart';

enum ClientType {
  company,
  person,
  institution,
  other;

  static ClientType fromValue(String value) {
    return switch (value) {
      'company' => ClientType.company,
      'person' => ClientType.person,
      'institution' => ClientType.institution,
      _ => ClientType.other,
    };
  }

  String get value {
    return switch (this) {
      ClientType.company => 'company',
      ClientType.person => 'person',
      ClientType.institution => 'institution',
      ClientType.other => 'other',
    };
  }

  String get displayName {
    return switch (this) {
      ClientType.company => 'Firma',
      ClientType.person => 'Osoba fizyczna',
      ClientType.institution => 'Instytucja',
      ClientType.other => 'Inny',
    };
  }
}

class Client {
  const Client({
    required this.id,
    required this.clientType,
    required this.name,
    required this.countryCode,
    required this.createdAt,
    required this.updatedAt,
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
  final ClientType clientType;
  final String name;
  final String? legalName;
  final String? taxId;
  final String? registrationNumber;
  final int? industryId;
  final Industry? industry;
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
  final DateTime? deletedAt;

  String get displayName {
    return name.trim().isEmpty ? 'Klient bez nazwy' : name.trim();
  }

  String get address {
    final List<String> streetParts = <String>[
      if (street?.trim().isNotEmpty == true) street!.trim(),
      if (buildingNumber?.trim().isNotEmpty == true) buildingNumber!.trim(),
      if (unitNumber?.trim().isNotEmpty == true) 'lok. ${unitNumber!.trim()}',
    ];

    final List<String> cityParts = <String>[
      if (postalCode?.trim().isNotEmpty == true) postalCode!.trim(),
      if (city?.trim().isNotEmpty == true) city!.trim(),
    ];

    return <String>[
      if (streetParts.isNotEmpty) streetParts.join(' '),
      if (cityParts.isNotEmpty) cityParts.join(' '),
      if (countryCode.trim().isNotEmpty) countryCode.trim(),
    ].join(', ');
  }

  bool get hasContactData {
    return primaryEmail?.trim().isNotEmpty == true ||
        primaryPhone?.trim().isNotEmpty == true;
  }
}
