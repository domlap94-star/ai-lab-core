import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/auth/domain/current_user.dart';
import 'package:ai_lab/features/global_search/application/global_search_providers.dart';
import 'package:ai_lab/features/global_search/data/global_search_api.dart';
import 'package:ai_lab/features/global_search/domain/global_search.dart';
import 'package:ai_lab/features/global_search/presentation/global_search_page.dart';
import 'package:ai_lab/features/dashboard/presentation/dashboard_page.dart';
import 'package:ai_lab/features/dashboard/application/dashboard_providers.dart';
import 'package:ai_lab/features/system_status/application/system_status_provider.dart';
import 'package:ai_lab/features/system_status/domain/backend_status.dart';
import 'package:ai_lab/features/tasks/application/tasks_providers.dart';
import 'package:ai_lab/features/tasks/domain/work_item.dart';
import 'package:ai_lab/core/widgets/app_shell.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

class _AuthController extends AuthController {
  @override
  Future<AuthState> build() async => const AuthState(
    session: AuthSession(accessToken: 'test-token', tokenType: 'Bearer'),
    user: CurrentUser(
      id: 1,
      username: 'tester',
      email: 'tester@example.com',
      role: 'User',
      isActive: true,
      mustChangePassword: false,
      passwordResetRequested: false,
    ),
  );
}

class _Gateway implements GlobalSearchGateway {
  _Gateway({required this.page, this.failures = 0});
  final GlobalSearchPageData page;
  int failures;
  final List<String> queries = <String>[];
  final List<GlobalSearchType?> types = <GlobalSearchType?>[];

  @override
  Future<GlobalSearchPageData> search({
    required AuthSession session,
    required String query,
    GlobalSearchType? type,
    int skip = 0,
    int limit = 25,
    CancelToken? cancelToken,
  }) async {
    queries.add(query);
    types.add(type);
    if (failures > 0) {
      failures--;
      throw DioException(
        requestOptions: RequestOptions(path: '/api/v1/search'),
        type: DioExceptionType.connectionError,
      );
    }
    return page;
  }
}

