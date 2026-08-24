import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/formatters/polish_date_time.dart';
import '../../auth/application/auth_controller.dart';
import '../application/backup_providers.dart';
import '../domain/backup_models.dart';

class AdminBackupRestorePage extends ConsumerWidget {
  const AdminBackupRestorePage({super.key});

  bool _isAdmin(String? role) {
    final value = role?.trim().toLowerCase();
    return value == 'admin' || value == 'administrator';
  }

  void _refresh(WidgetRef ref) {
    ref.invalidate(backupSchedulesProvider);
    ref.invalidate(backupRunsProvider);
    ref.invalidate(managedBackupsProvider);
    ref.invalidate(legacyBackupCandidatesProvider);
    ref.invalidate(restoreCandidatesProvider);
    ref.invalidate(restoreRunsProvider);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!_isAdmin(ref.watch(authControllerProvider).value?.user?.role)) {
      return const Scaffold(
        body: Center(child: Text('Brak uprawnień administratora.')),
      );
    }
    return Scaffold(
      appBar: AppBar(title: const Text('Backup i przywracanie')),
      body: RefreshIndicator(
        onRefresh: () async {
          _refresh(ref);
          await Future.wait(<Future<Object?>>[
            ref.read(backupSchedulesProvider.future),
            ref.read(backupRunsProvider.future),
            ref.read(managedBackupsProvider.future),
            ref.read(legacyBackupCandidatesProvider.future),
            ref.read(restoreCandidatesProvider.future),
            ref.read(restoreRunsProvider.future),
          ]);
        },
        child: LayoutBuilder(
          builder: (context, constraints) => ListView(
            key: const Key('backup-restore-page'),
            physics: const AlwaysScrollableScrollPhysics(),
            padding: EdgeInsets.all(constraints.maxWidth < 600 ? 12 : 24),
            children: <Widget>[
              _StatusSection(onRefresh: () => _refresh(ref)),
              const SizedBox(height: 16),
              const _ManualBackupSection(),
              const SizedBox(height: 16),
              const _SchedulesSection(),
              const SizedBox(height: 16),
              const _ManagedBackupsSection(),
              const SizedBox(height: 16),
              const _LegacyBackupsSection(),
              const SizedBox(height: 16),
              const _CheckpointsSection(),
              const SizedBox(height: 16),
              const _RunHistorySection(),
              const SizedBox(height: 16),
              const _RestoreHistorySection(),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusSection extends ConsumerWidget {
  const _StatusSection({required this.onRefresh});
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final runs = ref.watch(backupRunsProvider).value ?? const <BackupRun>[];
    final running = runs
        .where((item) => item.status == 'running' || item.status == 'queued')
        .firstOrNull;
    return _Section(
      title: 'Stan backupów',
      trailing: IconButton(
        tooltip: 'Odśwież',
        onPressed: onRefresh,
        icon: const Icon(Icons.refresh),
      ),
      child: running == null
          ? const ListTile(
              leading: Icon(Icons.check_circle_outline),
              title: Text('Brak trwającej operacji.'),
            )
          : ListTile(
              leading: const SizedBox.square(
                dimension: 24,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
              title: Text('Backup: ${running.scope.label}'),
              subtitle: Text('Etap: ${_stageLabel(running.stage)}'),
            ),
    );
  }
}

class _ManualBackupSection extends ConsumerStatefulWidget {
  const _ManualBackupSection();
  @override
  ConsumerState<_ManualBackupSection> createState() =>
      _ManualBackupSectionState();
}

class _ManualBackupSectionState extends ConsumerState<_ManualBackupSection> {
  BackupScope _scope = BackupScope.full;
  bool _busy = false;

  Future<void> _run() async {
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.windows) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Manualny backup z wyborem lokalizacji jest dostępny na hoście Windows.',
          ),
        ),
      );
      return;
    }
    final selected = await FilePicker.getDirectoryPath(
      dialogTitle: 'Wybierz lokalizację backupu',
    );
    if (selected == null || !mounted) return;
    final session = requireBackupSessionFromAuth(
      ref.read(authControllerProvider),
    );
    late final ManualBackupPreflight preflight;
    try {
      preflight = await ref
          .read(backupApiProvider)
          .preflightManual(
            session: session,
            scope: _scope,
            destination: selected,
          );
    } on DioException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              _apiError(error, 'Wybrana lokalizacja nie przeszła kontroli.'),
            ),
          ),
        );
      }
      return;
    }
    if (!mounted) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Wykonać backup teraz?'),
        content: Text(
          'Zakres: ${_scope.label}\nCel: ${preflight.destination}\nWolne miejsce: ${_bytes(preflight.freeBytes)}',
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Anuluj'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Wykonaj backup'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() => _busy = true);
    try {
      await ref
          .read(backupApiProvider)
          .startManualV2(session: session, scope: _scope, preflight: preflight);
      ref.invalidate(backupRunsProvider);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Backup został bezpiecznie uruchomiony.'),
          ),
        );
      }
    } on DioException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(_apiError(error, 'Nie udało się uruchomić backupu.')),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => _Section(
    title: 'Wykonaj backup teraz',
    child: Wrap(
      spacing: 12,
      runSpacing: 12,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: <Widget>[
        ConstrainedBox(
          constraints: const BoxConstraints(minWidth: 240, maxWidth: 420),
          child: DropdownButtonFormField<BackupScope>(
            key: const Key('manual-backup-scope'),
            isExpanded: true,
            initialValue: _scope,
            decoration: const InputDecoration(labelText: 'Zakres'),
            items: BackupScope.values
                .map(
                  (scope) => DropdownMenuItem(
                    value: scope,
                    child: Text(scope.label, overflow: TextOverflow.ellipsis),
                  ),
                )
                .toList(),
            onChanged: _busy
                ? null
                : (value) => setState(() => _scope = value ?? _scope),
          ),
        ),
        FilledButton.icon(
          key: const Key('run-backup-now'),
          onPressed: _busy ? null : _run,
          icon: _busy
              ? const SizedBox.square(
                  dimension: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.backup_outlined),
          label: const Text('Wykonaj backup teraz'),
        ),
      ],
    ),
  );
}

