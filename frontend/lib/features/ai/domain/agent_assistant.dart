class AgentSource {
  const AgentSource({
    required this.sourceType,
    required this.title,
    required this.snippet,
    this.sourceId,
    this.route,
  });
  factory AgentSource.fromJson(Map<String, dynamic> json) => AgentSource(
    sourceType: json['source_type'] as String,
    sourceId: (json['source_id'] as num?)?.toInt(),
    title: json['title'] as String,
    snippet: json['snippet'] as String? ?? '',
    route: json['route'] as String?,
  );
  final String sourceType;
  final int? sourceId;
  final String title;
  final String snippet;
  final String? route;
}

class AgentToolTrace {
  const AgentToolTrace({required this.name, required this.outcome});
  factory AgentToolTrace.fromJson(Map<String, dynamic> json) => AgentToolTrace(
    name: json['name'] as String,
    outcome: json['outcome'] as String,
  );
  final String name;
  final String outcome;
}

class AgentAssistantAnswer {
  const AgentAssistantAnswer({
    required this.requestId,
    required this.answer,
    required this.sources,
    required this.toolTrace,
    required this.limitations,
    required this.status,
    this.model,
  });
  factory AgentAssistantAnswer.fromJson(Map<String, dynamic> json) =>
      AgentAssistantAnswer(
        requestId: json['request_id'] as String,
        answer: json['answer'] as String,
        sources: (json['sources'] as List<dynamic>? ?? const [])
            .map((x) => AgentSource.fromJson(x as Map<String, dynamic>))
            .toList(growable: false),
        toolTrace: (json['tool_trace'] as List<dynamic>? ?? const [])
            .map((x) => AgentToolTrace.fromJson(x as Map<String, dynamic>))
            .toList(growable: false),
        limitations: (json['limitations'] as List<dynamic>? ?? const [])
            .cast<String>(),
        status: json['status'] as String,
        model: json['model'] as String?,
      );
  final String requestId;
  final String answer;
  final List<AgentSource> sources;
  final List<AgentToolTrace> toolTrace;
  final List<String> limitations;
  final String status;
  final String? model;
}
