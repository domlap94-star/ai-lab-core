import 'unified_assistant.dart';

class AssistantRunProgress {
  const AssistantRunProgress({
    required this.message,
    this.current,
    this.total,
    this.unit,
  });

  factory AssistantRunProgress.fromJson(Map<String, dynamic> json) =>
      AssistantRunProgress(
        message: json['message'] as String,
        current: (json['current'] as num?)?.toInt(),
        total: (json['total'] as num?)?.toInt(),
        unit: json['unit'] as String?,
      );

  final String message;
  final int? current;
  final int? total;
  final String? unit;

  String get display {
    if (current == null || total == null || unit == null) return message;
    return '$message $current z $total $unit.';
  }
}

class AssistantRunSnapshot {
  const AssistantRunSnapshot({
    required this.runId,
    required this.attemptId,
    required this.status,
    required this.complexity,
    required this.progress,
    required this.canCancel,
    required this.pollAfterMs,
    required this.recoveryGeneration,
    required this.createdAt,
    required this.updatedAt,
    this.currentStage,
    this.result,
    this.errorCode,
  });

  factory AssistantRunSnapshot.fromJson(Map<String, dynamic> json) =>
      AssistantRunSnapshot(
        runId: json['run_id'] as String,
        attemptId: json['attempt_id'] as String,
        status: json['status'] as String,
        currentStage: json['current_stage'] as String?,
        complexity: json['complexity'] as String,
        progress: AssistantRunProgress.fromJson(
          Map<String, dynamic>.from(json['progress'] as Map),
        ),
        canCancel: json['can_cancel'] as bool? ?? false,
        pollAfterMs: (json['poll_after_ms'] as num?)?.toInt() ?? 2500,
        recoveryGeneration: (json['recovery_generation'] as num?)?.toInt() ?? 0,
        result: json['result'] == null
            ? null
            : UnifiedAssistantAnswer.fromJson(
                Map<String, dynamic>.from(json['result'] as Map),
              ),
        errorCode: json['error_code'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
        updatedAt: DateTime.parse(json['updated_at'] as String),
      );

  bool get isTerminal => <String>{
    'completed',
    'review_required',
    'failed',
    'cancelled',
  }.contains(status);

  final String runId;
  final String attemptId;
  final String status;
  final String? currentStage;
  final String complexity;
  final AssistantRunProgress progress;
  final bool canCancel;
  final int pollAfterMs;
  final int recoveryGeneration;
  final UnifiedAssistantAnswer? result;
  final String? errorCode;
  final DateTime createdAt;
  final DateTime updatedAt;
}
