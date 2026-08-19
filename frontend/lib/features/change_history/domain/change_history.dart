class ChangeHistoryItem {
  const ChangeHistoryItem({
    required this.stableKey,
    required this.createdAt,
    required this.actorUserId,
    required this.actorDisplayName,
    required this.entityType,
    required this.entityId,
    required this.entityLabel,
    required this.action,
    required this.changedFields,
    required this.beforeValues,
    required this.afterValues,
    required this.deepLink,
  });

  factory ChangeHistoryItem.fromJson(Map<String, dynamic> json) {
    Map<String, dynamic> map(Object? value) => value is Map
        ? value.map(
            (dynamic key, dynamic item) => MapEntry(key.toString(), item),
          )
        : const <String, dynamic>{};
    return ChangeHistoryItem(
      stableKey: json['stable_key']?.toString() ?? '',
      createdAt: DateTime.parse(json['created_at'].toString()),
      actorUserId: json['actor_user_id'] as int?,
      actorDisplayName: json['actor_display_name']?.toString(),
      entityType: json['entity_type']?.toString() ?? '',
      entityId: json['entity_id'] as int,
      entityLabel: json['entity_label']?.toString() ?? '',
      action: json['action']?.toString() ?? '',
      changedFields:
          (json['changed_fields'] as List<dynamic>? ?? const <dynamic>[])
              .map((dynamic item) => item.toString())
              .toList(growable: false),
      beforeValues: map(json['before_values']),
      afterValues: map(json['after_values']),
      deepLink: json['deep_link']?.toString(),
    );
  }

  final String stableKey;
  final DateTime createdAt;
  final int? actorUserId;
  final String? actorDisplayName;
  final String entityType;
  final int entityId;
  final String entityLabel;
  final String action;
  final List<String> changedFields;
  final Map<String, dynamic> beforeValues;
  final Map<String, dynamic> afterValues;
  final String? deepLink;
}

class ChangeHistoryPageData {
  const ChangeHistoryPageData({required this.items, required this.total});

  factory ChangeHistoryPageData.fromJson(Map<String, dynamic> json) {
    return ChangeHistoryPageData(
      items: (json['items'] as List<dynamic>? ?? const <dynamic>[])
          .whereType<Map>()
          .map(
            (Map<dynamic, dynamic> item) => ChangeHistoryItem.fromJson(
              item.map(
                (dynamic key, dynamic value) => MapEntry(key.toString(), value),
              ),
            ),
          )
          .toList(growable: false),
      total: json['total'] as int? ?? 0,
    );
  }

  final List<ChangeHistoryItem> items;
  final int total;
}
