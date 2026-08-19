import 'package:dio/dio.dart';

import '../domain/client_candidate_context.dart';
import 'client_candidate_response.dart';

class ClientCandidatesApi {
  const ClientCandidatesApi(this._dio);

  final Dio _dio;

  static const String _path = '/api/v1/client-candidates';

  Future<List<ClientCandidateResponse>> fetchCandidates({
    required String accessToken,
    required String tokenType,
    String? search,
    String status = 'pending',
    int skip = 0,
    int limit = 100,
  }) async {
    final Response<List<dynamic>> response = await _dio.get<List<dynamic>>(
      _path,
      queryParameters: <String, dynamic>{
        'status': status,
        if (search != null && search.trim().isNotEmpty) 'search': search.trim(),
        'skip': skip,
        'limit': limit,
      },
      options: Options(
        headers: _headers(accessToken: accessToken, tokenType: tokenType),
      ),
    );

    final List<dynamic>? data = response.data;

    if (data == null) {
      throw const FormatException(
        'Endpoint kandydatów zwrócił pustą odpowiedź.',
      );
    }

    return data
        .map<ClientCandidateResponse>(
          (dynamic item) => ClientCandidateResponse.fromJson(
            Map<String, dynamic>.from(item as Map),
          ),
        )
        .toList(growable: false);
  }

  Future<ClientCandidateContext> fetchContext({
    required int candidateId,
    required String accessToken,
    required String tokenType,
  }) async {
    final Response<Map<String, dynamic>> response = await _dio
        .get<Map<String, dynamic>>(
          '$_path/$candidateId',
          options: Options(
            headers: _headers(accessToken: accessToken, tokenType: tokenType),
          ),
        );

    final Map<String, dynamic>? data = response.data;

    if (data == null) {
      throw const FormatException(
        'Endpoint szczegółów kandydata zwrócił pustą odpowiedź.',
      );
    }

    return ClientCandidateContext(
      candidate: _map(data['candidate']),
      gmailMessages: _mapList(data['gmail_messages']),
      sheetsRows: _mapList(data['sheets_rows']),
      documents: _mapList(data['documents']),
      otherSources: _mapList(data['other_sources']),
      metadata: _map(data['metadata']),
    );
  }

  Future<CandidateAcceptResult> accept({
    required int candidateId,
    required String accessToken,
    required String tokenType,
  }) async {
    try {
      final Response<Map<String, dynamic>> response = await _dio
          .post<Map<String, dynamic>>(
            '$_path/$candidateId/accept',
            options: Options(
              headers: _headers(accessToken: accessToken, tokenType: tokenType),
            ),
          );

      final Map<String, dynamic>? data = response.data;

      if (data == null) {
        throw const FormatException(
          'Endpoint akceptacji zwrócił pustą odpowiedź.',
        );
      }

      return CandidateAcceptResult(
        candidateId: data['candidate_id'] as int,
        clientId: data['client_id'] as int,
        clientName: data['client_name']?.toString() ?? '',
      );
    } on DioException catch (error) {
      if (error.response?.statusCode == 409) {
        final dynamic responseData = error.response?.data;

        if (responseData is Map) {
          final dynamic detail = responseData['detail'];

          if (detail is Map &&
              detail['code'] == 'candidate_matches_existing_client') {
            throw CandidateDuplicateException(
              clientId: (detail['matched_client_id'] as num).toInt(),
              matchedBy: detail['matched_by']?.toString() ?? 'unknown',
              matches:
                  (detail['matches'] as List<dynamic>? ?? const <dynamic>[])
                      .whereType<Map>()
                      .map(
                        (Map<dynamic, dynamic> value) =>
                            CandidateDuplicateMatch.fromJson(
                              Map<String, dynamic>.from(value),
                            ),
                      )
                      .toList(growable: false),
            );
          }
        }
      }

      rethrow;
    }
  }

  Future<CandidateMergePreview> fetchMergePreview({
    required int candidateId,
    required int targetClientId,
    required String accessToken,
    required String tokenType,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '$_path/$candidateId/merge-preview',
      queryParameters: <String, dynamic>{'target_client_id': targetClientId},
      options: Options(
        headers: _headers(accessToken: accessToken, tokenType: tokenType),
      ),
    );
    final data = response.data;
    if (data == null) {
      throw const FormatException('Podgląd połączenia jest pusty.');
    }
    return CandidateMergePreview.fromJson(data);
  }

  Future<CandidateMergeResult> merge({
    required int candidateId,
    required int targetClientId,
    required String operationId,
    required String expectedCandidateVersion,
    required Map<String, String> fieldDecisions,
    required String accessToken,
    required String tokenType,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$_path/$candidateId/merge',
      data: <String, dynamic>{
        'operation_id': operationId,
        'target_client_id': targetClientId,
        'field_decisions': fieldDecisions,
        'expected_candidate_version': expectedCandidateVersion,
      },
      options: Options(
        headers: _headers(accessToken: accessToken, tokenType: tokenType),
      ),
    );
    final data = response.data;
    if (data == null) {
      throw const FormatException(
        'Operacja połączenia zwróciła pustą odpowiedź.',
      );
    }
    return CandidateMergeResult(
      clientId: (data['client_id'] as num).toInt(),
      clientName: data['client_name']?.toString() ?? '',
      idempotentReplay: data['idempotent_replay'] == true,
    );
  }

  Future<void> reject({
    required int candidateId,
    required String accessToken,
    required String tokenType,
  }) async {
    await _dio.post<void>(
      '$_path/$candidateId/reject',
      options: Options(
        headers: _headers(accessToken: accessToken, tokenType: tokenType),
      ),
    );
  }

  Future<Map<String, dynamic>> bulkAccept({
    required List<int> candidateIds,
    required String accessToken,
    required String tokenType,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$_path/bulk-accept',
      data: <String, dynamic>{'candidate_ids': candidateIds},
      options: Options(
        headers: _headers(accessToken: accessToken, tokenType: tokenType),
      ),
    );
    return response.data ?? <String, dynamic>{};
  }

  Map<String, Object> _headers({
    required String accessToken,
    required String tokenType,
  }) {
    final String normalized = tokenType.trim();

    final String type = normalized.isEmpty
        ? 'Bearer'
        : '${normalized[0].toUpperCase()}'
              '${normalized.substring(1).toLowerCase()}';

    return <String, Object>{
      'Authorization': '$type $accessToken',
      'Accept': 'application/json',
    };
  }

  static Map<String, dynamic> _map(dynamic value) {
    if (value is Map) {
      return Map<String, dynamic>.from(value);
    }

    return <String, dynamic>{};
  }

  static List<Map<String, dynamic>> _mapList(dynamic value) {
    if (value is! List) {
      return <Map<String, dynamic>>[];
    }

    return value
        .whereType<Map>()
        .map<Map<String, dynamic>>(
          (Map item) => Map<String, dynamic>.from(item),
        )
        .toList(growable: false);
  }
}
