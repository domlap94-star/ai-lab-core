import 'package:ai_lab/features/clients/application/client_list_view_memory.dart';
import 'package:ai_lab/features/clients/application/clients_controller.dart';
import 'package:ai_lab/features/clients/application/clients_providers.dart';
import 'package:ai_lab/features/clients/data/client_response.dart';
import 'package:ai_lab/features/clients/domain/client.dart';
import 'package:ai_lab/features/clients/domain/client_page.dart';
import 'package:ai_lab/features/clients/domain/industry.dart';
import 'package:ai_lab/features/clients/presentation/client_details_page.dart';
import 'package:ai_lab/features/clients/presentation/clients_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

final Client _client = Client(
  id: 123,
  clientType: ClientType.person,
  name: 'Klient testowy',
  countryCode: 'PL',
  sourceRecordDate: DateTime(2025, 1, 17),
  createdAt: DateTime.utc(2026, 8, 14, 12),
  updatedAt: DateTime.utc(2026, 8, 14, 12),
);

class _HotfixClientsController extends ClientsController {
  int previousCalls = 0;
  int nextCalls = 0;
  ClientType? lastClientType;
  int? lastIndustryId;

  @override
  Future<ClientPage> build() async {
    return ClientPage(
      items: <Client>[_client],
      total: 125,
      skip: 50,
      limit: 50,
    );
  }

  @override
  Future<void> setFilters({ClientType? clientType, int? industryId}) async {
    lastClientType = clientType;
    lastIndustryId = industryId;
  }

  @override
  Future<void> previousPage() async {
    previousCalls++;
  }

  @override
  Future<void> nextPage() async {
    nextCalls++;
  }

  @override
  Future<void> search(String query) async {}

  @override
  Future<void> clearSearch() async {}

  @override
  Future<void> refresh() async {}
}

ProviderContainer _container() {
  return ProviderContainer(
    overrides: [
      clientsControllerProvider.overrideWith(_HotfixClientsController.new),
      industriesProvider.overrideWith((Ref ref) async {
        return const <Industry>[
          Industry(
            id: 7,
            code: 'construction',
            name: 'Budownictwo',
            isActive: true,
          ),
        ];
      }),
      clientDetailsProvider.overrideWith((Ref ref, int clientId) async {
        return _client;
      }),
    ],
  );
}

void main() {
  setUp(() {
    ClientListViewMemory.instance.reset();
  });

  test('client response parses source date and display falls back to CRM', () {
    final Client parsed = ClientResponse.fromJson(<String, dynamic>{
      'id': 123,
      'client_type': 'person',
      'name': 'Klient testowy',
      'country_code': 'PL',
      'source_record_date': '2025-01-17',
      'created_at': '2026-08-14T12:00:00Z',
      'updated_at': '2026-08-14T12:00:00Z',
    }).toDomain();

    expect(parsed.sourceRecordDate, DateTime(2025, 1, 17));
    expect(parsed.displayCreatedDate, DateTime(2025, 1, 17));

    final Client fallback = Client(
      id: 1,
      clientType: ClientType.other,
      name: 'Manual',
      countryCode: 'PL',
      createdAt: DateTime.utc(2026, 8, 14),
      updatedAt: DateTime.utc(2026, 8, 14),
    );

    expect(fallback.displayCreatedDate, fallback.createdAt);
  });

  testWidgets('server filters are collapsed and remain server-side', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(390, 1200);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final ProviderContainer container = _container();
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: ClientsPage()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Filtry i sortowanie'), findsOneWidget);
    expect(find.text('Typ klienta'), findsNothing);
    expect(find.text('Branża'), findsNothing);
    expect(tester.takeException(), isNull);

    await tester.tap(find.text('Filtry i sortowanie'));
    await tester.pumpAndSettle();

    expect(find.text('Typ klienta'), findsOneWidget);
    expect(find.text('Branża'), findsOneWidget);
    expect(find.text('Lokalizacja'), findsOneWidget);
    expect(find.text('Sortowanie'), findsOneWidget);
    expect(find.text('Status'), findsOneWidget);
    expect(find.text('Wyczyść filtry'), findsOneWidget);
    expect(tester.takeException(), isNull);

    await tester.tap(find.text('Wszystkie typy'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Osoba fizyczna').last);
    await tester.pumpAndSettle();

    final _HotfixClientsController controller =
        container.read(clientsControllerProvider.notifier)
            as _HotfixClientsController;
    expect(controller.lastClientType, ClientType.person);
  });

  testWidgets('pagination is available above and below source-dated cards', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(1200, 2600);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final ProviderContainer container = _container();
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: ClientsPage()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('client-pagination-top')), findsOneWidget);
    expect(find.byKey(const Key('client-pagination-bottom')), findsOneWidget);
    expect(find.text('Dodano: 17.01.2025'), findsOneWidget);
    expect(find.text('2 / 3'), findsNWidgets(2));

    await tester.tap(
      find.descendant(
        of: find.byKey(const Key('client-pagination-top')),
        matching: find.text('Następna'),
      ),
    );
    await tester.tap(
      find.descendant(
        of: find.byKey(const Key('client-pagination-bottom')),
        matching: find.text('Poprzednia'),
      ),
    );

    final _HotfixClientsController controller =
        container.read(clientsControllerProvider.notifier)
            as _HotfixClientsController;
    expect(controller.nextCalls, 1);
    expect(controller.previousCalls, 1);
  });

  testWidgets('push drill-down preserves list state and system back returns', (
    WidgetTester tester,
  ) async {
    final ProviderContainer container = _container();
    addTearDown(container.dispose);
    final GoRouter router = _router(initialLocation: '/clients');
    addTearDown(router.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, 'zachowany filtr');
    final Finder clientCard = find.byKey(
      const ValueKey<String>('client-card-123'),
    );
    await tester.ensureVisible(clientCard);
    final InkWell cardInkWell = tester.widget<InkWell>(clientCard);
    cardInkWell.onTap!();
    await tester.pumpAndSettle();
    expect(find.text('Szczegóły klienta'), findsOneWidget);

    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
    expect(find.text('Klienci'), findsOneWidget);
    expect(find.text('zachowany filtr'), findsOneWidget);
  });

  testWidgets('direct-entry system and AppBar back fall back to client list', (
    WidgetTester tester,
  ) async {
    final ProviderContainer container = _container();
    addTearDown(container.dispose);
    GoRouter router = _router(initialLocation: '/clients/123');

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
    expect(router.routeInformationProvider.value.uri.path, '/clients');

    router.dispose();
    router = _router(initialLocation: '/clients/123');
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Wróć do klientów'));
    await tester.pumpAndSettle();
    expect(router.routeInformationProvider.value.uri.path, '/clients');
    router.dispose();
  });
}

GoRouter _router({required String initialLocation}) {
  return GoRouter(
    initialLocation: initialLocation,
    routes: <RouteBase>[
      GoRoute(path: '/clients', builder: (_, _) => const ClientsPage()),
      GoRoute(
        path: '/clients/:clientId',
        builder: (_, GoRouterState state) => ClientDetailsPage(
          clientId: int.parse(state.pathParameters['clientId']!),
        ),
      ),
    ],
  );
}
