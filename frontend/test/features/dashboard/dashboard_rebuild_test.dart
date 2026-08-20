import 'package:ai_lab/core/widgets/app_shell.dart';
import 'package:ai_lab/features/dashboard/application/dashboard_providers.dart';
import 'package:ai_lab/features/dashboard/presentation/dashboard_page.dart';
import 'package:ai_lab/features/documents/domain/document.dart';
import 'package:ai_lab/features/mail/domain/global_mail.dart';
import 'package:ai_lab/features/system_status/application/system_status_provider.dart';
import 'package:ai_lab/features/system_status/domain/backend_status.dart';
import 'package:ai_lab/features/tasks/application/tasks_providers.dart';
import 'package:ai_lab/features/tasks/domain/work_item.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

void main() {
  test('primary navigation removes Sprawy without changing legacy routes', () {
    expect(
      AppShell.navigationItems.any((item) => item.label == 'Sprawy'),
      isFalse,
    );
    expect(
      AppShell.navigationItems.any((item) => item.label == 'Zadania'),
      true,
    );
    expect(AppShell.navigationItems.any((item) => item.label == 'Maile'), true);
  });

  for (final Size size in <Size>[
    const Size(360, 900),
    const Size(390, 900),
    const Size(600, 900),
    const Size(1200, 900),
  ]) {
    testWidgets('live Dashboard is ordered and responsive at $size', (
      WidgetTester tester,
    ) async {
      await _pumpDashboard(tester, size: size);

      final finders = <Finder>[
        find.byKey(const Key('dashboard-calendar-section')),
        find.byKey(const Key('dashboard-mail-section')),
        find.byKey(const Key('dashboard-documents-section')),
        find.byKey(const Key('dashboard-last-activity-section')),
        find.byKey(const Key('dashboard-system-status-section')),
      ];
      for (final finder in finders) {
        expect(finder, findsOneWidget);
      }
      final positions = finders
          .map(tester.getTopLeft)
          .map((p) => p.dy)
          .toList();
      expect(positions, orderedEquals(<double>[...positions]..sort()));
      expect(find.text('Dodaj zadanie'), findsOneWidget);
      expect(find.text('Dodaj absencję'), findsOneWidget);
      expect(find.text('Aktywne sprawy'), findsNothing);
      expect(find.text('Analizy'), findsNothing);
      expect(find.text('Zadania: 0'), findsNothing);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('Mail and Documents use real bounded presentation', (
    WidgetTester tester,
  ) async {
    await _pumpDashboard(
      tester,
      size: const Size(600, 1000),
      mail: <GlobalMailItem>[_mail],
      documents: <RepositoryDocument>[_document],
    );
    expect(find.text('Wiadomość operacyjna'), findsOneWidget);
    expect(find.text('raport.pdf'), findsOneWidget);
    expect(find.byKey(const Key('dashboard-mail-41')), findsOneWidget);
    expect(find.byKey(const Key('dashboard-document-72')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'section errors remain isolated and backend is not falsely offline',
    (WidgetTester tester) async {
      await _pumpDashboard(
        tester,
        size: const Size(390, 900),
        mailFailure: true,
        backendFailure: true,
      );
      expect(
        find.text('Nie udało się wczytać ostatnich wiadomości.'),
        findsOneWidget,
      );
      expect(find.text('Brak dokumentów.'), findsOneWidget);
      expect(find.text('Kalendarz i zadania'), findsOneWidget);
      expect(find.text('Backend: NIEDOSTĘPNY'), findsOneWidget);
      expect(find.text('Backend: OFFLINE'), findsNothing);
    },
  );

  testWidgets('Dashboard refresh invalidates every live section', (
    WidgetTester tester,
  ) async {
    int calendarLoads = 0;
    int mailLoads = 0;
    int documentLoads = 0;
    int healthLoads = 0;
    await _pumpDashboard(
      tester,
      size: const Size(600, 900),
      calendarLoader: (DateTime month) async {
        calendarLoads++;
        return _month(month);
      },
      mailLoader: () async {
        mailLoads++;
        return const <GlobalMailItem>[];
      },
      documentLoader: () async {
        documentLoads++;
        return const <RepositoryDocument>[];
      },
      healthLoader: () async {
        healthLoads++;
        return _status;
      },
    );
    await tester.tap(find.byKey(const Key('dashboard-refresh')));
    await tester.pumpAndSettle();
    expect(calendarLoads, 2);
    expect(mailLoads, 2);
    expect(documentLoads, 2);
    expect(healthLoads, 2);
  });
}

Future<void> _pumpDashboard(
  WidgetTester tester, {
  required Size size,
  List<GlobalMailItem> mail = const <GlobalMailItem>[],
  List<RepositoryDocument> documents = const <RepositoryDocument>[],
  bool mailFailure = false,
  bool backendFailure = false,
  Future<CalendarMonthData> Function(DateTime)? calendarLoader,
  Future<List<GlobalMailItem>> Function()? mailLoader,
  Future<List<RepositoryDocument>> Function()? documentLoader,
  Future<BackendStatus> Function()? healthLoader,
}) async {
  tester.view.devicePixelRatio = 1;
  tester.view.physicalSize = size;
  addTearDown(tester.view.resetDevicePixelRatio);
  addTearDown(tester.view.resetPhysicalSize);
  final router = GoRouter(
    initialLocation: '/dashboard',
    routes: <RouteBase>[
      GoRoute(path: '/dashboard', builder: (_, _) => const DashboardPage()),
      GoRoute(path: '/search', builder: (_, _) => const Scaffold()),
      GoRoute(path: '/mail', builder: (_, _) => const Scaffold()),
      GoRoute(path: '/documents', builder: (_, _) => const Scaffold()),
      GoRoute(path: '/tasks', builder: (_, _) => const Scaffold()),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        calendarMonthProvider.overrideWith((Ref ref, DateTime month) {
          return calendarLoader?.call(month) ?? Future.value(_month(month));
        }),
        dashboardRecentMailProvider.overrideWith((Ref ref) {
          if (mailLoader != null) return mailLoader();
          if (mailFailure) return Future.error(StateError('mail unavailable'));
          return Future.value(mail);
        }),
        dashboardRecentDocumentsProvider.overrideWith((Ref ref) {
          return documentLoader?.call() ?? Future.value(documents);
        }),
        backendStatusProvider.overrideWith((Ref ref) {
          if (healthLoader != null) return healthLoader();
          if (backendFailure) {
            return Future.error(StateError('health unavailable'));
          }
          return Future.value(_status);
        }),
      ],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
}

CalendarMonthData _month(DateTime month) => CalendarMonthData(
  year: month.year,
  month: month.month,
  items: const <CalendarEntry>[],
  total: 0,
  dayCounts: const <String, int>{},
  truncated: false,
);

const BackendStatus _status = BackendStatus(
  isOnline: true,
  application: 'AI-Lab',
  version: 'test',
  environment: 'test',
  debug: false,
  latencyMilliseconds: 5,
  baseUrl: 'https://example.invalid',
);

final GlobalMailItem _mail = GlobalMailItem(
  sourceId: 41,
  messageId: 'message-41',
  direction: 'received',
  readState: 'unread',
  sender: 'sender@example.invalid',
  recipients: const <String>['recipient@example.invalid'],
  subject: 'Wiadomość operacyjna',
  occurredAt: DateTime.utc(2026, 8, 20, 10),
  hasAttachments: false,
  attachmentCount: 0,
);

final RepositoryDocument _document = RepositoryDocument(
  id: 72,
  originalFilename: 'raport.pdf',
  contentType: 'application/pdf',
  fileSize: 1024,
  sourceType: 'manual_upload',
  processingStatus: 'processed',
  metadataStatus: 'ready',
  matchStatus: 'unlinked',
  archiveDepth: 0,
  createdAt: DateTime.utc(2026, 8, 20, 9),
  updatedAt: DateTime.utc(2026, 8, 20, 9),
);
