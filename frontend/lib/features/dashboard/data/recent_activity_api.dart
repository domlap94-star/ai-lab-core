import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../auth/domain/auth_session.dart';
import '../domain/recent_activity.dart';

class RecentActivityApi {
  const RecentActivityApi(this._dio);
  final Dio _dio;

  Future<RecentActivityPageData> recent({
    required AuthSession session,
    int skip = 0,
    int limit = 8,
  }) async {
    final Response<Map<String, dynamic>> response = await _dio.get(
      '/api/v1/activity/recent',
      queryParameters: <String, dynamic>{'skip': skip, 'limit': limit},
      options: Options(
        headers: <String, Object>{
          'Authorization': '${session.tokenType} ${session.accessToken}',
        },
      ),
    );
    return RecentActivityPageData.fromJson(
      response.data ?? <String, dynamic>{},
    );
  }
}

final recentActivityApiProvider = Provider<RecentActivityApi>(
  (Ref ref) => RecentActivityApi(ref.watch(dioProvider)),
);
