enum InspectionStatus { planned, inProgress, completed, cancelled }

DateTime? parseInspectionDateOnly(Object? value) {
  final text = value?.toString() ?? '';
  final match = RegExp(r'^(\d{4})-(\d{2})-(\d{2})$').firstMatch(text);
  if (match == null) return null;
  return DateTime(
    int.parse(match.group(1)!),
    int.parse(match.group(2)!),
    int.parse(match.group(3)!),
  );
}

String inspectionDateApi(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';

String inspectionDateDisplay(DateTime value) =>
    '${value.day.toString().padLeft(2, '0')}.${value.month.toString().padLeft(2, '0')}.${value.year.toString().padLeft(4, '0')}';

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
    this.scheduledDate,
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
  final DateTime? scheduledDate;
  DateTime? get scheduledAt => scheduledDate;
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
    scheduledDate:
        parseInspectionDateOnly(json['scheduled_date']) ??
        _legacyInspectionDate(json['scheduled_at']) ??
        _legacyInspectionDate(json['started_at']),
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

DateTime? _legacyInspectionDate(Object? value) {
  final text = value?.toString() ?? '';
  final parsed = DateTime.tryParse(text);
  if (parsed == null) return null;
  if (!text.endsWith('Z') && !RegExp(r'[+-]\d{2}:?\d{2}$').hasMatch(text)) {
    return DateTime(parsed.year, parsed.month, parsed.day);
  }
  final utc = parsed.toUtc();
  final marchEnd = DateTime.utc(utc.year, 4, 0);
  final octoberEnd = DateTime.utc(utc.year, 11, 0);
  final dstStart = DateTime.utc(
    utc.year,
    3,
    marchEnd.day - (marchEnd.weekday % 7),
    1,
  );
  final dstEnd = DateTime.utc(
    utc.year,
    10,
    octoberEnd.day - (octoberEnd.weekday % 7),
    1,
  );
  final offsetHours = !utc.isBefore(dstStart) && utc.isBefore(dstEnd) ? 2 : 1;
  final warsaw = utc.add(Duration(hours: offsetHours));
  return DateTime(warsaw.year, warsaw.month, warsaw.day);
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
