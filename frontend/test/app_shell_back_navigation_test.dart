import 'package:ai_lab/core/widgets/app_shell.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('dashboard exit guard requires two attempts within two seconds', () {
    final DashboardExitGuard guard = DashboardExitGuard();
    final DateTime start = DateTime(2026, 8, 17, 12);

    expect(guard.registerBackAttempt(start), isFalse);
    expect(
      guard.isArmed(start.add(const Duration(milliseconds: 1500))),
      isTrue,
    );
    expect(
      guard.registerBackAttempt(start.add(const Duration(milliseconds: 1500))),
      isTrue,
    );

    expect(guard.registerBackAttempt(start), isFalse);
    expect(
      guard.registerBackAttempt(start.add(const Duration(milliseconds: 2100))),
      isFalse,
    );
  });

  testWidgets('every root module returns to Dashboard on Android Back', (
    WidgetTester tester,
  ) async {
    await _setMobileSurface(tester);
    final GoRouter router = _router();
    addTearDown(router.dispose);
    await tester.pumpWidget(_application(router));
    await tester.pumpAndSettle();

    for (final NavigationItem item in AppShell.navigationItems.skip(1)) {
      router.go(item.path);
      await tester.pumpAndSettle();
      expect(_location(router), item.path);

      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(_location(router), '/dashboard');
    }
  });

  testWidgets('settings and nested CRM branches pop one logical level', (
    WidgetTester tester,
  ) async {
    await _setMobileSurface(tester);
    final GoRouter router = _router();
    addTearDown(router.dispose);
    await tester.pumpWidget(_application(router));
    await tester.pumpAndSettle();

    router.go('/settings');
    router.push('/system');
    await tester.pumpAndSettle();
    await _back(tester, router, '/settings');
    await _back(tester, router, '/dashboard');

    router.go('/clients');
    router.push('/clients/7');
    await tester.pumpAndSettle();
    await _back(tester, router, '/clients');
    await _back(tester, router, '/dashboard');

    router.go('/projects');
    router.push('/projects/8');
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('open-project-inspection')));
    await tester.pumpAndSettle();
    expect(
      tester.widget<AppShell>(find.byType(AppShell)).currentLocation,
      '/inspections/9?return_to=%2Fprojects%2F8',
    );
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
    expect(find.text('Szczegóły realizacji 8'), findsWidgets);
    await _back(tester, router, '/projects');
    await _back(tester, router, '/dashboard');
  });

  testWidgets('Drawer root switch discards the previous detail branch', (
    WidgetTester tester,
  ) async {
    await _setMobileSurface(tester);
    final GoRouter router = _router();
    addTearDown(router.dispose);
    await tester.pumpWidget(_application(router));
    await tester.pumpAndSettle();

    router.go('/clients');
    router.push('/clients/7');
    await tester.pumpAndSettle();

    _shellState(tester).openDrawer();
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('mobile-nav-/documents')));
    await tester.pumpAndSettle();
    expect(_location(router), '/documents');

    await _back(tester, router, '/dashboard');
    expect(find.text('Szczegóły klienta 7'), findsNothing);
  });

  testWidgets('Global Search result returns through Search to Dashboard', (
    WidgetTester tester,
  ) async {
    await _setMobileSurface(tester);
    final GoRouter router = _router();
    addTearDown(router.dispose);
    await tester.pumpWidget(_application(router));
    await tester.pumpAndSettle();

    router.push('/search');
    await tester.pumpAndSettle();
    router.go('/clients/7?return_to=%2Fsearch');
    await tester.pumpAndSettle();

    await _back(tester, router, '/search');
    await _back(tester, router, '/dashboard');
  });

  for (final ({String direct, String parent}) route
      in <({String direct, String parent})>[
        (direct: '/clients/7', parent: '/clients'),
        (direct: '/clients/7?email_source_id=456', parent: '/clients'),
        (direct: '/projects/8', parent: '/projects'),
        (direct: '/inspections/9', parent: '/inspections'),
      ]) {
    testWidgets('deep link ${route.direct} falls back through its root', (
      WidgetTester tester,
    ) async {
      await _setMobileSurface(tester);
      final GoRouter router = _router(initialLocation: route.direct);
      addTearDown(router.dispose);
      await tester.pumpWidget(_application(router));
      await tester.pumpAndSettle();

      await _back(tester, router, route.parent);
      await _back(tester, router, '/dashboard');
    });
  }

  testWidgets('Dashboard first Back shows message and arms system pop', (
    WidgetTester tester,
  ) async {
    await _setMobileSurface(tester);
    final GoRouter router = _router();
    addTearDown(router.dispose);
    await tester.pumpWidget(_application(router));
    await tester.pumpAndSettle();

    await tester.binding.handlePopRoute();
    await tester.pump();
    expect(_location(router), '/dashboard');
    expect(find.text('Naciśnij jeszcze raz, aby wyjść'), findsOneWidget);
    expect(_shellPopScope(tester).canPop, isTrue);

    await tester.pump(const Duration(milliseconds: 2100));
    expect(_location(router), '/dashboard');
    expect(_shellPopScope(tester).canPop, isFalse);
  });

  testWidgets('Back closes Drawer before changing the route', (
    WidgetTester tester,
  ) async {
    await _setMobileSurface(tester);
    final GoRouter router = _router(initialLocation: '/clients');
    addTearDown(router.dispose);
    await tester.pumpWidget(_application(router));
    await tester.pumpAndSettle();

    _shellState(tester).openDrawer();
    await tester.pumpAndSettle();
    expect(_shellState(tester).isDrawerOpen, isTrue);

    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
    expect(_shellState(tester).isDrawerOpen, isFalse);
    expect(_location(router), '/clients');
  });

  testWidgets('Windows does not use Android double-back messaging', (
    WidgetTester tester,
  ) async {
    await _setMobileSurface(tester);
    final GoRouter router = _router(androidBackPolicy: false);
    addTearDown(router.dispose);
    await tester.pumpWidget(_application(router));
    await tester.pumpAndSettle();

    expect(_shellPopScope(tester).canPop, isTrue);
    expect(find.text('Naciśnij jeszcze raz, aby wyjść'), findsNothing);
  });
}

