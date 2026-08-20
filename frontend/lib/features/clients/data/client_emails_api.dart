import 'package:dio/dio.dart';

import 'client_email_page_response.dart';

class ClientEmailsApi {
  const ClientEmailsApi(this._dio);

  final Dio _dio;

  Future<ClientEmailPageResponse> fetchEmails({
    required int clientId,
    required String accessToken,
    required String tokenType,
    int skip = 0,
    int limit = 20,
    int? sourceId,
    bool? ignored,
  }) async {
    final String normalizedType = tokenType.trim().isEmpty
        ? 'Bearer'
        : tokenType;
    final Response<Map<String, dynamic>> response = await _dio
        .get<Map<String, dynamic>>(
          '/api/v1/clients/$clientId/emails',
          queryParameters: <String, dynamic>{
            'skip': skip,
            'limit': limit,
            'source_id': ?sourceId,
            'ignored': ?ignored,
          },
          options: Options(
            headers: <String, Object>{
              'Authorization': '$normalizedType $accessToken',
              'Accept': 'application/json',
            },
          ),
        );
    if (response.data == null) {
      throw const FormatException(
        'Endpoint historii maili zwrócił pustą odpowiedź.',
      );
    }
    return ClientEmailPageResponse.fromJson(response.data!);
  }
}
