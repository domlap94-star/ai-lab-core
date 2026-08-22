import 'industry.dart';

class ClientContactPoint {
  const ClientContactPoint({
    required this.id,
    required this.value,
    required this.isPrimary,
    this.origin = 'manual',
    this.sourceType,
    this.sourceId,
    this.contactPersonId,
  });
  final int id;
  final String value;
  final bool isPrimary;
  final String origin;
  final String? sourceType;
  final int? sourceId;
  final int? contactPersonId;
}

class ContactPerson {
  const ContactPerson({
    required this.id,
    required this.clientId,
    required this.displayName,
    required this.isPreferred,
    required this.isDecisionMaker,
    required this.position,
    required this.origin,
    required this.createdAt,
    required this.updatedAt,
    this.role,
    this.notes,
    this.sourceType,
    this.sourceId,
    this.contactPoints = const <ClientContactPoint>[],
  });

  final int id;
  final int clientId;
  final String displayName;
  final String? role;
  final bool isPreferred;
  final bool isDecisionMaker;
  final String? notes;
  final int position;
  final String origin;
  final String? sourceType;
  final int? sourceId;
  final DateTime createdAt;
  final DateTime updatedAt;
  final List<ClientContactPoint> contactPoints;

  List<ClientContactPoint> get emails => contactPoints
      .where((item) => item.value.contains('@'))
      .toList(growable: false);
  List<ClientContactPoint> get phones => contactPoints
      .where((item) => !item.value.contains('@'))
      .toList(growable: false);
}

class ClientAddress {
  const ClientAddress({
    required this.id,
    required this.label,
    required this.countryCode,
    required this.isPrimary,
    this.street,
    this.buildingNumber,
    this.unitNumber,
    this.postalCode,
    this.city,
    this.origin = 'manual',
    this.sourceType,
    this.sourceId,
  });

  final int id;
  final String label;
  final String? street;
  final String? buildingNumber;
  final String? unitNumber;
  final String? postalCode;
  final String? city;
  final String countryCode;
  final bool isPrimary;
  final String origin;
  final String? sourceType;
  final int? sourceId;

  String get formatted {
    final parts = <String>[
      [
        street,
        buildingNumber,
        if (unitNumber?.isNotEmpty == true) 'lok. $unitNumber',
      ].whereType<String>().where((value) => value.trim().isNotEmpty).join(' '),
      [
        postalCode,
        city,
      ].whereType<String>().where((value) => value.trim().isNotEmpty).join(' '),
      countryCode,
    ].where((value) => value.trim().isNotEmpty).toList();
    return parts.join(', ');
  }
}

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
    this.emails = const <ClientContactPoint>[],
    this.phones = const <ClientContactPoint>[],
    this.addresses = const <ClientAddress>[],
    this.contactPersons = const <ContactPerson>[],
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
  final String workflowStatus;
  final String workflowStatusLabel;
  final DateTime? workflowEffectiveDate;
  final DateTime? sourceRecordDate;
  final DateTime? clientAddedAt;
  final DateTime effectiveAddedDate;
  final DateTime? deletedAt;
  final List<ClientContactPoint> emails;
  final List<ClientContactPoint> phones;
  final List<ClientAddress> addresses;
  final List<ContactPerson> contactPersons;

  List<ClientContactPoint> get genericEmails => emails
      .where((item) => item.contactPersonId == null)
      .toList(growable: false);
  List<ClientContactPoint> get genericPhones => phones
      .where((item) => item.contactPersonId == null)
      .toList(growable: false);

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
    ClientAddress? primaryAddress;
    for (final item in addresses) {
      if (item.isPrimary) {
        primaryAddress = item;
        break;
      }
    }
    if (primaryAddress != null && primaryAddress.formatted.isNotEmpty) {
      return primaryAddress.formatted;
    }
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
