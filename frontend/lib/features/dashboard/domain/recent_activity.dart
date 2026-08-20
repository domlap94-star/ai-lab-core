class RecentActivityItem {
  const RecentActivityItem({
    required this.stableKey,
    required this.timestamp,
    required this.actorDisplay,
    required this.action,
    required this.entityType,
    required this.entityId,
    required this.summary,
    this.actorUserId,
    this.deepLink,
    this.clientId,
    this.clientName,
  });

  factory RecentActivityItem.fromJson(Map<String, dynamic> json) =>
      RecentActivityItem(
        stableKey: json['stable_key'] as String,
        timestamp: DateTime.parse(json['timestamp'] as String).toLocal(),
        actorUserId: json['actor_user_id'] as int?,
        actorDisplay: json['actor_display'] as String? ?? 'System',
        action: json['action'] as String,
        entityType: json['entity_type'] as String,
        entityId: json['entity_id'] as int,
        summary: json['summary'] as String,
        deepLink: json['deep_link'] as String?,
        clientId: json['client_id'] as int?,
        clientName: json['client_name'] as String?,
      );

  final String stableKey;
  final DateTime timestamp;
  final int? actorUserId;
  final String actorDisplay;
  final String action;
  final String entityType;
  final int entityId;
  final String summary;
  final String? deepLink;
  final int? clientId;
  final String? clientName;
}

class RecentActivityPageData {
  const RecentActivityPageData({
    required this.items,
    required this.skip,
    required this.limit,
    required this.hasMore,
  });

  factory RecentActivityPageData.fromJson(Map<String, dynamic> json) =>
      RecentActivityPageData(
        items: (json['items'] as List<dynamic>? ?? const <dynamic>[])
            .whereType<Map<String, dynamic>>()
            .map(RecentActivityItem.fromJson)
            .toList(growable: false),
        skip: json['skip'] as int? ?? 0,
        limit: json['limit'] as int? ?? 8,
        hasMore: json['has_more'] as bool? ?? false,
      );

  final List<RecentActivityItem> items;
  final int skip;
  final int limit;
  final bool hasMore;
}
