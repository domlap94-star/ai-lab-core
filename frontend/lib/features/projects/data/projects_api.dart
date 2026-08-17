import 'package:dio/dio.dart';
import '../../auth/domain/auth_session.dart';
import '../domain/project.dart';

class ProjectsApi {
  const ProjectsApi(this._dio);
  final Dio _dio;
  static const path = '/api/v1/projects';
  Options _options(AuthSession session) => Options(
    headers: <String, Object>{
      'Authorization': '${session.tokenType} ${session.accessToken}',
    },
  );
  Future<ProjectPage> list(
    AuthSession session, {
    String search = '',
    int? clientId,
    ProjectStatus? status,
    int skip = 0,
    int limit = 50,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      path,
      queryParameters: <String, dynamic>{
        if (search.trim().isNotEmpty) 'search': search.trim(),
        'client_id': ?clientId,
        'status': ?status?.name,
        'skip': skip,
        'limit': limit,
      },
      options: _options(session),
    );
    final data = response.data!;
    return ProjectPage(
      items: (data['items'] as List<dynamic>)
          .cast<Map<String, dynamic>>()
          .map(Project.fromJson)
          .toList(),
      total: data['total'] as int,
      skip: data['skip'] as int,
      limit: data['limit'] as int,
    );
  }

  Future<Project> get(AuthSession session, int id) async => Project.fromJson(
    (await _dio.get<Map<String, dynamic>>(
      '$path/$id',
      options: _options(session),
    )).data!,
  );
  Future<Project> create(
    AuthSession session,
    Map<String, dynamic> data,
  ) async => Project.fromJson(
    (await _dio.post<Map<String, dynamic>>(
      path,
      data: data,
      options: _options(session),
    )).data!,
  );
  Future<Project> update(
    AuthSession session,
    int id,
    Map<String, dynamic> data,
  ) async => Project.fromJson(
    (await _dio.patch<Map<String, dynamic>>(
      '$path/$id',
      data: data,
      options: _options(session),
    )).data!,
  );
  Future<void> delete(AuthSession session, int id) async {
    await _dio.delete<void>('$path/$id', options: _options(session));
  }
}
