import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/auth/domain/current_user.dart';
import 'package:ai_lab/features/knowledge_base/application/knowledge_base_providers.dart';
import 'package:ai_lab/features/knowledge_base/data/knowledge_base_api.dart';
import 'package:ai_lab/features/knowledge_base/domain/knowledge_base_models.dart';
import 'package:ai_lab/features/knowledge_base/presentation/admin_knowledge_base_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _session = AuthSession(accessToken: 'kb-test', tokenType: 'bearer');

class _AuthController extends AuthController {
  _AuthController(this.role);
  final String role;
  @override
  Future<AuthState> build() async => AuthState(
    session: _session,
    user: CurrentUser(
      id: 1,
      username: 'kb-user',
      email: 'kb@example.invalid',
      role: role,
      isActive: true,
      mustChangePassword: false,
      passwordResetRequested: false,
    ),
  );
}

final _item = KnowledgeBaseItem(
  id: 17,
  title: 'Karta techniczna ALPHA 600',
  source: 'Publiczna próbka',
  publisher: 'Fixture Publisher',
  version: 'v2',
  effectiveDate: '2026-08-21',
  category: 'technical_datasheets',
  tags: const <String>['formula', 'load'],
  status: 'current',
  supersedesId: null,
  originalFilename: 'alpha-600.txt',
  fileSize: 1200,
  processingStatus: 'processed',
  processingMethod: 'native_text',
  pages: const <KnowledgeBasePageExcerpt>[
    KnowledgeBasePageExcerpt(
      page: 1,
      method: 'native_text',
      text: 'Formula R = U / I',
    ),
  ],
);

class _Api extends KnowledgeBaseApi {
  _Api() : super(Dio());
  @override
  Future<KnowledgeBaseListResult> list(
    AuthSession session, {
    String? query,
    String? category,
    String? status,
  }) async => KnowledgeBaseListResult(<KnowledgeBaseItem>[_item], 1);
  @override
  Future<KnowledgeBaseItem> detail(AuthSession session, int id) async => _item;
}

class _StatusApi extends KnowledgeBaseApi {
  _StatusApi() : super(Dio());
  int retries = 0;
  final item = KnowledgeBaseItem(
    id: 18,
    title: 'Materiał oczekujący',
    source: 'Publiczna próbka',
    category: 'norms',
    tags: const <String>[],
    status: 'current',
    originalFilename: 'queued.txt',
    fileSize: 100,
    processingStatus: 'queued',
    analysisStatus: 'advanced_queued',
    indexingStatus: 'not_ready',
    analysisReason: 'analysis_runtime_disabled',
    pages: const <KnowledgeBasePageExcerpt>[],
  );
  @override
  Future<KnowledgeBaseListResult> list(
    AuthSession session, {
    String? query,
    String? category,
    String? status,
  }) async => KnowledgeBaseListResult(<KnowledgeBaseItem>[item], 1);
  @override
  Future<KnowledgeBaseItem> detail(AuthSession session, int id) async => item;
  @override
  Future<void> retry(AuthSession session, int id) async {
    retries += 1;
  }
}

Future<void> _pump(
  WidgetTester tester,
  double width, {
  String role = 'Administrator',
  KnowledgeBaseApi? api,
  bool settle = true,
}) async {
  tester.view.physicalSize = Size(width, 1800);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final container = ProviderContainer(
    overrides: [
      authControllerProvider.overrideWith(() => _AuthController(role)),
      knowledgeBaseApiProvider.overrideWithValue(api ?? _Api()),
    ],
  );
  addTearDown(container.dispose);
  await container.read(authControllerProvider.future);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(home: AdminKnowledgeBasePage()),
    ),
  );
  if (settle) {
    await tester.pumpAndSettle();
  } else {
    await tester.pump(const Duration(milliseconds: 200));
  }
}

void main() {
  for (final width in <double>[360, 390, 600, 1200]) {
    testWidgets('Knowledge Base is responsive at ${width.toInt()}', (
      tester,
    ) async {
      await _pump(tester, width);
      expect(find.text('Baza wiedzy'), findsOneWidget);
      expect(find.text('Karta techniczna ALPHA 600'), findsOneWidget);
      expect(find.byKey(const Key('knowledge-base-add')), findsOneWidget);
      final Object? layoutError = tester.takeException();
      expect(layoutError, isNull);
    });
  }

  testWidgets('normal User has no Knowledge Base management controls', (
    tester,
  ) async {
    await _pump(tester, 390, role: 'User');
    expect(find.text('Brak uprawnień.'), findsOneWidget);
    expect(find.byKey(const Key('knowledge-base-add')), findsNothing);
  });

  testWidgets('detail presents page-level citation provenance', (tester) async {
    await _pump(tester, 600);
    await tester.tap(find.byType(PopupMenuButton<String>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Szczegóły i cytowania'));
    await tester.pumpAndSettle();
    expect(find.text('Cytowania / strony'), findsOneWidget);
    expect(find.text('Strona 1 • native_text'), findsOneWidget);
    expect(find.text('Formula R = U / I'), findsOneWidget);
  });

  testWidgets(
    'queued and advanced pipeline state is truthful and retry is exact',
    (tester) async {
      final api = _StatusApi();
      await _pump(tester, 390, api: api, settle: false);
      expect(find.textContaining('W kolejce'), findsOneWidget);
      expect(
        find.textContaining('Analiza zaawansowana w kolejce'),
        findsOneWidget,
      );
      await tester.tap(find.byType(PopupMenuButton<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Ponów przetwarzanie'));
      await tester.pumpAndSettle();
      expect(api.retries, 1);
    },
  );
}
