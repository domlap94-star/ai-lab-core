import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/inspections/application/inspections_providers.dart';
import 'package:ai_lab/features/inspections/data/inspections_api.dart';
import 'package:ai_lab/features/inspections/domain/inspection.dart';
import 'package:ai_lab/features/inspections/presentation/inspection_details_page.dart';
import 'package:ai_lab/features/inspections/presentation/inspection_form_dialog.dart';
import 'package:ai_lab/features/inspections/presentation/inspections_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

Map<String, dynamic> _inspectionJson() => <String, dynamic>{
  'id': 12,
  'project_id': null,
  'project_name': null,
  'client_id': 3,
  'client_name': 'Klient A',
  'title': 'Wizja lokalna — Klient A',
  'status': 'planned',
  'scheduled_at': '2026-08-18T10:00:00Z',
  'started_at': null,
  'completed_at': null,
  'notes': 'Notatka wizji',
  'latitude': 52.2297,
  'longitude': 21.0122,
  'location_accuracy_m': 5.0,
  'created_at': '2026-08-17T10:00:00Z',
  'updated_at': '2026-08-17T10:00:00Z',
  'deleted_at': null,
};

Inspection _inspection() => Inspection.fromJson(_inspectionJson());

void main() {
  test('inspection response preserves client-only status and GPS location', () {
    final inspection = _inspection();
    expect(inspection.status, InspectionStatus.planned);
    expect(inspection.projectId, isNull);
    expect(inspection.clientId, 3);
    expect(inspection.location, contains('52.22970'));
  });

  test('InspectionsApi sends server-side filters and JWT for CRUD', () async {
    final dio = Dio(BaseOptions(baseUrl: 'https://example.test'));
    final requests = <RequestOptions>[];
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          requests.add(options);
          if (options.method == 'DELETE') {
            handler.resolve(
              Response<void>(requestOptions: options, statusCode: 204),
            );
            return;
          }
          final data =
              options.method == 'GET' && options.path.endsWith('inspections')
              ? <String, dynamic>{
                  'items': <Map<String, dynamic>>[_inspectionJson()],
                  'total': 1,
                  'skip': 0,
                  'limit': 50,
                }
              : _inspectionJson();
          handler.resolve(
            Response<Map<String, dynamic>>(
              requestOptions: options,
              statusCode: options.method == 'POST' ? 201 : 200,
              data: data,
            ),
          );
        },
      ),
    );
    const session = AuthSession(accessToken: 'token', tokenType: 'bearer');
    final api = InspectionsApi(dio);
    await api.list(
      session,
      search: 'elewacji',
      clientId: 3,
      status: InspectionStatus.planned,
      dateFrom: DateTime.utc(2026, 8, 17),
      dateTo: DateTime.utc(2026, 8, 19),
    );
    await api.get(session, 12);
    await api.create(session, <String, dynamic>{'client_id': 3});
    await api.update(session, 12, <String, dynamic>{'status': 'completed'});
    await api.delete(session, 12);

    expect(requests.first.queryParameters.containsKey('project_id'), isFalse);
    expect(requests.first.queryParameters, containsPair('client_id', 3));
    expect(requests.first.queryParameters, containsPair('status', 'planned'));
    expect(requests.map((request) => request.method), <String>[
      'GET',
      'GET',
      'POST',
      'PATCH',
      'DELETE',
    ]);
    expect(
      requests.every(
        (request) => request.headers['Authorization'] == 'bearer token',
      ),
      isTrue,
    );
  });

  testWidgets('create form requires only client and has no project or title', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: InspectionFormDialog(clientId: 3, clientName: 'Klient A'),
        ),
      ),
    );
    expect(find.text('Klient A'), findsOneWidget);
    expect(find.text('Realizacja'), findsNothing);
    expect(find.text('Nazwa wizji'), findsNothing);
    expect(find.text('Szerokość geograficzna'), findsNothing);
    expect(find.text('Długość geograficzna'), findsNothing);
    expect(find.text('Dokładność GPS (m)'), findsNothing);
    expect(find.text('Zapisz'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('edit form has no project or manual title', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: InspectionFormDialog(inspection: _inspection())),
      ),
    );
    expect(find.text('Edytuj wizję lokalną'), findsOneWidget);
    expect(find.text('Realizacja'), findsNothing);
    expect(find.text('Nazwa wizji'), findsNothing);
    expect(find.text('Szerokość geograficzna'), findsNothing);
    expect(find.text('Długość geograficzna'), findsNothing);
    expect(find.text('Dokładność GPS (m)'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'details are mobile-safe, expose upload and preserve Android Back',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final router = GoRouter(
        initialLocation: '/inspections/12',
        routes: <RouteBase>[
          GoRoute(
            path: '/inspections',
            builder: (_, _) => const Scaffold(body: Text('Lista wizji')),
          ),
          GoRoute(
            path: '/inspections/:id',
            builder: (_, _) => const InspectionDetailsPage(inspectionId: 12),
          ),
        ],
      );
      addTearDown(router.dispose);
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            inspectionDetailsProvider(
              12,
            ).overrideWith((ref) async => _inspection()),
          ],
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Wizja lokalna'), findsWidgets);
      expect(find.textContaining('Realizacja:'), findsNothing);
      expect(
        find.byKey(const Key('inspection-document-upload')),
        findsOneWidget,
      );
      expect(find.text('Zakończ'), findsOneWidget);
      expect(tester.takeException(), isNull);

      await tester.tap(find.text('Usuń wizję'));
      await tester.pumpAndSettle();
      expect(find.text('Usunąć wizję lokalną?'), findsOneWidget);
      await tester.tap(find.text('Anuluj'));
      await tester.pumpAndSettle();
      expect(find.text('Usunąć wizję lokalną?'), findsNothing);

      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(find.text('Lista wizji'), findsOneWidget);
    },
  );

  testWidgets('global list exposes filters and pagination at mobile width', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    const query = InspectionQuery();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          inspectionsPageProvider(query).overrideWith(
            (ref) async => const InspectionPage(
              items: <Inspection>[],
              total: 0,
              skip: 0,
              limit: 50,
            ),
          ),
        ],
        child: const MaterialApp(home: InspectionsPage()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Szukaj wizji'), findsOneWidget);
    expect(find.text('Realizacja ID'), findsNothing);
    expect(find.text('Klient ID'), findsOneWidget);
    expect(find.text('Status'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('inspection timeout is friendly and retry repeats the read', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    var calls = 0;
    const query = InspectionQuery();
    await tester.pumpWidget(
      ProviderScope(
        retry: (_, _) => null,
        overrides: [
          inspectionsPageProvider(query).overrideWith((ref) async {
            calls++;
            if (calls == 1) {
              throw DioException.connectionTimeout(
                timeout: const Duration(seconds: 30),
                requestOptions: RequestOptions(path: '/inspections'),
              );
            }
            return const InspectionPage(
              items: <Inspection>[],
              total: 0,
              skip: 0,
              limit: 50,
            );
          }),
        ],
        child: const MaterialApp(home: InspectionsPage()),
      ),
    );
    await tester.pumpAndSettle();
    expect(
      find.text('Nie udało się połączyć z serwerem w wymaganym czasie.'),
      findsOneWidget,
    );
    expect(find.textContaining('DioException'), findsNothing);
    await tester.tap(find.text('Spróbuj ponownie'));
    await tester.pumpAndSettle();
    expect(calls, 2);
    expect(find.text('Brak wizji lokalnych.'), findsOneWidget);
  });
}
