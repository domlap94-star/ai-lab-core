import 'package:dio/dio.dart';

import '../../auth/domain/auth_session.dart';
import '../domain/agent_assistant.dart';

abstract interface class AgentAssistantGateway {
  Future<AgentAssistantAnswer> ask({
    required AuthSession session,
    required String question,
    int? clientId,
    int? inspectionId,
    List<Map<String, String>> conversation = const [],
    CancelToken? cancelToken,
  });
}

class AgentAssistantApi implements AgentAssistantGateway {
  const AgentAssistantApi(this._dio);
  final Dio _dio;

  @override
  Future<AgentAssistantAnswer> ask({
    required AuthSession session,
    required String question,
    int? clientId,
    int? inspectionId,
    List<Map<String, String>> conversation = const [],
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/ai/agent/ask',
      data: <String, dynamic>{
        'question': question.trim(),
        'client_id': ?clientId,
        'inspection_id': ?inspectionId,
        'conversation': conversation,
      },
      options: Options(
        headers: <String, Object>{
          'Authorization': '${session.tokenType} ${session.accessToken}',
        },
        receiveTimeout: const Duration(minutes: 3),
      ),
      cancelToken: cancelToken,
    );
    if (response.data == null) {
      throw const FormatException('Agent zwrócił pustą odpowiedź.');
    }
    return AgentAssistantAnswer.fromJson(response.data!);
  }
}
