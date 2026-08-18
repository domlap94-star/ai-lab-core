class BusinessAssistantSource {
  const BusinessAssistantSource({
    required this.sourceType,
    required this.title,
    required this.snippet,
    this.sourceId,
    this.route,
    this.date,
  });
  factory BusinessAssistantSource.fromJson(Map<String, dynamic> json) =>
      BusinessAssistantSource(
        sourceType: json['source_type'] as String,
        sourceId: (json['source_id'] as num?)?.toInt(),
        title: json['title'] as String,
        snippet: json['snippet'] as String,
        route: json['route'] as String?,
        date: json['date'] == null
            ? null
            : DateTime.parse(json['date'] as String),
      );
  final String sourceType;
  final int? sourceId;
  final String title;
  final String snippet;
  final String? route;
  final DateTime? date;
}

class BusinessAssistantAnswer {
  const BusinessAssistantAnswer({
    required this.answer,
    required this.sources,
    required this.limitations,
    required this.intent,
    required this.directAnswer,
    required this.semanticStatus,
    this.model,
  });
  factory BusinessAssistantAnswer.fromJson(Map<String, dynamic> json) =>
      BusinessAssistantAnswer(
        answer: json['answer'] as String,
        sources: (json['sources'] as List<dynamic>? ?? const [])
            .map(
              (item) => BusinessAssistantSource.fromJson(
                item as Map<String, dynamic>,
              ),
            )
            .toList(growable: false),
        limitations: (json['limitations'] as List<dynamic>? ?? const [])
            .cast<String>(),
        intent: json['intent'] as String,
        directAnswer: json['direct_answer'] as bool? ?? false,
        semanticStatus: json['semantic_status'] as String,
        model: json['model'] as String?,
      );
  final String answer;
  final List<BusinessAssistantSource> sources;
  final List<String> limitations;
  final String intent;
  final bool directAnswer;
  final String semanticStatus;
  final String? model;
}
