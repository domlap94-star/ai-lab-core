import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/auth/domain/current_user.dart';
import 'package:ai_lab/features/mail/data/global_mail_api.dart';
import 'package:ai_lab/features/mail/domain/global_mail.dart';
import 'package:ai_lab/features/mail/presentation/global_mail_page.dart';
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
  _FakeMailApi() : super(Dio());
  int listCalls = 0;
  String? readState;

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
    attachments: const <GlobalMailAttachment>[
      GlobalMailAttachment(
        documentId: 55,
        filename: 'zalacznik.pdf',
        mimeType: 'application/pdf',
        processingStatus: 'processed',
      ),
    ],
  );

  @override
  Future<GlobalMailPageData> list({
    required AuthSession session,
    required int skip,
    String? search,
    String? direction,
    String? readState,
    bool? linked,
    bool? hasAttachments,
    DateTime? dateFrom,
    DateTime? dateTo,
  }) async {
    listCalls += 1;
    this.readState = readState;
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

  testWidgets('desktop detail exposes thread action without send controls', (
    WidgetTester tester,
  ) async {
    await _pump(tester, _FakeMailApi());
    await tester.tap(find.text('Testowy temat'));
    await tester.pumpAndSettle();
    expect(find.text('Pokaż wątek'), findsOneWidget);
    expect(find.textContaining('Wyślij'), findsNothing);
    expect(find.textContaining('Odpowiedz'), findsNothing);
  });
}
