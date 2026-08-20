import 'package:dio/dio.dart';

import '../../auth/domain/auth_session.dart';
import '../domain/trash_entry.dart';

class TrashApi {
  const TrashApi(this._dio);
  final Dio _dio;

  Options _options(AuthSession session) => Options(
    headers: <String, String>{
      'Authorization': '${session.tokenType} ${session.accessToken}',
    },
  );

  Future<TrashPageData> fetch({
    required AuthSession session,
    required TrashEntityType entityType,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/admin/trash',
      queryParameters: <String, dynamic>{
        'entity_type': entityType.name,
        'skip': 0,
        'limit': 100,
      },
      options: _options(session),
    );
    final data = response.data ?? const <String, dynamic>{};
    final raw = data['items'] as List<dynamic>? ?? const <dynamic>[];
    return TrashPageData(
      items: raw
          .map((item) => TrashEntry.fromJson(item as Map<String, dynamic>))
          .toList(growable: false),
      total: data['total'] as int? ?? raw.length,
    );
  }

  Future<void> restore({required AuthSession session, required int entryId}) =>
      _dio.post<void>(
        '/api/v1/admin/trash/$entryId/restore',
        options: _options(session),
      );

  Future<void> trashDocument({
    required AuthSession session,
    required int documentId,
  }) => _dio.post<void>(
    '/api/v1/documents/$documentId/trash',
    options: _options(session),
  );

  Future<void> trashUser({required AuthSession session, required int userId}) =>
      _dio.post<void>(
        '/api/v1/admin/users/$userId/trash',
        options: _options(session),
      );
}
