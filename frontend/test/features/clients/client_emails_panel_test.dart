import 'dart:typed_data';

import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/auth/domain/current_user.dart';
import 'package:ai_lab/features/clients/application/client_emails_provider.dart';
import 'package:ai_lab/features/clients/application/client_emails_repository.dart';
import 'package:ai_lab/features/clients/domain/client_email.dart';
import 'package:ai_lab/features/clients/domain/client_email_page.dart';
import 'package:ai_lab/features/clients/presentation/client_emails_panel.dart';
import 'package:ai_lab/features/documents/application/document_open_service.dart';
import 'package:ai_lab/features/documents/application/documents_providers.dart';
import 'package:ai_lab/features/documents/application/documents_repository.dart';
import 'package:ai_lab/features/documents/data/document_content.dart';
import 'package:ai_lab/features/documents/domain/document.dart';
import 'package:ai_lab/features/documents/domain/document_filters.dart';
import 'package:ai_lab/features/documents/domain/document_page.dart';
import 'package:ai_lab/features/mail/data/global_mail_api.dart';
import 'package:ai_lab/features/mail/domain/global_mail.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('emails stay lazy and collapse does not reload at 390 px', (
    WidgetTester tester,
  ) async {
    final _EmailRepository repository = _EmailRepository();
    await _pumpPanel(tester, repository);

    expect(find.text('Maile'), findsOneWidget);
    expect(repository.calls, isEmpty);
    expect(tester.takeException(), isNull);

    await tester.tap(find.byKey(const Key('client-emails-toggle')));
    await tester.pumpAndSettle();
    expect(repository.calls, hasLength(1));
    expect(repository.calls.single.clientId, 7);
    expect(repository.calls.single.limit, 10);
    expect(find.text('12 wiadomości'), findsOneWidget);
    expect(find.text('1–10 z 12'), findsOneWidget);
    expect(find.text('Wysłana'), findsWidgets);
    expect(find.text('Odebrana'), findsWidgets);
    expect(find.text('Nieustalona'), findsWidgets);
    expect(find.text('(bez tematu)'), findsOneWidget);
    expect(find.byKey(const Key('client-email-body-1')), findsNothing);
    expect(tester.takeException(), isNull);

    await tester.tap(find.byKey(const Key('client-emails-toggle')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('client-emails-toggle')));
    await tester.pumpAndSettle();
    expect(repository.calls, hasLength(1));
  });

  testWidgets('message body expands and pagination uses server pages', (
    WidgetTester tester,
  ) async {
    final _EmailRepository repository = _EmailRepository();
    await _pumpPanel(tester, repository);
    await tester.tap(find.byKey(const Key('client-emails-toggle')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('client-email-toggle-1')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('client-email-body-1')), findsOneWidget);
    expect(find.textContaining('Pełna treść wiadomości numer 1'), findsWidgets);

    await tester.ensureVisible(find.byKey(const Key('client-emails-next')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('client-emails-next')));
    await tester.pumpAndSettle();
    expect(repository.calls, hasLength(2));
    expect(repository.calls.last.skip, 10);
    expect(find.text('11–12 z 12'), findsOneWidget);
    expect(find.byKey(const Key('client-email-11')), findsOneWidget);

    await tester.ensureVisible(find.byKey(const Key('client-emails-previous')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('client-emails-previous')));
    await tester.pumpAndSettle();
    expect(find.text('1–10 z 12'), findsOneWidget);
  });

  testWidgets('empty and error remain isolated from client content', (
    WidgetTester tester,
  ) async {
    final _EmailRepository emptyRepository = _EmailRepository(empty: true);
    await _pumpPanel(tester, emptyRepository);
    await tester.tap(find.byKey(const Key('client-emails-toggle')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('client-emails-empty')), findsOneWidget);

    final _EmailRepository failedRepository = _EmailRepository(fail: true);
    await _pumpPanel(
      tester,
      failedRepository,
      clientId: 8,
      clientMarker: 'Dane klienta pozostają widoczne',
    );
    await tester.tap(find.byKey(const Key('client-emails-toggle')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('client-emails-error')), findsOneWidget);
    expect(find.text('Dane klienta pozostają widoczne'), findsOneWidget);
  });

  testWidgets('attachment opens through shared DocumentOpenService', (
    WidgetTester tester,
  ) async {
    final _EmailRepository emailRepository = _EmailRepository();
    final _DocumentRepository documentRepository = _DocumentRepository();
    int openerCalls = 0;
    final DocumentOpenService openService = DocumentOpenService(
      documentRepository,
      opener: (DocumentContent content, int documentId) async {
        openerCalls++;
        expect(documentId, 91);
      },
    );
    await _pumpPanel(
      tester,
      emailRepository,
      documentRepository: documentRepository,
      openService: openService,
    );
    await tester.tap(find.byKey(const Key('client-emails-toggle')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('client-email-toggle-1')));
    await tester.pumpAndSettle();
    await tester.ensureVisible(
      find.byKey(const Key('client-email-attachment-91')),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('client-email-attachment-91')));
    await tester.pumpAndSettle();

    expect(documentRepository.detailCalls, 1);
    expect(documentRepository.contentCalls, 1);
    expect(openerCalls, 1);
  });

  testWidgets('focused source auto-opens exact email and scopes the request', (
    WidgetTester tester,
  ) async {
    final _EmailRepository repository = _EmailRepository();
    await _pumpPanel(tester, repository, focusedSourceId: 4);
    await tester.pumpAndSettle();

    expect(repository.calls, hasLength(1));
    expect(repository.calls.single.sourceId, 4);
    expect(find.byKey(const Key('client-email-4')), findsOneWidget);
    expect(find.byKey(const Key('client-email-body-4')), findsOneWidget);
    expect(find.byKey(const Key('client-emails-next')), findsNothing);
  });

  testWidgets('missing focused email shows a readable scoped fallback', (
    WidgetTester tester,
  ) async {
    final _EmailRepository repository = _EmailRepository(empty: true);
    await _pumpPanel(tester, repository, focusedSourceId: 999);
    await tester.pumpAndSettle();
    expect(
      find.text('Nie znaleziono wskazanej wiadomości dla tego klienta.'),
      findsOneWidget,
    );
  });

  testWidgets('client refresh discloses mailbox scope before apply', (
    WidgetTester tester,
  ) async {
    final _EmailRepository repository = _EmailRepository();
    final _ReconciliationApi reconciliationApi = _ReconciliationApi();
    await _pumpPanel(tester, repository, reconciliationApi: reconciliationApi);
    await tester.tap(find.byKey(const Key('client-emails-toggle')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('client-emails-refresh')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(
      find.textContaining('Odświeżenie obejmuje całą skrzynkę'),
      findsOneWidget,
    );
    expect(reconciliationApi.applyCalls, 0);
    await tester.tap(find.byKey(const Key('mail-reconcile-confirm')));
    await tester.pumpAndSettle();
    expect(reconciliationApi.applyCalls, 1);
    expect(find.textContaining('Dodano 1 brakujące'), findsOneWidget);
    expect(find.text('1–10 z 12'), findsOneWidget);
  });

  testWidgets('ignored filter stays scoped to Client Mail request', (
    WidgetTester tester,
  ) async {
    final repository = _EmailRepository();
    await _pumpPanel(tester, repository);
    await tester.tap(find.byKey(const Key('client-emails-toggle')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('client-mail-ignored-filter')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ignorowane').last);
    await tester.pumpAndSettle();
    expect(repository.calls.last.clientId, 7);
    expect(repository.calls.last.ignored, isTrue);
  });

  testWidgets('admin can ignore a received Client Email sender', (
    WidgetTester tester,
  ) async {
    final _EmailRepository repository = _EmailRepository();
    final _IgnoreApi api = _IgnoreApi();
    await _pumpPanel(tester, repository, admin: true, mailApi: api);
    await tester.tap(find.byKey(const Key('client-emails-toggle')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('client-email-ignore-menu-1')), findsNothing);
    await tester.ensureVisible(
      find.byKey(const Key('client-email-ignore-menu-2')),
    );
    await tester.tap(find.byKey(const Key('client-email-ignore-menu-2')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ignoruj nadawcę').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-ignore-mail-rule')));
    await tester.pumpAndSettle();
    expect(api.created, <(String, String)>[('email', 'nadawca2@example.com')]);
  });
}

Future<void> _pumpPanel(
  WidgetTester tester,
  _EmailRepository repository, {
  _DocumentRepository? documentRepository,
  DocumentOpenService? openService,
  String? clientMarker,
  int clientId = 7,
  int? focusedSourceId,
  _ReconciliationApi? reconciliationApi,
  GlobalMailApi? mailApi,
  bool admin = false,
}) async {
  tester.view.physicalSize = const Size(390, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authControllerProvider.overrideWith(
          admin ? _AdminTestAuthController.new : _TestAuthController.new,
        ),
        clientEmailsRepositoryProvider.overrideWithValue(repository),
        if (documentRepository != null)
          documentsRepositoryProvider.overrideWithValue(documentRepository),
        if (openService != null)
          documentOpenServiceProvider.overrideWithValue(openService),
        if (mailApi != null)
          globalMailApiProvider.overrideWithValue(mailApi)
        else if (reconciliationApi != null)
          globalMailApiProvider.overrideWithValue(reconciliationApi),
      ],
      child: MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: Column(
              children: <Widget>[
                if (clientMarker != null) Text(clientMarker),
                ClientEmailsPanel(
                  clientId: clientId,
                  focusedSourceId: focusedSourceId,
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

class _ReconciliationApi extends GlobalMailApi {
  _ReconciliationApi() : super(Dio());

  int applyCalls = 0;

  @override
  Future<MailReconciliationDryRun> reconciliationDryRun(
    AuthSession session, {
    int windowDays = 7,
  }) async => MailReconciliationDryRun(
    windowDays: windowDays,
    messagesExamined: 12,
    alreadyPresent: 11,
    missingCount: 1,
    expectedCandidates: 1,
    expectedDocuments: 0,
    dryRunToken: 'technical-plan-token',
  );

  @override
  Future<MailReconciliationResult> reconciliationApply(
    AuthSession session,
    MailReconciliationDryRun dryRun,
  ) async {
    applyCalls += 1;
    return const MailReconciliationResult(
      messagesExamined: 12,
      alreadyPresent: 11,
      newMessagesIngested: 1,
      failed: 0,
    );
  }
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

class _AdminTestAuthController extends AuthController {
  @override
  Future<AuthState> build() async => const AuthState(
    session: _session,
    user: CurrentUser(
      id: 1,
      username: 'client-mail-admin',
      email: 'client-mail-admin@example.invalid',
      role: 'Administrator',
      isActive: true,
      mustChangePassword: false,
      passwordResetRequested: false,
    ),
  );
}

class _IgnoreApi extends GlobalMailApi {
  _IgnoreApi() : super(Dio());

  final List<(String, String)> created = <(String, String)>[];

  @override
  Future<IgnoredMailSourceRule> ignoreSender(
    AuthSession session, {
    required String value,
    String ruleType = 'email',
  }) async {
    created.add((ruleType, value));
    return IgnoredMailSourceRule(
      id: 1,
      ruleType: ruleType,
      normalizedValue: value,
      isActive: true,
      createdAt: DateTime(2026, 8, 29),
      updatedAt: DateTime(2026, 8, 29),
    );
  }
}

class _EmailCall {
  const _EmailCall({
    required this.clientId,
    required this.skip,
    required this.limit,
    this.sourceId,
    this.ignored,
  });
  final int clientId;
  final int skip;
  final int limit;
  final int? sourceId;
  final bool? ignored;
}

class _EmailRepository implements ClientEmailsRepository {
  _EmailRepository({this.empty = false, this.fail = false});
  final bool empty;
  final bool fail;
  final List<_EmailCall> calls = <_EmailCall>[];

  @override
  Future<ClientEmailPage> fetchEmails({
    required AuthSession session,
    required int clientId,
    int skip = 0,
    int limit = 20,
    int? sourceId,
    bool? ignored,
  }) async {
    calls.add(
      _EmailCall(
        clientId: clientId,
        skip: skip,
        limit: limit,
        sourceId: sourceId,
        ignored: ignored,
      ),
    );
    if (fail) throw StateError('email endpoint unavailable');
    if (empty) {
      return ClientEmailPage(
        items: const <ClientEmail>[],
        total: 0,
        skip: skip,
        limit: limit,
      );
    }
    if (sourceId != null) {
      return ClientEmailPage(
        items: <ClientEmail>[_email(sourceId)],
        total: 1,
        skip: 0,
        limit: limit,
      );
    }
    final int end = (skip + limit).clamp(0, 12);
    return ClientEmailPage(
      items: <ClientEmail>[
        for (int index = skip; index < end; index++) _email(index + 1),
      ],
      total: 12,
      skip: skip,
      limit: limit,
    );
  }
}

ClientEmail _email(int id) {
  final ClientEmailDirection direction = switch (id % 3) {
    1 => ClientEmailDirection.sent,
    2 => ClientEmailDirection.received,
    _ => ClientEmailDirection.unknown,
  };
  return ClientEmail(
    id: id,
    externalId: 'gmail-$id',
    messageId: 'gmail-$id',
    threadId: 'thread-${(id + 1) ~/ 2}',
    direction: direction,
    messageAt: DateTime.utc(2026, 8, 15, 12, id),
    fromName: 'Nadawca $id',
    fromAddress: 'nadawca$id@example.com',
    toAddresses: const <String>['kontakt@podnoszenieposadzek.pl'],
    ccAddresses: id == 1 ? const <String>['dw@example.com'] : const <String>[],
    subject: id == 2 ? null : 'Temat $id',
    bodyText:
        'Pełna treść wiadomości numer $id. '
        '${List<String>.filled(30, 'Dalsza treść').join(' ')}',
    sourceUrl: null,
    attachmentCount: id == 1 ? 1 : 0,
    attachments: id == 1
        ? const <ClientEmailAttachment>[
            ClientEmailAttachment(
              documentId: 91,
              originalFilename: 'oferta.pdf',
              contentType: 'application/pdf',
              fileSize: 2048,
            ),
          ]
        : const <ClientEmailAttachment>[],
    createdAt: DateTime.utc(2026, 8, 15),
  );
}

class _DocumentRepository extends DocumentsRepository {
  int detailCalls = 0;
  int contentCalls = 0;

  @override
  Future<RepositoryDocument> fetchDocument({
    required AuthSession session,
    required int documentId,
  }) async {
    detailCalls++;
    return _document(documentId);
  }

  @override
  Future<DocumentContent> fetchContent({
    required AuthSession session,
    required RepositoryDocument document,
    void Function(int received, int total)? onProgress,
  }) async {
    contentCalls++;
    return DocumentContent(
      bytes: Uint8List.fromList(<int>[1, 2, 3]),
      fileName: document.displayName,
      contentType: document.contentType,
    );
  }

  @override
  Future<DocumentPage> fetchDocuments({
    required AuthSession session,
    required DocumentFilters filters,
    String search = '',
    int skip = 0,
    int limit = 50,
  }) {
    throw UnimplementedError();
  }
}

RepositoryDocument _document(int id) => RepositoryDocument(
  id: id,
  originalFilename: 'oferta.pdf',
  contentType: 'application/pdf',
  fileSize: 2048,
  sourceType: 'gmail_attachment',
  processingStatus: 'processed',
  metadataStatus: 'processed',
  matchStatus: 'matched',
  archiveDepth: 0,
  createdAt: DateTime.utc(2026, 8, 15),
  updatedAt: DateTime.utc(2026, 8, 15),
);