class _SchedulesSection extends ConsumerWidget {
  const _SchedulesSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final schedules = ref.watch(backupSchedulesProvider);
    return _Section(
      title: 'Harmonogramy',
      trailing: IconButton(
        key: const Key('add-backup-schedule'),
        tooltip: 'Dodaj harmonogram',
        onPressed: () => _edit(context, ref),
        icon: const Icon(Icons.add),
      ),
      child: schedules.when(
        loading: () => const LinearProgressIndicator(),
        error: (_, _) => const Text('Nie udało się pobrać harmonogramów.'),
        data: (items) => items.isEmpty
            ? const Text('Brak skonfigurowanych harmonogramów.')
            : Column(
                children: items
                    .map(
                      (item) => ListTile(
                        title: Text(item.name),
                        subtitle: Text(
                          [
                            '${item.scope.label} • ${_cadenceLabel(item.cadence)} ${item.localTime.substring(0, 5)}',
                            'Status: ${_syncLabel(item)}',
                            'Następne uruchomienie: ${_date(item.hostNextRunAt ?? item.nextRunAt)}',
                            if (item.lastBackupAt != null)
                              'Ostatni backup: ${_date(item.lastBackupAt!)} • ${_backupResultLabel(item.lastBackupResult)}',
                          ].join('\n'),
                        ),
                        leading: Icon(
                          item.hostEnabled && item.syncStatus == 'synced'
                              ? Icons.schedule
                              : item.syncStatus == 'error' ||
                                    item.syncStatus == 'destination_unavailable'
                              ? Icons.error_outline
                              : Icons.schedule_outlined,
                        ),
                        trailing: Wrap(
                          spacing: 4,
                          children: <Widget>[
                            IconButton(
                              tooltip: 'Podgląd retencji',
                              onPressed: () =>
                                  _previewRetention(context, ref, item),
                              icon: const Icon(
                                Icons.cleaning_services_outlined,
                              ),
                            ),
                            if (item.syncStatus == 'error' ||
                                item.syncStatus == 'pending')
                              IconButton(
                                tooltip: 'Ponów synchronizację',
                                onPressed: () => _reconcile(ref),
                                icon: const Icon(Icons.sync),
                              ),
                            IconButton(
                              tooltip: 'Edytuj',
                              onPressed: () => _edit(context, ref, item: item),
                              icon: const Icon(Icons.edit_outlined),
                            ),
                            IconButton(
                              tooltip: 'Usuń konfigurację',
                              onPressed: () => _delete(context, ref, item),
                              icon: const Icon(Icons.delete_outline),
                            ),
                          ],
                        ),
                      ),
                    )
                    .toList(),
              ),
      ),
    );
  }

  Future<void> _delete(
    BuildContext context,
    WidgetRef ref,
    BackupSchedule item,
  ) async {
    await ref
        .read(backupApiProvider)
        .deleteSchedule(
          requireBackupSessionFromAuth(ref.read(authControllerProvider)),
          item.id,
        );
    await ref
        .read(backupApiProvider)
        .reconcileSchedules(
          requireBackupSessionFromAuth(ref.read(authControllerProvider)),
        );
    ref.invalidate(backupSchedulesProvider);
  }

  Future<void> _reconcile(WidgetRef ref) async {
    await ref
        .read(backupApiProvider)
        .reconcileSchedules(
          requireBackupSessionFromAuth(ref.read(authControllerProvider)),
        );
    ref.invalidate(backupSchedulesProvider);
  }

  Future<void> _previewRetention(
    BuildContext context,
    WidgetRef ref,
    BackupSchedule item,
  ) async {
    try {
      final preview = await ref
          .read(backupApiProvider)
          .retentionPreview(
            requireBackupSessionFromAuth(ref.read(authControllerProvider)),
            item.id,
          );
      if (!context.mounted) return;
      await showDialog<void>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Podgląd retencji — bez usuwania'),
          content: Text(
            'Wolne: ${_bytes(preview.currentFreeBytes)}\n'
            'Wymagana rezerwa: ${_bytes(preview.requiredFreeBytes)}\n'
            'Proponowane usunięcia: ${preview.proposedDeletionCount}\n'
            'Możliwe odzyskanie: ${_bytes(preview.predictedReclaimedBytes)}\n'
            'Stan: ${preview.blockedReason ?? 'OK'}',
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Zamknij'),
            ),
          ],
        ),
      );
    } on DioException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(_apiError(error, 'Nie udało się obliczyć retencji.')),
          ),
        );
      }
    }
  }

  Future<void> _edit(
    BuildContext context,
    WidgetRef ref, {
    BackupSchedule? item,
  }) async {
    final name = TextEditingController(text: item?.name ?? 'Backup dzienny');
    final destination = TextEditingController(text: item?.destination ?? '');
    String destinationType = item?.destinationType ?? 'local_path';
    bool autoDelete = item?.autoDelete ?? false;
    final minimumFreePercent = TextEditingController(
      text: item?.minimumFreePercent?.toString() ?? '10',
    );
    final minimumFreeBytes = TextEditingController(
      text: item?.minimumFreeBytes?.toString() ?? '',
    );
    final minimumKeep = TextEditingController(
      text: item?.minimumBackupsToKeep.toString() ?? '3',
    );
    BackupScope scope = item?.scope ?? BackupScope.full;
    String cadence = item?.cadence ?? 'daily';
    bool enabled = item?.enabled ?? false;
    int weekday = item?.weekday ?? 1;
    int monthDay = item?.monthDay ?? 1;
    final parts = (item?.localTime ?? '03:00:00').split(':');
    TimeOfDay localTime = TimeOfDay(
      hour: int.tryParse(parts.first) ?? 3,
      minute: int.tryParse(parts.length > 1 ? parts[1] : '') ?? 0,
    );
    final saved = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(
            item == null ? 'Dodaj harmonogram' : 'Edytuj harmonogram',
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                TextField(
                  controller: name,
                  decoration: const InputDecoration(labelText: 'Nazwa'),
                ),
                DropdownButtonFormField<String>(
                  initialValue: destinationType,
                  decoration: const InputDecoration(
                    labelText: 'Typ miejsca docelowego',
                  ),
                  items: const <DropdownMenuItem<String>>[
                    DropdownMenuItem(
                      value: 'local_path',
                      child: Text('Dysk lokalny'),
                    ),
                    DropdownMenuItem(
                      value: 'removable_or_mounted_path',
                      child: Text('Dysk wymienny / zamontowany'),
                    ),
                    DropdownMenuItem(
                      value: 'network_path',
                      child: Text('Ścieżka sieciowa / NAS'),
                    ),
                  ],
                  onChanged: (value) => setDialogState(
                    () => destinationType = value ?? destinationType,
                  ),
                ),
                TextField(
                  controller: destination,
                  decoration: const InputDecoration(labelText: 'Cel backupu'),
                ),
                DropdownButtonFormField<BackupScope>(
                  isExpanded: true,
                  initialValue: scope,
                  decoration: const InputDecoration(labelText: 'Zakres'),
                  items: BackupScope.values
                      .map(
                        (value) => DropdownMenuItem(
                          value: value,
                          child: Text(
                            value.label,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      )
                      .toList(),
                  onChanged: (value) =>
                      setDialogState(() => scope = value ?? scope),
                ),
                DropdownButtonFormField<String>(
                  isExpanded: true,
                  initialValue: cadence,
                  decoration: const InputDecoration(labelText: 'Częstotliwość'),
                  items: const <DropdownMenuItem<String>>[
                    DropdownMenuItem(value: 'daily', child: Text('Codziennie')),
                    DropdownMenuItem(
                      value: 'weekly',
                      child: Text('Co tydzień'),
                    ),
                    DropdownMenuItem(
                      value: 'monthly',
                      child: Text('Co miesiąc'),
                    ),
                  ],
                  onChanged: (value) =>
                      setDialogState(() => cadence = value ?? cadence),
                ),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Godzina lokalna'),
                  subtitle: Text(localTime.format(context)),
                  trailing: const Icon(Icons.schedule),
                  onTap: () async {
                    final selected = await showTimePicker(
                      context: context,
                      initialTime: localTime,
                    );
                    if (selected != null) {
                      setDialogState(() => localTime = selected);
                    }
                  },
                ),
                if (cadence == 'weekly')
                  DropdownButtonFormField<int>(
                    initialValue: weekday,
                    decoration: const InputDecoration(
                      labelText: 'Dzień tygodnia',
                    ),
                    items: List.generate(
                      7,
                      (index) => DropdownMenuItem(
                        value: index + 1,
                        child: Text('${index + 1}'),
                      ),
                    ),
                    onChanged: (value) => weekday = value ?? weekday,
                  ),
                if (cadence == 'monthly')
                  DropdownButtonFormField<int>(
                    initialValue: monthDay.clamp(1, 28),
                    decoration: const InputDecoration(
                      labelText: 'Dzień miesiąca (1–28)',
                    ),
                    items: List.generate(
                      28,
                      (index) => DropdownMenuItem(
                        value: index + 1,
                        child: Text('${index + 1}'),
                      ),
                    ),
                    onChanged: (value) => monthDay = value ?? monthDay,
                  ),
                SwitchListTile(
                  value: enabled,
                  onChanged: (value) => setDialogState(() => enabled = value),
                  title: const Text('Włącz harmonogram systemowy'),
                ),
                SwitchListTile(
                  value: autoDelete,
                  onChanged: (value) =>
                      setDialogState(() => autoDelete = value),
                  title: const Text('Automatyczne bezpieczne usuwanie'),
                  subtitle: const Text(
                    'Najstarsze kwalifikujące się backupy będą automatycznie usuwane zgodnie z zasadami tego planu.',
                  ),
                ),
                TextField(
                  controller: minimumFreePercent,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Minimalne wolne miejsce (%)',
                  ),
                ),
                TextField(
                  controller: minimumFreeBytes,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Minimalne wolne miejsce (bajty, opcjonalnie)',
                  ),
                ),
                TextField(
                  controller: minimumKeep,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Minimalna liczba backupów do zachowania',
                  ),
                ),
              ],
            ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Anuluj'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Zapisz'),
            ),
          ],
        ),
      ),
    );
    if (saved != true) return;
    try {
      await ref
          .read(backupApiProvider)
          .saveSchedule(
            session: requireBackupSessionFromAuth(
              ref.read(authControllerProvider),
            ),
            id: item?.id,
            payload: <String, dynamic>{
              'name': name.text.trim(),
              'enabled': enabled,
              'scope': scope.wireName,
              'destination': destination.text.trim(),
              'destination_type': destinationType,
              'cadence': cadence,
              'local_time':
                  '${localTime.hour.toString().padLeft(2, '0')}:${localTime.minute.toString().padLeft(2, '0')}:00',
              'weekday': cadence == 'weekly' ? weekday : null,
              'month_day': cadence == 'monthly' ? monthDay : null,
              'auto_delete': autoDelete,
              'minimum_free_percent': int.tryParse(
                minimumFreePercent.text.trim(),
              ),
              'minimum_free_bytes': int.tryParse(minimumFreeBytes.text.trim()),
              'minimum_backups_to_keep':
                  int.tryParse(minimumKeep.text.trim()) ?? 3,
              'retention_trigger': 'after_successful_backup',
            },
          );
      await ref
          .read(backupApiProvider)
          .reconcileSchedules(
            requireBackupSessionFromAuth(ref.read(authControllerProvider)),
          );
      ref.invalidate(backupSchedulesProvider);
    } on DioException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              _apiError(error, 'Nie udało się zsynchronizować harmonogramu.'),
            ),
          ),
        );
      }
    }
  }
}

