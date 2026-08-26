import 'package:dio/dio.dart';
import '../../auth/domain/auth_session.dart';
import '../domain/unified_assistant.dart';

class UnifiedAssistantApi {
  const UnifiedAssistantApi(this._dio);
  final Dio _dio;
  Future<UnifiedAssistantAnswer> ask({
    required AuthSession session,
    required String question,
    required List<Map<String, String>> conversation,
    int? clientId,
    int? candidateId,
    int? documentId,
    int? mailSourceId,
    int? inspectionId,
    String? attemptId,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/ai/assistant/ask',
      data: <String, dynamic>{
        'question': question.trim(),
        'conversation': conversation,
        'client_id': ?clientId,
        'candidate_id': ?candidateId,
        'document_id': ?documentId,
        'mail_source_id': ?mailSourceId,
        'inspection_id': ?inspectionId,
        'attempt_id': ?attemptId,
      },
      options: Options(
        headers: <String, Object>{
          'Authorization': '${session.tokenType} ${session.accessToken}',
        },
        // The backend ends local reasoning at 105 s and may still need bounded
        // model cleanup before serializing the terminal timeout response.
        receiveTimeout: const Duration(seconds: 160),
      ),
      cancelToken: cancelToken,
    );
    if (response.data == null) {
      throw const FormatException('Asystent AI zwrócił pustą odpowiedź.');
    }
    return UnifiedAssistantAnswer.fromJson(response.data!);
  }

  Future<UnifiedAssistantAnswer> cancel({
    required AuthSession session,
    required String requestId,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/ai/assistant/$requestId/cancel',
      options: Options(
        headers: <String, Object>{
          'Authorization': '${session.tokenType} ${session.accessToken}',
        },
      ),
    );
    if (response.data == null) {
      throw const FormatException('Nie potwierdzono anulowania analizy.');
    }
    return UnifiedAssistantAnswer.fromJson(response.data!);
  }

  Future<UnifiedAssistantAnswer> status({
    required AuthSession session,
    required String requestId,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/ai/assistant/$requestId',
      options: Options(
        headers: <String, Object>{
          'Authorization': '${session.tokenType} ${session.accessToken}',
        },
      ),
      cancelToken: cancelToken,
    );
    if (response.data == null) {
      throw const FormatException('Nie udało się odczytać stanu analizy.');
    }
    return UnifiedAssistantAnswer.fromJson(response.data!);
  }
}
