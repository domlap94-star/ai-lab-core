enum WorkItemType { task, order, realization, reminder, event }

enum WorkItemStatus { todo, inProgress, completed, cancelled }

enum WorkItemPriority { low, normal, high, urgent }

class WorkAssignee {
  const WorkAssignee({required this.id, required this.username});
  final int id;
  final String username;
  factory WorkAssignee.fromJson(Map<String, dynamic> json) => WorkAssignee(
    id: json['id'] as int,
    username: json['username'].toString(),
  );
}

extension WorkItemTypePresentation on WorkItemType {
  String get api => name == 'inProgress' ? 'in_progress' : name;
  String get label => switch (this) {
    WorkItemType.task => 'Zadanie',
    WorkItemType.order => 'Zlecenie',
    WorkItemType.realization => 'Realizacja',
    WorkItemType.reminder => 'Przypomnienie',
    WorkItemType.event => 'Wydarzenie',
  };
}

class WorkItem {
  const WorkItem({
    required this.id,
    required this.type,
    required this.title,
    required this.status,
    required this.priority,
    required this.version,
    this.allDay = false,
    this.description,
    this.startAt,
    this.dueAt,
    this.assigneeUserId,
    this.assigneeDisplay,
    this.clientId,
    this.clientName,
    this.projectId,
    this.partyName,
    this.deletedAt,
    this.timezoneName,
  });
  final int id, version;
  final WorkItemType type;
  final String title;
  final String? description;
  final bool allDay;
  final String? timezoneName;
  final DateTime? startAt, dueAt, deletedAt;
  final WorkItemStatus status;
  final WorkItemPriority priority;
  final int? assigneeUserId, clientId, projectId;
  final String? assigneeDisplay, clientName, partyName;
  factory WorkItem.fromJson(Map<String, dynamic> j) => WorkItem(
    id: j['id'] as int,
    type: WorkItemType.values.firstWhere((v) => v.name == j['item_type']),
    title: j['title'].toString(),
    description: j['description']?.toString(),
    startAt: DateTime.tryParse(j['start_at']?.toString() ?? ''),
    dueAt: DateTime.tryParse(j['due_at']?.toString() ?? ''),
    allDay: j['all_day'] == true,
    timezoneName: j['timezone_name']?.toString(),
    status: WorkItemStatus.values.firstWhere(
      (v) => v.name.replaceAll('inProgress', 'in_progress') == j['status'],
    ),
    priority: WorkItemPriority.values.firstWhere(
      (v) => v.name == j['priority'],
    ),
    assigneeUserId: j['assignee_user_id'] as int?,
    assigneeDisplay: j['assignee_display']?.toString(),
    clientId: j['client_id'] as int?,
    clientName: j['client_name']?.toString(),
    projectId: j['project_id'] as int?,
    partyName: j['party_name']?.toString(),
    deletedAt: DateTime.tryParse(j['deleted_at']?.toString() ?? ''),
    version: j['version'] as int,
  );
}

class CalendarEntry {
  const CalendarEntry({
    required this.id,
    required this.kind,
    required this.type,
    required this.title,
    required this.start,
    required this.end,
    required this.status,
    this.priority,
    this.clientId,
  });
  final int id;
  final String kind, type, title, status;
  final DateTime start, end;
  final String? priority;
  final int? clientId;
  bool covers(DateTime day) {
    final d = DateTime(day.year, day.month, day.day);
    return !d.isBefore(DateTime(start.year, start.month, start.day)) &&
        !d.isAfter(DateTime(end.year, end.month, end.day));
  }

  factory CalendarEntry.fromJson(Map<String, dynamic> j) => CalendarEntry(
    id: j['entity_id'] as int,
    kind: j['entity_kind'].toString(),
    type: j['item_type'].toString(),
    title: j['title'].toString(),
    start: DateTime.parse(j['start'].toString()),
    end: DateTime.parse(j['end'].toString()),
    status: j['status'].toString(),
    priority: j['priority']?.toString(),
    clientId: j['client_id'] as int?,
  );
}

class CalendarMonthData {
  const CalendarMonthData({
    required this.year,
    required this.month,
    required this.items,
    required this.total,
    required this.dayCounts,
    required this.truncated,
  });
  final int year, month, total;
  final List<CalendarEntry> items;
  final Map<String, int> dayCounts;
  final bool truncated;
  factory CalendarMonthData.fromJson(Map<String, dynamic> j) =>
      CalendarMonthData(
        year: j['year'] as int,
        month: j['month'] as int,
        items: (j['items'] as List)
            .cast<Map<String, dynamic>>()
            .map(CalendarEntry.fromJson)
            .toList(),
        total: j['total'] as int,
        dayCounts: (j['day_counts'] as Map<String, dynamic>).map(
          (k, v) => MapEntry(k, v as int),
        ),
        truncated: j['truncated'] as bool,
      );
}

class AbsenceRequestItem {
  const AbsenceRequestItem({
    required this.id,
    required this.requesterUserId,
    required this.type,
    required this.start,
    required this.end,
    required this.status,
    required this.version,
    this.requesterDisplay,
    this.note,
  });
  final int id, version;
  final int requesterUserId;
  final String type, status;
  final DateTime start, end;
  final String? requesterDisplay;
  final String? note;
  factory AbsenceRequestItem.fromJson(Map<String, dynamic> j) =>
      AbsenceRequestItem(
        id: j['id'] as int,
        requesterUserId: j['requester_user_id'] as int,
        type: j['absence_type'].toString(),
        start: DateTime.parse(j['start_date'].toString()),
        end: DateTime.parse(j['end_date'].toString()),
        status: j['status'].toString(),
        version: j['version'] as int,
        requesterDisplay: j['requester_display']?.toString(),
        note: j['note']?.toString(),
      );
}

class WorkItemNote {
  const WorkItemNote({
    required this.id,
    required this.workItemId,
    required this.text,
    required this.version,
  });
  final int id;
  final int workItemId;
  final String text;
  final int version;
  factory WorkItemNote.fromJson(Map<String, dynamic> json) => WorkItemNote(
    id: json['id'] as int,
    workItemId: json['work_item_id'] as int,
    text: json['text'].toString(),
    version: json['version'] as int,
  );
}

class WorkItemDocument {
  const WorkItemDocument({
    required this.id,
    required this.workItemId,
    required this.documentId,
    required this.filename,
    required this.contentType,
    required this.fileSize,
    required this.sourceType,
    required this.createdAt,
    this.noteId,
    this.capturedAt,
  });

  final int id;
  final int workItemId;
  final int? noteId;
  final int documentId;
  final String filename;
  final String contentType;
  final int fileSize;
  final String sourceType;
  final DateTime? capturedAt;
  final DateTime createdAt;

  factory WorkItemDocument.fromJson(Map<String, dynamic> json) =>
      WorkItemDocument(
        id: json['id'] as int,
        workItemId: json['work_item_id'] as int,
        noteId: json['note_id'] as int?,
        documentId: json['document_id'] as int,
        filename: json['filename'].toString(),
        contentType: json['content_type'].toString(),
        fileSize: json['file_size'] as int,
        sourceType: json['source_type'].toString(),
        capturedAt: DateTime.tryParse(json['captured_at']?.toString() ?? ''),
        createdAt: DateTime.parse(json['created_at'].toString()),
      );
}