class _ManagedBackupsSection extends ConsumerWidget {
  const _ManagedBackupsSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final backups = ref.watch(managedBackupsProvider);
    return _Section(
      title: 'Zarządzane backupy V2',
      child: backups.when(
        loading: () => const LinearProgressIndicator(),
        error: (_, _) => const Text('Nie udało się pobrać katalogu backupów.'),
        data: (items) => items.isEmpty
            ? const Text(
                'Brak zarządzanych backupów. Historyczne backupy V1 nie są automatycznie adoptowane.',
              )
            : Column(
                children: items
                    .map(
                      (item) => ListTile(
                        title: Text(_date(item.createdAt)),
                        subtitle: Text(
                          '${item.destinationRoot}\n'
                          '${_bytes(item.totalBytes)} • ${item.appVersion} • '
                          '${item.integrityStatus} • ${item.lifecycle}',
                        ),
                        leading: Icon(
                          item.integrityStatus == 'verified'
                              ? Icons.verified_outlined
                              : Icons.warning_amber_outlined,
                        ),
                        trailing: const Tooltip(
                          message:
                              'Usuwanie produkcyjnych backupów nie zostało włączone.',
                          child: IconButton(
                            tooltip: 'Usuwanie wyłączone',
                            onPressed: null,
                            icon: Icon(Icons.delete_outline),
                          ),
                        ),
                      ),
                    )
                    .toList(),
              ),
      ),
    );
  }
}

