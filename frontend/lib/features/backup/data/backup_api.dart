import 'package:dio/dio.dart';

import '../../auth/domain/auth_session.dart';
import '../domain/backup_models.dart';

class BackupApi {
  const BackupApi(this._dio);
  final Dio _dio;
  Options _options(AuthSession session) => Options(headers: <String, String>{'Authorization': '${session.tokenType} ${session.accessToken}'});

  Future<List<BackupSchedule>> schedules(AuthSession session) async {
    final response = await _dio.get<List<dynamic>>('/api/v1/admin/backups/schedules', options: _options(session));
    return (response.data ?? const <dynamic>[]).map((item) => BackupSchedule.fromJson(item as Map<String, dynamic>)).toList(growable: false);
  }

  Future<void> saveSchedule({required AuthSession session, int? id, required Map<String, dynamic> payload}) async {
    if (id == null) {
      await _dio.post<void>('/api/v1/admin/backups/schedules', data: payload, options: _options(session));
    } else {
      await _dio.put<void>('/api/v1/admin/backups/schedules/$id', data: payload, options: _options(session));
    }
  }

  Future<void> deleteSchedule(AuthSession session, int id) => _dio.delete<void>('/api/v1/admin/backups/schedules/$id', options: _options(session));

  Future<BackupRun> runNow({required AuthSession session, required BackupScope scope, required String destination}) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/admin/backups/run', data: <String, dynamic>{'scope': scope.wireName, 'destination': destination, 'confirmed': true}, options: _options(session));
    return BackupRun.fromJson(response.data!);
  }

  Future<List<BackupRun>> runs(AuthSession session) async {
    final response = await _dio.get<Map<String, dynamic>>('/api/v1/admin/backups/runs', queryParameters: const <String, dynamic>{'limit': 50}, options: _options(session));
    return ((response.data?['items'] as List<dynamic>?) ?? const <dynamic>[]).map((item) => BackupRun.fromJson(item as Map<String, dynamic>)).toList(growable: false);
  }

  Future<List<RestoreCandidate>> candidates(AuthSession session) async {
    final response = await _dio.get<List<dynamic>>('/api/v1/admin/backups/restore-candidates', options: _options(session));
    return (response.data ?? const <dynamic>[]).map((item) => RestoreCandidate.fromJson(item as Map<String, dynamic>)).toList(growable: false);
  }

  Future<RestorePreview> preview({required AuthSession session, required String checkpoint, required String mode}) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/admin/backups/restore-preview', data: <String, dynamic>{'checkpoint_path': checkpoint, 'mode': mode}, options: _options(session));
    return RestorePreview.fromJson(response.data!);
  }

  Future<void> requestRestore({required AuthSession session, required String checkpoint, required String mode}) => _dio.post<void>('/api/v1/admin/backups/restore', data: <String, dynamic>{'checkpoint_path': checkpoint, 'mode': mode, 'acknowledged': true, 'confirmation': 'PRZYWRÓĆ'}, options: _options(session));

  Future<List<RestoreRun>> restores(AuthSession session) async {
    final response = await _dio.get<List<dynamic>>('/api/v1/admin/backups/restores', queryParameters: const <String, dynamic>{'limit': 50}, options: _options(session));
    return (response.data ?? const <dynamic>[]).map((item) => RestoreRun.fromJson(item as Map<String, dynamic>)).toList(growable: false);
  }
}
