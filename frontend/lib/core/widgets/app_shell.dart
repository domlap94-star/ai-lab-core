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
      label: 'Realizacje',
      path: '/projects',
      icon: Icons.construction_outlined,
      selectedIcon: Icons.construction,
    ),
    NavigationItem(
      label: 'Wizje lokalne',
      path: '/inspections',
      icon: Icons.location_searching_outlined,
      selectedIcon: Icons.location_searching,
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
            'Czy na pewno chcesz wylogowa\u0107 si\u0119 z NEXT Stabil?',
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

  static Widget? mobileNavigationLeading(BuildContext context) {
    if (MediaQuery.sizeOf(context).width >= desktopBreakpoint) {
      return null;
    }

    return const MobileNavigationButton();
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
          semanticLabel: 'NEXT Stabil',
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

class _MobileShell extends StatefulWidget {
  const _MobileShell({
    required this.selectedIndex,
    required this.username,
    required this.onDestinationSelected,
    required this.onLogout,
    required this.child,
  });

  final int selectedIndex;
  final String username;
  final ValueChanged<int> onDestinationSelected;
  final VoidCallback onLogout;
  final Widget child;

  @override
  State<_MobileShell> createState() => _MobileShellState();
}

class _MobileShellState extends State<_MobileShell> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();

  void _selectDestination(BuildContext drawerContext, int index) {
    Navigator.of(drawerContext).pop();
    widget.onDestinationSelected(index);
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return _MobileDrawerScope(
      openDrawer: () => _scaffoldKey.currentState?.openDrawer(),
      child: Scaffold(
        key: _scaffoldKey,
        body: widget.child,
        drawer: Drawer(
          child: SafeArea(
            child: ListView(
              padding: EdgeInsets.zero,
              children: <Widget>[
                const _MobileDrawerHeader(),
                for (
                  int index = 0;
                  index < AppShell.navigationItems.length;
                  index++
                )
                  Builder(
                    builder: (BuildContext drawerContext) {
                      final NavigationItem item =
                          AppShell.navigationItems[index];
                      final bool selected = widget.selectedIndex == index;

                      return ListTile(
                        key: Key('mobile-nav-${item.path}'),
                        minTileHeight: 52,
                        leading: Icon(selected ? item.selectedIcon : item.icon),
                        title: Text(
                          item.label,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        selected: selected,
                        selectedColor: theme.colorScheme.onSecondaryContainer,
                        selectedTileColor: theme.colorScheme.secondaryContainer,
                        onTap: () => _selectDestination(drawerContext, index),
                      );
                    },
                  ),
                const Divider(height: 24),
                ListTile(
                  leading: CircleAvatar(
                    child: Text(
                      widget.username.isEmpty
                          ? '?'
                          : widget.username[0].toUpperCase(),
                    ),
                  ),
                  title: Text(
                    widget.username,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Builder(
                  builder: (BuildContext drawerContext) => ListTile(
                    leading: const Icon(Icons.logout),
                    title: const Text('Wyloguj si\u0119'),
                    onTap: () {
                      Navigator.of(drawerContext).pop();
                      widget.onLogout();
                    },
                  ),
                ),
                const SizedBox(height: 12),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _MobileDrawerHeader extends StatelessWidget {
  const _MobileDrawerHeader();

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
      child: Row(
        children: <Widget>[
          Image.asset(
            'logo.png',
            width: 52,
            height: 52,
            fit: BoxFit.contain,
            semanticLabel: 'NEXT Stabil',
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Text(
                  'NEXT Stabil',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Text('CRM', style: theme.textTheme.bodyMedium),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MobileDrawerScope extends InheritedWidget {
  const _MobileDrawerScope({required this.openDrawer, required super.child});

  final VoidCallback openDrawer;

  static _MobileDrawerScope? maybeOf(BuildContext context) {
    return context.dependOnInheritedWidgetOfExactType<_MobileDrawerScope>();
  }

  @override
  bool updateShouldNotify(_MobileDrawerScope oldWidget) {
    return openDrawer != oldWidget.openDrawer;
  }
}

class MobileNavigationButton extends StatelessWidget {
  const MobileNavigationButton({super.key});

  @override
  Widget build(BuildContext context) {
    return IconButton(
      key: const Key('mobile-navigation-menu-button'),
      tooltip: 'Otw\u00f3rz menu',
      onPressed: _MobileDrawerScope.maybeOf(context)?.openDrawer,
      icon: const Icon(Icons.menu),
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
