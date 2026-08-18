import 'dart:typed_data';

import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/clients/presentation/client_workspace_panels.dart';
import 'package:ai_lab/features/documents/application/document_open_service.dart';
import 'package:ai_lab/features/documents/application/documents_providers.dart';
import 'package:ai_lab/features/documents/application/documents_repository.dart';
import 'package:ai_lab/features/documents/data/document_content.dart';
import 'package:ai_lab/features/documents/domain/document.dart';
import 'package:ai_lab/features/documents/domain/document_filters.dart';
import 'package:ai_lab/features/documents/domain/document_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

void main() {
  testWidgets('documents stay lazy and collapse does not reload', (
    WidgetTester tester,
  ) async {
    final _PanelRepository repository = _PanelRepository();
    await _pumpPanel(tester, repository);

    expect(find.text('Dokumenty'), findsOneWidget);
    expect(find.text('Maile'), findsOneWidget);
    expect(repository.calls, isEmpty);

    await tester.tap(find.byKey(const Key('client-documents-toggle')));
    await tester.pumpAndSettle();
    expect(repository.calls, hasLength(1));
    expect(repository.calls.single.filters.clientId, 7);
    expect(repository.calls.single.limit, 10);
    expect(find.text('12 dokumentów'), findsOneWidget);
    expect(find.text('1–10 z 12'), findsOneWidget);
    expect(find.text('client-7-document-1.pdf'), findsOneWidget);
    expect(find.text('other-client.pdf'), findsNothing);

    await tester.tap(find.byKey(const Key('client-documents-toggle')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('client-documents-toggle')));
    await tester.pumpAndSettle();
    expect(repository.calls, hasLength(1));
  });

  testWidgets('client document pagination uses distinct server pages', (
    WidgetTester tester,
  ) async {
    final _PanelRepository repository = _PanelRepository();
    await _pumpPanel(tester, repository);
    await tester.tap(find.byKey(const Key('client-documents-toggle')));
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.byKey(const Key('client-documents-next')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('client-documents-next')));
    await tester.pumpAndSettle();

    expect(repository.calls, hasLength(2));
    expect(repository.calls.last.skip, 10);
    expect(find.text('11–12 z 12'), findsOneWidget);
    expect(find.text('client-7-document-11.pdf'), findsOneWidget);
    expect(find.text('client-7-document-1.pdf'), findsNothing);

    await tester.ensureVisible(
      find.byKey(const Key('client-documents-previous')),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('client-documents-previous')));
    await tester.pumpAndSettle();
    expect(find.text('1–10 z 12'), findsOneWidget);
  });

  testWidgets('empty documents are a normal panel state', (
    WidgetTester tester,
  ) async {
    final _PanelRepository repository = _PanelRepository(empty: true);
    await _pumpPanel(tester, repository);
    await tester.tap(find.byKey(const Key('client-documents-toggle')));
    await tester.pumpAndSettle();

    expect(
      find.text('Brak dokumentów przypisanych do tego klienta.'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('client-documents-error')), findsNothing);
  });

  testWidgets('documents error remains isolated from client content', (
    WidgetTester tester,
  ) async {
    final _PanelRepository repository = _PanelRepository(failList: true);
    await _pumpPanel(
      tester,
      repository,
      clientMarker: 'Dane podstawowe klienta pozostają widoczne',
    );
    await tester.tap(find.byKey(const Key('client-documents-toggle')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('client-documents-error')), findsOneWidget);
    expect(
      find.text('Dane podstawowe klienta pozostają widoczne'),
      findsOneWidget,
    );
    expect(find.text('Spróbuj ponownie'), findsOneWidget);
  });

  testWidgets('open action delegates to shared DocumentOpenService', (
    WidgetTester tester,
  ) async {
    final _PanelRepository repository = _PanelRepository();
    int openerCalls = 0;
    final DocumentOpenService openService = DocumentOpenService(
      repository,
      opener: (DocumentContent content, int documentId) async {
        openerCalls++;
        expect(documentId, 1);
      },
    );
    await _pumpPanel(tester, repository, openService: openService);
    await tester.tap(find.byKey(const Key('client-documents-toggle')));
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.byKey(const Key('client-document-open-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('client-document-open-1')));
    await tester.pumpAndSettle();

    expect(repository.contentCalls, 1);
    expect(openerCalls, 1);
  });

  testWidgets('full repository link preserves client id and visible name', (
    WidgetTester tester,
  ) async {
    final _PanelRepository repository = _PanelRepository();
    final GoRouter router = GoRouter(
      initialLocation: '/client',
      routes: <RouteBase>[
        GoRoute(
          path: '/client',
          builder: (_, _) => const Scaffold(
            body: SingleChildScrollView(
              child: ClientDocumentsPanel(
                clientId: 7,
                clientName: 'Klient Test',
              ),
            ),
          ),
        ),
        GoRoute(
          path: '/documents',
          builder: (_, GoRouterState state) => Scaffold(
            body: Text(
              'filter=${state.uri.queryParameters['client_id']} '
              'name=${state.uri.queryParameters['client_name']}',
            ),
          ),
        ),
      ],
    );
    addTearDown(router.dispose);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider.overrideWith(_TestAuthController.new),
          documentsRepositoryProvider.overrideWithValue(repository),
        ],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('client-documents-toggle')));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('client-documents-all')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('client-documents-all')));
    await tester.pumpAndSettle();

    expect(find.text('filter=7 name=Klient Test'), findsOneWidget);
  });
}

