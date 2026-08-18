enum InspectionStatus { planned, inProgress, completed, cancelled }

extension InspectionStatusValue on InspectionStatus {
  String get apiValue => switch (this) {
    InspectionStatus.planned => 'planned',
    InspectionStatus.inProgress => 'in_progress',
    InspectionStatus.completed => 'completed',
    InspectionStatus.cancelled => 'cancelled',
  };
  String get label => switch (this) {
    InspectionStatus.planned => 'Planowana',
    InspectionStatus.inProgress => 'W toku',
    InspectionStatus.completed => 'Zakończona',
    InspectionStatus.cancelled => 'Anulowana',
  };
}

class Inspection {
  const Inspection({
    required this.id,
    this.projectId,
    this.projectName,
    required this.clientId,
    required this.clientName,
    required this.title,
    required this.status,
    required this.createdAt,
    required this.updatedAt,
    this.scheduledAt,
    this.startedAt,
    this.completedAt,
    this.notes,
    this.latitude,
    this.longitude,
    this.locationAccuracyM,
  });
  final int id;
  final int? projectId;
  final String? projectName;
  final int clientId;
  final String clientName;
  final String title;
  final InspectionStatus status;
  final DateTime? scheduledAt;
  final DateTime? startedAt;
  final DateTime? completedAt;
  final String? notes;
  final double? latitude;
  final double? longitude;
  final double? locationAccuracyM;
  final DateTime createdAt;
  final DateTime updatedAt;
  String get location => latitude == null || longitude == null
      ? 'brak'
      : '${latitude!.toStringAsFixed(5)}, ${longitude!.toStringAsFixed(5)}';
  factory Inspection.fromJson(Map<String, dynamic> json) => Inspection(
    id: json['id'] as int,
    projectId: json['project_id'] as int?,
    projectName: json['project_name']?.toString(),
    clientId: json['client_id'] as int,
    clientName: json['client_name']?.toString() ?? '',
    title: json['title']?.toString() ?? '',
    status: InspectionStatus.values.firstWhere(
      (value) => value.apiValue == json['status'],
      orElse: () => InspectionStatus.planned,
    ),
    scheduledAt: DateTime.tryParse(json['scheduled_at']?.toString() ?? ''),
    startedAt: DateTime.tryParse(json['started_at']?.toString() ?? ''),
    completedAt: DateTime.tryParse(json['completed_at']?.toString() ?? ''),
    notes: json['notes']?.toString(),
    latitude: (json['latitude'] as num?)?.toDouble(),
    longitude: (json['longitude'] as num?)?.toDouble(),
    locationAccuracyM: (json['location_accuracy_m'] as num?)?.toDouble(),
    createdAt: DateTime.parse(json['created_at'].toString()),
    updatedAt: DateTime.parse(json['updated_at'].toString()),
  );
}

class InspectionPage {
  const InspectionPage({
    required this.items,
    required this.total,
    required this.skip,
    required this.limit,
  });
  final List<Inspection> items;
  final int total;
  final int skip;
  final int limit;
}
