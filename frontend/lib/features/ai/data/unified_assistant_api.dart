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
      },
      options: Options(
        headers: <String, Object>{
          'Authorization': '${session.tokenType} ${session.accessToken}',
        },
        receiveTimeout: const Duration(minutes: 6),
      ),
      cancelToken: cancelToken,
    );
    if (response.data == null) {
      throw const FormatException('Asystent AI zwrócił pustą odpowiedź.');
    }
    return UnifiedAssistantAnswer.fromJson(response.data!);
  }
}
