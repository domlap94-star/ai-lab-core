import 'dart:convert';

import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/auth/domain/current_user.dart';
import 'package:ai_lab/features/mail/data/global_mail_api.dart';
import 'package:ai_lab/features/mail/domain/global_mail.dart';
import 'package:ai_lab/features/mail/presentation/global_mail_page.dart';
import 'package:ai_lab/features/documents/application/documents_providers.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const AuthSession _session = AuthSession(
  accessToken: 'mail-test-token',
  tokenType: 'Bearer',
);

class _AuthController extends AuthController {
  @override
  Future<AuthState> build() async => const AuthState(
    session: _session,
    user: CurrentUser(
      id: 1,
      username: 'mail.user',
      email: 'mail.user@example.invalid',
      role: 'User',
      isActive: true,
      mustChangePassword: false,
      passwordResetRequested: false,
    ),
  );
}

class _FakeMailApi extends GlobalMailApi {
  _FakeMailApi({this.imageAttachment = false, this.missingCount = 0})
    : super(Dio());
  final bool imageAttachment;
  final int missingCount;
  int listCalls = 0;
  String? readState;
  bool? ignored;
  int sendCalls = 0;
  int reconciliationDryRuns = 0;
  int reconciliationApplies = 0;

  GlobalMailItem get item => GlobalMailItem(
    sourceId: 2,
    messageId: 'technical-message',
    threadId: 'technical-thread',
    direction: 'received',
    readState: 'unknown',
    sender: 'masked@example.invalid',
    recipients: const <String>['inbox@example.invalid'],
    subject: 'Testowy temat',
    occurredAt: DateTime.utc(2026, 8, 19, 12, 30),
    clientId: 123,
    clientName: 'Klient #123',
    reviewState: 'accepted',
    hasAttachments: true,
    attachmentCount: 1,
    bodyText: 'Bezpieczna treść tekstowa',
    attachments: <GlobalMailAttachment>[
      GlobalMailAttachment(
        documentId: 55,
        filename: imageAttachment ? 'zalacznik.png' : 'zalacznik.pdf',
        mimeType: imageAttachment ? 'image/png' : 'application/pdf',
        processingStatus: 'processed',
      ),
    ],
  );

  @override
  Future<GlobalMailPageData> list({
    required AuthSession session,
    required int skip,
    int limit = 50,
    String? search,
    String? direction,
    String? readState,
    bool? linked,
    bool? hasAttachments,
    bool? ignored,
    DateTime? dateFrom,
    DateTime? dateTo,
  }) async {
    listCalls += 1;
    this.readState = readState;
    this.ignored = ignored;
    return GlobalMailPageData(items: <GlobalMailItem>[item], hasMore: false);
  }

  @override
  Future<GlobalMailItem> detail(AuthSession session, int sourceId) async =>
      item;

  @override
  Future<List<GlobalMailItem>> thread(
    AuthSession session,
    String threadId,
  ) async => <GlobalMailItem>[item];

  @override
  Future<MailReconciliationDryRun> reconciliationDryRun(
    AuthSession session, {
    int windowDays = 7,
  }) async {
    reconciliationDryRuns += 1;
    return MailReconciliationDryRun(
      windowDays: windowDays,
      messagesExamined: 25,
      alreadyPresent: 25 - missingCount,
      missingCount: missingCount,
      expectedCandidates: missingCount,
      expectedDocuments: 0,
      dryRunToken: 'technical-plan-token',
    );
  }

  @override
  Future<MailReconciliationResult> reconciliationApply(
    AuthSession session,
    MailReconciliationDryRun dryRun,
  ) async {
    reconciliationApplies += 1;
    return MailReconciliationResult(
      messagesExamined: dryRun.messagesExamined,
      alreadyPresent: dryRun.alreadyPresent,
      newMessagesIngested: dryRun.missingCount,
      failed: 0,
    );
  }

  @override
  Future<MailSendResult> send(
    AuthSession session, {
    required String operationId,
    required List<String> to,
    required String subject,
    required String body,
    List<String> cc = const <String>[],
    List<String> bcc = const <String>[],
    List<int> attachmentDocumentIds = const <int>[],
    int? clientId,
    int? sourceId,
    String action = 'compose',
  }) async {
    sendCalls += 1;
    return MailSendResult(
      operationId: operationId,
      status: 'canonical_synced',
      canonicalSourceId: 99,
    );
  }
}

