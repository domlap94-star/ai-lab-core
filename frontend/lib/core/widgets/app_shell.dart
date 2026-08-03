import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class AppShell extends StatelessWidget {
  const AppShell({
    required this.currentLocation,
    required this.child,
    super.key,
  });

  final String currentLocation;
  final Widget child;

  static const double desktopBreakpoint = 900;

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

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final bool useDesktopLayout = constraints.maxWidth >= desktopBreakpoint;

        if (useDesktopLayout) {
          return _DesktopShell(
            selectedIndex: selectedIndex,
            onDestinationSelected: (int index) => _navigate(context, index),
            child: child,
          );
        }

        return _MobileShell(
          selectedIndex: selectedIndex,
          onDestinationSelected: (int index) => _navigate(context, index),
          child: child,
        );
      },
    );
  }
}

class _DesktopShell extends StatelessWidget {
  const _DesktopShell({
    required this.selectedIndex,
    required this.onDestinationSelected,
    required this.child,
  });

  final int selectedIndex;
  final ValueChanged<int> onDestinationSelected;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return Scaffold(
      body: Row(
        children: <Widget>[
          NavigationRail(
            selectedIndex: selectedIndex,
            extended: true,
            minExtendedWidth: 230,
            onDestinationSelected: onDestinationSelected,
            leading: Padding(
              padding: const EdgeInsets.fromLTRB(16, 20, 16, 28),
              child: Row(
                children: <Widget>[
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: theme.colorScheme.primary,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(Icons.hub, color: theme.colorScheme.onPrimary),
                  ),
                  const SizedBox(width: 12),
                  Text(
                    'AI LAB',
                    style: theme.textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
            destinations: AppShell.navigationItems
                .map(
                  (NavigationItem item) => NavigationRailDestination(
                    icon: Icon(item.icon),
                    selectedIcon: Icon(item.selectedIcon),
                    label: Text(item.label),
                  ),
                )
                .toList(),
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

class _MobileShell extends StatelessWidget {
  const _MobileShell({
    required this.selectedIndex,
    required this.onDestinationSelected,
    required this.child,
  });

  final int selectedIndex;
  final ValueChanged<int> onDestinationSelected;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: child,
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
