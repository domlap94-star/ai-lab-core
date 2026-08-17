import 'package:ai_lab/core/widgets/app_shell.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues(<String, String>{});
  });

  for (final Size size in <Size>[
    const Size(360, 800),
    const Size(390, 900),
    const Size(600, 900),
  ]) {
    testWidgets('mobile drawer is readable and navigates at $size', (
      WidgetTester tester,
    ) async {
      await _setSurface(tester, size);
      final GoRouter router = _router();
      addTearDown(router.dispose);

      await tester.pumpWidget(_application(router));
      await tester.pumpAndSettle();

      expect(find.byType(NavigationBar), findsNothing);
      expect(
        find.byKey(const Key('mobile-navigation-menu-button')),
        findsOneWidget,
      );

      await _openDrawer(tester);
      expect(find.byType(Drawer), findsOneWidget);
      expect(
        tester
            .widget<ListTile>(find.byKey(const Key('mobile-nav-/dashboard')))
            .selected,
        isTrue,
      );

      for (final NavigationItem item in AppShell.navigationItems) {
        expect(find.byKey(Key('mobile-nav-${item.path}')), findsOneWidget);
        expect(find.text(item.label), findsAtLeast(1));
      }

      await _navigate(tester, router, '/clients');
      await _navigate(tester, router, '/projects');
      await _navigate(tester, router, '/inspections');
      await _navigate(tester, router, '/documents');
      await _navigate(tester, router, '/dashboard');

      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('desktop keeps the existing side navigation', (
    WidgetTester tester,
  ) async {
    await _setSurface(tester, const Size(1200, 900));
    final GoRouter router = _router();
    addTearDown(router.dispose);

    await tester.pumpWidget(_application(router));
    await tester.pumpAndSettle();

    expect(find.byType(NavigationBar), findsNothing);
    expect(find.byType(Drawer), findsNothing);
    expect(
      find.byKey(const Key('mobile-navigation-menu-button')),
      findsNothing,
    );
    for (final NavigationItem item in AppShell.navigationItems) {
      expect(find.text(item.label), findsAtLeast(1));
    }
    expect(tester.takeException(), isNull);
  });

  testWidgets('detail page preserves Back and does not open the drawer', (
    WidgetTester tester,
  ) async {
    await _setSurface(tester, const Size(390, 900));
    final GoRouter router = _router();
    addTearDown(router.dispose);

    await tester.pumpWidget(_application(router));
    await tester.pumpAndSettle();
    router.go('/clients');
    await tester.pumpAndSettle();
    router.push('/clients/42');
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('detail-back')), findsOneWidget);
    expect(
      find.byKey(const Key('mobile-navigation-menu-button')),
      findsNothing,
    );

    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();

    expect(router.routerDelegate.currentConfiguration.uri.path, '/clients');
    final ScaffoldState shell = _shellState(tester);
    expect(shell.isDrawerOpen, isFalse);
    expect(tester.takeException(), isNull);
  });
}

Future<void> _setSurface(WidgetTester tester, Size size) async {
  tester.view.devicePixelRatio = 1;
  tester.view.physicalSize = size;
  addTearDown(tester.view.resetDevicePixelRatio);
  addTearDown(tester.view.resetPhysicalSize);
}

Widget _application(GoRouter router) {
  return ProviderScope(child: MaterialApp.router(routerConfig: router));
}

GoRouter _router() {
  return GoRouter(
    initialLocation: '/dashboard',
    routes: <RouteBase>[
      ShellRoute(
        builder: (BuildContext context, GoRouterState state, Widget child) {
          return AppShell(currentLocation: state.uri.path, child: child);
        },
        routes: <RouteBase>[
          for (final NavigationItem item in AppShell.navigationItems)
            GoRoute(
              path: item.path,
              builder: (BuildContext context, GoRouterState state) {
                return _RootTestPage(label: item.label);
              },
            ),
          GoRoute(
            path: '/clients/:clientId',
            builder: (BuildContext context, GoRouterState state) {
              return Scaffold(
                appBar: AppBar(
                  leading: IconButton(
                    key: const Key('detail-back'),
                    onPressed: context.pop,
                    icon: const Icon(Icons.arrow_back),
                  ),
                  title: const Text('Szczeg\u00f3\u0142y klienta'),
                ),
              );
            },
          ),
        ],
      ),
    ],
  );
}

class _RootTestPage extends StatelessWidget {
  const _RootTestPage({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: AppShell.mobileNavigationLeading(context),
        title: Text(label),
      ),
      body: Center(child: Text('$label test')),
    );
  }
}

Future<void> _openDrawer(WidgetTester tester) async {
  await tester.tap(find.byKey(const Key('mobile-navigation-menu-button')));
  await tester.pumpAndSettle();
}

Future<void> _navigate(
  WidgetTester tester,
  GoRouter router,
  String path,
) async {
  final ScaffoldState shell = _shellState(tester);
  if (!shell.isDrawerOpen) {
    await _openDrawer(tester);
  }

  await tester.tap(find.byKey(Key('mobile-nav-$path')));
  await tester.pumpAndSettle();

  expect(router.routerDelegate.currentConfiguration.uri.path, path);
  expect(shell.isDrawerOpen, isFalse);
  await _openDrawer(tester);
  expect(
    tester.widget<ListTile>(find.byKey(Key('mobile-nav-$path'))).selected,
    isTrue,
  );
}

ScaffoldState _shellState(WidgetTester tester) {
  return tester
      .stateList<ScaffoldState>(find.byType(Scaffold))
      .singleWhere((ScaffoldState state) => state.widget.drawer != null);
}