void main() {
  test('result parser keeps bounded display contract and exact route', () {
    final result = GlobalSearchResult.fromJson(<String, dynamic>{
      'type': 'email',
      'id': 12,
      'title': 'Temat',
      'subtitle': 'received · Klient',
      'snippet': 'Krótki fragment',
      'score': 0.86,
      'match_reason': 'email_subject',
      'match_reasons': <String>['email_subject'],
      'client_id': 3,
      'route': '/clients/3?email_source_id=12',
      'raw_payload': <String, dynamic>{'secret': true},
    });
    expect(result.type, GlobalSearchType.email);
    expect(result.route, '/clients/3?email_source_id=12');
    expect(result.snippet, 'Krótki fragment');
  });

  test('client result parses canonical workflow projection', () {
    final result = GlobalSearchResult.fromJson(<String, dynamic>{
      'type': 'client',
      'id': 3,
      'title': 'Klient',
      'score': 1,
      'match_reason': 'name',
      'match_reasons': <String>['name'],
      'client_id': 3,
      'client_workflow_status': 'inspection',
      'client_workflow_status_label': 'Oględziny',
      'client_workflow_effective_date': '2026-08-19',
      'route': '/clients/3',
    });
    expect(result.clientWorkflowStatus, 'inspection');
    expect(result.clientWorkflowStatusLabel, 'Oględziny');
    expect(result.clientWorkflowEffectiveDate, DateTime(2026, 8, 19));
  });

  testWidgets('debounces, filters and opens exact result route', (
    WidgetTester tester,
  ) async {
    final gateway = _Gateway(page: _page());
    final router = _router();
    addTearDown(router.dispose);
    await _pump(tester, router, gateway, const Size(390, 900));

    final field = find.byKey(const Key('global-search-field'));
    await tester.enterText(field, 'o');
    await tester.pump(const Duration(milliseconds: 100));
    await tester.enterText(field, 'orion');
    await tester.pump(const Duration(milliseconds: 319));
    expect(gateway.queries, isEmpty);
    await tester.pump(const Duration(milliseconds: 2));
    await _pumpResponse(tester);
    expect(gateway.queries, <String>['orion']);
    expect(find.byKey(const Key('global-search-client-3')), findsOneWidget);
    expect(find.text('Dopasowanie: nazwa, e-mail'), findsOneWidget);
    expect(find.text('Oględziny'), findsOneWidget);
    expect(find.text('19.08.2026, 12:34'), findsOneWidget);
    expect(tester.takeException(), isNull);

    await tester.tap(find.byKey(const Key('global-search-filter-client')));
    await tester.pump(const Duration(milliseconds: 330));
    await _pumpResponse(tester);
    expect(gateway.types.last, GlobalSearchType.client);

    await tester.tap(find.byKey(const Key('global-search-client-3')));
    await _pumpResponse(tester);
    expect(router.routerDelegate.currentConfiguration.uri.path, '/clients/3');
    expect(
      router
          .routerDelegate
          .currentConfiguration
          .uri
          .queryParameters['return_to'],
      '/search',
    );
  });

  testWidgets('friendly error retries read without exposing DioException', (
    WidgetTester tester,
  ) async {
    final gateway = _Gateway(page: _page(), failures: 1);
    final router = _router();
    addTearDown(router.dispose);
    await _pump(tester, router, gateway, const Size(360, 800));
    await tester.enterText(
      find.byKey(const Key('global-search-field')),
      'orion',
    );
    await tester.pump(const Duration(milliseconds: 330));
    await _pumpResponse(tester);
    expect(find.textContaining('Brak połączenia z serwerem'), findsOneWidget);
    expect(find.textContaining('DioException'), findsNothing);
    await tester.tap(find.byKey(const Key('global-search-retry')));
    await _pumpResponse(tester);
    expect(find.byKey(const Key('global-search-client-3')), findsOneWidget);
    expect(gateway.queries.length, 2);
  });

  testWidgets('Dashboard opens the shared Global Search without loading data', (
    WidgetTester tester,
  ) async {
    final gateway = _Gateway(page: _page());
    final router = _dashboardRouter();
    addTearDown(router.dispose);
    await _pump(tester, router, gateway, const Size(390, 900));

    expect(gateway.queries, isEmpty);
    expect(
      find.byKey(const Key('dashboard-global-search-bar')),
      findsOneWidget,
    );
    await tester.tap(
      find.descendant(
        of: find.byKey(const Key('dashboard-global-search-bar')),
        matching: find.byType(EditableText),
      ),
    );
    await tester.pumpAndSettle();

    expect(router.routerDelegate.currentConfiguration.uri.path, '/search');
    expect(find.byKey(const Key('global-search-field')), findsOneWidget);
    expect(gateway.queries, isEmpty);
  });

  testWidgets('Dashboard hands query to Global Search and runs it once', (
    WidgetTester tester,
  ) async {
    final gateway = _Gateway(page: _page());
    final router = _dashboardRouter();
    addTearDown(router.dispose);
    await _pump(tester, router, gateway, const Size(1200, 900));

    tester
        .widget<SearchBar>(find.byKey(const Key('dashboard-global-search-bar')))
        .onSubmitted!('  orion  ');
    await tester.pumpAndSettle();
    await _pumpResponse(tester);

    expect(router.routerDelegate.currentConfiguration.uri.path, '/search');
    expect(
      router.routerDelegate.currentConfiguration.uri.queryParameters['q'],
      'orion',
    );
    expect(
      tester
          .widget<TextField>(find.byKey(const Key('global-search-field')))
          .controller!
          .text,
      'orion',
    );
    expect(gateway.queries, <String>['orion']);

    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
    expect(router.routerDelegate.currentConfiguration.uri.path, '/dashboard');
  });

  for (final size in <Size>[
    const Size(360, 800),
    const Size(390, 900),
    const Size(600, 900),
    const Size(1200, 900),
  ]) {
    testWidgets('Dashboard search bar is responsive at $size', (
      WidgetTester tester,
    ) async {
      final gateway = _Gateway(page: _page());
      final router = _dashboardRouter();
      addTearDown(router.dispose);
      await _pump(tester, router, gateway, size);

      expect(
        find.byKey(const Key('dashboard-global-search-bar')),
        findsOneWidget,
      );
      expect(gateway.queries, isEmpty);
      expect(tester.takeException(), isNull);
    });
  }

  for (final size in <Size>[
    const Size(360, 800),
    const Size(390, 900),
    const Size(600, 900),
    const Size(1200, 900),
  ]) {
    testWidgets('search is responsive without overflow at $size', (
      WidgetTester tester,
    ) async {
      final gateway = _Gateway(page: _page());
      final router = _router();
      addTearDown(router.dispose);
      await _pump(tester, router, gateway, size);
      await tester.enterText(
        find.byKey(const Key('global-search-field')),
        'orion',
      );
      await tester.pump(const Duration(milliseconds: 330));
      await _pumpResponse(tester);
      expect(find.byKey(const Key('global-search-results')), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }
}

Future<void> _pumpResponse(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 500));
}

Future<void> _pump(
  WidgetTester tester,
  GoRouter router,
  GlobalSearchGateway gateway,
  Size size,
) async {
  tester.view.devicePixelRatio = 1;
  tester.view.physicalSize = size;
  addTearDown(tester.view.resetDevicePixelRatio);
  addTearDown(tester.view.resetPhysicalSize);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authControllerProvider.overrideWith(_AuthController.new),
        globalSearchGatewayProvider.overrideWithValue(gateway),
        backendStatusProvider.overrideWith(
          (Ref ref) async => const BackendStatus(
            isOnline: true,
            application: 'AI-Lab',
            version: 'test',
            environment: 'test',
            debug: false,
            latencyMilliseconds: 1,
            baseUrl: 'http://test',
          ),
        ),
        dashboardRecentMailProvider.overrideWith((Ref ref) async => []),
        dashboardRecentDocumentsProvider.overrideWith((Ref ref) async => []),
        dashboardRecentActivityProvider.overrideWith((Ref ref) async => []),
        calendarMonthProvider.overrideWith(
          (Ref ref, DateTime month) async => CalendarMonthData(
            year: month.year,
            month: month.month,
            items: const [],
            total: 0,
            dayCounts: const {},
            truncated: false,
          ),
        ),
      ],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
}

