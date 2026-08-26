import 'package:ai_lab/features/ai/application/unified_assistant_providers.dart';
import 'package:ai_lab/features/ai/data/unified_assistant_api.dart';
import 'package:ai_lab/features/ai/domain/unified_assistant.dart';
import 'package:ai_lab/features/ai/presentation/unified_assistant_page.dart';
import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('single assistant has quick actions and no mode selector', (
    tester,
  ) async {
    await _pump(tester);
    expect(find.text('Jeden asystent, pełny kontekst'), findsOneWidget);
    expect(find.byKey(const Key('ai-mode-selector')), findsNothing);
    expect(find.text('Podsumuj ten przypadek'), findsOneWidget);
  });

  testWidgets('renders semantics and keeps Sources collapsed by default', (
    tester,
  ) async {
    await _pump(tester);
    await tester.enterText(
      find.byKey(const Key('unified-ai-question')),
      'Co wynika z danych?',
    );
    await tester.ensureVisible(find.byKey(const Key('unified-ai-send')));
    await tester.tap(find.byKey(const Key('unified-ai-send')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('unified-ai-answer')), findsOneWidget);
    expect(find.text('Estymacja — niska pewność'), findsOneWidget);
    expect(find.byKey(const Key('unified-source-S01')), findsNothing);
    await tester.ensureVisible(find.text('Źródła'));
    await tester.tap(find.text('Źródła'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('unified-source-S01')), findsOneWidget);
  });

  testWidgets('Cancel propagates to backend job and restores composer', (
    tester,
  ) async {
    final api = _PendingApi();
    await _pump(tester, api: api);
    await tester.enterText(
      find.byKey(const Key('unified-ai-question')),
      'Trudny przypadek syntetyczny',
    );
    await tester.ensureVisible(find.byKey(const Key('unified-ai-send')));
    await tester.tap(find.byKey(const Key('unified-ai-send')));
    await tester.pump();
    await tester.ensureVisible(find.text('Anuluj'));
    await tester.tap(find.text('Anuluj'));
    await tester.pumpAndSettle();
    expect(api.cancelledRequestId, 'pending-request');
    expect(find.byKey(const Key('unified-ai-send')), findsOneWidget);
  });

  testWidgets(
    'explicit reset clears reasoning history before the next request',
    (tester) async {
      final api = _RecordingApi();
      await _pump(tester, api: api);
      await tester.enterText(
        find.byKey(const Key('unified-ai-question')),
        'Przeanalizuj poprzedni temat',
      );
      await tester.ensureVisible(find.byKey(const Key('unified-ai-send')));
      await tester.tap(find.byKey(const Key('unified-ai-send')));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('unified-ai-question')),
        'Ignoruj poprzednie zapytanie. Co potrafisz?',
      );
      await tester.ensureVisible(find.byKey(const Key('unified-ai-send')));
      await tester.tap(find.byKey(const Key('unified-ai-send')));
      await tester.pumpAndSettle();
      expect(api.conversations, hasLength(2));
      expect(api.conversations.first, isEmpty);
      expect(api.conversations.last, isEmpty);
    },
  );

  testWidgets(
    'terminal retrieval failure does not claim a general-knowledge answer or Sources',
    (tester) async {
      await _pump(tester, api: _TerminalFailureApi());
      await tester.enterText(
        find.byKey(const Key('unified-ai-question')),
        'Znajdź opisany dokument',
      );
      await tester.ensureVisible(find.byKey(const Key('unified-ai-send')));
      await tester.tap(find.byKey(const Key('unified-ai-send')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('unified-ai-error')), findsOneWidget);
      expect(find.byKey(const Key('unified-ai-answer')), findsNothing);
      expect(find.byKey(const Key('unified-ai-sources')), findsNothing);
      expect(find.textContaining('wiedzy ogólnej'), findsNothing);
    },
  );
}

Future<void> _pump(WidgetTester tester, {UnifiedAssistantApi? api}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authControllerProvider.overrideWith(_Auth.new),
        unifiedAssistantApiProvider.overrideWithValue(api ?? _Api()),
      ],
      child: const MaterialApp(home: UnifiedAssistantPage()),
    ),
  );
  await tester.pumpAndSettle();
}

class _Auth extends AuthController {
  @override
  Future<AuthState> build() async => const AuthState(
    session: AuthSession(accessToken: 'token', tokenType: 'Bearer'),
    user: null,
  );
}

