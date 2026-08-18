import 'package:dio/dio.dart';

import '../../auth/domain/auth_session.dart';
import '../domain/technical_assistant.dart';

abstract interface class TechnicalAssistantGateway {
  Future<TechnicalAssistantAnswer> ask({
    required AuthSession session,
    required String question,
    int? clientId,
    int? inspectionId,
    List<Map<String, String>> conversation = const [],
    CancelToken? cancelToken,
  });
}

class TechnicalAssistantApi implements TechnicalAssistantGateway {
  const TechnicalAssistantApi(this._dio);
  final Dio _dio;

  @override
  Future<TechnicalAssistantAnswer> ask({
    required AuthSession session,
    required String question,
    int? clientId,
    int? inspectionId,
    List<Map<String, String>> conversation = const [],
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/ai/technical/ask',
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
        receiveTimeout: const Duration(minutes: 5),
      ),
      cancelToken: cancelToken,
    );
    if (response.data == null) {
      throw const FormatException(
        'Asystent techniczny zwrócił pustą odpowiedź.',
      );
    }
    return TechnicalAssistantAnswer.fromJson(response.data!);
  }
}
