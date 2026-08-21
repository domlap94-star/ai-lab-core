enum ProjectStatus { planned, active, completed, cancelled }

extension ProjectStatusLabel on ProjectStatus {
  String get label => switch (this) {
    ProjectStatus.planned => 'Planowana',
    ProjectStatus.active => 'Aktywna',
    ProjectStatus.completed => 'Zakończona',
    ProjectStatus.cancelled => 'Anulowana',
  };
}

class Project {
  const Project({
    required this.id,
    required this.clientId,
    required this.clientName,
    required this.name,
    required this.status,
    required this.countryCode,
    required this.createdAt,
    required this.updatedAt,
    this.description,
    this.startDate,
    this.endDate,
    this.street,
    this.buildingNumber,
    this.unitNumber,
    this.postalCode,
    this.city,
    this.latitude,
    this.longitude,
    this.workItemId,
  });
  final int id;
  final int? workItemId;
  final int clientId;
  final String clientName;
  final String name;
  final String? description;
  final ProjectStatus status;
  final DateTime? startDate;
  final DateTime? endDate;
  final String? street;
  final String? buildingNumber;
  final String? unitNumber;
  final String? postalCode;
  final String? city;
  final String countryCode;
  final double? latitude;
  final double? longitude;
  final DateTime createdAt;
  final DateTime updatedAt;
  String get location => <String?>[
    street,
    buildingNumber,
    unitNumber,
    postalCode,
    city,
    countryCode,
  ].whereType<String>().where((value) => value.trim().isNotEmpty).join(' ');
  factory Project.fromJson(Map<String, dynamic> json) => Project(
    id: json['id'] as int,
    clientId: json['client_id'] as int,
    clientName: json['client_name']?.toString() ?? '',
    name: json['name']?.toString() ?? '',
    description: json['description']?.toString(),
    status: ProjectStatus.values.firstWhere(
      (value) => value.name == json['status'],
      orElse: () => ProjectStatus.planned,
    ),
    startDate: DateTime.tryParse(json['start_date']?.toString() ?? ''),
    endDate: DateTime.tryParse(json['end_date']?.toString() ?? ''),
    street: json['street']?.toString(),
    buildingNumber: json['building_number']?.toString(),
    unitNumber: json['unit_number']?.toString(),
    postalCode: json['postal_code']?.toString(),
    city: json['city']?.toString(),
    countryCode: json['country_code']?.toString() ?? 'PL',
    latitude: (json['latitude'] as num?)?.toDouble(),
    longitude: (json['longitude'] as num?)?.toDouble(),
    workItemId: json['work_item_id'] as int?,
    createdAt: DateTime.parse(json['created_at'].toString()),
    updatedAt: DateTime.parse(json['updated_at'].toString()),
  );
}

class ProjectPage {
  const ProjectPage({
    required this.items,
    required this.total,
    required this.skip,
    required this.limit,
  });
  final List<Project> items;
  final int total;
  final int skip;
  final int limit;
}
