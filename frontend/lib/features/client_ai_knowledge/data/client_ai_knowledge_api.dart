import 'package:dio/dio.dart';
import '../../auth/domain/auth_session.dart';
import '../domain/client_ai_knowledge.dart';

abstract interface class ClientAiKnowledgeGateway {
  Future<ClientAiAnswer> ask({
    required AuthSession session,
    required int clientId,
    required String question,
    List<Map<String, String>> conversation = const <Map<String, String>>[],
    CancelToken? cancelToken,
  });
}

class ClientAiKnowledgeApi implements ClientAiKnowledgeGateway {
  const ClientAiKnowledgeApi(this._dio);
  final Dio _dio;
  @override
  Future<ClientAiAnswer> ask({
    required AuthSession session,
    required int clientId,
    required String question,
    List<Map<String, String>> conversation = const <Map<String, String>>[],
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/clients/$clientId/ai/ask',
      data: <String, dynamic>{
        'question': question.trim(),
        'conversation': conversation,
      },
      options: Options(
        headers: <String, Object>{
          'Authorization': '${session.tokenType} ${session.accessToken}',
        },
        receiveTimeout: const Duration(minutes: 5),
      ),
      cancelToken: cancelToken,
    );
    final data = response.data;
    if (data == null) {
      throw const FormatException('Asystent AI zwrócił pustą odpowiedź.');
    }
    return ClientAiAnswer.fromJson(data);
  }
}