class _LegacyBackupsSection extends ConsumerWidget {
  const _LegacyBackupsSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final candidates = ref.watch(legacyBackupCandidatesProvider);
    return _Section(
      title: 'Istniejące backupy do dodania',
      child: candidates.when(
        loading: () => const LinearProgressIndicator(),
        error: (_, _) => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            const Text('Nie udało się pobrać istniejących backupów.'),
            TextButton.icon(
              onPressed: () => ref.invalidate(legacyBackupCandidatesProvider),
              icon: const Icon(Icons.refresh),
              label: const Text('Spróbuj ponownie'),
            ),
          ],
        ),
        data: (items) => items.isEmpty
            ? const Text('Brak istniejących backupów do dodania.')
            : Column(
                children: items.map((item) {
                  final created = item.createdAt == null
                      ? 'Data nieznana'
                      : _date(item.createdAt!);
                  return ListTile(
                    leading: Icon(
                      item.verified
                          ? Icons.verified_outlined
                          : Icons.warning_amber_outlined,
                    ),
                    title: Text(created),
                    subtitle: Text(
                      '${item.destinationRoot}\n'
                      '${_bytes(item.totalBytes)} • '
                      '${item.verified ? 'ZWERYFIKOWANY' : 'WYMAGA WERYFIKACJI'}'
                      '${item.alreadyManaged ? ' • już zarządzany' : ''}',
                    ),
                    trailing: item.adoptable
                        ? FilledButton.tonal(
                            onPressed: () => _adopt(context, ref, item),
                            child: const Text('Zweryfikuj i dodaj'),
                          )
                        : null,
                  );
                }).toList(),
              ),
      ),
    );
  }

  Future<void> _adopt(
    BuildContext context,
    WidgetRef ref,
    LegacyBackupCandidate item,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Dodać backup do katalogu?'),
        content: Text(
          '${item.createdAt == null ? 'Data nieznana' : _date(item.createdAt!)}\n'
          '${item.destinationRoot}\n${_bytes(item.totalBytes)}\n\n'
          'Pliki nie zostaną przeniesione, zmienione ani usunięte.',
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Anuluj'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Dodaj zweryfikowany backup'),
          ),
        ],
      ),
    );
    if (confirmed != true || item.adoptionToken == null) return;
    try {
      await ref
          .read(backupApiProvider)
          .adoptLegacyBackup(
            session: requireBackupSessionFromAuth(
              ref.read(authControllerProvider),
            ),
            adoptionToken: item.adoptionToken!,
          );
      ref.invalidate(legacyBackupCandidatesProvider);
      ref.invalidate(managedBackupsProvider);
    } on DioException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(_apiError(error, 'Nie udało się dodać backupu.')),
          ),
        );
      }
    }
  }
}

