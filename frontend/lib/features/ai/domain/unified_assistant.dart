class UnifiedAssistantClaim {
  const UnifiedAssistantClaim({
    required this.claimId,
    required this.claimClass,
    required this.text,
    required this.sourceRefs,
    this.toolRefs = const [],
    this.estimateStatus,
    this.confidence,
    this.assumptions = const [],
    this.missingInputs = const [],
    this.confirmOrRefute,
  });
  factory UnifiedAssistantClaim.fromJson(Map<String, dynamic> json) =>
      UnifiedAssistantClaim(
        claimId: json['claim_id'] as String,
        claimClass: json['claim_class'] as String,
        text: json['text'] as String,
        sourceRefs: (json['source_refs'] as List<dynamic>? ?? const [])
            .cast<String>(),
        toolRefs: (json['tool_refs'] as List<dynamic>? ?? const [])
            .cast<String>(),
        estimateStatus: json['estimate_status'] as String?,
        confidence: json['confidence'] as String?,
        assumptions: (json['assumptions'] as List<dynamic>? ?? const [])
            .cast<String>(),
        missingInputs: (json['missing_inputs'] as List<dynamic>? ?? const [])
            .cast<String>(),
        confirmOrRefute: json['confirm_or_refute'] as String?,
      );
  final String claimId;
  final String claimClass;
  final String text;
  final List<String> sourceRefs;
  final List<String> toolRefs;
  final String? estimateStatus;
  final String? confidence;
  final List<String> assumptions;
  final List<String> missingInputs;
  final String? confirmOrRefute;
}

class UnifiedAssistantSource {
  const UnifiedAssistantSource({
    required this.sourceRef,
    required this.sourceType,
    required this.title,
    required this.excerpt,
    required this.whyUsed,
    required this.supportsClaimIds,
    this.sourceId,
    this.route,
    this.externalAnalysis = false,
  });
  factory UnifiedAssistantSource.fromJson(Map<String, dynamic> json) =>
      UnifiedAssistantSource(
        sourceRef: json['source_ref'] as String,
        sourceType: json['source_type'] as String,
        sourceId: (json['source_id'] as num?)?.toInt(),
        title: json['title'] as String,
        excerpt: json['excerpt'] as String,
        whyUsed: json['why_used'] as String,
        supportsClaimIds:
            (json['supports_claim_ids'] as List<dynamic>? ?? const [])
                .cast<String>(),
        route: json['route'] as String?,
        externalAnalysis: json['external_analysis'] as bool? ?? false,
      );
  final String sourceRef;
  final String sourceType;
  final int? sourceId;
  final String title;
  final String excerpt;
  final String whyUsed;
  final List<String> supportsClaimIds;
  final String? route;
  final bool externalAnalysis;
}

class UnifiedAssistantAnswer {
  const UnifiedAssistantAnswer({
    required this.requestId,
    required this.answer,
    required this.status,
    required this.progress,
    required this.targetScope,
    required this.claims,
    required this.sources,
    required this.usedTools,
    required this.externalAnalysisUsed,
    this.model,
    this.errorMessage,
  });
  factory UnifiedAssistantAnswer.fromJson(Map<String, dynamic> json) =>
      UnifiedAssistantAnswer(
        requestId: json['request_id'] as String,
        answer: json['answer'] as String,
        status: json['status'] as String,
        progress: json['progress'] as String,
        targetScope: json['target_scope'] as String,
        claims: (json['claims'] as List<dynamic>? ?? const [])
            .map(
              (item) => UnifiedAssistantClaim.fromJson(
                Map<String, dynamic>.from(item as Map),
              ),
            )
            .toList(growable: false),
        sources: (json['sources'] as List<dynamic>? ?? const [])
            .map(
              (item) => UnifiedAssistantSource.fromJson(
                Map<String, dynamic>.from(item as Map),
              ),
            )
            .toList(growable: false),
        usedTools: (json['used_tools'] as List<dynamic>? ?? const [])
            .cast<String>(),
        externalAnalysisUsed: json['external_analysis_used'] as bool? ?? false,
        model: json['model'] as String?,
        errorMessage: json['error_message'] as String?,
      );
  bool get isPending =>
      status == 'advanced_queued' || status == 'advanced_processing';
  final String requestId;
  final String answer;
  final String status;
  final String progress;
  final String targetScope;
  final List<UnifiedAssistantClaim> claims;
  final List<UnifiedAssistantSource> sources;
  final List<String> usedTools;
  final bool externalAnalysisUsed;
  final String? model;
  final String? errorMessage;
}
