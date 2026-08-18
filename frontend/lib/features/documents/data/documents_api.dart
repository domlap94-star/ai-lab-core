import 'dart:typed_data';
import 'dart:convert';

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

  Future<void> uploadUserDocument({
    required String accessToken,
    required String tokenType,
    required String name,
    String? path,
    Uint8List? bytes,
    int? clientId,
    int? projectId,
    int? inspectionId,
    String origin = 'manual_upload',
    DateTime? capturedAt,
    double? latitude,
    double? longitude,
    double? accuracy,
    String? deviceModel,
    String? comment,
    void Function(int sent, int total)? onProgress,
  }) async {
    if (path == null && bytes == null) {
      throw ArgumentError('Upload requires a path or bytes.');
    }
    final file = path != null
        ? await MultipartFile.fromFile(path, filename: name)
        : MultipartFile.fromBytes(bytes!, filename: name);
    final sourceType = origin == 'camera_capture'
        ? 'camera_photo'
        : 'manual_upload';
    final fields = <String, dynamic>{
      'file': file,
      'source_type': sourceType,
      'intake_metadata': jsonEncode(<String, dynamic>{
        'origin': origin,
        'platform': 'flutter',
        'device_model': ?deviceModel,
        'user_comment': ?(comment != null && comment.trim().isNotEmpty
            ? comment.trim()
            : null),
      }),
    };
    if (clientId != null) fields['client_id'] = clientId;
    if (projectId != null) fields['project_id'] = projectId;
    if (inspectionId != null) fields['inspection_id'] = inspectionId;
    if (capturedAt != null) {
      fields['captured_at'] = capturedAt.toUtc().toIso8601String();
    }
    if (latitude != null) {
      fields['latitude'] = latitude;
      fields['location_source'] = 'device_gps';
    }
    if (longitude != null) fields['longitude'] = longitude;
    if (accuracy != null) fields['location_accuracy_m'] = accuracy;
    final form = FormData.fromMap(fields);
    await _dio.post<Map<String, dynamic>>(
      '$_path/user-upload',
      data: form,
      options: Options(
        headers: _headers(accessToken, tokenType),
        sendTimeout: const Duration(minutes: 5),
      ),
      onSendProgress: onProgress,
    );
  }

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

  Future<void> analyzeVision({
    required int documentId,
    required String accessToken,
    required String tokenType,
  }) async {
    await _dio.post<Map<String, dynamic>>(
      '$_path/$documentId/vision/analyze',
      options: Options(headers: _headers(accessToken, tokenType)),
    );
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
      if (filters.projectId != null) 'project_id': filters.projectId,
      if (filters.inspectionId != null) 'inspection_id': filters.inspectionId,
      if (filters.documentId != null) 'document_id': filters.documentId,
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
