import 'package:dio/dio.dart';

import '../../auth/domain/auth_session.dart';
import '../domain/global_search.dart';

abstract interface class GlobalSearchGateway {
  Future<GlobalSearchPageData> search({
    required AuthSession session,
    required String query,
    GlobalSearchType? type,
    int skip = 0,
    int limit = 25,
    CancelToken? cancelToken,
  });
}

class GlobalSearchApi implements GlobalSearchGateway {
  const GlobalSearchApi(this._dio);
  final Dio _dio;

  @override
  Future<GlobalSearchPageData> search({
    required AuthSession session,
    required String query,
    GlobalSearchType? type,
    int skip = 0,
    int limit = 25,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/search',
      queryParameters: <String, dynamic>{
        'q': query.trim(),
        if (type != null) 'types': type.name,
        'skip': skip,
        'limit': limit,
      },
      options: Options(
        headers: <String, Object>{
          'Authorization': '${session.tokenType} ${session.accessToken}',
        },
      ),
      cancelToken: cancelToken,
    );
    final data = response.data;
    if (data == null) {
      throw const FormatException('Wyszukiwarka zwróciła pustą odpowiedź.');
    }
    return GlobalSearchPageData.fromJson(data);
  }
}
