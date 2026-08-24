enum BackupScope { full, database, documents, qdrant, n8nConfig }

extension BackupScopeLabel on BackupScope {
  String get label => switch (this) {
    BackupScope.full => 'Pełny checkpoint systemu',
    BackupScope.database => 'Baza danych',
    BackupScope.documents => 'Dokumenty',
    BackupScope.qdrant => 'Qdrant',
    BackupScope.n8nConfig => 'n8n i konfiguracja',
  };
  String get wireName => this == BackupScope.n8nConfig ? 'n8n_config' : name;
  static BackupScope parse(String value) => value == 'n8n_config'
      ? BackupScope.n8nConfig
      : BackupScope.values.byName(value);
}

class BackupSchedule {
  const BackupSchedule({
    required this.id,
    required this.name,
    required this.enabled,
    required this.scope,
    required this.destination,
    required this.cadence,
    required this.localTime,
    required this.nextRunAt,
    this.weekday,
    this.monthDay,
    this.syncStatus = 'pending_sync',
    this.hostTaskName,
    this.hostEnabled = false,
    this.hostNextRunAt,
    this.hostLastRunAt,
    this.hostLastResult,
    this.lastBackupAt,
    this.lastBackupResult,
    this.destinationType = 'local_path',
    this.destinationStatus = 'unknown',
    this.autoDelete = false,
    this.minimumFreePercent,
    this.minimumFreeBytes,
    this.minimumBackupsToKeep = 3,
    this.keepLastN,
    this.keepDays,
    this.retentionTrigger = 'after_successful_backup',
    this.planRevision = 1,
    this.lastReconciledRevision = 0,
    this.lastSyncErrorCode,
  });
  final int id;
  final String name;
  final bool enabled;
  final BackupScope scope;
  final String destination;
  final String cadence;
  final String localTime;
  final DateTime nextRunAt;
  final int? weekday;
  final int? monthDay;
  final String syncStatus;
  final String? hostTaskName;
  final bool hostEnabled;
  final DateTime? hostNextRunAt;
  final DateTime? hostLastRunAt;
  final int? hostLastResult;
  final DateTime? lastBackupAt;
  final String? lastBackupResult;
  final String destinationType;
  final String destinationStatus;
  final bool autoDelete;
  final int? minimumFreePercent;
  final int? minimumFreeBytes;
  final int minimumBackupsToKeep;
  final int? keepLastN;
  final int? keepDays;
  final String retentionTrigger;
  final int planRevision;
  final int lastReconciledRevision;
  final String? lastSyncErrorCode;
  factory BackupSchedule.fromJson(Map<String, dynamic> json) => BackupSchedule(
    id: json['id'] as int,
    name: json['name'] as String,
    enabled: json['enabled'] as bool,
    scope: BackupScopeLabel.parse(json['scope'] as String),
    destination: json['destination'] as String,
    cadence: json['cadence'] as String,
    localTime: json['local_time'] as String,
    nextRunAt: DateTime.parse(json['next_run_at'] as String).toLocal(),
    weekday: json['weekday'] as int?,
    monthDay: json['month_day'] as int?,
    syncStatus: json['sync_status'] as String? ?? 'pending_sync',
    hostTaskName: json['host_task_name'] as String?,
    hostEnabled: json['host_enabled'] as bool? ?? false,
    hostNextRunAt: DateTime.tryParse(
      json['host_next_run_at']?.toString() ?? '',
    )?.toLocal(),
    hostLastRunAt: DateTime.tryParse(
      json['host_last_run_at']?.toString() ?? '',
    )?.toLocal(),
    hostLastResult: json['host_last_result'] as int?,
    lastBackupAt: DateTime.tryParse(
      json['last_backup_at']?.toString() ?? '',
    )?.toLocal(),
    lastBackupResult: json['last_backup_result'] as String?,
    destinationType: json['destination_type'] as String? ?? 'local_path',
    destinationStatus: json['destination_status'] as String? ?? 'unknown',
    autoDelete: json['auto_delete'] as bool? ?? false,
    minimumFreePercent: json['minimum_free_percent'] as int?,
    minimumFreeBytes: json['minimum_free_bytes'] as int?,
    minimumBackupsToKeep: json['minimum_backups_to_keep'] as int? ?? 3,
    keepLastN: json['keep_last_n'] as int?,
    keepDays: json['keep_days'] as int?,
    retentionTrigger:
        json['retention_trigger'] as String? ?? 'after_successful_backup',
    planRevision: json['plan_revision'] as int? ?? 1,
    lastReconciledRevision: json['last_reconciled_revision'] as int? ?? 0,
    lastSyncErrorCode: json['last_sync_error_code'] as String?,
  );
}

