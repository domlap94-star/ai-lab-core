import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/auth/domain/current_user.dart';
import 'package:ai_lab/features/backup/application/backup_providers.dart';
import 'package:ai_lab/features/backup/data/backup_api.dart';
import 'package:ai_lab/features/backup/domain/backup_models.dart';
import 'package:ai_lab/features/backup/presentation/admin_backup_restore_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const AuthSession _session = AuthSession(
  accessToken: 'backup-test',
  tokenType: 'bearer',
);

class _AdminAuthController extends AuthController {
  @override
  Future<AuthState> build() async => const AuthState(
    session: _session,
    user: CurrentUser(
      id: 1,
      username: 'admin',
      email: 'admin@example.invalid',
      role: 'Administrator',
      isActive: true,
      mustChangePassword: false,
      passwordResetRequested: false,
    ),
  );
}

class _UserAuthController extends AuthController {
  @override
  Future<AuthState> build() async => const AuthState(
    session: _session,
    user: CurrentUser(
      id: 2,
      username: 'user',
      email: 'user@example.invalid',
      role: 'User',
      isActive: true,
      mustChangePassword: false,
      passwordResetRequested: false,
    ),
  );
}

class _FakeBackupApi extends BackupApi {
  _FakeBackupApi() : super(Dio());
  int restoreRequests = 0;
  int adoptionRequests = 0;
  int manualBackups = 0;

  @override
  Future<ManagedBackup> adoptLegacyBackup({
    required AuthSession session,
    required String adoptionToken,
    int? planId,
  }) async {
    adoptionRequests += 1;
    return ManagedBackup(
      id: 99,
      backupId: 'legacy-fixture',
      destinationRoot: r'C:\backup-fixture',
      scope: 'database',
      appVersion: '1.0.2+25',
      totalBytes: 10,
      integrityStatus: 'verified',
      protected: false,
      lifecycle: 'available',
      createdAt: DateTime.utc(2026, 8, 20),
    );
  }

  @override
  Future<LegacyVerificationJob> startLegacyVerification({
    required AuthSession session,
    required String adoptionToken,
    int? planId,
  }) async {
    adoptionRequests += 1;
    return LegacyVerificationJob(
      jobToken: 'job-token',
      jobId: '00000000-0000-0000-0000-000000000001',
      state: 'SUCCEEDED',
      filesChecked: 1,
      filesTotal: 1,
      bytesChecked: 10,
      bytesTotal: 10,
    );
  }

  @override
  Future<HostStorageBrowseResult> browseStorage({
    required AuthSession session,
    required HostStorageLocation location,
    required String relativePath,
  }) async => HostStorageBrowseResult(
    locationId: location.id,
    relativePath: relativePath,
    displayPath: 'Lokalizacja hosta',
    directories: const <HostStorageDirectory>[],
  );

  @override
  Future<ManualBackupPreflight> preflightManualV3({
    required AuthSession session,
    required BackupScope scope,
    required HostStorageLocation location,
    required String relativePath,
  }) async => ManualBackupPreflight(
    destination: r'D:\NEXT-Backups',
    destinationDisplay: 'Dysk backupowy',
    storageLocationId: location.id,
    available: true,
    writable: true,
    totalBytes: 100000,
    freeBytes: 80000,
    token: 'preflight-token',
    expiresAt: DateTime.utc(2026, 8, 24, 12),
  );

  @override
  Future<BackupRun> startManualV3({
    required AuthSession session,
    required BackupScope scope,
    required ManualBackupPreflight preflight,
  }) async {
    manualBackups += 1;
    return BackupRun(
      id: 1,
      scope: scope,
      trigger: 'manual',
      status: 'running',
      stage: 'validating',
      destination: preflight.destination,
      startedAt: DateTime.utc(2026, 8, 24),
      verified: false,
      totalBytes: 0,
    );
  }

  @override
  Future<RestorePreview> preview({
    required AuthSession session,
    required String checkpoint,
    required String mode,
  }) async => RestorePreview(
    mode: mode,
    checkpointPath: checkpoint,
    createdAt: DateTime.utc(2026, 8, 21, 10),
    appVersion: '1.0.2+25',
    backupDbRevision: 'followup_admin_backup_restore_ui_20260821',
    currentDbRevision: 'followup_admin_backup_restore_ui_20260821',
    compatibility: 'compatible',
    eligible: true,
    replaces: mode == 'full'
        ? const <String>['database', 'documents', 'qdrant', 'n8n_config']
        : const <String>['database'],
  );

  @override
  Future<void> requestRestore({
    required AuthSession session,
    required String checkpoint,
    required String mode,
  }) async {
    restoreRequests += 1;
    final options = RequestOptions(path: '/api/v1/admin/backups/restore');
    throw DioException(
      requestOptions: options,
      response: Response<dynamic>(
        requestOptions: options,
        statusCode: 409,
        data: const <String, dynamic>{
          'detail': <String, String>{
            'code': 'production_restore_approval_required',
          },
        },
      ),
    );
  }
}

