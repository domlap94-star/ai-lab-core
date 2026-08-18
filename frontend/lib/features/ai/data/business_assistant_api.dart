import 'package:dio/dio.dart';
import '../../auth/domain/auth_session.dart';
import '../domain/business_assistant.dart';

abstract interface class BusinessAssistantGateway {
  Future<BusinessAssistantAnswer> ask({
    required AuthSession session,
    required String question,
    List<Map<String, String>> conversation = const [],
    CancelToken? cancelToken,
  });
}

class BusinessAssistantApi implements BusinessAssistantGateway {
  const BusinessAssistantApi(this._dio);
  final Dio _dio;
  @override
  Future<BusinessAssistantAnswer> ask({
    required AuthSession session,
    required String question,
    List<Map<String, String>> conversation = const [],
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/ai/business/ask',
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
    if (response.data == null) {
      throw const FormatException('Asystent AI zwrócił pustą odpowiedź.');
    }
    return BusinessAssistantAnswer.fromJson(response.data!);
  }
}
