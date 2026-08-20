enum TrashEntityType { document, client, user }

class TrashEntry {
  const TrashEntry({
    required this.id,
    required this.entityType,
    required this.entityId,
    required this.state,
    required this.safeDisplayLabel,
    required this.trashedAt,
    required this.purgeAfter,
    required this.trashedByUserId,
    required this.attemptCount,
    this.lastErrorCode,
  });

  final int id;
  final TrashEntityType entityType;
  final int entityId;
  final String state;
  final String safeDisplayLabel;
  final DateTime trashedAt;
  final DateTime purgeAfter;
  final int trashedByUserId;
  final int attemptCount;
  final String? lastErrorCode;

  factory TrashEntry.fromJson(Map<String, dynamic> json) => TrashEntry(
    id: json['id'] as int,
    entityType: TrashEntityType.values.byName(json['entity_type'] as String),
    entityId: json['entity_id'] as int,
    state: json['state'] as String,
    safeDisplayLabel: json['safe_display_label'] as String,
    trashedAt: DateTime.parse(json['trashed_at'] as String).toLocal(),
    purgeAfter: DateTime.parse(json['purge_after'] as String).toLocal(),
    trashedByUserId: json['trashed_by_user_id'] as int,
    attemptCount: json['attempt_count'] as int,
    lastErrorCode: json['last_error_code'] as String?,
  );
}

class TrashPageData {
  const TrashPageData({required this.items, required this.total});
  final List<TrashEntry> items;
  final int total;
}