final RestoreCandidate _candidate = RestoreCandidate(
  checkpointPath: r'C:\ai-lab-core-backups\20260821T100000Z',
  createdAt: DateTime.utc(2026, 8, 21, 10),
  scope: BackupScope.full,
  appVersion: '1.0.2+25',
  dbRevision: 'followup_admin_backup_restore_ui_20260821',
  totalBytes: 1024 * 1024,
  verified: true,
  databaseEligible: true,
  fullEligible: true,
  compatibility: 'compatible',
);

final RestoreCandidate _qdrantBlockedCandidate = RestoreCandidate(
  checkpointPath: r'C:\ai-lab-core-backups\20260821T100000Z',
  createdAt: DateTime.utc(2026, 8, 21, 10),
  scope: BackupScope.full,
  appVersion: '1.0.2+25',
  dbRevision: 'followup_admin_backup_restore_ui_20260821',
  totalBytes: 1024 * 1024,
  verified: true,
  databaseEligible: true,
  fullEligible: false,
  compatibility: 'compatible',
  errorCode: 'qdrant_restore_verification_required',
);

Future<_FakeBackupApi> _pump(
  WidgetTester tester, {
  required double width,
  bool admin = true,
  List<BackupSchedule> schedules = const <BackupSchedule>[],
  List<LegacyBackupCandidate> legacy = const <LegacyBackupCandidate>[],
}) async {
  tester.view.physicalSize = Size(width, 1800);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final api = _FakeBackupApi();
  final container = ProviderContainer(
    overrides: [
      authControllerProvider.overrideWith(
        admin ? _AdminAuthController.new : _UserAuthController.new,
      ),
      backupApiProvider.overrideWithValue(api),
      backupSchedulesProvider.overrideWith((ref) async => schedules),
      backupRunsProvider.overrideWith((ref) async => const <BackupRun>[]),
      managedBackupsProvider.overrideWith(
        (ref) async => const <ManagedBackup>[],
      ),
      hostStorageLocationsProvider.overrideWith(
        (ref) async => <HostStorageLocation>[
          HostStorageLocation(
            id: 'LOC_TEST',
            label: 'Dysk backupowy',
            pathType: 'local_path',
            available: true,
            writable: true,
            totalBytes: 100000,
            freeBytes: 80000,
            token: 'location-token',
            expiresAt: DateTime.utc(2026, 8, 24, 12),
          ),
        ],
      ),
      legacyBackupCandidatesProvider.overrideWith((ref) async => legacy),
      restoreCandidatesProvider.overrideWith(
        (ref) async => <RestoreCandidate>[_candidate],
      ),
      restoreRunsProvider.overrideWith((ref) async => const <RestoreRun>[]),
    ],
  );
  addTearDown(container.dispose);
  await container.read(authControllerProvider.future);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(home: AdminBackupRestorePage()),
    ),
  );
  await tester.pumpAndSettle();
  return api;
}

