import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../auth/domain/auth_session.dart';
import '../domain/change_history.dart';

class ChangeHistoryApi {
  const ChangeHistoryApi(this._dio);
  final Dio _dio;

  Future<ChangeHistoryPageData> fetch({
    required AuthSession session,
    String? entityType,
    int? actorUserId,
    String? action,
    DateTime? dateFrom,
    DateTime? dateTo,
    int skip = 0,
    int limit = 50,
  }) async {
    final Response<dynamic> response = await _dio.get<dynamic>(
      '/api/v1/admin/change-history',
      queryParameters: <String, dynamic>{
        'entity_type': ?entityType,
        'actor_user_id': ?actorUserId,
        'action': ?action,
        if (dateFrom != null) 'date_from': dateFrom.toUtc().toIso8601String(),
        if (dateTo != null) 'date_to': dateTo.toUtc().toIso8601String(),
        'skip': skip,
        'limit': limit,
      },
      options: Options(
        headers: <String, Object>{
          'Authorization': '${session.tokenType} ${session.accessToken}',
          'Accept': 'application/json',
        },
      ),
    );
    if (response.data is! Map) {
      throw const FormatException('Nieprawidłowa historia zmian.');
    }
    final Map<dynamic, dynamic> data = response.data as Map<dynamic, dynamic>;
    return ChangeHistoryPageData.fromJson(
      data.map((dynamic key, dynamic value) => MapEntry(key.toString(), value)),
    );
  }
}

final changeHistoryApiProvider = Provider<ChangeHistoryApi>(
  (Ref ref) => ChangeHistoryApi(ref.watch(dioProvider)),
);
