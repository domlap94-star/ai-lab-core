class TimelineEvent {
  const TimelineEvent({
    required this.stableKey,
    required this.eventType,
    required this.occurredAt,
    required this.title,
    required this.sourceType,
    required this.sourceId,
    this.summary,
    this.clientId,
    this.projectId,
    this.inspectionId,
    this.documentId,
    this.actorUserId,
    this.actorDisplayName,
    this.direction,
    this.entityType,
    this.entityId,
    this.deepLink,
    this.metadata = const <String, dynamic>{},
  });
  final String stableKey;
  final String eventType;
  final DateTime occurredAt;
  final String title;
  final String? summary;
  final int? clientId;
  final int? projectId;
  final int? inspectionId;
  final int? documentId;
  final String sourceType;
  final Object sourceId;
  final int? actorUserId;
  final String? actorDisplayName;
  final String? direction;
  final String? entityType;
  final int? entityId;
  final String? deepLink;
  final Map<String, dynamic> metadata;

  factory TimelineEvent.fromJson(Map<String, dynamic> json) => TimelineEvent(
    stableKey: json['stable_key'] as String,
    eventType: json['event_type'] as String,
    occurredAt: DateTime.parse(json['occurred_at'] as String),
    title: json['title'] as String,
    summary: json['summary'] as String?,
    clientId: json['client_id'] as int?,
    projectId: json['project_id'] as int?,
    inspectionId: json['inspection_id'] as int?,
    documentId: json['document_id'] as int?,
    sourceType: json['source_type'] as String,
    sourceId: json['source_id'] as Object,
    actorUserId: json['actor_user_id'] as int?,
    actorDisplayName: json['actor_display_name'] as String?,
    direction: json['direction'] as String?,
    entityType: json['entity_type'] as String?,
    entityId: json['entity_id'] as int?,
    deepLink: json['deep_link'] as String?,
    metadata: (json['metadata'] as Map<String, dynamic>?) ?? const {},
  );
}

class TimelinePage {
  const TimelinePage({
    required this.items,
    required this.total,
    required this.skip,
    required this.limit,
  });
  final List<TimelineEvent> items;
  final int total;
  final int skip;
  final int limit;
  bool get hasMore => skip + items.length < total;
  factory TimelinePage.fromJson(Map<String, dynamic> json) => TimelinePage(
    items: (json['items'] as List<dynamic>)
        .cast<Map<String, dynamic>>()
        .map(TimelineEvent.fromJson)
        .toList(growable: false),
    total: json['total'] as int,
    skip: json['skip'] as int,
    limit: json['limit'] as int,
  );
}

enum TimelineScope { client, project }

class TimelineRequest {
  const TimelineRequest({
    required this.scope,
    required this.id,
    this.limit = 20,
    this.eventType,
  });
  final TimelineScope scope;
  final int id;
  final int limit;
  final String? eventType;
  @override
  int get hashCode => Object.hash(scope, id, limit, eventType);
  @override
  bool operator ==(Object other) =>
      other is TimelineRequest &&
      other.scope == scope &&
      other.id == id &&
      other.limit == limit &&
      other.eventType == eventType;
}