Future<void> _pumpCandidate(
  WidgetTester tester,
  RestoreCandidate candidate,
) async {
  tester.view.physicalSize = const Size(600, 1800);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final api = _FakeBackupApi();
  final container = ProviderContainer(
    overrides: [
      authControllerProvider.overrideWith(_AdminAuthController.new),
      backupApiProvider.overrideWithValue(api),
      backupSchedulesProvider.overrideWith(
        (ref) async => const <BackupSchedule>[],
      ),
      backupRunsProvider.overrideWith((ref) async => const <BackupRun>[]),
      managedBackupsProvider.overrideWith(
        (ref) async => const <ManagedBackup>[],
      ),
      hostStorageLocationsProvider.overrideWith(
        (ref) async => const <HostStorageLocation>[],
      ),
      legacyBackupCandidatesProvider.overrideWith(
        (ref) async => const <LegacyBackupCandidate>[],
      ),
      restoreCandidatesProvider.overrideWith(
        (ref) async => <RestoreCandidate>[candidate],
      ),
      restoreRunsProvider.overrideWith((ref) async => const <RestoreRun>[]),
    ],
  );
  addTearDown(container.dispose);
  await container.read(authControllerProvider.future);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(home: AdminBackupRestorePage()),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  for (final width in <double>[360, 390, 600, 1200]) {
    testWidgets('backup workspace has no overflow at ${width.toInt()}', (
      tester,
    ) async {
      await _pump(tester, width: width);
      expect(find.byKey(const Key('backup-restore-page')), findsOneWidget);
      expect(find.text('Wykonaj backup teraz'), findsWidgets);
      expect(find.text('Dostępne checkpointy i przywracanie'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('restore requires acknowledgement and exact Polish token', (
    tester,
  ) async {
    final api = await _pump(tester, width: 600);
    await tester.ensureVisible(find.text('Przywróć bazę'));
    await tester.tap(find.text('Przywróć bazę'));
    await tester.pumpAndSettle();
    final buttonFinder = find.widgetWithText(
      FilledButton,
      'Przejdź do bezpiecznego przywracania',
    );
    expect(tester.widget<FilledButton>(buttonFinder).onPressed, isNull);
    await tester.tap(
      find.text('Rozumiem, że bieżące dane zostaną zastąpione.'),
    );
    await tester.enterText(
      find.widgetWithText(TextField, 'Wpisz PRZYWRÓĆ'),
      'WRONG',
    );
    await tester.pump();
    expect(tester.widget<FilledButton>(buttonFinder).onPressed, isNull);
    await tester.enterText(
      find.widgetWithText(TextField, 'Wpisz PRZYWRÓĆ'),
      'PRZYWRÓĆ',
    );
    await tester.pump();
    expect(tester.widget<FilledButton>(buttonFinder).onPressed, isNotNull);
    await tester.tap(buttonFinder);
    await tester.pumpAndSettle();
    expect(api.restoreRequests, 1);
    expect(
      find.text('Przywracanie produkcyjne wymaga osobnej zgody właściciela.'),
      findsOneWidget,
    );
  });

  testWidgets('normal user cannot access backup workspace', (tester) async {
    await _pump(tester, width: 390, admin: false);
    expect(find.text('Brak uprawnień administratora.'), findsOneWidget);
    expect(find.byKey(const Key('backup-restore-page')), findsNothing);
  });

  testWidgets('manual backup uses host selector on narrow clients', (
    tester,
  ) async {
    final api = await _pump(tester, width: 390);
    await tester.ensureVisible(find.byKey(const Key('run-backup-now')));
    await tester.tap(find.byKey(const Key('run-backup-now')));
    await tester.pumpAndSettle();
    expect(find.text('Wybierz lokalizację na hoście'), findsOneWidget);
    await tester.tap(find.byKey(const Key('confirm-host-storage')));
    await tester.pumpAndSettle();
    expect(find.text('Wykonać backup teraz?'), findsOneWidget);
    await tester.tap(find.widgetWithText(FilledButton, 'Wykonaj backup'));
    await tester.pumpAndSettle();
    expect(api.manualBackups, 1);
    expect(find.textContaining('dostępny na hoście Windows'), findsNothing);
  });

  testWidgets('Qdrant blocker disables only Full restore', (tester) async {
    await _pumpCandidate(tester, _qdrantBlockedCandidate);
    await tester.ensureVisible(find.text('Przywróć system'));
    expect(
      tester
          .widget<OutlinedButton>(
            find.widgetWithText(OutlinedButton, 'Przywróć bazę'),
          )
          .onPressed,
      isNotNull,
    );
    expect(
      tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Przywróć system'),
          )
          .onPressed,
      isNull,
    );
    expect(
      find.textContaining(
        'odtworzenie Qdrant nie zostało bezpiecznie zweryfikowane',
      ),
      findsOneWidget,
    );
  });

  testWidgets('scheduler shows truthful active state and next run', (
    tester,
  ) async {
    final next = DateTime(2026, 8, 22, 3);
    await _pump(
      tester,
      width: 390,
      schedules: <BackupSchedule>[
        BackupSchedule(
          id: 1,
          name: 'Daily Backup',
          enabled: true,
          scope: BackupScope.full,
          destination: r'C:\ai-lab-core-backups',
          cadence: 'daily',
          localTime: '03:00:00',
          nextRunAt: next,
          syncStatus: 'synced',
          hostTaskName: 'NEXT Stabil - Backup - 1',
          hostEnabled: true,
          hostNextRunAt: next,
          lastBackupAt: DateTime(2026, 8, 21, 3),
          lastBackupResult: 'completed',
        ),
      ],
    );
    expect(find.textContaining('Status: Aktywny'), findsOneWidget);
    expect(find.textContaining('Ostatni backup:'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'legacy candidate requires explicit verify-and-add confirmation',
    (tester) async {
      final api = await _pump(
        tester,
        width: 600,
        legacy: <LegacyBackupCandidate>[
          LegacyBackupCandidate(
            candidateId: 'fixture',
            checkpointPath: r'C:\backup-fixture\checkpoint',
            destinationRoot: r'C:\backup-fixture',
            totalBytes: 10,
            verified: false,
            integrityStatus: 'unverified',
            adoptable: true,
            alreadyManaged: false,
            adoptionToken: 'synthetic-adoption-token',
            createdAt: DateTime.utc(2026, 8, 20),
          ),
        ],
      );
      await tester.ensureVisible(find.text('Zweryfikuj i dodaj'));
      await tester.tap(find.text('Zweryfikuj i dodaj'));
      await tester.pumpAndSettle();
      expect(api.adoptionRequests, 0);
      await tester.tap(find.text('Dodaj zweryfikowany backup'));
      await tester.pumpAndSettle();
      expect(api.adoptionRequests, 1);
    },
  );
}
