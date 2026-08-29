import 'package:dio/dio.dart';

import '../../auth/domain/auth_session.dart';
import '../domain/assistant_run.dart';

class AssistantRunRepository {
  const AssistantRunRepository(this._dio);

  final Dio _dio;

  Options _options(AuthSession session) => Options(
    headers: <String, Object>{
      'Authorization': '${session.tokenType} ${session.accessToken}',
    },
    sendTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 15),
  );

  Future<AssistantRunSnapshot> create({
    required AuthSession session,
    required String question,
    required String attemptId,
    required List<Map<String, String>> conversation,
    int? conversationId,
    int? clientId,
    int? candidateId,
    int? documentId,
    int? mailSourceId,
    int? inspectionId,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/ai/assistant/runs',
      data: <String, dynamic>{
        'question': question.trim(),
        'attempt_id': attemptId,
        'conversation': conversation,
        'conversation_id': ?conversationId,
        'client_id': ?clientId,
        'candidate_id': ?candidateId,
        'document_id': ?documentId,
        'mail_source_id': ?mailSourceId,
        'inspection_id': ?inspectionId,
      },
      options: _options(session),
    );
    if (response.data == null) {
      throw const FormatException('Nie utworzono trwałej analizy.');
    }
    return AssistantRunSnapshot.fromJson(response.data!);
  }

  Future<AssistantRunSnapshot> get({
    required AuthSession session,
    required String runId,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/ai/assistant/runs/$runId',
      options: _options(session),
      cancelToken: cancelToken,
    );
    if (response.data == null) {
      throw const FormatException('Nie odczytano stanu analizy.');
    }
    return AssistantRunSnapshot.fromJson(response.data!);
  }

  Future<List<AssistantRunSnapshot>> listActive({
    required AuthSession session,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/ai/assistant/runs',
      queryParameters: const <String, dynamic>{'active': true, 'limit': 20},
      options: _options(session),
    );
    final items = response.data?['items'] as List<dynamic>? ?? const [];
    return items
        .map(
          (item) => AssistantRunSnapshot.fromJson(
            Map<String, dynamic>.from(item as Map),
          ),
        )
        .toList(growable: false);
  }

  Future<AssistantRunSnapshot> cancel({
    required AuthSession session,
    required String runId,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/ai/assistant/runs/$runId/cancel',
      options: _options(session),
    );
    if (response.data == null) {
      throw const FormatException('Nie potwierdzono anulowania analizy.');
    }
    return AssistantRunSnapshot.fromJson(response.data!);
  }
}