class _CheckpointsSection extends ConsumerWidget {
  const _CheckpointsSection();
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final candidates = ref.watch(restoreCandidatesProvider);
    return _Section(
      title: 'Dostępne checkpointy i przywracanie',
      child: candidates.when(
        loading: () => const LinearProgressIndicator(),
        error: (_, _) => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            const Text('Nie udało się pobrać checkpointów.'),
            TextButton.icon(
              onPressed: () => ref.invalidate(restoreCandidatesProvider),
              icon: const Icon(Icons.refresh),
              label: const Text('Spróbuj ponownie'),
            ),
          ],
        ),
        data: (items) => items.isEmpty
            ? const Text(
                'Brak zweryfikowanych checkpointów w zatwierdzonych katalogach.',
              )
            : Column(
                children: items
                    .map(
                      (item) => Card.outlined(
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: <Widget>[
                              Text(
                                _date(item.createdAt),
                                style: Theme.of(context).textTheme.titleMedium,
                              ),
                              Text(
                                '${item.scope.label} • NEXT Stabil ${item.appVersion}',
                              ),
                              Text('Rewizja DB: ${item.dbRevision}'),
                              Text(
                                'Rozmiar: ${_bytes(item.totalBytes)} • ${item.verified ? 'Zweryfikowany' : 'Niezweryfikowany'}',
                              ),
                              if (!item.fullEligible && item.errorCode != null)
                                Padding(
                                  padding: EdgeInsets.only(top: 6),
                                  child: Text(
                                    item.errorCode == 'verification_required'
                                        ? 'Pełne przywracanie wymaga weryfikacji wybranego checkpointu.'
                                        : 'Pełne przywracanie jest niedostępne: odtworzenie Qdrant nie zostało bezpiecznie zweryfikowane.',
                                  ),
                                ),
                              const SizedBox(height: 8),
                              Wrap(
                                spacing: 8,
                                runSpacing: 8,
                                children: <Widget>[
                                  OutlinedButton(
                                    onPressed: item.databaseEligible
                                        ? () => _restore(
                                            context,
                                            ref,
                                            item,
                                            'database',
                                          )
                                        : null,
                                    child: const Text('Przywróć bazę'),
                                  ),
                                  FilledButton.tonal(
                                    onPressed: item.fullEligible
                                        ? () => _restore(
                                            context,
                                            ref,
                                            item,
                                            'full',
                                          )
                                        : null,
                                    child: const Text('Przywróć system'),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                    )
                    .toList(),
              ),
      ),
    );
  }

  Future<void> _restore(
    BuildContext context,
    WidgetRef ref,
    RestoreCandidate item,
    String mode,
  ) async {
    final api = ref.read(backupApiProvider);
    final session = requireBackupSessionFromAuth(
      ref.read(authControllerProvider),
    );
    late final RestorePreview preview;
    try {
      preview = await api.preview(
        session: session,
        checkpoint: item.checkpointPath,
        mode: mode,
      );
    } on DioException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              _apiError(error, 'Checkpoint nie przeszedł walidacji.'),
            ),
          ),
        );
      }
      return;
    }
    if (!context.mounted) return;
    bool acknowledged = false;
    final controller = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          icon: const Icon(Icons.warning_amber_rounded),
          title: Text(
            mode == 'full'
                ? 'Przywróć pełny checkpoint systemu'
                : 'Przywróć bazę danych',
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                const Text(
                  'Przywrócenie zastąpi aktualne dane. Przed operacją zostanie wykonany pełny backup bezpieczeństwa.',
                ),
                const SizedBox(height: 12),
                Text('Checkpoint: ${preview.checkpointPath}'),
                Text('Utworzono: ${_date(preview.createdAt)}'),
                Text('Wersja: ${preview.appVersion}'),
                Text('Rewizja backupu: ${preview.backupDbRevision}'),
                Text('Bieżąca rewizja: ${preview.currentDbRevision}'),
                Text('Zastępowane komponenty: ${preview.replaces.join(', ')}'),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: acknowledged,
                  onChanged: (value) =>
                      setDialogState(() => acknowledged = value ?? false),
                  title: const Text(
                    'Rozumiem, że bieżące dane zostaną zastąpione.',
                  ),
                ),
                TextField(
                  controller: controller,
                  decoration: const InputDecoration(
                    labelText: 'Wpisz PRZYWRÓĆ',
                  ),
                  onChanged: (_) => setDialogState(() {}),
                ),
              ],
            ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Anuluj'),
            ),
            FilledButton(
              onPressed:
                  acknowledged &&
                      controller.text == 'PRZYWRÓĆ' &&
                      preview.eligible
                  ? () => Navigator.pop(context, true)
                  : null,
              child: const Text('Przejdź do bezpiecznego przywracania'),
            ),
          ],
        ),
      ),
    );
    if (confirmed != true || !context.mounted) return;
    try {
      await api.requestRestore(
        session: session,
        checkpoint: item.checkpointPath,
        mode: mode,
      );
    } on DioException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              _apiError(
                error,
                'Przywracanie wymaga osobnej zgody produkcyjnej.',
              ),
            ),
          ),
        );
      }
    }
  }
}

