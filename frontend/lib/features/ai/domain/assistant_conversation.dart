import 'unified_assistant.dart';

class AssistantConversationSummary {
  const AssistantConversationSummary({
    required this.id,
    required this.title,
    required this.createdAt,
    required this.lastActivityAt,
    required this.active,
    this.lastMessagePreview,
    this.latestRunId,
    this.latestRunStatus,
  });

  factory AssistantConversationSummary.fromJson(Map<String, dynamic> json) =>
      AssistantConversationSummary(
        id: (json['id'] as num).toInt(),
        title: json['title'] as String,
        createdAt: DateTime.parse(json['created_at'] as String),
        lastActivityAt: DateTime.parse(json['last_activity_at'] as String),
        lastMessagePreview: json['last_message_preview'] as String?,
        latestRunId: json['latest_run_id'] as String?,
        latestRunStatus: json['latest_run_status'] as String?,
        active: json['active'] as bool? ?? false,
      );

  final int id;
  final String title;
  final DateTime createdAt;
  final DateTime lastActivityAt;
  final String? lastMessagePreview;
  final String? latestRunId;
  final String? latestRunStatus;
  final bool active;
}

class AssistantConversationMessage {
  const AssistantConversationMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.createdAt,
    this.assistantRunId,
    this.runStatus,
    this.runCurrentStage,
    this.runResult,
  });

  factory AssistantConversationMessage.fromJson(Map<String, dynamic> json) =>
      AssistantConversationMessage(
        id: (json['id'] as num).toInt(),
        role: json['role'] as String,
        content: json['content'] as String,
        assistantRunId: json['assistant_run_id'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
        runStatus: json['run_status'] as String?,
        runCurrentStage: json['run_current_stage'] as String?,
        runResult: json['run_result'] == null
            ? null
            : UnifiedAssistantAnswer.fromJson(
                Map<String, dynamic>.from(json['run_result'] as Map),
              ),
      );

  final int id;
  final String role;
  final String content;
  final String? assistantRunId;
  final DateTime createdAt;
  final String? runStatus;
  final String? runCurrentStage;
  final UnifiedAssistantAnswer? runResult;
}

class AssistantConversationDetail extends AssistantConversationSummary {
  const AssistantConversationDetail({
    required super.id,
    required super.title,
    required super.createdAt,
    required super.lastActivityAt,
    required super.active,
    required this.messages,
    required this.hasOlder,
    super.lastMessagePreview,
    super.latestRunId,
    super.latestRunStatus,
  });

  factory AssistantConversationDetail.fromJson(Map<String, dynamic> json) {
    final summary = AssistantConversationSummary.fromJson(json);
    return AssistantConversationDetail(
      id: summary.id,
      title: summary.title,
      createdAt: summary.createdAt,
      lastActivityAt: summary.lastActivityAt,
      active: summary.active,
      lastMessagePreview: summary.lastMessagePreview,
      latestRunId: summary.latestRunId,
      latestRunStatus: summary.latestRunStatus,
      messages: (json['messages'] as List<dynamic>? ?? const [])
          .map(
            (item) => AssistantConversationMessage.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(growable: false),
      hasOlder: json['has_older'] as bool? ?? false,
    );
  }

  final List<AssistantConversationMessage> messages;
  final bool hasOlder;
}

class AssistantConversationDeleteResult {
  const AssistantConversationDeleteResult({
    required this.id,
    required this.deletedAt,
    required this.message,
    this.activeRunId,
  });

  factory AssistantConversationDeleteResult.fromJson(
    Map<String, dynamic> json,
  ) => AssistantConversationDeleteResult(
    id: (json['id'] as num).toInt(),
    deletedAt: DateTime.parse(json['deleted_at'] as String),
    activeRunId: json['active_run_id'] as String?,
    message: json['message'] as String,
  );

  final int id;
  final DateTime deletedAt;
  final String? activeRunId;
  final String message;
}
