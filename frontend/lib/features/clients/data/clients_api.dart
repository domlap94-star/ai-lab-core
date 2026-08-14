import 'package:dio/dio.dart';

import 'client_create_request.dart';
import 'client_page_response.dart';
import 'client_response.dart';
import 'industry_response.dart';

class ClientsApi {
  const ClientsApi(this._dio);

  final Dio _dio;

  static const String _clientsPath = '/api/v1/clients';
  static const String _industriesPath = '/api/v1/clients/industries';

  Future<ClientPageResponse> fetchClients({
    required String accessToken,
    required String tokenType,
    String? search,
    String? clientType,
    int? industryId,
    int skip = 0,
    int limit = 50,
  }) async {
    final Response<Map<String, dynamic>> response = await _dio
        .get<Map<String, dynamic>>(
          _clientsPath,
          queryParameters: <String, dynamic>{
            if (search != null && search.trim().isNotEmpty)
              'search': search.trim(),
            if (clientType != null && clientType.isNotEmpty)
              'client_type': clientType,
            'industry_id': ?industryId,
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
