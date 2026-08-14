import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
                title: const Text('Zmień hasło'),
                subtitle: const Text(
                  'Zmień hasło aktualnie '
                  'zalogowanego użytkownika.',
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
                  title: const Text('Dodaj użytkownika'),
                  subtitle: const Text(
                    'Utwórz konto z rolą i '
                    'hasłem tymczasowym.',
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
                        'Nie udało się odczytać '
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
                        '• ${value.environment}',
                    loading: () => 'Sprawdzanie backendu...',
                    error: (_, _) => 'Backend niedostępny.',
                  ),
                ),
              ),
              const ListTile(
                leading: Icon(Icons.verified_user_outlined),
                title: Text('Zgodność wersji'),
                subtitle: Text(
                  'Warstwa Flutter jest gotowa. '
                  'Minimalną obsługiwaną wersję '
                  'i wymuszenie aktualizacji '
                  'podłączymy po zakończeniu '
                  'batcha klientów.',
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
