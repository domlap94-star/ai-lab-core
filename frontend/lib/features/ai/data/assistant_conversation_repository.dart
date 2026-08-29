import 'package:dio/dio.dart';

import '../../auth/domain/auth_session.dart';
import '../domain/assistant_conversation.dart';

class AssistantConversationRepository {
  const AssistantConversationRepository(this._dio);

  final Dio _dio;

  Options _options(AuthSession session) => Options(
    headers: <String, Object>{
      'Authorization': '${session.tokenType} ${session.accessToken}',
    },
    sendTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 15),
  );

  Future<AssistantConversationDetail> createChat({
    required AuthSession session,
    String? title,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/ai/assistant/conversations',
      data: <String, dynamic>{'title': ?title},
      options: _options(session),
    );
    return AssistantConversationDetail.fromJson(_required(response.data));
  }

  Future<List<AssistantConversationSummary>> listChats({
    required AuthSession session,
    int limit = 20,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/ai/assistant/conversations',
      queryParameters: <String, dynamic>{'limit': limit},
      options: _options(session),
    );
    return (response.data?['items'] as List<dynamic>? ?? const [])
        .map(
          (item) => AssistantConversationSummary.fromJson(
            Map<String, dynamic>.from(item as Map),
          ),
        )
        .toList(growable: false);
  }

  Future<AssistantConversationDetail> getChat({
    required AuthSession session,
    required int conversationId,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/ai/assistant/conversations/$conversationId',
      options: _options(session),
    );
    return AssistantConversationDetail.fromJson(_required(response.data));
  }

  Future<AssistantConversationDetail> renameChat({
    required AuthSession session,
    required int conversationId,
    required String title,
  }) async {
    final response = await _dio.patch<Map<String, dynamic>>(
      '/api/v1/ai/assistant/conversations/$conversationId',
      data: <String, dynamic>{'title': title.trim()},
      options: _options(session),
    );
    return AssistantConversationDetail.fromJson(_required(response.data));
  }

  Future<AssistantConversationDeleteResult> deleteChat({
    required AuthSession session,
    required int conversationId,
  }) async {
    final response = await _dio.delete<Map<String, dynamic>>(
      '/api/v1/ai/assistant/conversations/$conversationId',
      options: _options(session),
    );
    return AssistantConversationDeleteResult.fromJson(_required(response.data));
  }

  Map<String, dynamic> _required(Map<String, dynamic>? value) {
    if (value == null) {
      throw const FormatException('Nie odczytano rozmowy Asystenta.');
    }
    return value;
  }
}