class ManualBackupPreflight {
  const ManualBackupPreflight({
    required this.destination,
    required this.available,
    required this.writable,
    required this.totalBytes,
    required this.freeBytes,
    required this.token,
    required this.expiresAt,
    this.estimatedRequiredBytes,
    this.storageLocationId,
    this.destinationDisplay,
    this.predictedFreeBytes,
    this.reserveRequiredBytes = 0,
    this.retentionImpact = 'not_applicable',
  });
  final String destination;
  final bool available;
  final bool writable;
  final int totalBytes;
  final int freeBytes;
  final int? estimatedRequiredBytes;
  final String? storageLocationId;
  final String? destinationDisplay;
  final int? predictedFreeBytes;
  final int reserveRequiredBytes;
  final String retentionImpact;
  final String token;
  final DateTime expiresAt;
  factory ManualBackupPreflight.fromJson(Map<String, dynamic> json) =>
      ManualBackupPreflight(
        destination: json['normalized_destination'] as String,
        available: json['available'] as bool,
        writable: json['writable'] as bool,
        totalBytes: json['total_bytes'] as int? ?? 0,
        freeBytes: json['free_bytes'] as int? ?? 0,
        estimatedRequiredBytes: json['estimated_required_bytes'] as int?,
        storageLocationId: json['storage_location_id'] as String?,
        destinationDisplay: json['destination_display'] as String?,
        predictedFreeBytes: json['predicted_free_bytes'] as int?,
        reserveRequiredBytes: json['reserve_required_bytes'] as int? ?? 0,
        retentionImpact:
            json['retention_impact'] as String? ?? 'not_applicable',
        token: json['token'] as String,
        expiresAt: DateTime.parse(json['expires_at'] as String),
      );
}

class ManagedBackup {
  const ManagedBackup({
    required this.id,
    required this.backupId,
    required this.destinationRoot,
    required this.scope,
    required this.appVersion,
    required this.totalBytes,
    required this.integrityStatus,
    required this.protected,
    required this.lifecycle,
    required this.createdAt,
    this.planId,
  });
  final int id;
  final String backupId;
  final int? planId;
  final String destinationRoot;
  final String scope;
  final String appVersion;
  final int totalBytes;
  final String integrityStatus;
  final bool protected;
  final String lifecycle;
  final DateTime createdAt;

  factory ManagedBackup.fromJson(Map<String, dynamic> json) => ManagedBackup(
    id: json['id'] as int,
    backupId: json['backup_id'] as String,
    planId: json['plan_id'] as int?,
    destinationRoot: json['destination_root'] as String,
    scope: json['scope'] as String,
    appVersion: json['app_version'] as String,
    totalBytes: json['total_bytes'] as int? ?? 0,
    integrityStatus: json['integrity_status'] as String,
    protected: json['protected'] as bool? ?? false,
    lifecycle: json['lifecycle'] as String,
    createdAt: DateTime.parse(json['created_at'] as String).toLocal(),
  );
}

class LegacyBackupCandidate {
  const LegacyBackupCandidate({
    required this.candidateId,
    required this.checkpointPath,
    required this.destinationRoot,
    required this.totalBytes,
    required this.verified,
    required this.integrityStatus,
    required this.adoptable,
    required this.alreadyManaged,
    this.createdAt,
    this.scope,
    this.appVersion,
    this.manifestSchema,
    this.reason,
    this.adoptionToken,
    this.classification = 'NEEDS_VERIFICATION',
    this.retryable = false,
    this.diagnosticCode,
  });
  final String candidateId;
  final String checkpointPath;
  final String destinationRoot;
  final DateTime? createdAt;
  final String? scope;
  final String? appVersion;
  final int totalBytes;
  final String? manifestSchema;
  final bool verified;
  final String integrityStatus;
  final bool adoptable;
  final bool alreadyManaged;
  final String? reason;
  final String? adoptionToken;
  final String classification;
  final bool retryable;
  final String? diagnosticCode;

  factory LegacyBackupCandidate.fromJson(Map<String, dynamic> json) =>
      LegacyBackupCandidate(
        candidateId: json['candidate_id'] as String,
        checkpointPath: json['checkpoint_path'] as String,
        destinationRoot: json['destination_root'] as String,
        createdAt: DateTime.tryParse(
          json['created_at']?.toString() ?? '',
        )?.toLocal(),
        scope: json['scope'] as String?,
        appVersion: json['app_version'] as String?,
        totalBytes: json['total_bytes'] as int? ?? 0,
        manifestSchema: json['manifest_schema'] as String?,
        verified: json['verified'] as bool? ?? false,
        integrityStatus: json['integrity_status'] as String,
        adoptable: json['adoptable'] as bool? ?? false,
        alreadyManaged: json['already_managed'] as bool? ?? false,
        reason: json['reason'] as String?,
        adoptionToken: json['adoption_token'] as String?,
        classification:
            json['classification'] as String? ?? 'NEEDS_VERIFICATION',
        retryable: json['retryable'] as bool? ?? false,
        diagnosticCode: json['diagnostic_code'] as String?,
      );
}

