import 'package:dio/dio.dart';

import 'client_create_request.dart';
import 'client_page_response.dart';
import 'client_response.dart';
import 'industry_response.dart';

class ClientsApi {
  const ClientsApi(this._dio);

  final Dio _dio;

  static const String _clientsPath = '/api/v1/clients';
  static const String clientsPagePath = '$_clientsPath/page';
  static const String _industriesPath = '/api/v1/clients/industries';

  Future<ClientPageResponse> fetchClients({
    required String accessToken,
    required String tokenType,
    String? search,
    String? clientType,
    int? industryId,
    List<String> excludeStatuses = const <String>[],
    String sortOrder = 'newest',
    int skip = 0,
    int limit = 50,
  }) async {
    final Response<Map<String, dynamic>> response = await _dio
        .get<Map<String, dynamic>>(
          clientsPagePath,
          queryParameters: <String, dynamic>{
            if (search != null && search.trim().isNotEmpty)
              'search': search.trim(),
            if (clientType != null && clientType.isNotEmpty)
              'client_type': clientType,
            'industry_id': ?industryId,
            if (excludeStatuses.isNotEmpty) 'exclude_status': excludeStatuses,
            'sort_order': sortOrder,
            'skip': skip,
            'limit': limit,
          },
          options: Options(
            headers: _authorizationHeaders(
              accessToken: accessToken,
              tokenType: tokenType,
            ),
          ),
        );

    final Map<String, dynamic>? data = response.data;

    if (data == null) {
      throw const FormatException('Endpoint klientów zwrócił pustą odpowiedź.');
    }

    return ClientPageResponse.fromJson(data);
  }

  Future<ClientResponse> fetchClient({
    required int clientId,
    required String accessToken,
    required String tokenType,
  }) async {
    final Response<Map<String, dynamic>> response = await _dio
        .get<Map<String, dynamic>>(
          '$_clientsPath/$clientId',
          options: Options(
            headers: _authorizationHeaders(
              accessToken: accessToken,
              tokenType: tokenType,
            ),
          ),
        );

    final Map<String, dynamic>? data = response.data;

    if (data == null) {
      throw const FormatException('Endpoint klienta zwrócił pustą odpowiedź.');
    }

    return ClientResponse.fromJson(data);
  }

  Future<List<IndustryResponse>> fetchIndustries({
    required String accessToken,
    required String tokenType,
  }) async {
    final Response<List<dynamic>> response = await _dio.get<List<dynamic>>(
      _industriesPath,
      options: Options(
        headers: _authorizationHeaders(
          accessToken: accessToken,
          tokenType: tokenType,
        ),
      ),
    );

    final List<dynamic>? data = response.data;

    if (data == null) {
      throw const FormatException('Endpoint branż zwrócił pustą odpowiedź.');
    }

    return data
        .map<IndustryResponse>(
          (dynamic item) =>
              IndustryResponse.fromJson(Map<String, dynamic>.from(item as Map)),
        )
        .toList(growable: false);
  }

  Future<ClientResponse> createClient({
    required ClientCreateRequest request,
    required String accessToken,
    required String tokenType,
  }) async {
    final Response<Map<String, dynamic>> response = await _dio
        .post<Map<String, dynamic>>(
          _clientsPath,
          data: request.toJson(),
          options: Options(
            headers: _authorizationHeaders(
              accessToken: accessToken,
              tokenType: tokenType,
            ),
            contentType: Headers.jsonContentType,
          ),
        );

    final Map<String, dynamic>? data = response.data;

    if (data == null) {
      throw const FormatException(
        'Endpoint tworzenia klienta zwrócił pustą odpowiedź.',
      );
    }

    return ClientResponse.fromJson(data);
  }

  Future<ClientResponse> updateClient({
    required int clientId,
    required Map<String, dynamic> data,
    required String accessToken,
    required String tokenType,
  }) async {
    final response = await _dio.patch<Map<String, dynamic>>(
      '$_clientsPath/$clientId',
      data: data,
      options: Options(
        headers: _authorizationHeaders(
          accessToken: accessToken,
          tokenType: tokenType,
        ),
      ),
    );
    if (response.data == null) {
      throw const FormatException('Pusta odpowiedź aktualizacji klienta.');
    }
    return ClientResponse.fromJson(response.data!);
  }

