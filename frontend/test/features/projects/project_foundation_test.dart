import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/projects/application/projects_providers.dart';
import 'package:ai_lab/features/projects/data/projects_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:dio/dio.dart';
import 'package:go_router/go_router.dart';

import 'package:ai_lab/features/projects/domain/project.dart';
import 'package:ai_lab/features/projects/presentation/client_projects_panel.dart';
import 'package:ai_lab/features/projects/presentation/project_details_page.dart';
import 'package:ai_lab/features/projects/presentation/project_form_dialog.dart';
import 'package:ai_lab/features/projects/presentation/projects_page.dart';

Map<String, dynamic> _projectJson({int id = 7}) => <String, dynamic>{
  'id': id,
  'client_id': 3,
  'client_name': 'Klient',
  'name': 'Realizacja A',
  'description': 'Opis',
  'status': 'active',
  'start_date': '2026-08-17',
  'end_date': null,
  'street': 'Polna',
  'building_number': '4',
  'unit_number': null,
  'postal_code': '00-001',
  'city': 'Warszawa',
  'country_code': 'PL',
  'latitude': 52.1,
  'longitude': 21.0,
  'created_at': '2026-08-17T10:00:00Z',
  'updated_at': '2026-08-17T10:00:00Z',
  'deleted_at': null,
};

Project _project() => Project.fromJson(_projectJson());

void main() {
  test(
    'project response preserves client, status and independent location',
    () {
      final project = _project();
      expect(project.status, ProjectStatus.active);
      expect(project.location, contains('Polna'));
      expect(project.clientId, 3);
    },
  );

  testWidgets('project form is usable at mobile width', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: ProjectFormDialog(clientId: 3))),
    );
    expect(find.text('Dodaj realizację'), findsOneWidget);
    expect(find.text('Lokalizacja realizacji'), findsOneWidget);
    expect(find.text('Zapisz'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  test('ProjectsApi sends pagination, search and filters for CRUD', () async {
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
              options.method == 'GET' && options.path.endsWith('projects')
              ? <String, dynamic>{
                  'items': <Map<String, dynamic>>[_projectJson()],
                  'total': 51,
                  'skip': 50,
                  'limit': 50,
                }
              : _projectJson();
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
    final api = ProjectsApi(dio);

    final page = await api.list(
      session,
      search: 'Realizacja',
      clientId: 3,
      status: ProjectStatus.active,
      skip: 50,
      limit: 50,
    );
    await api.get(session, 7);
    await api.create(session, <String, dynamic>{
      'client_id': 3,
      'name': 'Realizacja A',
    });
    await api.update(session, 7, <String, dynamic>{'status': 'completed'});
    await api.delete(session, 7);

    expect(page.total, 51);
    expect(page.skip, 50);
    expect(
      requests.first.queryParameters,
      containsPair('search', 'Realizacja'),
    );
    expect(requests.first.queryParameters, containsPair('client_id', 3));
    expect(requests.first.queryParameters, containsPair('status', 'active'));
    expect(requests.first.queryParameters, containsPair('skip', 50));
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

  testWidgets('project list exposes global filters at mobile width', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    const query = ProjectQuery();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          projectsPageProvider(query).overrideWith(
            (ref) async => const ProjectPage(
              items: <Project>[],
              total: 0,
              skip: 0,
              limit: 50,
            ),
          ),
        ],
        child: const MaterialApp(home: ProjectsPage()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Szukaj realizacji'), findsOneWidget);
    expect(find.text('ID klienta'), findsOneWidget);
    expect(find.text('Status'), findsOneWidget);
    expect(find.byKey(const Key('project-create')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('project 500 is friendly and retry repeats the read', (
    tester,
  ) async {
    var calls = 0;
    const query = ProjectQuery();
    await tester.pumpWidget(
      ProviderScope(
        retry: (_, _) => null,
        overrides: [
          projectsPageProvider(query).overrideWith((ref) async {
            calls++;
            if (calls == 1) {
              throw _dioFailure(500, '/projects');
            }
            return const ProjectPage(
              items: <Project>[],
              total: 0,
              skip: 0,
              limit: 50,
            );
          }),
        ],
        child: const MaterialApp(home: ProjectsPage()),
      ),
    );
    await tester.pumpAndSettle();
    expect(
      find.text('Wystąpił błąd serwera. Spróbuj ponownie.'),
      findsOneWidget,
    );
    expect(find.textContaining('DioException'), findsNothing);
    await tester.tap(find.text('Spróbuj ponownie'));
    await tester.pumpAndSettle();
    expect(calls, 2);
    expect(find.text('Brak realizacji.'), findsOneWidget);
  });

  testWidgets('Client 360 lazily shows projects and create action', (
    tester,
  ) async {
    const query = ProjectQuery(clientId: 3, limit: 20);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          projectsPageProvider(query).overrideWith(
            (ref) async => ProjectPage(
              items: <Project>[_project()],
              total: 1,
              skip: 0,
              limit: 20,
            ),
          ),
        ],
        child: const MaterialApp(
          home: Scaffold(body: ClientProjectsPanel(clientId: 3)),
        ),
      ),
    );
    expect(find.text('Realizacja A'), findsNothing);
    await tester.tap(find.byKey(const Key('client-projects-toggle')));
    await tester.pumpAndSettle();
    expect(find.text('Realizacja A'), findsOneWidget);
    expect(find.text('Dodaj realizację'), findsOneWidget);
  });

  testWidgets('details are responsive and delete can be cancelled', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final router = GoRouter(
      initialLocation: '/projects/7',
      routes: <RouteBase>[
        GoRoute(
          path: '/projects',
          builder: (_, _) => const Scaffold(body: Text('Lista realizacji')),
        ),
        GoRoute(
          path: '/projects/:id',
          builder: (_, _) => const ProjectDetailsPage(projectId: 7),
        ),
      ],
    );
    addTearDown(router.dispose);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          projectDetailsProvider(7).overrideWith((ref) async => _project()),
        ],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Realizacja A'), findsOneWidget);
    expect(find.textContaining('Lokalizacja:'), findsOneWidget);
    expect(find.byKey(const Key('project-document-upload')), findsOneWidget);
    expect(find.text('Wizje lokalne'), findsNothing);
    expect(tester.takeException(), isNull);

    await tester.tap(find.text('Usuń realizację'));
    await tester.pumpAndSettle();
    expect(find.text('Usunąć realizację?'), findsOneWidget);
    await tester.tap(find.text('Anuluj'));
    await tester.pumpAndSettle();
    expect(find.text('Usunąć realizację?'), findsNothing);

    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
    expect(find.text('Lista realizacji'), findsOneWidget);
  });
}

DioException _dioFailure(int status, String path) {
  final request = RequestOptions(path: path);
  return DioException.badResponse(
    statusCode: status,
    requestOptions: request,
    response: Response<void>(requestOptions: request, statusCode: status),
  );
}
