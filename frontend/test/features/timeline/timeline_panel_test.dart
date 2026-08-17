import 'package:ai_lab/features/timeline/application/timeline_providers.dart';
import 'package:ai_lab/features/timeline/domain/timeline.dart';
import 'package:ai_lab/features/timeline/presentation/timeline_panel.dart';
import 'package:ai_lab/features/documents/data/documents_api.dart';
import 'package:ai_lab/features/documents/domain/document_filters.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

void main() {
  test('timeline response keeps bounded display fields only', () {
    final event = TimelineEvent.fromJson(<String, dynamic>{
      'stable_key': 'email:7',
      'event_type': 'email_received',
      'occurred_at': '2026-08-17T10:00:00Z',
      'title': 'Odebrano wiadomość',
      'summary': 'Temat wiadomości',
      'client_id': 3,
      'project_id': null,
      'inspection_id': null,
      'document_id': null,
      'source_type': 'candidate_source',
      'source_id': 7,
      'actor_user_id': null,
      'metadata': <String, dynamic>{'direction': 'received'},
    });
    expect(event.summary, 'Temat wiadomości');
    expect(event.metadata, isNot(contains('raw_payload')));
    expect(event.metadata, isNot(contains('body')));
    expect(
      DocumentsApi.buildQueryParameters(
        filters: const DocumentFilters(documentId: 91),
      )['document_id'],
      91,
    );
  });

  testWidgets('client timeline is lazy, responsive and loads more', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    const firstRequest = TimelineRequest(scope: TimelineScope.client, id: 3);
    const expandedRequest = TimelineRequest(
      scope: TimelineScope.client,
      id: 3,
      limit: 40,
    );
    final initial = _page(20, total: 21);
    final expanded = _page(21, total: 21);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          timelinePageProvider(
            firstRequest,
          ).overrideWith((ref) async => initial),
          timelinePageProvider(
            expandedRequest,
          ).overrideWith((ref) async => expanded),
        ],
        child: const MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: TimelinePanel(
                scope: TimelineScope.client,
                id: 3,
                title: 'Oś czasu',
              ),
            ),
          ),
        ),
      ),
    );
    expect(find.text('Zdarzenie 0'), findsNothing);
    await tester.tap(find.byKey(const Key('timeline-toggle')));
    await tester.pumpAndSettle();
    expect(find.text('Zdarzenie 0'), findsOneWidget);
    expect(find.byKey(const Key('timeline-load-more')), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.ensureVisible(find.byKey(const Key('timeline-load-more')));
    await tester.tap(find.byKey(const Key('timeline-load-more')));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Zdarzenie 20'));
    expect(find.text('Zdarzenie 20'), findsOneWidget);
    expect(find.byKey(const Key('timeline-load-more')), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'project timeline opens document deep link and Android back works',
    (tester) async {
      const request = TimelineRequest(scope: TimelineScope.project, id: 8);
      final router = GoRouter(
        initialLocation: '/projects/8',
        routes: <RouteBase>[
          GoRoute(path: '/projects', builder: (_, _) => const Text('Projects')),
          GoRoute(
            path: '/projects/:id',
            builder: (_, _) => const Scaffold(
              body: TimelinePanel(
                scope: TimelineScope.project,
                id: 8,
                title: 'Oś czasu realizacji',
              ),
            ),
          ),
          GoRoute(
            path: '/documents',
            builder: (_, state) =>
                Text('Document ${state.uri.queryParameters['document_id']}'),
          ),
        ],
      );
      addTearDown(router.dispose);
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            timelinePageProvider(request).overrideWith(
              (ref) async => TimelinePage(
                items: <TimelineEvent>[_event(1, documentId: 91, projectId: 8)],
                total: 1,
                skip: 0,
                limit: 20,
              ),
            ),
          ],
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.tap(find.byKey(const Key('timeline-toggle')));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Otwórz źródło'));
      await tester.pumpAndSettle();
      expect(find.text('Document 91'), findsOneWidget);
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(find.text('Oś czasu realizacji'), findsOneWidget);
    },
  );
}

TimelinePage _page(int count, {required int total}) => TimelinePage(
  items: List<TimelineEvent>.generate(count, (index) => _event(index)),
  total: total,
  skip: 0,
  limit: count <= 20 ? 20 : 40,
);

TimelineEvent _event(
  int index, {
  int? documentId,
  int? projectId,
}) => TimelineEvent(
  stableKey: 'document:$index',
  eventType: 'document_added',
  occurredAt: DateTime.utc(2026, 8, 17).subtract(Duration(minutes: index)),
  title: 'Zdarzenie $index',
  summary: index == 0
      ? 'Bardzo długi opis osi czasu, który nie może powodować przepełnienia mobilnego interfejsu.'
      : null,
  clientId: 3,
  projectId: projectId,
  documentId: documentId,
  sourceType: 'document',
  sourceId: index,
);
