class ClientAiSource {
  const ClientAiSource({
    required this.sourceType,
    required this.sourceId,
    required this.title,
    required this.route,
    required this.snippet,
    this.date,
  });
  factory ClientAiSource.fromJson(Map<String, dynamic> json) => ClientAiSource(
    sourceType: json['source_type'] as String,
    sourceId: json['source_id'] as int,
    title: json['title'] as String,
    route: json['route'] as String,
    snippet: json['snippet'] as String,
    date: json['date'] == null ? null : DateTime.parse(json['date'] as String),
  );
  final String sourceType;
  final int sourceId;
  final String title;
  final String route;
  final String snippet;
  final DateTime? date;
}

class ClientAiCoverage {
  const ClientAiCoverage({
    required this.emailsSearched,
    required this.documentsLexicalSearched,
    required this.documentVectorsUsed,
    required this.projectsConsidered,
    required this.inspectionsConsidered,
    required this.timelineEventsConsidered,
  });
  factory ClientAiCoverage.fromJson(Map<String, dynamic> json) =>
      ClientAiCoverage(
        emailsSearched: json['emails_searched'] as int? ?? 0,
        documentsLexicalSearched:
            json['documents_lexical_searched'] as int? ?? 0,
        documentVectorsUsed: json['document_vectors_used'] as int? ?? 0,
        projectsConsidered: json['projects_considered'] as int? ?? 0,
        inspectionsConsidered: json['inspections_considered'] as int? ?? 0,
        timelineEventsConsidered:
            json['timeline_events_considered'] as int? ?? 0,
      );
  final int emailsSearched;
  final int documentsLexicalSearched;
  final int documentVectorsUsed;
  final int projectsConsidered;
  final int inspectionsConsidered;
  final int timelineEventsConsidered;
}

class ClientAiAnswer {
  const ClientAiAnswer({
    required this.answer,
    required this.sources,
    required this.coverage,
    required this.semanticStatus,
    required this.limitations,
    required this.directAnswer,
    this.model,
  });
  factory ClientAiAnswer.fromJson(Map<String, dynamic> json) => ClientAiAnswer(
    answer: json['answer'] as String,
    sources: (json['sources'] as List<dynamic>? ?? const <dynamic>[])
        .map((item) => ClientAiSource.fromJson(item as Map<String, dynamic>))
        .toList(growable: false),
    coverage: ClientAiCoverage.fromJson(
      json['coverage'] as Map<String, dynamic>? ?? const <String, dynamic>{},
    ),
    semanticStatus: json['semantic_status'] as String,
    limitations: (json['limitations'] as List<dynamic>? ?? const <dynamic>[])
        .cast<String>(),
    directAnswer: json['direct_answer'] as bool? ?? false,
    model: json['model'] as String?,
  );
  final String answer;
  final List<ClientAiSource> sources;
  final ClientAiCoverage coverage;
  final String semanticStatus;
  final List<String> limitations;
  final bool directAnswer;
  final String? model;
}
