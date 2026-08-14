import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

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

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<AuthState> authValue = ref.watch(authControllerProvider);

    final AsyncValue<AppVersionInfo> appVersion = ref.watch(appVersionProvider);

    final AsyncValue<BackendStatus> backendStatus = ref.watch(
      backendStatusProvider,
    );

    final String role = authValue.value?.user?.role ?? '';

    final bool isAdmin = _isAdminRole(role);

    return Scaffold(
      appBar: AppBar(title: const Text('Ustawienia')),
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
                    context.go('/system');
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
                        'AI-Lab ${value.displayVersion}',
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
                        '${value.application} '
                        '${value.version} '
                        '\u2022 ${value.environment}',
                    loading: () => 'Sprawdzanie backendu...',
                    error: (_, _) => 'Backend niedost\u0119pny.',
                  ),
                ),
              ),
              const ListTile(
                leading: Icon(Icons.verified_user_outlined),
                title: Text('Zgodno\u015b\u0107 wersji'),
                subtitle: Text(
                  'Warstwa Flutter jest gotowa. '
                  'Minimaln\u0105 obs\u0142ugiwan\u0105 wersj\u0119 '
                  'i wymuszenie aktualizacji '
                  'pod\u0142\u0105czymy po zako\u0144czeniu '
                  'batcha klient\u00f3w.',
                ),
              ),
            ],
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