class HostStorageLocation {
  const HostStorageLocation({
    required this.id,
    required this.label,
    required this.pathType,
    required this.available,
    required this.writable,
    required this.totalBytes,
    required this.freeBytes,
    required this.token,
    required this.expiresAt,
  });
  final String id;
  final String label;
  final String pathType;
  final bool available;
  final bool writable;
  final int totalBytes;
  final int freeBytes;
  final String token;
  final DateTime expiresAt;
  factory HostStorageLocation.fromJson(Map<String, dynamic> json) =>
      HostStorageLocation(
        id: json['location_id'] as String,
        label: json['display_label'] as String,
        pathType: json['path_type'] as String,
        available: json['available'] as bool? ?? false,
        writable: json['writable'] as bool? ?? false,
        totalBytes: json['total_bytes'] as int? ?? 0,
        freeBytes: json['free_bytes'] as int? ?? 0,
        token: json['location_token'] as String,
        expiresAt: DateTime.parse(json['expires_at'] as String),
      );
}

class HostStorageDirectory {
  const HostStorageDirectory({required this.name, required this.relativePath});
  final String name;
  final String relativePath;
  factory HostStorageDirectory.fromJson(Map<String, dynamic> json) =>
      HostStorageDirectory(
        name: json['name'] as String,
        relativePath: json['relative_path'] as String,
      );
}

class HostStorageBrowseResult {
  const HostStorageBrowseResult({
    required this.locationId,
    required this.relativePath,
    required this.displayPath,
    required this.directories,
  });
  final String locationId;
  final String relativePath;
  final String displayPath;
  final List<HostStorageDirectory> directories;
  factory HostStorageBrowseResult.fromJson(Map<String, dynamic> json) =>
      HostStorageBrowseResult(
        locationId: json['location_id'] as String,
        relativePath: json['relative_path'] as String? ?? '',
        displayPath: json['display_path'] as String,
        directories: (json['directories'] as List<dynamic>? ?? const [])
            .map(
              (item) =>
                  HostStorageDirectory.fromJson(item as Map<String, dynamic>),
            )
            .toList(growable: false),
      );
}

class LegacyVerificationJob {
  const LegacyVerificationJob({
    required this.jobToken,
    required this.jobId,
    required this.state,
    required this.filesChecked,
    required this.bytesChecked,
    this.filesTotal,
    this.bytesTotal,
    this.errorCode,
    this.retryable = false,
    this.managedBackup,
  });
  final String jobToken;
  final String jobId;
  final String state;
  final int filesChecked;
  final int? filesTotal;
  final int bytesChecked;
  final int? bytesTotal;
  final String? errorCode;
  final bool retryable;
  final ManagedBackup? managedBackup;
  bool get terminal =>
      const {'SUCCEEDED', 'FAILED', 'CANCELLED'}.contains(state);
  factory LegacyVerificationJob.fromJson(Map<String, dynamic> json) =>
      LegacyVerificationJob(
        jobToken: json['job_token'] as String,
        jobId: json['job_id'] as String,
        state: json['state'] as String,
        filesChecked: json['files_checked'] as int? ?? 0,
        filesTotal: json['files_total'] as int?,
        bytesChecked: json['bytes_checked'] as int? ?? 0,
        bytesTotal: json['bytes_total'] as int?,
        errorCode: json['error_code'] as String?,
        retryable: json['retryable'] as bool? ?? false,
        managedBackup: json['managed_backup'] == null
            ? null
            : ManagedBackup.fromJson(
                json['managed_backup'] as Map<String, dynamic>,
              ),
      );
}

class RetentionPreview {
  const RetentionPreview({
    required this.currentFreeBytes,
    required this.requiredFreeBytes,
    required this.proposedDeletionCount,
    required this.predictedReclaimedBytes,
    this.blockedReason,
  });
  final int currentFreeBytes;
  final int requiredFreeBytes;
  final int proposedDeletionCount;
  final int predictedReclaimedBytes;
  final String? blockedReason;

  factory RetentionPreview.fromJson(Map<String, dynamic> json) =>
      RetentionPreview(
        currentFreeBytes: json['current_free_bytes'] as int? ?? 0,
        requiredFreeBytes: json['required_free_bytes'] as int? ?? 0,
        proposedDeletionCount:
            (json['proposed_deletions'] as List<dynamic>? ?? const []).length,
        predictedReclaimedBytes: json['predicted_reclaimed_bytes'] as int? ?? 0,
        blockedReason: json['blocked_reason'] as String?,
      );
}

