import 'package:dio/dio.dart';

import '../../auth/domain/auth_session.dart';

class ClientAccessRepository {
  ClientAccessRepository(this._dio);

  final Dio _dio;

  Options _options(AuthSession session) => Options(
    headers: <String, String>{
      'Authorization': '${session.tokenType} ${session.accessToken}',
    },
  );

  Future<List<Map<String, dynamic>>> fetchSharedClients(
    AuthSession session,
  ) async {
    final Response<List<dynamic>> response = await _dio.get<List<dynamic>>(
      '/api/v1/client-access/shared-clients',
      options: _options(session),
    );
    return (response.data ?? const <dynamic>[])
        .whereType<Map<String, dynamic>>()
        .toList(growable: false);
  }

  Future<List<Map<String, dynamic>>> fetchGrantHistory(
    AuthSession session,
  ) async {
    final Response<Map<String, dynamic>> response = await _dio
        .get<Map<String, dynamic>>(
          '/api/v1/client-access/grants',
          options: _options(session),
        );
    return (response.data?['items'] as List<dynamic>? ?? const <dynamic>[])
        .whereType<Map<String, dynamic>>()
        .toList(growable: false);
  }

  Future<Map<String, List<Map<String, dynamic>>>> fetchManagerOptions(
    AuthSession session,
  ) async {
    final Response<Map<String, dynamic>> response = await _dio
        .get<Map<String, dynamic>>(
          '/api/v1/client-access/manager-options',
          options: _options(session),
        );

    List<Map<String, dynamic>> rows(String key) =>
        (response.data?[key] as List<dynamic>? ?? const <dynamic>[])
            .whereType<Map<String, dynamic>>()
            .toList(growable: false);

    return <String, List<Map<String, dynamic>>>{
      'clients': rows('clients'),
      'external_users': rows('external_users'),
    };
  }

  Future<void> grant({
    required AuthSession session,
    required int clientId,
    required int externalUserId,
  }) async {
    await _dio.post<void>(
      '/api/v1/client-access/grants',
      data: <String, int>{
        'client_id': clientId,
        'external_user_id': externalUserId,
      },
      options: _options(session),
    );
  }

  Future<void> revoke({
    required AuthSession session,
    required int clientId,
    required int externalUserId,
  }) async {
    await _dio.delete<void>(
      '/api/v1/client-access/grants',
      queryParameters: <String, int>{
        'client_id': clientId,
        'external_user_id': externalUserId,
      },
      options: _options(session),
    );
  }
}