Future<void> _pumpPanel(
  WidgetTester tester,
  _PanelRepository repository, {
  DocumentOpenService? openService,
  String? clientMarker,
}) async {
  tester.view.physicalSize = const Size(390, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authControllerProvider.overrideWith(_TestAuthController.new),
        documentsRepositoryProvider.overrideWithValue(repository),
        if (openService != null)
          documentOpenServiceProvider.overrideWithValue(openService),
      ],
      child: MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: Column(
              children: <Widget>[
                if (clientMarker != null) Text(clientMarker),
                const ClientWorkspacePanels(
                  clientId: 7,
                  clientName: 'Klient Test',
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

const AuthSession _session = AuthSession(
  accessToken: 'token',
  tokenType: 'Bearer',
);

class _TestAuthController extends AuthController {
  @override
  Future<AuthState> build() async =>
      const AuthState(session: _session, user: null);
}

class _RepositoryCall {
  const _RepositoryCall({
    required this.filters,
    required this.skip,
    required this.limit,
  });

  final DocumentFilters filters;
  final int skip;
  final int limit;
}

class _PanelRepository extends DocumentsRepository {
  _PanelRepository({this.empty = false, this.failList = false});

  final bool empty;
  final bool failList;
  final List<_RepositoryCall> calls = <_RepositoryCall>[];
  int contentCalls = 0;

  @override
  Future<DocumentPage> fetchDocuments({
    required AuthSession session,
    required DocumentFilters filters,
    String search = '',
    int skip = 0,
    int limit = 50,
  }) async {
    calls.add(_RepositoryCall(filters: filters, skip: skip, limit: limit));
    if (failList) throw StateError('documents unavailable');
    if (empty) {
      return DocumentPage(
        items: const <RepositoryDocument>[],
        total: 0,
        skip: skip,
        limit: limit,
      );
    }

    final int clientId = filters.clientId ?? -1;
    final int end = (skip + limit).clamp(0, 12);
    final List<RepositoryDocument> items = <RepositoryDocument>[
      for (int index = skip; index < end; index++)
        _document(id: index + 1, clientId: clientId),
    ];
    return DocumentPage(items: items, total: 12, skip: skip, limit: limit);
  }

  @override
  Future<RepositoryDocument> fetchDocument({
    required AuthSession session,
    required int documentId,
  }) async => _document(id: documentId, clientId: 7);

  @override
  Future<DocumentContent> fetchContent({
    required AuthSession session,
    required RepositoryDocument document,
    void Function(int received, int total)? onProgress,
  }) async {
    contentCalls++;
    onProgress?.call(3, 3);
    return DocumentContent(
      bytes: Uint8List.fromList(<int>[1, 2, 3]),
      fileName: document.displayName,
      contentType: document.contentType,
    );
  }
}

RepositoryDocument _document({required int id, required int clientId}) {
  return RepositoryDocument(
    id: id,
    originalFilename: 'client-$clientId-document-$id.pdf',
    contentType: 'application/pdf',
    fileSize: 2048,
    sourceType: 'gmail',
    clientId: clientId,
    clientName: 'Klient Test',
    processingStatus: 'processed',
    metadataStatus: 'complete',
    matchStatus: 'matched',
    archiveDepth: 0,
    createdAt: DateTime.utc(2026, 8, 15),
    updatedAt: DateTime.utc(2026, 8, 15),
  );
}