Future<void> _setMobileSurface(WidgetTester tester) async {
  tester.view.devicePixelRatio = 1;
  tester.view.physicalSize = const Size(390, 900);
  addTearDown(tester.view.resetDevicePixelRatio);
  addTearDown(tester.view.resetPhysicalSize);
}

Widget _application(GoRouter router) {
  return ProviderScope(child: MaterialApp.router(routerConfig: router));
}

GoRouter _router({
  String initialLocation = '/dashboard',
  bool androidBackPolicy = true,
}) {
  return GoRouter(
    initialLocation: initialLocation,
    routes: <RouteBase>[
      ShellRoute(
        builder: (BuildContext context, GoRouterState state, Widget child) {
          return AppShell(
            currentLocation: state.uri.toString(),
            androidBackPolicyOverride: androidBackPolicy,
            child: child,
          );
        },
        routes: <RouteBase>[
          for (final NavigationItem item in AppShell.navigationItems)
            GoRoute(
              path: item.path,
              builder: (_, _) => _RootPage(label: item.label),
            ),
          GoRoute(
            path: '/search',
            builder: (_, _) => const _RootPage(label: 'Global Search'),
          ),
          GoRoute(
            path: '/system',
            builder: (_, _) => const _DetailPage(
              label: 'Sterowanie systemem',
              fallback: '/settings',
            ),
          ),
          GoRoute(
            path: '/clients/:id',
            builder: (_, GoRouterState state) => _DetailPage(
              label: 'Szczegóły klienta ${state.pathParameters['id']}',
              fallback: '/clients',
            ),
          ),
          GoRoute(
            path: '/projects/:id',
            builder: (_, GoRouterState state) => _DetailPage(
              label: 'Szczegóły realizacji ${state.pathParameters['id']}',
              fallback: '/projects',
            ),
          ),
          GoRoute(
            path: '/inspections/:id',
            builder: (_, GoRouterState state) => _DetailPage(
              label: 'Wizja ${state.pathParameters['id']}',
              fallback: '/inspections',
            ),
          ),
        ],
      ),
    ],
  );
}

class _RootPage extends StatelessWidget {
  const _RootPage({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: AppShell.mobileNavigationLeading(context),
        title: Text(label),
      ),
      body: Center(child: Text('$label root')),
    );
  }
}

class _DetailPage extends StatelessWidget {
  const _DetailPage({required this.label, required this.fallback});

  final String label;
  final String fallback;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(label)),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Text(label),
            if (label == 'Szczegóły realizacji 8')
              FilledButton(
                key: const Key('open-project-inspection'),
                onPressed: () => context.push(
                  AppShell.inspectionPathWithReturn(
                    inspectionId: 9,
                    returnPath: '/projects/8',
                  ),
                ),
                child: const Text('Otwórz wizję'),
              ),
          ],
        ),
      ),
    );
  }
}

Future<void> _back(
  WidgetTester tester,
  GoRouter router,
  String expected,
) async {
  await tester.binding.handlePopRoute();
  await tester.pumpAndSettle();
  expect(_location(router), expected);
}

String _location(GoRouter router) =>
    router.routerDelegate.currentConfiguration.uri.path;

ScaffoldState _shellState(WidgetTester tester) {
  return tester
      .stateList<ScaffoldState>(find.byType(Scaffold))
      .singleWhere((ScaffoldState state) => state.widget.drawer != null);
}

PopScope<Object?> _shellPopScope(WidgetTester tester) {
  return tester.widget<PopScope<Object?>>(find.byType(PopScope<Object?>).first);
}
