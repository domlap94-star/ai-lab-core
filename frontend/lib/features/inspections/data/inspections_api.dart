import 'package:dio/dio.dart';
import '../../auth/domain/auth_session.dart';
import '../domain/inspection.dart';

class InspectionsApi {
  const InspectionsApi(this._dio);
  final Dio _dio;
  static const path = '/api/v1/inspections';
  Options _options(AuthSession session) => Options(
    headers: <String, Object>{
      'Authorization': '${session.tokenType} ${session.accessToken}',
    },
  );
  Future<InspectionPage> list(
    AuthSession session, {
    String search = '',
    int? projectId,
    int? clientId,
    InspectionStatus? status,
    DateTime? dateFrom,
    DateTime? dateTo,
    int skip = 0,
    int limit = 50,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      path,
      queryParameters: <String, dynamic>{
        if (search.trim().isNotEmpty) 'search': search.trim(),
        'project_id': ?projectId,
        'client_id': ?clientId,
        'status': ?status?.apiValue,
        'date_from': ?dateFrom?.toUtc().toIso8601String(),
        'date_to': ?dateTo?.toUtc().toIso8601String(),
        'skip': skip,
        'limit': limit,
      },
      options: _options(session),
    );
    final data = response.data!;
    return InspectionPage(
      items: (data['items'] as List<dynamic>)
          .cast<Map<String, dynamic>>()
          .map(Inspection.fromJson)
          .toList(),
      total: data['total'] as int,
      skip: data['skip'] as int,
      limit: data['limit'] as int,
    );
  }

  Future<Inspection> get(AuthSession session, int id) async =>
      Inspection.fromJson(
        (await _dio.get<Map<String, dynamic>>(
          '$path/$id',
          options: _options(session),
        )).data!,
      );
  Future<Inspection> create(
    AuthSession session,
    Map<String, dynamic> data,
  ) async => Inspection.fromJson(
    (await _dio.post<Map<String, dynamic>>(
      path,
      data: data,
      options: _options(session),
    )).data!,
  );
  Future<Inspection> update(
    AuthSession session,
    int id,
    Map<String, dynamic> data,
  ) async => Inspection.fromJson(
    (await _dio.patch<Map<String, dynamic>>(
      '$path/$id',
      data: data,
      options: _options(session),
    )).data!,
  );
  Future<void> delete(AuthSession session, int id) async =>
      _dio.delete<void>('$path/$id', options: _options(session));
}
