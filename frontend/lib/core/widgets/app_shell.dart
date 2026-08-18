import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/application/auth_controller.dart';
import '../../features/auth/application/auth_state.dart';

class AppShell extends ConsumerStatefulWidget {
  const AppShell({
    required this.currentLocation,
    required this.child,
    this.androidBackPolicyOverride,
    super.key,
  });

  final String currentLocation;
  final Widget child;
  final bool? androidBackPolicyOverride;

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

  @override
  ConsumerState<AppShell> createState() => _AppShellState();

  static Widget? mobileNavigationLeading(BuildContext context) {
    if (MediaQuery.sizeOf(context).width >= desktopBreakpoint) {
      return null;
    }

    return const MobileNavigationButton();
  }

  static Widget globalSearchAction(BuildContext context) {
    if (MediaQuery.sizeOf(context).width >= desktopBreakpoint) {
      return const SizedBox.shrink();
    }

    return IconButton(
      key: const Key('global-search-action'),
      tooltip: 'Szukaj w NEXT Stabil',
      onPressed: () => context.push('/search'),
      icon: const Icon(Icons.search),
    );
  }

  static bool centrallyHandlesBack(BuildContext context) =>
      _CentralBackNavigationScope.maybeOf(context) != null;

  static String inspectionPathWithReturn({
    required int inspectionId,
    required String returnPath,
  }) {
    final String query = Uri(
      queryParameters: <String, String>{'return_to': returnPath},
    ).query;
    return '/inspections/$inspectionId?$query';
  }
}

class _AppShellState extends ConsumerState<AppShell> {
  final DashboardExitGuard _dashboardExitGuard = DashboardExitGuard();
  Timer? _dashboardExitTimer;
  bool _mobileDrawerOpen = false;

  int get _selectedIndex {
    final int index = AppShell.navigationItems.indexWhere(
      (NavigationItem item) => widget.currentLocation.startsWith(item.path),
    );

    return index < 0 ? 0 : index;
  }

  void _navigate(BuildContext context, int index) {
    final String destination = AppShell.navigationItems[index].path;

    if (widget.currentLocation != destination) {
      context.go(destination);
    }
  }

  bool get _usesAndroidBackPolicy =>
      widget.androidBackPolicyOverride ??
      (!kIsWeb && defaultTargetPlatform == TargetPlatform.android);

  bool _canPop(BuildContext context) {
    if (!_usesAndroidBackPolicy || _mobileDrawerOpen) {
      return true;
    }

    if (AppNavigationPolicy.isDashboard(widget.currentLocation)) {
      return _dashboardExitGuard.isArmed(DateTime.now());
    }

    if (AppNavigationPolicy.fallbackFor(widget.currentLocation) != null) {
      return false;
    }

    return GoRouter.of(context).canPop();
  }

  void _handlePop(BuildContext context, bool didPop) {
    if (didPop || !_usesAndroidBackPolicy) {
      return;
    }

    final String? fallback = AppNavigationPolicy.fallbackFor(
      widget.currentLocation,
    );
    if (fallback != null) {
      context.go(fallback);
      return;
    }

    if (!AppNavigationPolicy.isDashboard(widget.currentLocation)) {
      return;
    }

    final bool allowExit = _dashboardExitGuard.registerBackAttempt(
      DateTime.now(),
    );
    if (allowExit) {
      return;
    }

    _dashboardExitTimer?.cancel();
    _dashboardExitTimer = Timer(_dashboardExitGuard.timeout, () {
      if (!mounted) return;
      setState(_dashboardExitGuard.reset);
    });
    setState(() {});

    final ScaffoldMessengerState messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      const SnackBar(
        content: Text('Naciśnij jeszcze raz, aby wyjść'),
        duration: Duration(seconds: 2),
      ),
    );
  }

  @override
  void didUpdateWidget(AppShell oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.currentLocation != widget.currentLocation) {
      _dashboardExitTimer?.cancel();
      _dashboardExitGuard.reset();
    }
  }

  @override
  void dispose() {
    _dashboardExitTimer?.cancel();
    super.dispose();
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
  Widget build(BuildContext context) {
    final AsyncValue<AuthState> authValue = ref.watch(authControllerProvider);

    final AuthState? authState = authValue.value;

    final String username = authState?.user?.username.trim().isNotEmpty == true
        ? authState!.user!.username
        : 'U\u017cytkownik';

    final String role = authState?.user?.role ?? '';

    return _CentralBackNavigationScope(
      child: PopScope<Object?>(
        canPop: _canPop(context),
        onPopInvokedWithResult: (bool didPop, Object? result) {
          _handlePop(context, didPop);
        },
        child: LayoutBuilder(
          builder: (BuildContext context, BoxConstraints constraints) {
            final bool useDesktopLayout =
                constraints.maxWidth >= AppShell.desktopBreakpoint;

            if (useDesktopLayout) {
              return _DesktopShell(
                selectedIndex: _selectedIndex,
                username: username,
                role: role,
                onDestinationSelected: (int index) {
                  _navigate(context, index);
                },
                onLogout: () {
                  _logout(context, ref);
                },
                onSearch: () => context.push('/search'),
                child: widget.child,
              );
            }

            return _MobileShell(
              selectedIndex: _selectedIndex,
              username: username,
              onDrawerChanged: (bool isOpen) {
                if (_mobileDrawerOpen == isOpen) return;
                setState(() {
                  _mobileDrawerOpen = isOpen;
                });
              },
              onDestinationSelected: (int index) {
                _navigate(context, index);
              },
              onLogout: () {
                _logout(context, ref);
              },
              child: widget.child,
            );
          },
        ),
      ),
    );
  }
}