Future<void> _pump(
  WidgetTester tester,
  _FakeMailApi api, {
  double width = 1200,
}) async {
  tester.view.physicalSize = Size(width, 1000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final container = ProviderContainer(
    overrides: [
      authControllerProvider.overrideWith(_AuthController.new),
      globalMailApiProvider.overrideWithValue(api),
      if (api.imageAttachment)
        documentThumbnailProvider(55).overrideWith(
          (_) async => base64Decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
          ),
        ),
    ],
  );
  addTearDown(container.dispose);
  await container.read(authControllerProvider.future);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(home: GlobalMailPage()),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  test('nullable read state parses as unknown', () {
    final item = GlobalMailItem.fromJson(<String, dynamic>{
      'source_id': 2,
      'message_id': 'id',
      'direction': 'unknown',
      'read_state': 'unknown',
      'recipients': <String>[],
      'occurred_at': '2026-08-19T12:00:00Z',
      'has_attachments': false,
      'attachment_count': 0,
    });
    expect(item.readState, 'unknown');
  });

  for (final width in <double>[360, 390, 600, 1200]) {
    testWidgets('mail workspace is responsive at ${width.toInt()}', (
      WidgetTester tester,
    ) async {
      await _pump(tester, _FakeMailApi(), width: width);
      expect(find.text('Maile'), findsOneWidget);
      expect(find.text('Testowy temat'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('mobile list opens safe detail and Back returns to list', (
    WidgetTester tester,
  ) async {
    await _pump(tester, _FakeMailApi(), width: 390);
    await tester.tap(find.text('Testowy temat'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('mail-detail')), findsOneWidget);
    expect(find.text('Bezpieczna treść tekstowa'), findsOneWidget);
    expect(find.text('zalacznik.pdf'), findsOneWidget);
    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('mail-list')), findsOneWidget);
  });

  testWidgets('unknown read filter reloads from backend', (
    WidgetTester tester,
  ) async {
    final api = _FakeMailApi();
    await _pump(tester, api);
    final Finder readFilter = find.byType(DropdownButton<String?>).at(1);
    await tester.ensureVisible(readFilter);
    await tester.tap(readFilter);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Nieznany').last);
    await tester.pumpAndSettle();
    expect(api.readState, 'unknown');
    expect(api.listCalls, greaterThan(1));
  });

  testWidgets('ignored-state filter reloads from backend', (
    WidgetTester tester,
  ) async {
    final api = _FakeMailApi();
    await _pump(tester, api);
    final Finder ignoredFilter = find.byType(DropdownButton<String?>).at(3);
    await tester.ensureVisible(ignoredFilter);
    await tester.tap(ignoredFilter);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Tylko ignorowane').last);
    await tester.pumpAndSettle();
    expect(api.ignored, isTrue);
    expect(api.listCalls, greaterThan(1));
  });

  testWidgets('desktop detail exposes bounded reply and forward controls', (
    WidgetTester tester,
  ) async {
    await _pump(tester, _FakeMailApi());
    await tester.tap(find.text('Testowy temat'));
    await tester.pumpAndSettle();
    expect(find.text('Pokaż wątek'), findsOneWidget);
    expect(find.text('Odpowiedz'), findsOneWidget);
    expect(find.text('Przekaż dalej'), findsOneWidget);
  });

  testWidgets('Global Mail image attachment uses shared thumbnail', (
    WidgetTester tester,
  ) async {
    await _pump(tester, _FakeMailApi(imageAttachment: true));
    await tester.tap(find.text('Testowy temat'));
    await tester.pumpAndSettle();
    final Finder thumbnail = find.byKey(
      const ValueKey<String>('document-thumbnail-55'),
    );
    expect(thumbnail, findsOneWidget);
    expect(tester.getSize(thumbnail).width, 100);
    expect(find.text('zalacznik.png'), findsOneWidget);
  });

  testWidgets('compose requires final confirmation before one send', (
    WidgetTester tester,
  ) async {
    final api = _FakeMailApi();
    await _pump(tester, api);
    await tester.tap(find.byKey(const Key('mail-compose')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('mail-to')),
      'owner@example.invalid',
    );
    await tester.enterText(find.byKey(const Key('mail-subject')), 'Synthetic');
    await tester.enterText(
      find.byKey(const Key('mail-body')),
      'Synthetic body',
    );
    await tester.tap(find.byKey(const Key('mail-review-send')));
    await tester.pumpAndSettle();
    expect(find.text('Wyślij wiadomość?'), findsOneWidget);
    expect(api.sendCalls, 0);
    await tester.tap(find.byKey(const Key('mail-confirm-send')));
    await tester.pumpAndSettle();
    expect(api.sendCalls, 1);
  });

  testWidgets('refresh dry-run with no gaps reloads without apply', (
    WidgetTester tester,
  ) async {
    final api = _FakeMailApi();
    await _pump(tester, api);
    final int initialListCalls = api.listCalls;
    await tester.tap(find.byKey(const Key('mail-reconcile')));
    await tester.pumpAndSettle();
    expect(api.reconciliationDryRuns, 1);
    expect(api.reconciliationApplies, 0);
    expect(api.listCalls, initialListCalls + 1);
    expect(find.textContaining('Wiadomości są aktualne'), findsOneWidget);
  });

  testWidgets('refresh requires explicit approval before applying gaps', (
    WidgetTester tester,
  ) async {
    final api = _FakeMailApi(missingCount: 2);
    await _pump(tester, api);
    await tester.tap(find.byKey(const Key('mail-reconcile')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.text('Dodać brakujące wiadomości?'), findsOneWidget);
    expect(api.reconciliationApplies, 0);
    await tester.tap(find.byKey(const Key('mail-reconcile-confirm')));
    await tester.pumpAndSettle();
    expect(api.reconciliationApplies, 1);
    expect(find.textContaining('Dodano 2 brakujące'), findsOneWidget);
  });
}
