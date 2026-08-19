enum GlobalSearchType {
  client,
  project,
  inspection,
  document,
  email,
  candidate,
}

extension GlobalSearchTypeLabel on GlobalSearchType {
  String get label => switch (this) {
    GlobalSearchType.client => 'Klient',
    GlobalSearchType.project => 'Realizacja',
    GlobalSearchType.inspection => 'Wizja',
    GlobalSearchType.document => 'Dokument',
    GlobalSearchType.email => 'E-mail',
    GlobalSearchType.candidate => 'Kandydat',
  };
}

class GlobalSearchResult {
  const GlobalSearchResult({
    required this.type,
    required this.id,
    required this.title,
    required this.score,
    required this.matchReason,
    required this.matchReasons,
    required this.route,
    this.subtitle,
    this.snippet,
    this.occurredAt,
    this.clientId,
    this.projectId,
    this.inspectionId,
    this.clientWorkflowStatus,
    this.clientWorkflowStatusLabel,
    this.clientWorkflowEffectiveDate,
  });

  final GlobalSearchType type;
  final int id;
  final String title;
  final String? subtitle;
  final String? snippet;
  final double score;
  final String matchReason;
  final List<String> matchReasons;
  final DateTime? occurredAt;
  final int? clientId;
  final int? projectId;
  final int? inspectionId;
  final String? clientWorkflowStatus;
  final String? clientWorkflowStatusLabel;
  final DateTime? clientWorkflowEffectiveDate;
  final String route;

  factory GlobalSearchResult.fromJson(Map<String, dynamic> json) {
    return GlobalSearchResult(
      type: GlobalSearchType.values.firstWhere(
        (GlobalSearchType value) => value.name == json['type'],
      ),
      id: (json['id'] as num).toInt(),
      title: json['title']?.toString() ?? '',
      subtitle: json['subtitle']?.toString(),
      snippet: json['snippet']?.toString(),
      score: (json['score'] as num).toDouble(),
      matchReason: json['match_reason']?.toString() ?? 'text',
      matchReasons: (json['match_reasons'] as List<dynamic>? ?? const [])
          .map((dynamic item) => item.toString())
          .toList(growable: false),
      occurredAt: DateTime.tryParse(json['occurred_at']?.toString() ?? ''),
      clientId: (json['client_id'] as num?)?.toInt(),
      projectId: (json['project_id'] as num?)?.toInt(),
      inspectionId: (json['inspection_id'] as num?)?.toInt(),
      clientWorkflowStatus: json['client_workflow_status']?.toString(),
      clientWorkflowStatusLabel: json['client_workflow_status_label']
          ?.toString(),
      clientWorkflowEffectiveDate: DateTime.tryParse(
        json['client_workflow_effective_date']?.toString() ?? '',
      ),
      route: json['route']?.toString() ?? '',
    );
  }
}

class GlobalSearchPageData {
  const GlobalSearchPageData({
    required this.items,
    required this.skip,
    required this.limit,
    required this.hasMore,
    required this.semanticStatus,
  });

  final List<GlobalSearchResult> items;
  final int skip;
  final int limit;
  final bool hasMore;
  final String semanticStatus;

  factory GlobalSearchPageData.fromJson(Map<String, dynamic> json) {
    return GlobalSearchPageData(
      items: (json['items'] as List<dynamic>? ?? const [])
          .whereType<Map>()
          .map(
            (Map item) =>
                GlobalSearchResult.fromJson(Map<String, dynamic>.from(item)),
          )
          .toList(growable: false),
      skip: (json['skip'] as num?)?.toInt() ?? 0,
      limit: (json['limit'] as num?)?.toInt() ?? 25,
      hasMore: json['has_more'] == true,
      semanticStatus: json['semantic_status']?.toString() ?? 'not_requested',
    );
  }
}
