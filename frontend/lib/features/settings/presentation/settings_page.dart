import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/widgets/app_shell.dart';
import '../../app_update/application/update_install_controller.dart';
import '../../app_update/application/update_provider.dart';
import '../../app_update/domain/app_update.dart';
import '../../app_version/application/app_version_provider.dart';
import '../../app_version/domain/app_version_info.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/application/auth_state.dart';
import '../../auth/presentation/admin_users_page.dart';
import '../../auth/presentation/change_password_page.dart';
import '../../system_status/application/system_status_provider.dart';
import '../../system_status/domain/backend_status.dart';

class SettingsPage extends ConsumerWidget {
  const SettingsPage({super.key});

  bool _isAdminRole(String role) {
    final String normalized = role.trim().toLowerCase();

    return normalized == 'admin' || normalized == 'administrator';
  }

  String _describeUpdate(UpdateCheckResult result) {
    if (result.platform == AppUpdatePlatform.web) {
      switch (result.state) {
        case AppUpdateState.current:
          return 'Wersja web jest aktualna: '
              '${result.latestDisplayVersion}.';

        case AppUpdateState.available:
        case AppUpdateState.required:
          return 'Dost\u0119pna jest nowsza wersja web. '
              'Od\u015bwie\u017c kart\u0119 przegl\u0105darki.';

        case AppUpdateState.unsupported:
          return 'Kana\u0142 aktualizacji web jest niedost\u0119pny.';
      }
    }

    switch (result.state) {
      case AppUpdateState.current:
        return 'Masz aktualn\u0105 wersj\u0119. '
            'Kana\u0142 stable: ${result.latestDisplayVersion}.';

      case AppUpdateState.available:
        return 'Dost\u0119pna aktualizacja: '
            '${result.latestDisplayVersion}.';

      case AppUpdateState.required:
        return 'Ta wersja nie jest ju\u017c obs\u0142ugiwana. '
            'Wymagana wersja minimalna: '
            '${result.manifest.minimumVersion}.';

      case AppUpdateState.unsupported:
        return 'Aktualizacje natywne nie s\u0105 obs\u0142ugiwane '
            'na tej platformie.';
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<AuthState> authValue = ref.watch(authControllerProvider);
    final AsyncValue<AppVersionInfo> appVersion = ref.watch(appVersionProvider);

    final AsyncValue<BackendStatus> backendStatus = ref.watch(
      backendStatusProvider,
    );

    final AsyncValue<UpdateCheckResult> updateCheck = ref.watch(
      updateCheckProvider,
    );

    final UpdateInstallState installState = ref.watch(
      updateInstallControllerProvider,
    );

    final String role = authValue.value?.user?.role ?? '';
    final bool isAdmin = _isAdminRole(role);

    return Scaffold(
      appBar: AppBar(
        leading: AppShell.mobileNavigationLeading(context),
        title: const Text('Ustawienia'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: <Widget>[
          _SettingsSection(
            title: 'Konto',
            children: <Widget>[
              ListTile(
                leading: const Icon(Icons.password),
                title: const Text('Zmie\u0144 has\u0142o'),
                subtitle: const Text(
                  'Zmie\u0144 has\u0142o aktualnie '
                  'zalogowanego u\u017cytkownika.',
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => const ChangePasswordPage(),
                    ),
                  );
                },
              ),
            ],
          ),
          if (isAdmin) ...<Widget>[
            const SizedBox(height: 20),
            _SettingsSection(
              title: 'Administracja',
              children: <Widget>[
                ListTile(
                  leading: const Icon(Icons.person_add_alt_1),
                  title: const Text('Dodaj u\u017cytkownika'),
                  subtitle: const Text(
                    'Utw\u00f3rz konto z rol\u0105 i '
                    'has\u0142em tymczasowym.',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => const AdminUsersPage(),
                      ),
                    );
                  },
                ),
                ListTile(
                  leading: const Icon(Icons.power_settings_new),
                  title: const Text('Sterowanie systemem'),
                  subtitle: const Text(
                    'Sprawd\u017a stan us\u0142ug oraz uruchom, '
                    'zrestartuj lub zatrzymaj system.',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () {
                    context.push('/system');
                  },
                ),
              ],
            ),
          ],
          const SizedBox(height: 20),
          _SettingsSection(
            title: 'Wersja systemu',
            children: <Widget>[
              ListTile(
                leading: const Icon(Icons.apps_outlined),
                title: const Text('Aplikacja'),
                subtitle: Text(
                  appVersion.when(
                    data: (AppVersionInfo value) =>
                        'NEXT Stabil ${value.displayVersion}',
                    loading: () => 'Odczytywanie wersji...',
                    error: (_, _) =>
                        'Nie uda\u0142o si\u0119 odczyta\u0107 '
                        'wersji aplikacji.',
                  ),
                ),
              ),
              ListTile(
                leading: const Icon(Icons.dns_outlined),
                title: const Text('Backend'),
                subtitle: Text(
                  backendStatus.when(
                    data: (BackendStatus value) =>
                        'NEXT Stabil Backend ${value.version} '
                        '\u2022 ${value.environment}',
                    loading: () => 'Sprawdzanie backendu...',
                    error: (_, _) => 'Backend niedost\u0119pny.',
                  ),
                ),
              ),
              updateCheck.when(
                data: (UpdateCheckResult result) {
                  final bool installable =
                      result.platform != AppUpdatePlatform.web &&
                      result.platform != AppUpdatePlatform.unsupported &&
                      (result.state == AppUpdateState.available ||
                          result.state == AppUpdateState.required);

                  return _UpdateTile(
                    description: _describeUpdate(result),
                    result: result,
                    installState: installState,
                    installable: installable,
                    onRefresh: installState.isBusy
                        ? null
                        : () {
                            ref.invalidate(updateCheckProvider);
                          },
                    onInstall: installable && !installState.isBusy
                        ? () {
                            ref
                                .read(updateInstallControllerProvider.notifier)
                                .install(result);
                          }
                        : null,
                  );
                },
                loading: () => const ListTile(
                  leading: Icon(Icons.system_update_alt),
                  title: Text('Kana\u0142 aktualizacji'),
                  subtitle: Text('Sprawdzanie kana\u0142u stable...'),
                ),
                error: (_, _) => ListTile(
                  leading: const Icon(Icons.error_outline),
                  title: const Text('Kana\u0142 aktualizacji'),
                  subtitle: const Text(
                    'Nie uda\u0142o si\u0119 sprawdzi\u0107 '
                    'kana\u0142u stable.',
                  ),
                  trailing: IconButton(
                    tooltip: 'Sprawd\u017a ponownie',
                    icon: const Icon(Icons.refresh),
                    onPressed: () {
                      ref.invalidate(updateCheckProvider);
                    },
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _UpdateTile extends StatelessWidget {
  const _UpdateTile({
    required this.description,
    required this.result,
    required this.installState,
    required this.installable,
    required this.onRefresh,
    required this.onInstall,
  });

  final String description;
  final UpdateCheckResult result;
  final UpdateInstallState installState;
  final bool installable;
  final VoidCallback? onRefresh;
  final VoidCallback? onInstall;

  String? _installMessage() {
    switch (installState.phase) {
      case UpdateInstallPhase.idle:
        return null;

      case UpdateInstallPhase.downloading:
        final double? progress = installState.progress;

        if (progress == null) {
          return 'Pobieranie aktualizacji...';
        }

        return 'Pobieranie: ${(progress * 100).round()}%';

      case UpdateInstallPhase.verifying:
        return 'Weryfikacja SHA256...';

      case UpdateInstallPhase.launching:
        if (result.platform == AppUpdatePlatform.windows) {
          return 'Uruchamianie instalatora Windows...';
        }

        return 'Otwieranie instalatora Android...';

      case UpdateInstallPhase.failed:
        return 'B\u0142\u0105d aktualizacji: '
            '${installState.error ?? 'nieznany b\u0142\u0105d'}';
    }
  }

  @override
  Widget build(BuildContext context) {
    final String? installMessage = _installMessage();

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          ListTile(
            leading: const Icon(Icons.system_update_alt),
            title: const Text('Kana\u0142 aktualizacji'),
            subtitle: Text(
              installMessage == null
                  ? description
                  : '$description\n$installMessage',
            ),
            trailing: IconButton(
              tooltip: 'Sprawd\u017a ponownie',
              icon: const Icon(Icons.refresh),
              onPressed: onRefresh,
            ),
          ),
          if (installState.phase == UpdateInstallPhase.downloading &&
              installState.progress != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: LinearProgressIndicator(value: installState.progress),
            ),
          if (installable)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
              child: FilledButton.icon(
                onPressed: onInstall,
                icon: const Icon(Icons.download),
                label: Text(
                  result.state == AppUpdateState.required
                      ? 'Zainstaluj wymagan\u0105 aktualizacj\u0119'
                      : 'Pobierz i zainstaluj',
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _SettingsSection extends StatelessWidget {
  const _SettingsSection({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              child: Text(
                title,
                style: Theme.of(
                  context,
                ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
              ),
            ),
            ...children,
          ],
        ),
      ),
    );
  }
}