GoRouter _router() => GoRouter(
  initialLocation: '/search',
  routes: <RouteBase>[
    GoRoute(path: '/search', builder: (_, _) => const GlobalSearchPage()),
    GoRoute(
      path: '/clients/:id',
      builder: (_, state) => Scaffold(
        appBar: AppBar(),
        body: Text('Client ${state.pathParameters['id']}'),
      ),
    ),
  ],
);

GoRouter _dashboardRouter() => GoRouter(
  initialLocation: '/dashboard',
  routes: <RouteBase>[
    ShellRoute(
      builder: (_, state, child) => AppShell(
        currentLocation: state.uri.toString(),
        androidBackPolicyOverride: true,
        child: child,
      ),
      routes: <RouteBase>[
        GoRoute(path: '/dashboard', builder: (_, _) => const DashboardPage()),
        GoRoute(
          path: '/search',
          builder: (_, state) => GlobalSearchPage(
            initialQuery: state.uri.queryParameters['q'] ?? '',
          ),
        ),
      ],
    ),
  ],
);

GlobalSearchPageData _page() => GlobalSearchPageData(
  items: <GlobalSearchResult>[
    GlobalSearchResult(
      type: GlobalSearchType.client,
      id: 3,
      title: 'Bardzo długa nazwa klienta bez ryzyka overflow',
      subtitle: 'Warszawa',
      snippet: 'orion@example.com',
      score: 1,
      matchReason: 'name',
      matchReasons: <String>['name', 'email'],
      route: '/clients/3',
      clientId: 3,
      occurredAt: DateTime(2026, 8, 19, 12, 34),
      clientWorkflowStatus: 'inspection',
      clientWorkflowStatusLabel: 'Oględziny',
      clientWorkflowEffectiveDate: DateTime.utc(2026, 8, 19),
    ),
    const GlobalSearchResult(
      type: GlobalSearchType.document,
      id: 9,
      title: 'bardzo-dluga-nazwa-dokumentu-orion.pdf',
      score: 0.7,
      matchReason: 'document_text',
      matchReasons: <String>['document_text', 'semantic'],
      route: '/documents?document_id=9',
    ),
  ],
  skip: 0,
  limit: 25,
  hasMore: false,
  semanticStatus: 'available',
);
