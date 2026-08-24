import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/application/auth_state.dart';
import '../../auth/domain/auth_session.dart';
import '../data/backup_api.dart';
import '../domain/backup_models.dart';

final backupApiProvider = Provider<BackupApi>(
  (ref) => BackupApi(ref.watch(dioProvider)),
);

AuthSession requireBackupSession(Ref ref) {
  return requireBackupSessionFromAuth(ref.read(authControllerProvider));
}

AuthSession requireBackupSessionFromAuth(AsyncValue<AuthState> auth) {
  final session = auth.value?.session;
  if (session == null || !session.isAuthenticated) {
    throw StateError('Brak aktywnej sesji.');
  }
  return session;
}

final backupSchedulesProvider =
    FutureProvider.autoDispose<List<BackupSchedule>>(
      (ref) =>
          ref.watch(backupApiProvider).schedules(requireBackupSession(ref)),
    );
final backupRunsProvider = FutureProvider.autoDispose<List<BackupRun>>(
  (ref) => ref.watch(backupApiProvider).runs(requireBackupSession(ref)),
);
final managedBackupsProvider = FutureProvider.autoDispose<List<ManagedBackup>>(
  (ref) =>
      ref.watch(backupApiProvider).managedBackups(requireBackupSession(ref)),
);
final hostStorageLocationsProvider =
    FutureProvider.autoDispose<List<HostStorageLocation>>(
      (ref) => ref
          .watch(backupApiProvider)
          .storageLocations(requireBackupSession(ref)),
    );
final legacyBackupCandidatesProvider =
    FutureProvider.autoDispose<List<LegacyBackupCandidate>>(
      (ref) => ref
          .watch(backupApiProvider)
          .legacyCandidates(requireBackupSession(ref)),
    );
final restoreCandidatesProvider =
    FutureProvider.autoDispose<List<RestoreCandidate>>(
      (ref) =>
          ref.watch(backupApiProvider).candidates(requireBackupSession(ref)),
    );
final restoreRunsProvider = FutureProvider.autoDispose<List<RestoreRun>>(
  (ref) => ref.watch(backupApiProvider).restores(requireBackupSession(ref)),
);
