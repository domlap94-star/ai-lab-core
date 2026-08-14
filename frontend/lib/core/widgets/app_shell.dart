import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/application/auth_controller.dart';
import '../../features/auth/application/auth_state.dart';

class AppShell extends ConsumerWidget {
  const AppShell({
    required this.currentLocation,
    required this.child,
    super.key,
  });

  final String currentLocation;
  final Widget child;

  static const double desktopBreakpoint = 700;
  static const double desktopSidebarWidth = 240;

  static const List<NavigationItem> navigationItems = <NavigationItem>[
    NavigationItem(
      label: 'Dashboard',
      path: '/dashboard',
      icon: Icons.dashboard_outlined,
      selectedIcon: Icons.dashboard,
    ),
    NavigationItem(
      label: 'Sprawy',
      path: '/cases',
      icon: Icons.work_outline,
      selectedIcon: Icons.work,
    ),
    NavigationItem(
      label: 'Klienci',
      path: '/clients',
      icon: Icons.people_outline,
      selectedIcon: Icons.people,
    ),
    NavigationItem(
      label: 'Dokumenty',
      path: '/documents',
      icon: Icons.description_outlined,
      selectedIcon: Icons.description,
    ),
    NavigationItem(
      label: 'Asystent AI',
      path: '/ai',
      icon: Icons.auto_awesome_outlined,
      selectedIcon: Icons.auto_awesome,
    ),
    NavigationItem(
      label: 'Ustawienia',
      path: '/settings',
      icon: Icons.settings_outlined,
      selectedIcon: Icons.settings,
    ),
  ];

  int get selectedIndex {
    final int index = navigationItems.indexWhere(
      (NavigationItem item) => currentLocation.startsWith(item.path),
    );

    return index < 0 ? 0 : index;
  }

  void _navigate(BuildContext context, int index) {
    final String destination = navigationItems[index].path;

    if (currentLocation != destination) {
      context.go(destination);
    }
  }

  Future<void> _logout(BuildContext context, WidgetRef ref) async {
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext dialogContext) {
        return AlertDialog(
          title: const Text('Wylogowanie'),
          content: const Text(
            'Czy na pewno chcesz wylogowa\u0107 si\u0119 z AI-Lab?',
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop(false);
              },
              child: const Text('Anuluj'),
            ),
            FilledButton(
              onPressed: () {
                Navigator.of(dialogContext).pop(true);
              },
              child: const Text('Wyloguj si\u0119'),
            ),
          ],
        );
      },
    );

    if (confirmed != true) {
      return;
    }

    await ref.read(authControllerProvider.notifier).logout();
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<AuthState> authValue = ref.watch(authControllerProvider);

    final AuthState? authState = authValue.value;

    final String username = authState?.user?.username.trim().isNotEmpty == true
        ? authState!.user!.username
        : 'U\u017cytkownik';

    final String role = authState?.user?.role ?? '';

    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final bool useDesktopLayout = constraints.maxWidth >= desktopBreakpoint;

        if (useDesktopLayout) {
          return _DesktopShell(
            selectedIndex: selectedIndex,
            username: username,
            role: role,
            onDestinationSelected: (int index) {
              _navigate(context, index);
            },
            onLogout: () {
              _logout(context, ref);
            },
            child: child,
          );
        }

        return _MobileShell(
          selectedIndex: selectedIndex,
          username: username,
          role: role,
          onDestinationSelected: (int index) {
            _navigate(context, index);
          },
          onLogout: () {
            _logout(context, ref);
          },
          child: child,
        );
      },
    );
  }
}

class _DesktopShell extends StatelessWidget {
  const _DesktopShell({
    required this.selectedIndex,
    required this.username,
    required this.role,
    required this.onDestinationSelected,
    required this.onLogout,
    required this.child,
  });

  final int selectedIndex;
  final String username;
  final String role;
  final ValueChanged<int> onDestinationSelected;
  final VoidCallback onLogout;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return Scaffold(
      body: Row(
        children: <Widget>[
          SizedBox(
            width: AppShell.desktopSidebarWidth,
            child: Material(
              color:
                  theme.navigationRailTheme.backgroundColor ??
                  theme.colorScheme.surface,
              child: SafeArea(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    const _ApplicationHeader(),
                    const SizedBox(height: 8),
                    Expanded(
                      child: ListView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                        itemCount: AppShell.navigationItems.length,
                        itemBuilder: (BuildContext context, int index) {
                          final NavigationItem item =
                              AppShell.navigationItems[index];

                          return _DesktopNavigationTile(
                            item: item,
                            selected: selectedIndex == index,
                            onTap: () {
                              onDestinationSelected(index);
                            },
                          );
                        },
                      ),
                    ),
                    const Divider(height: 1),
                    _UserPanel(
                      username: username,
                      role: role,
                      onLogout: onLogout,
                    ),
                  ],
                ),
              ),
            ),
          ),
          VerticalDivider(
            width: 1,
            thickness: 1,
            color: theme.colorScheme.outlineVariant,
          ),
          Expanded(child: child),
        ],
      ),
    );
  }
}

