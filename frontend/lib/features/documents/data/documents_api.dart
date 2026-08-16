import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../domain/document_filters.dart';
import '../domain/document_client_match.dart';
import 'document_content.dart';
import 'document_page_response.dart';
import 'document_response.dart';

class DocumentsApi {
  const DocumentsApi(this._dio);

  final Dio _dio;

  static const String _path = '/api/v1/documents';

  Future<DocumentPageResponse> fetchDocuments({
    required String accessToken,
    required String tokenType,
    required DocumentFilters filters,
    String search = '',
    int skip = 0,
    int limit = 50,
  }) async {
    final Response<Map<String, dynamic>> response = await _dio
        .get<Map<String, dynamic>>(
          _path,
          queryParameters: buildQueryParameters(
            filters: filters,
            search: search,
            skip: skip,
            limit: limit,
          ),
          options: Options(headers: _headers(accessToken, tokenType)),
        );

    if (response.data == null) {
      throw const FormatException(
        'Endpoint dokumentów zwrócił pustą odpowiedź.',
      );
    }

    return DocumentPageResponse.fromJson(response.data!);
  }

  Future<DocumentResponse> fetchDocument({
    required int documentId,
    required String accessToken,
    required String tokenType,
  }) async {
    final Response<Map<String, dynamic>> response = await _dio
        .get<Map<String, dynamic>>(
          '$_path/$documentId',
          options: Options(headers: _headers(accessToken, tokenType)),
        );

    if (response.data == null) {
      throw const FormatException(
        'Endpoint dokumentu zwrócił pustą odpowiedź.',
      );
    }

    return DocumentResponse.fromJson(response.data!);
  }

  Future<DocumentContent> fetchContent({
    required int documentId,
    required String fileName,
    required String contentType,
    required String accessToken,
    required String tokenType,
    void Function(int received, int total)? onProgress,
  }) async {
    final Response<List<int>> response = await _dio.get<List<int>>(
      '$_path/$documentId/content',
      options: Options(
        headers: <String, Object>{
          ..._headers(accessToken, tokenType),
          'Accept': '*/*',
        },
        responseType: ResponseType.bytes,
        receiveTimeout: const Duration(minutes: 2),
      ),
      onReceiveProgress: onProgress,
    );

    final List<int>? data = response.data;
    if (data == null) {
      throw const FormatException('Endpoint treści zwrócił pustą odpowiedź.');
    }

    return DocumentContent(
      bytes: data is Uint8List ? data : Uint8List.fromList(data),
      fileName: fileName,
      contentType:
          response.headers.value(Headers.contentTypeHeader) ?? contentType,
    );
  }

  Future<DocumentClientMatch> fetchClientMatch({
    required int documentId,
    required String accessToken,
    required String tokenType,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '$_path/$documentId/client-match',
      options: Options(headers: _headers(accessToken, tokenType)),
    );
    if (response.data == null) {
      throw const FormatException('Pusta odpowiedź dopasowania.');
    }
    return DocumentClientMatch.fromJson(response.data!);
  }

  Future<void> linkClient({
    required int documentId,
    required int clientId,
    required bool move,
    required bool confirmConflict,
    required String accessToken,
    required String tokenType,
  }) async {
    await _dio.post<Map<String, dynamic>>(
      '$_path/$documentId/${move ? 'move-client' : 'link-client'}',
      data: <String, dynamic>{
        'client_id': clientId,
        'reason': 'manual UI',
        'confirm_conflict': confirmConflict,
      },
      options: Options(headers: _headers(accessToken, tokenType)),
    );
  }

  Future<void> unlinkClient({
    required int documentId,
    required String accessToken,
    required String tokenType,
  }) async {
    await _dio.post<Map<String, dynamic>>(
      '$_path/$documentId/unlink-client',
      data: const <String, dynamic>{'reason': 'manual UI', 'confirm': true},
      options: Options(headers: _headers(accessToken, tokenType)),
    );
  }

  Future<void> undoClientLink({
    required int documentId,
    required String accessToken,
    required String tokenType,
  }) async {
    await _dio.post<Map<String, dynamic>>(
      '$_path/$documentId/undo-client-link',
      options: Options(headers: _headers(accessToken, tokenType)),
    );
  }

  static Map<String, dynamic> buildQueryParameters({
    required DocumentFilters filters,
    String search = '',
    int skip = 0,
    int limit = 50,
  }) {
    return <String, dynamic>{
      if (search.trim().isNotEmpty) 'search': search.trim(),
      if (filters.clientId != null) 'client_id': filters.clientId,
      if (filters.sourceType != null) 'source_type': filters.sourceType,
      if (filters.matchStatus != null) 'match_status': filters.matchStatus,
      if (filters.processingStatus != null)
        'processing_status': filters.processingStatus,
      if (filters.contentType != null) 'content_type': filters.contentType,
      'link_state': filters.linkState.queryValue,
      'skip': skip,
      'limit': limit,
    };
  }

  Map<String, Object> _headers(String accessToken, String tokenType) {
    final String normalized = tokenType.trim().isEmpty ? 'Bearer' : tokenType;
    return <String, Object>{
      'Authorization': '$normalized $accessToken',
      'Accept': 'application/json',
    };
  }
}