  Future<void> deleteClient({
    required int clientId,
    required String accessToken,
    required String tokenType,
  }) async {
    await _dio.delete<void>(
      '$_clientsPath/$clientId',
      options: Options(
        headers: _authorizationHeaders(
          accessToken: accessToken,
          tokenType: tokenType,
        ),
      ),
    );
  }

  Future<void> createContactPerson({
    required int clientId,
    required Map<String, dynamic> data,
    required String accessToken,
    required String tokenType,
  }) async {
    await _dio.post<Map<String, dynamic>>(
      '$_clientsPath/$clientId/contact-persons',
      data: data,
      options: Options(
        headers: _authorizationHeaders(
          accessToken: accessToken,
          tokenType: tokenType,
        ),
      ),
    );
  }

  Future<void> updateContactPerson({
    required int clientId,
    required int personId,
    required Map<String, dynamic> data,
    required String accessToken,
    required String tokenType,
  }) async {
    await _dio.patch<Map<String, dynamic>>(
      '$_clientsPath/$clientId/contact-persons/$personId',
      data: data,
      options: Options(
        headers: _authorizationHeaders(
          accessToken: accessToken,
          tokenType: tokenType,
        ),
      ),
    );
  }

  Future<void> archiveContactPerson({
    required int clientId,
    required int personId,
    required String accessToken,
    required String tokenType,
  }) async {
    await _dio.delete<void>(
      '$_clientsPath/$clientId/contact-persons/$personId',
      options: Options(
        headers: _authorizationHeaders(
          accessToken: accessToken,
          tokenType: tokenType,
        ),
      ),
    );
  }

  Future<List<Map<String, dynamic>>> fetchWorkflowStatuses({
    required List<int> clientIds,
    required String accessToken,
    required String tokenType,
  }) async {
    final response = await _dio.get<List<dynamic>>(
      '$_clientsPath/workflow-statuses',
      queryParameters: <String, dynamic>{'client_ids': clientIds},
      options: Options(
        headers: _authorizationHeaders(
          accessToken: accessToken,
          tokenType: tokenType,
        ),
      ),
    );
    return (response.data ?? const <dynamic>[])
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList();
  }

  Future<Map<String, dynamic>> bulkWorkflowStatus({
    required List<int> clientIds,
    required String status,
    String? effectiveDate,
    required String accessToken,
    required String tokenType,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$_clientsPath/bulk/workflow-status',
      data: <String, dynamic>{
        'client_ids': clientIds,
        'status': status,
        'effective_date': effectiveDate,
      },
      options: Options(
        headers: _authorizationHeaders(
          accessToken: accessToken,
          tokenType: tokenType,
        ),
      ),
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> recordCallInitiated({
    required int clientId,
    required String operationId,
    int? contactId,
    required String accessToken,
    required String tokenType,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$_clientsPath/$clientId/activities/call-initiated',
      data: <String, dynamic>{
        'operation_id': operationId,
        'contact_id': contactId,
      },
      options: Options(
        headers: _authorizationHeaders(
          accessToken: accessToken,
          tokenType: tokenType,
        ),
      ),
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> bulkSoftDelete({
    required List<int> clientIds,
    required String accessToken,
    required String tokenType,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$_clientsPath/bulk/soft-delete',
      data: <String, dynamic>{'client_ids': clientIds},
      options: Options(
        headers: _authorizationHeaders(
          accessToken: accessToken,
          tokenType: tokenType,
        ),
      ),
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<void> uploadClientDocument({
    required int clientId,
    required String path,
    required String accessToken,
    required String tokenType,
  }) async {
    final name = path.replaceAll('\\', '/').split('/').last;
    final form = FormData.fromMap(<String, dynamic>{
      'file': await MultipartFile.fromFile(path, filename: name),
    });
    await _dio.post<Map<String, dynamic>>(
      '$_clientsPath/$clientId/documents/upload',
      data: form,
      options: Options(
        headers: _authorizationHeaders(
          accessToken: accessToken,
          tokenType: tokenType,
        ),
      ),
    );
  }

  Map<String, Object> _authorizationHeaders({
    required String accessToken,
    required String tokenType,
  }) {
    return <String, Object>{
      'Authorization': '${_normalizeTokenType(tokenType)} $accessToken',
      'Accept': 'application/json',
    };
  }

  String _normalizeTokenType(String tokenType) {
    final String normalized = tokenType.trim();

    if (normalized.isEmpty) {
      return 'Bearer';
    }

    return '${normalized[0].toUpperCase()}'
        '${normalized.substring(1).toLowerCase()}';
  }
}