class _ApplicationHeader extends StatelessWidget {
  const _ApplicationHeader();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
      child: SizedBox(
        height: 96,
        child: Image.asset(
          'logo.png',
          fit: BoxFit.contain,
          alignment: Alignment.centerLeft,
          semanticLabel: 'AI-Lab',
          height: 72,
        ),
      ),
    );
  }
}

class _DesktopNavigationTile extends StatelessWidget {
  const _DesktopNavigationTile({
    required this.item,
    required this.selected,
    required this.onTap,
  });

  final NavigationItem item;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    final Color selectedBackground =
        theme.navigationRailTheme.indicatorColor ??
        theme.colorScheme.secondaryContainer;

    final Color selectedForeground = theme.colorScheme.onSecondaryContainer;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Material(
        color: selected ? selectedBackground : Colors.transparent,
        borderRadius: BorderRadius.circular(12),
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            child: Row(
              children: <Widget>[
                Icon(
                  selected ? item.selectedIcon : item.icon,
                  color: selected
                      ? selectedForeground
                      : theme.colorScheme.onSurfaceVariant,
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Text(
                    item.label,
                    style: theme.textTheme.bodyLarge?.copyWith(
                      color: selected
                          ? selectedForeground
                          : theme.colorScheme.onSurface,
                      fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _UserPanel extends StatelessWidget {
  const _UserPanel({
    required this.username,
    required this.role,
    required this.onLogout,
  });

  final String username;
  final String role;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          ListTile(
            contentPadding: const EdgeInsets.symmetric(horizontal: 8),
            leading: CircleAvatar(
              child: Text(username.isEmpty ? '?' : username[0].toUpperCase()),
            ),
            title: Text(username, maxLines: 1, overflow: TextOverflow.ellipsis),
            subtitle: role.isEmpty
                ? null
                : Text(role, maxLines: 1, overflow: TextOverflow.ellipsis),
          ),
          ListTile(
            contentPadding: const EdgeInsets.symmetric(horizontal: 8),
            leading: const Icon(Icons.logout),
            title: const Text('Wyloguj si\u0119'),
            onTap: onLogout,
          ),
        ],
      ),
    );
  }
}

class _MobileShell extends StatelessWidget {
  const _MobileShell({
    required this.selectedIndex,
    required this.username,
    required this.role,
    required this.onDestinationSelected,
    required this.onLogout,
    required this.child,
  });

  final int selectedIndex;
  final String username;
  final String role;
  final ValueChanged<int> onDestinationSelected;
  final VoidCallback onLogout;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: child,
      drawer: Drawer(
        child: SafeArea(
          child: Column(
            children: <Widget>[
              const _ApplicationHeader(),
              const Divider(height: 1),
              ListTile(
                leading: CircleAvatar(
                  child: Text(
                    username.isEmpty ? '?' : username[0].toUpperCase(),
                  ),
                ),
                title: Text(username),
                subtitle: role.isEmpty ? null : Text(role),
              ),
              const Spacer(),
              ListTile(
                leading: const Icon(Icons.logout),
                title: const Text('Wyloguj si\u0119'),
                onTap: () {
                  Navigator.of(context).pop();
                  onLogout();
                },
              ),
              const SizedBox(height: 12),
            ],
          ),
        ),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: selectedIndex,
        onDestinationSelected: onDestinationSelected,
        destinations: AppShell.navigationItems
            .map(
              (NavigationItem item) => NavigationDestination(
                icon: Icon(item.icon),
                selectedIcon: Icon(item.selectedIcon),
                label: item.label,
              ),
            )
            .toList(),
      ),
    );
  }
}

class NavigationItem {
  const NavigationItem({
    required this.label,
    required this.path,
    required this.icon,
    required this.selectedIcon,
  });

  final String label;
  final String path;
  final IconData icon;
  final IconData selectedIcon;
}
