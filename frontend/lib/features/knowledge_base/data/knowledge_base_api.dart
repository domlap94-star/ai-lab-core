import 'dart:convert';
import 'dart:typed_data';
import 'package:dio/dio.dart';
import '../../auth/domain/auth_session.dart';
import '../domain/knowledge_base_models.dart';

class KnowledgeBaseApi {
  const KnowledgeBaseApi(this._dio);
  final Dio _dio;
  Options _options(AuthSession session) => Options(
    headers: <String, String>{
      'Authorization': '${session.tokenType} ${session.accessToken}',
    },
  );
  Future<KnowledgeBaseListResult> list(
    AuthSession session, {
    String? query,
    String? category,
    String? status,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/admin/knowledge-base',
      queryParameters: <String, dynamic>{
        'q': query,
        'category': category,
        'item_status': status,
        'limit': 100,
      },
      options: _options(session),
    );
    final data = response.data!;
    return KnowledgeBaseListResult(
      ((data['items'] as List<dynamic>?) ?? const <dynamic>[])
          .map(
            (dynamic value) =>
                KnowledgeBaseItem.fromJson(value as Map<String, dynamic>),
          )
          .toList(growable: false),
      data['total'] as int,
    );
  }

  Future<KnowledgeBaseItem> detail(AuthSession session, int id) async =>
      KnowledgeBaseItem.fromJson(
        (await _dio.get<Map<String, dynamic>>(
          '/api/v1/admin/knowledge-base/$id',
          options: _options(session),
        )).data!,
      );
  Future<void> create(
    AuthSession session, {
    required Map<String, dynamic> metadata,
    required Uint8List bytes,
    required String filename,
  }) => _dio.post<void>(
    '/api/v1/admin/knowledge-base',
    data: FormData.fromMap(<String, dynamic>{
      'metadata_json': jsonEncode(metadata),
      'file': MultipartFile.fromBytes(bytes, filename: filename),
    }),
    options: _options(session),
  );
  Future<void> update(
    AuthSession session,
    int id,
    Map<String, dynamic> metadata,
  ) => _dio.patch<void>(
    '/api/v1/admin/knowledge-base/$id',
    data: metadata,
    options: _options(session),
  );
  Future<void> retry(AuthSession session, int id) => _dio.post<void>(
    '/api/v1/admin/knowledge-base/$id/retry',
    options: _options(session),
  );
  Future<void> archive(AuthSession session, int id) => _dio.delete<void>(
    '/api/v1/admin/knowledge-base/$id',
    options: _options(session),
  );
}