class _RunHistorySection extends ConsumerWidget {
  const _RunHistorySection();
  @override
  Widget build(BuildContext context, WidgetRef ref) => _Section(
    title: 'Historia backupów',
    child: ref
        .watch(backupRunsProvider)
        .when(
          loading: () => const LinearProgressIndicator(),
          error: (_, _) =>
              const Text('Nie udało się pobrać historii backupów.'),
          data: (items) => items.isEmpty
              ? const Text('Brak wykonanych backupów.')
              : Column(
                  children: items
                      .map(
                        (item) => ListTile(
                          leading: Icon(
                            item.status == 'completed'
                                ? Icons.verified_outlined
                                : item.status == 'failed'
                                ? Icons.error_outline
                                : Icons.sync,
                          ),
                          title: Text(
                            '${item.scope.label} • ${_date(item.startedAt)}',
                          ),
                          subtitle: Text(
                            '${item.trigger} • ${_stageLabel(item.stage)} • ${_bytes(item.totalBytes)}${item.errorCode == null ? '' : '\nKod: ${item.errorCode}'}',
                          ),
                        ),
                      )
                      .toList(),
                ),
        ),
  );
}

class _RestoreHistorySection extends ConsumerWidget {
  const _RestoreHistorySection();
  @override
  Widget build(BuildContext context, WidgetRef ref) => _Section(
    title: 'Historia przywracania',
    child: ref
        .watch(restoreRunsProvider)
        .when(
          loading: () => const LinearProgressIndicator(),
          error: (_, _) =>
              const Text('Nie udało się pobrać historii przywracania.'),
          data: (items) => items.isEmpty
              ? const Text(
                  'Produkcja nie była przywracana. Wykonanie pozostaje zablokowane do osobnej zgody właściciela.',
                )
              : Column(
                  children: items
                      .map(
                        (item) => ListTile(
                          leading: const Icon(Icons.settings_backup_restore),
                          title: Text(
                            '${item.mode == 'full' ? 'Pełny system' : 'Baza danych'} • ${_date(item.startedAt)}',
                          ),
                          subtitle: Text(
                            '${item.status} • ${item.stage}${item.errorCode == null ? '' : '\nKod: ${item.errorCode}'}',
                          ),
                        ),
                      )
                      .toList(),
                ),
        ),
  );
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.child, this.trailing});
  final String title;
  final Widget child;
  final Widget? trailing;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              ?trailing,
            ],
          ),
          const SizedBox(height: 12),
          child,
        ],
      ),
    ),
  );
}

