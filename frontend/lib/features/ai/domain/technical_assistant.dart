class TechnicalAssistantSource {
  const TechnicalAssistantSource({
    required this.sourceType,
    required this.title,
    required this.snippet,
    this.sourceId,
    this.route,
    this.date,
  });
  factory TechnicalAssistantSource.fromJson(Map<String, dynamic> json) =>
      TechnicalAssistantSource(
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

class TechnicalAssistantAnswer {
  const TechnicalAssistantAnswer({
    required this.answer,
    required this.facts,
    required this.inferences,
    required this.missingInformation,
    required this.sources,
    required this.limitations,
    required this.intent,
    required this.semanticStatus,
    this.model,
  });
  factory TechnicalAssistantAnswer.fromJson(Map<String, dynamic> json) =>
      TechnicalAssistantAnswer(
        answer: json['answer'] as String,
        facts: (json['facts'] as List<dynamic>? ?? const []).cast<String>(),
        inferences: (json['inferences'] as List<dynamic>? ?? const [])
            .cast<String>(),
        missingInformation:
            (json['missing_information'] as List<dynamic>? ?? const [])
                .cast<String>(),
        sources: (json['sources'] as List<dynamic>? ?? const [])
            .map(
              (item) => TechnicalAssistantSource.fromJson(
                item as Map<String, dynamic>,
              ),
            )
            .toList(growable: false),
        limitations: (json['limitations'] as List<dynamic>? ?? const [])
            .cast<String>(),
        intent: json['intent'] as String,
        semanticStatus: json['semantic_status'] as String,
        model: json['model'] as String?,
      );
  final String answer;
  final List<String> facts;
  final List<String> inferences;
  final List<String> missingInformation;
  final List<TechnicalAssistantSource> sources;
  final List<String> limitations;
  final String intent;
  final String semanticStatus;
  final String? model;
}
