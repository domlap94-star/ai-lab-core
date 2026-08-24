import 'package:dio/dio.dart';

import '../../auth/domain/auth_session.dart';
import '../domain/backup_models.dart';

class BackupApi {
  const BackupApi(this._dio);
  final Dio _dio;
  Options _options(AuthSession session) => Options(
    headers: <String, String>{
      'Authorization': '${session.tokenType} ${session.accessToken}',
    },
  );

  Future<List<BackupSchedule>> schedules(AuthSession session) async {
    final response = await _dio.get<List<dynamic>>(
      '/api/v1/admin/backups/schedules',
      options: _options(session),
    );
    return (response.data ?? const <dynamic>[])
        .map((item) => BackupSchedule.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
  }

  Future<void> saveSchedule({
    required AuthSession session,
    int? id,
    required Map<String, dynamic> payload,
  }) async {
    if (id == null) {
      await _dio.post<void>(
        '/api/v1/admin/backups/schedules',
        data: payload,
        options: _options(session),
      );
    } else {
      await _dio.put<void>(
        '/api/v1/admin/backups/schedules/$id',
        data: payload,
        options: _options(session),
      );
    }
  }

  Future<void> deleteSchedule(AuthSession session, int id) => _dio.delete<void>(
    '/api/v1/admin/backups/schedules/$id',
    options: _options(session),
  );

  Future<void> reconcileSchedules(AuthSession session) => _dio.post<void>(
    '/api/v1/admin/backups/schedules/reconcile',
    options: _options(session),
  );

  Future<List<ManagedBackup>> managedBackups(AuthSession session) async {
    final response = await _dio.get<List<dynamic>>(
      '/api/v1/admin/backups/managed',
      options: _options(session),
    );
    return (response.data ?? const <dynamic>[])
        .map((item) => ManagedBackup.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
  }

  Future<List<LegacyBackupCandidate>> legacyCandidates(
    AuthSession session,
  ) async {
    final response = await _dio.get<List<dynamic>>(
      '/api/v1/admin/backups/legacy-candidates',
      options: _options(
        session,
      ).copyWith(receiveTimeout: const Duration(seconds: 45)),
    );
    return (response.data ?? const <dynamic>[])
        .map(
          (item) =>
              LegacyBackupCandidate.fromJson(item as Map<String, dynamic>),
        )
        .toList(growable: false);
  }

  Future<ManagedBackup> adoptLegacyBackup({
    required AuthSession session,
    required String adoptionToken,
    int? planId,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/admin/backups/legacy-adopt',
      data: <String, dynamic>{
        'adoption_token': adoptionToken,
        'plan_id': planId,
        'confirmed': true,
      },
      options: _options(session),
    );
    return ManagedBackup.fromJson(
      response.data!['managed_backup'] as Map<String, dynamic>,
    );
  }

  Future<LegacyVerificationJob> startLegacyVerification({
    required AuthSession session,
    required String adoptionToken,
    int? planId,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/admin/backups/legacy-verifications',
      data: <String, dynamic>{
        'adoption_token': adoptionToken,
        'plan_id': planId,
        'confirmed': true,
      },
      options: _options(session),
    );
    return LegacyVerificationJob.fromJson(response.data!);
  }

  Future<LegacyVerificationJob> legacyVerificationStatus({
    required AuthSession session,
    required String jobToken,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/admin/backups/legacy-verifications/status',
      data: <String, dynamic>{'job_token': jobToken},
      options: _options(session),
    );
    return LegacyVerificationJob.fromJson(response.data!);
  }

  Future<List<HostStorageLocation>> storageLocations(
    AuthSession session,
  ) async {
    final response = await _dio.get<List<dynamic>>(
      '/api/v1/admin/backups/storage-locations',
      options: _options(session),
    );
    return (response.data ?? const <dynamic>[])
        .map(
          (item) => HostStorageLocation.fromJson(item as Map<String, dynamic>),
        )
        .toList(growable: false);
  }

  Future<HostStorageLocation> registerStorageLocation({
    required AuthSession session,
    required String hostPath,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/admin/backups/storage-locations/register',
      data: <String, dynamic>{'host_path': hostPath},
      options: _options(session),
    );
    return HostStorageLocation.fromJson(response.data!);
  }

  Future<HostStorageBrowseResult> browseStorage({
    required AuthSession session,
    required HostStorageLocation location,
    required String relativePath,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/admin/backups/storage-locations/browse',
      data: <String, dynamic>{
        'location_token': location.token,
        'relative_path': relativePath,
      },
      options: _options(session),
    );
    return HostStorageBrowseResult.fromJson(response.data!);
  }

  Future<RetentionPreview> retentionPreview(
    AuthSession session,
    int scheduleId,
  ) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/admin/backups/schedules/$scheduleId/retention-preview',
      options: _options(session),
    );
    return RetentionPreview.fromJson(response.data!);
  }