class BackupRun {
  const BackupRun({
    required this.id,
    required this.scope,
    required this.trigger,
    required this.status,
    required this.stage,
    required this.destination,
    required this.startedAt,
    required this.verified,
    required this.totalBytes,
    this.checkpointPath,
    this.errorCode,
  });
  final int id;
  final BackupScope scope;
  final String trigger;
  final String status;
  final String stage;
  final String destination;
  final DateTime startedAt;
  final bool verified;
  final int totalBytes;
  final String? checkpointPath;
  final String? errorCode;
  factory BackupRun.fromJson(Map<String, dynamic> json) => BackupRun(
    id: json['id'] as int,
    scope: BackupScopeLabel.parse(json['scope'] as String),
    trigger: json['trigger'] as String,
    status: json['status'] as String,
    stage: json['stage'] as String,
    destination: json['destination'] as String,
    startedAt: DateTime.parse(json['started_at'] as String).toLocal(),
    verified: json['verified'] as bool? ?? false,
    totalBytes: json['total_bytes'] as int? ?? 0,
    checkpointPath: json['checkpoint_path'] as String?,
    errorCode: json['error_code'] as String?,
  );
}

class RestoreCandidate {
  const RestoreCandidate({
    required this.checkpointPath,
    required this.createdAt,
    required this.scope,
    required this.appVersion,
    required this.dbRevision,
    required this.totalBytes,
    required this.verified,
    required this.databaseEligible,
    required this.fullEligible,
    required this.compatibility,
    this.errorCode,
  });
  final String checkpointPath;
  final DateTime createdAt;
  final BackupScope scope;
  final String appVersion;
  final String dbRevision;
  final int totalBytes;
  final bool verified;
  final bool databaseEligible;
  final bool fullEligible;
  final String compatibility;
  final String? errorCode;
  factory RestoreCandidate.fromJson(Map<String, dynamic> json) =>
      RestoreCandidate(
        checkpointPath: json['checkpoint_path'] as String,
        createdAt: DateTime.parse(json['created_at'] as String).toLocal(),
        scope: BackupScopeLabel.parse(json['scope'] as String),
        appVersion: json['app_version'] as String,
        dbRevision: json['db_revision'] as String,
        totalBytes: json['total_bytes'] as int? ?? 0,
        verified: json['verified'] as bool? ?? false,
        databaseEligible: json['database_eligible'] as bool? ?? false,
        fullEligible: json['full_eligible'] as bool? ?? false,
        compatibility: json['compatibility'] as String,
        errorCode: json['error_code'] as String?,
      );
}

class RestorePreview {
  const RestorePreview({
    required this.mode,
    required this.checkpointPath,
    required this.createdAt,
    required this.appVersion,
    required this.backupDbRevision,
    required this.currentDbRevision,
    required this.compatibility,
    required this.eligible,
    required this.replaces,
  });
  final String mode;
  final String checkpointPath;
  final DateTime createdAt;
  final String appVersion;
  final String backupDbRevision;
  final String currentDbRevision;
  final String compatibility;
  final bool eligible;
  final List<String> replaces;
  factory RestorePreview.fromJson(Map<String, dynamic> json) => RestorePreview(
    mode: json['mode'] as String,
    checkpointPath: json['checkpoint_path'] as String,
    createdAt: DateTime.parse(json['created_at'] as String).toLocal(),
    appVersion: json['app_version'] as String,
    backupDbRevision: json['backup_db_revision'] as String,
    currentDbRevision: json['current_db_revision'] as String,
    compatibility: json['compatibility'] as String,
    eligible: json['eligible'] as bool,
    replaces: (json['replaces'] as List<dynamic>).cast<String>(),
  );
}

class RestoreRun {
  const RestoreRun({
    required this.id,
    required this.mode,
    required this.status,
    required this.stage,
    required this.checkpointPath,
    required this.startedAt,
    this.preRestoreBackupRunId,
    this.errorCode,
  });
  final int id;
  final String mode;
  final String status;
  final String stage;
  final String checkpointPath;
  final DateTime startedAt;
  final int? preRestoreBackupRunId;
  final String? errorCode;
  factory RestoreRun.fromJson(Map<String, dynamic> json) => RestoreRun(
    id: json['id'] as int,
    mode: json['mode'] as String,
    status: json['status'] as String,
    stage: json['stage'] as String,
    checkpointPath: json['checkpoint_path'] as String,
    startedAt: DateTime.parse(json['started_at'] as String).toLocal(),
    preRestoreBackupRunId: json['pre_restore_backup_run_id'] as int?,
    errorCode: json['error_code'] as String?,
  );
}
