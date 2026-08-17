import 'package:dio/dio.dart';
import '../../auth/domain/auth_session.dart';
import '../domain/timeline.dart';

class TimelineApi {
  const TimelineApi(this._dio);
  final Dio _dio;
  Future<TimelinePage> fetch(
    AuthSession session,
    TimelineRequest request,
  ) async {
    final resource = request.scope == TimelineScope.client
        ? 'clients'
        : 'projects';
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/$resource/${request.id}/timeline',
      queryParameters: <String, dynamic>{
        'skip': 0,
        'limit': request.limit,
        if (request.eventType != null) 'event_type': request.eventType,
      },
      options: Options(
        headers: <String, Object>{
          'Authorization': '${session.tokenType} ${session.accessToken}',
        },
      ),
    );
    return TimelinePage.fromJson(response.data!);
  }
}
