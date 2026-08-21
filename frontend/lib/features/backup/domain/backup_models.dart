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
