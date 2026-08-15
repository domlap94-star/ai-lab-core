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
  final DateTime? sourceRecordDate;
  final DateTime? deletedAt;

  DateTime get displayCreatedDate => sourceRecordDate ?? createdAt;

  String get displayName {
    return name.trim().isEmpty ? 'Klient bez nazwy' : name.trim();
  }

  bool get hasStructuredAddressData {
    return street?.trim().isNotEmpty == true ||
        buildingNumber?.trim().isNotEmpty == true ||
        unitNumber?.trim().isNotEmpty == true ||
        postalCode?.trim().isNotEmpty == true ||
        city?.trim().isNotEmpty == true;
  }

  String get structuredAddress {
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
      if (hasStructuredAddressData && countryCode.trim().isNotEmpty)
        countryCode.trim(),
    ].join(', ');
  }

  String? get addressFromNotes {
    final String source = notes?.trim() ?? '';

    if (source.isEmpty) {
      return null;
    }

    for (final String rawLine in source.split(RegExp(r'\r?\n'))) {
      final RegExpMatch? match = RegExp(
        r'^\s*adres\s*:\s*(.+?)\s*$',
        caseSensitive: false,
      ).firstMatch(rawLine);

      final String? value = match?.group(1)?.trim();

      if (value != null && value.isNotEmpty) {
        return value;
      }
    }

    return null;
  }

  String? get availableAddress {
    final String structured = structuredAddress.trim();

    if (structured.isNotEmpty) {
      return structured;
    }

    final String? fallback = addressFromNotes;

    if (fallback != null && fallback.trim().isNotEmpty) {
      return fallback.trim();
    }

    return null;
  }

  String get address {
    return availableAddress ?? '';
  }

  String? get displayNotes {
    final String source = notes?.trim() ?? '';

    if (source.isEmpty) {
      return null;
    }

    final List<String> lines = source
        .split(RegExp(r'\r?\n'))
        .where(
          (String rawLine) =>
              !RegExp(r'^\s*adres\s*:', caseSensitive: false).hasMatch(rawLine),
        )
        .map((String value) => value.trimRight())
        .toList();

    while (lines.isNotEmpty && lines.first.trim().isEmpty) {
      lines.removeAt(0);
    }

    while (lines.isNotEmpty && lines.last.trim().isEmpty) {
      lines.removeLast();
    }

    final String result = lines.join('\n').trim();

    return result.isEmpty ? null : result;
  }

  bool get hasContactData {
    return primaryEmail?.trim().isNotEmpty == true ||
        primaryPhone?.trim().isNotEmpty == true;
  }
}