String _date(DateTime value) => formatPolishDateTime(value);
String _bytes(int value) {
  if (value <= 0) return '—';
  if (value >= 1024 * 1024 * 1024) {
    return '${(value / (1024 * 1024 * 1024)).toStringAsFixed(2)} GB';
  }
  if (value >= 1024 * 1024) {
    return '${(value / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
  return '${(value / 1024).toStringAsFixed(1)} KB';
}

String _stageLabel(String value) => switch (value) {
  'queued' => 'W kolejce',
  'validating' => 'Walidacja',
  'database' => 'Baza danych',
  'documents' => 'Dokumenty',
  'qdrant' => 'Qdrant',
  'n8n' => 'n8n',
  'configuration' => 'Konfiguracja',
  'release' => 'Kanał wydania',
  'verifying' => 'Weryfikacja',
  'completed' => 'Zakończony',
  'failed' => 'Błąd',
  _ => value,
};
String _cadenceLabel(String value) => switch (value) {
  'daily' => 'codziennie',
  'weekly' => 'co tydzień',
  'monthly' => 'co miesiąc',
  _ => value,
};
String _syncLabel(BackupSchedule item) {
  if (!item.enabled && item.syncStatus == 'synced') return 'Wyłączony';
  return switch (item.syncStatus) {
    'synced' => item.hostEnabled ? 'Aktywny' : 'Wyłączony',
    'error' => 'Błąd synchronizacji',
    'disabled' => 'Wyłączony',
    'destination_unavailable' => 'Miejsce docelowe niedostępne',
    _ => 'Oczekuje na synchronizację',
  };
}

String _backupResultLabel(String? value) => switch (value) {
  'completed' => 'Sukces',
  'failed' => 'Błąd',
  'running' => 'W toku',
  'queued' => 'W kolejce',
  _ => value ?? 'brak',
};
String _apiError(DioException error, String fallback) {
  final data = error.response?.data;
  final detail = data is Map<String, dynamic> ? data['detail'] : null;
  final code = detail is Map<String, dynamic>
      ? detail['code']?.toString()
      : null;
  return switch (code) {
    'production_restore_approval_required' =>
      'Przywracanie produkcyjne wymaga osobnej zgody właściciela.',
    'backup_already_running' => 'Backup już trwa.',
    'restore_already_running' ||
    'operation_conflict' => 'Trwa inna operacja backupu lub przywracania.',
    'backup_destination_active_path' =>
      'Cel backupu nie może znajdować się w repozytorium ani aktywnych danych.',
    'backup_retention_delete_approval_required' =>
      'Usuwanie istniejących backupów wymaga osobnej zgody właściciela.',
    'backup_schedule_dst_unsafe_time' =>
      'Godziny 02:00–02:59 są niedostępne z powodu zmiany czasu CET/CEST.',
    'backup_supervisor_unavailable' || 'backup_scheduler_host_failure' =>
      'Nie udało się zsynchronizować Windows Task Scheduler.',
    _ => fallback,
  };
}