class _Api extends UnifiedAssistantApi {
  _Api() : super(Dio());
  @override
  Future<UnifiedAssistantAnswer> ask({
    required AuthSession session,
    required String question,
    required List<Map<String, String>> conversation,
    int? clientId,
    int? candidateId,
    int? documentId,
    int? mailSourceId,
    int? inspectionId,
    String? attemptId,
    CancelToken? cancelToken,
  }) async => const UnifiedAssistantAnswer(
    requestId: 'request',
    answer: 'Odpowiedź oparta na dowodzie.',
    status: 'accepted_local',
    progress: 'complete',
    targetScope: 'TARGET_01',
    usedTools: <String>['document_search'],
    externalAnalysisUsed: false,
    claims: <UnifiedAssistantClaim>[
      UnifiedAssistantClaim(
        claimId: 'C01',
        claimClass: 'ESTIMATE',
        text: '1–2 mm',
        sourceRefs: <String>['S01'],
        estimateStatus: 'ESTIMABLE',
        confidence: 'LOW',
      ),
    ],
    sources: <UnifiedAssistantSource>[
      UnifiedAssistantSource(
        sourceRef: 'S01',
        sourceType: 'document',
        title: 'Protokół',
        excerpt: 'Pomiar 1 mm.',
        whyUsed: 'Podstawa pomiaru.',
        supportsClaimIds: <String>['C01'],
      ),
    ],
  );
}

class _PendingApi extends UnifiedAssistantApi {
  _PendingApi() : super(Dio());
  String? cancelledRequestId;

  @override
  Future<UnifiedAssistantAnswer> ask({
    required AuthSession session,
    required String question,
    required List<Map<String, String>> conversation,
    int? clientId,
    int? candidateId,
    int? documentId,
    int? mailSourceId,
    int? inspectionId,
    String? attemptId,
    CancelToken? cancelToken,
  }) async => const UnifiedAssistantAnswer(
    requestId: 'pending-request',
    answer: '',
    status: 'advanced_processing',
    progress: 'advanced_analysis',
    targetScope: 'TARGET_01',
    claims: [],
    sources: [],
    usedTools: [],
    externalAnalysisUsed: true,
    canCancel: true,
  );

  @override
  Future<UnifiedAssistantAnswer> cancel({
    required AuthSession session,
    required String requestId,
  }) async {
    cancelledRequestId = requestId;
    return const UnifiedAssistantAnswer(
      requestId: 'pending-request',
      answer: '',
      status: 'cancelled',
      progress: 'complete',
      targetScope: 'TARGET_01',
      claims: [],
      sources: [],
      usedTools: [],
      externalAnalysisUsed: true,
    );
  }
}

class _RecordingApi extends _Api {
  final conversations = <List<Map<String, String>>>[];

  @override
  Future<UnifiedAssistantAnswer> ask({
    required AuthSession session,
    required String question,
    required List<Map<String, String>> conversation,
    int? clientId,
    int? candidateId,
    int? documentId,
    int? mailSourceId,
    int? inspectionId,
    String? attemptId,
    CancelToken? cancelToken,
  }) async {
    conversations.add(
      conversation.map((item) => Map<String, String>.from(item)).toList(),
    );
    return super.ask(
      session: session,
      question: question,
      conversation: conversation,
      clientId: clientId,
      candidateId: candidateId,
      documentId: documentId,
      mailSourceId: mailSourceId,
      inspectionId: inspectionId,
      attemptId: attemptId,
      cancelToken: cancelToken,
    );
  }
}

class _TerminalFailureApi extends _Api {
  @override
  Future<UnifiedAssistantAnswer> ask({
    required AuthSession session,
    required String question,
    required List<Map<String, String>> conversation,
    int? clientId,
    int? candidateId,
    int? documentId,
    int? mailSourceId,
    int? inspectionId,
    String? attemptId,
    CancelToken? cancelToken,
  }) async => const UnifiedAssistantAnswer(
    requestId: 'terminal-failure',
    answer: '',
    status: 'review_required',
    progress: 'complete',
    targetScope: 'TARGET_01',
    claims: [],
    sources: [],
    usedTools: [],
    externalAnalysisUsed: false,
    errorMessage: 'Nie znaleziono dokumentu.',
    currentStage: 'document_resolution',
  );
}