class AppNavigationPolicy {
  const AppNavigationPolicy._();

  static const String dashboardPath = '/dashboard';

  static const Map<String, String> _fallbacks = <String, String>{
    '/cases': dashboardPath,
    '/clients': dashboardPath,
    '/projects': dashboardPath,
    '/inspections': dashboardPath,
    '/documents': dashboardPath,
    '/ai': dashboardPath,
    '/settings': dashboardPath,
    '/search': dashboardPath,
    '/client-candidates': '/clients',
    '/system': '/settings',
  };

  static String? fallbackFor(String location) {
    final Uri uri = Uri.tryParse(location) ?? Uri(path: location);
    final String path = uri.path;
    final String? contextualReturn = detailReturnPath(
      uri.queryParameters['return_to'],
    );
    if (contextualReturn != null) return contextualReturn;
    final String? exact = _fallbacks[path];
    if (exact != null) return exact;
    if (path.startsWith('/clients/')) return '/clients';
    if (path.startsWith('/projects/')) return '/projects';
    if (path.startsWith('/inspections/')) return '/inspections';
    if (path.startsWith('/client-candidates/')) {
      return '/client-candidates';
    }
    return null;
  }

  static bool isDashboard(String location) =>
      (Uri.tryParse(location) ?? Uri(path: location)).path == dashboardPath;

  static String? detailReturnPath(String? candidate) {
    if (candidate == null) return null;
    final Uri? uri = Uri.tryParse(candidate);
    if (uri == null ||
        uri.hasScheme ||
        uri.hasAuthority ||
        uri.hasQuery ||
        uri.hasFragment) {
      return null;
    }

    if (uri.path == '/search') return uri.path;
    if (uri.pathSegments.length != 2) return null;

    final String section = uri.pathSegments.first;
    final int? id = int.tryParse(uri.pathSegments.last);
    if ((section != 'clients' && section != 'projects') ||
        id == null ||
        id <= 0) {
      return null;
    }
    return uri.path;
  }
}

class DashboardExitGuard {
  DashboardExitGuard({this.timeout = const Duration(seconds: 2)});

  final Duration timeout;
  DateTime? _armedAt;

  bool isArmed(DateTime now) {
    final DateTime? armedAt = _armedAt;
    return armedAt != null && now.difference(armedAt) <= timeout;
  }

  bool registerBackAttempt(DateTime now) {
    if (isArmed(now)) {
      reset();
      return true;
    }

    _armedAt = now;
    return false;
  }

  void reset() {
    _armedAt = null;
  }
}

class _CentralBackNavigationScope extends InheritedWidget {
  const _CentralBackNavigationScope({required super.child});

  static _CentralBackNavigationScope? maybeOf(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<_CentralBackNavigationScope>();

  @override
  bool updateShouldNotify(_CentralBackNavigationScope oldWidget) => false;
}

class _DesktopShell extends StatelessWidget {
  const _DesktopShell({
    required this.selectedIndex,
    required this.username,
    required this.role,
    required this.onDestinationSelected,
    required this.onLogout,
    required this.onSearch,
    required this.child,
  });

  final int selectedIndex;
  final String username;
  final String role;
  final ValueChanged<int> onDestinationSelected;
  final VoidCallback onLogout;
  final VoidCallback onSearch;
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
                    _ApplicationHeader(onSearch: onSearch),
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
  const _ApplicationHeader({required this.onSearch});

  final VoidCallback onSearch;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          SizedBox(
            height: 72,
            child: Image.asset(
              'logo.png',
              fit: BoxFit.contain,
              alignment: Alignment.centerLeft,
              semanticLabel: 'NEXT Stabil',
            ),
          ),
          TextButton.icon(
            key: const Key('desktop-global-search-action'),
            onPressed: onSearch,
            icon: const Icon(Icons.search),
            label: const Text('Szukaj'),
          ),
        ],
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
    required this.onDrawerChanged,
    required this.onDestinationSelected,
    required this.onLogout,
    required this.child,
  });

  final int selectedIndex;
  final String username;
  final ValueChanged<bool> onDrawerChanged;
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
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) widget.onDestinationSelected(index);
    });
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return _MobileDrawerScope(
      openDrawer: () => _scaffoldKey.currentState?.openDrawer(),
      child: Scaffold(
        key: _scaffoldKey,
        body: widget.child,
        onDrawerChanged: widget.onDrawerChanged,
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