  Future<void> deleteManagedBackup(AuthSession session, int managedBackupId) =>
      _dio.post<void>(
        '/api/v1/admin/backups/managed/$managedBackupId/delete',
        data: const <String, dynamic>{
          'confirmed': true,
          'confirmation': 'USUŃ BACKUP',
        },
        options: _options(session),
      );

  Future<BackupRun> runNow({
    required AuthSession session,
    required BackupScope scope,
    required String destination,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/admin/backups/run',
      data: <String, dynamic>{
        'scope': scope.wireName,
        'destination': destination,
        'confirmed': true,
      },
      options: _options(session),
    );
    return BackupRun.fromJson(response.data!);
  }

  Future<ManualBackupPreflight> preflightManual({
    required AuthSession session,
    required BackupScope scope,
    required String destination,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/admin/backups/manual-v2/preflight',
      data: <String, dynamic>{
        'scope': scope.wireName,
        'destination': destination,
      },
      options: _options(session),
    );
    return ManualBackupPreflight.fromJson(response.data!);
  }

  Future<BackupRun> startManualV2({
    required AuthSession session,
    required BackupScope scope,
    required ManualBackupPreflight preflight,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/admin/backups/manual-v2/run',
      data: <String, dynamic>{
        'scope': scope.wireName,
        'destination': preflight.destination,
        'preflight_token': preflight.token,
        'confirmed': true,
      },
      options: _options(session),
    );
    return BackupRun.fromJson(response.data!);
  }

  Future<ManualBackupPreflight> preflightManualV3({
    required AuthSession session,
    required BackupScope scope,
    required HostStorageLocation location,
    required String relativePath,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/admin/backups/manual-v3/preflight',
      data: <String, dynamic>{
        'scope': scope.wireName,
        'location_token': location.token,
        'relative_path': relativePath,
      },
      options: _options(session),
    );
    return ManualBackupPreflight.fromJson(response.data!);
  }

  Future<BackupRun> startManualV3({
    required AuthSession session,
    required BackupScope scope,
    required ManualBackupPreflight preflight,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/admin/backups/manual-v3/run',
      data: <String, dynamic>{
        'scope': scope.wireName,
        'preflight_token': preflight.token,
        'confirmed': true,
      },
      options: _options(session),
    );
    return BackupRun.fromJson(response.data!);
  }

  Future<List<BackupRun>> runs(AuthSession session) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/admin/backups/runs',
      queryParameters: const <String, dynamic>{'limit': 50},
      options: _options(session),
    );
    return ((response.data?['items'] as List<dynamic>?) ?? const <dynamic>[])
        .map((item) => BackupRun.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
  }

  Future<List<RestoreCandidate>> candidates(AuthSession session) async {
    final response = await _dio.get<List<dynamic>>(
      '/api/v1/admin/backups/restore-candidates',
      options: _options(
        session,
      ).copyWith(receiveTimeout: const Duration(seconds: 45)),
    );
    return (response.data ?? const <dynamic>[])
        .map((item) => RestoreCandidate.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
  }

  Future<RestorePreview> preview({
    required AuthSession session,
    required String checkpoint,
    required String mode,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/admin/backups/restore-preview',
      data: <String, dynamic>{'checkpoint_path': checkpoint, 'mode': mode},
      options: _options(session),
    );
    return RestorePreview.fromJson(response.data!);
  }

  Future<void> requestRestore({
    required AuthSession session,
    required String checkpoint,
    required String mode,
  }) => _dio.post<void>(
    '/api/v1/admin/backups/restore',
    data: <String, dynamic>{
      'checkpoint_path': checkpoint,
      'mode': mode,
      'acknowledged': true,
      'confirmation': 'PRZYWRÓĆ',
    },
    options: _options(session),
  );

  Future<List<RestoreRun>> restores(AuthSession session) async {
    final response = await _dio.get<List<dynamic>>(
      '/api/v1/admin/backups/restores',
      queryParameters: const <String, dynamic>{'limit': 50},
      options: _options(session),
    );
    return (response.data ?? const <dynamic>[])
        .map((item) => RestoreRun.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
  }
}
