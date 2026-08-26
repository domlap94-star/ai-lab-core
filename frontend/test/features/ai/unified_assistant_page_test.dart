import 'package:ai_lab/features/ai/application/assistant_run_controller.dart';
import 'package:ai_lab/features/ai/data/assistant_run_repository.dart';
import 'package:ai_lab/features/ai/data/unified_assistant_api.dart';
import 'package:ai_lab/features/ai/domain/assistant_run.dart';
import 'package:ai_lab/features/ai/domain/unified_assistant.dart';
import 'package:ai_lab/features/ai/presentation/unified_assistant_page.dart';
import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues(<String, String>{});
  });
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
    final api = _PendingRepository();
    await _pump(tester, repository: api);
    await tester.enterText(
      find.byKey(const Key('unified-ai-question')),
      'Trudny przypadek syntetyczny',
    );
    await tester.ensureVisible(find.byKey(const Key('unified-ai-send')));
    await tester.tap(find.byKey(const Key('unified-ai-send')));
    await tester.pump(const Duration(milliseconds: 100));
    await tester.ensureVisible(find.text('Anuluj'));
    await tester.tap(find.text('Anuluj'));
    await tester.pumpAndSettle();
    expect(api.cancelledRunId, 'pending-run');
    expect(find.byKey(const Key('unified-ai-send')), findsOneWidget);
  });

  testWidgets(
    'explicit reset clears reasoning history before the next request',
    (tester) async {
      final api = _RecordingRepository();
      await _pump(tester, repository: api);
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
      await _pump(tester, repository: _TerminalFailureRepository());
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

  testWidgets('document preparation polls durable status and resumes once', (
    tester,
  ) async {
    final api = _PreparationRepository();
    await _pump(tester, repository: api);
    await tester.enterText(
      find.byKey(const Key('unified-ai-question')),
      'Przeanalizuj zapisany skan',
    );
    await tester.ensureVisible(find.byKey(const Key('unified-ai-send')));
    await tester.tap(find.byKey(const Key('unified-ai-send')));
    await tester.pump();
    expect(find.text('Rozpoznaję skan.'), findsOneWidget);
    await tester.pump(const Duration(seconds: 3));
    await tester.pump();
    expect(api.statusCalls, 1);
    expect(find.byKey(const Key('unified-ai-answer')), findsOneWidget);
  });

  testWidgets('completed durable result is restored after leaving the page', (
    tester,
  ) async {
    FlutterSecureStorage.setMockInitialValues(<String, String>{
      'unified_assistant_latest_run_v2': 'completed-run',
    });
    await _pump(tester, repository: _CompletedRestoreRepository());
    expect(find.byKey(const Key('unified-ai-answer')), findsOneWidget);
    expect(find.text('Odpowiedź oparta na dowodzie.'), findsOneWidget);
  });
}

Future<void> _pump(
  WidgetTester tester, {
  AssistantRunRepository? repository,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authControllerProvider.overrideWith(_Auth.new),
        assistantRunRepositoryProvider.overrideWithValue(
          repository ?? _RunRepository(),
        ),
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

// Legacy fixtures retained only to prove the compatibility adapter still compiles.
// ignore: unused_element
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

// ignore: unused_element
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

// ignore: unused_element
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

// ignore: unused_element
class _PreparationApi extends _Api {
  int statusCalls = 0;

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
    requestId: 'preparation-request',
    answer: '',
    status: 'document_preparation_running',
    progress: 'preparing_document',
    targetScope: 'TARGET_01',
    claims: [],
    sources: [],
    usedTools: [],
    externalAnalysisUsed: false,
    currentStage: 'ocr_processing',
    canCancel: true,
  );

  @override
  Future<UnifiedAssistantAnswer> status({
    required AuthSession session,
    required String requestId,
    CancelToken? cancelToken,
  }) async {
    statusCalls += 1;
    return const UnifiedAssistantAnswer(
      requestId: 'preparation-request',
      answer: 'Dokument został przygotowany i przeanalizowany.',
      status: 'accepted_local',
      progress: 'complete',
      targetScope: 'TARGET_01',
      claims: [],
      sources: [],
      usedTools: [],
      externalAnalysisUsed: false,
      currentStage: 'complete',
    );
  }
}

AssistantRunSnapshot _snapshot({
  String runId = 'completed-run',
  String status = 'completed',
  String message = 'Analiza zakończona.',
  UnifiedAssistantAnswer? result,
}) => AssistantRunSnapshot(
  runId: runId,
  attemptId: 'attempt_0001',
  status: status,
  currentStage: status == 'completed' ? null : 'waiting_for_material',
  complexity: 'standard',
  progress: AssistantRunProgress(message: message),
  canCancel: !<String>{
    'completed',
    'review_required',
    'failed',
    'cancelled',
  }.contains(status),
  pollAfterMs: 500,
  recoveryGeneration: 0,
  result: result,
  createdAt: DateTime.utc(2026, 8, 26),
  updatedAt: DateTime.utc(2026, 8, 26),
);

const _completedAnswer = UnifiedAssistantAnswer(
  requestId: 'completed-run',
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

class _RunRepository extends AssistantRunRepository {
  _RunRepository() : super(Dio());

  @override
  Future<List<AssistantRunSnapshot>> listActive({
    required AuthSession session,
  }) async => const <AssistantRunSnapshot>[];

  @override
  Future<AssistantRunSnapshot> create({
    required AuthSession session,
    required String question,
    required String attemptId,
    required List<Map<String, String>> conversation,
    int? clientId,
    int? candidateId,
    int? documentId,
    int? mailSourceId,
    int? inspectionId,
  }) async => _snapshot(result: _completedAnswer);
}

class _CompletedRestoreRepository extends _RunRepository {
  @override
  Future<AssistantRunSnapshot> get({
    required AuthSession session,
    required String runId,
    CancelToken? cancelToken,
  }) async => _snapshot(runId: runId, result: _completedAnswer);
}

class _RecordingRepository extends _RunRepository {
  final conversations = <List<Map<String, String>>>[];

  @override
  Future<AssistantRunSnapshot> create({
    required AuthSession session,
    required String question,
    required String attemptId,
    required List<Map<String, String>> conversation,
    int? clientId,
    int? candidateId,
    int? documentId,
    int? mailSourceId,
    int? inspectionId,
  }) async {
    conversations.add(
      conversation.map(Map<String, String>.from).toList(growable: false),
    );
    return _snapshot(
      runId: 'completed-${conversations.length}',
      result: _completedAnswer,
    );
  }
}

class _PendingRepository extends _RunRepository {
  String? cancelledRunId;

  @override
  Future<AssistantRunSnapshot> create({
    required AuthSession session,
    required String question,
    required String attemptId,
    required List<Map<String, String>> conversation,
    int? clientId,
    int? candidateId,
    int? documentId,
    int? mailSourceId,
    int? inspectionId,
  }) async => _snapshot(
    runId: 'pending-run',
    status: 'waiting',
    message: 'Oczekuję na analizę.',
  );

  @override
  Future<AssistantRunSnapshot> get({
    required AuthSession session,
    required String runId,
    CancelToken? cancelToken,
  }) async => _snapshot(
    runId: runId,
    status: 'waiting',
    message: 'Oczekuję na analizę.',
  );

  @override
  Future<AssistantRunSnapshot> cancel({
    required AuthSession session,
    required String runId,
  }) async {
    cancelledRunId = runId;
    return _snapshot(runId: runId, status: 'cancelled');
  }
}

class _TerminalFailureRepository extends _RunRepository {
  @override
  Future<AssistantRunSnapshot> create({
    required AuthSession session,
    required String question,
    required String attemptId,
    required List<Map<String, String>> conversation,
    int? clientId,
    int? candidateId,
    int? documentId,
    int? mailSourceId,
    int? inspectionId,
  }) async => _snapshot(
    runId: 'terminal-failure',
    status: 'review_required',
    result: const UnifiedAssistantAnswer(
      requestId: 'terminal-failure',
      answer: '',
      status: 'review_required',
      progress: 'complete',
      targetScope: 'TARGET_01',
      claims: <UnifiedAssistantClaim>[],
      sources: <UnifiedAssistantSource>[],
      usedTools: <String>[],
      externalAnalysisUsed: false,
      errorMessage: 'Nie znaleziono dokumentu.',
    ),
  );
}

class _PreparationRepository extends _RunRepository {
  int statusCalls = 0;

  @override
  Future<AssistantRunSnapshot> create({
    required AuthSession session,
    required String question,
    required String attemptId,
    required List<Map<String, String>> conversation,
    int? clientId,
    int? candidateId,
    int? documentId,
    int? mailSourceId,
    int? inspectionId,
  }) async => _snapshot(
    runId: 'preparation-run',
    status: 'waiting',
    message: 'Rozpoznaję skan.',
  );

  @override
  Future<AssistantRunSnapshot> get({
    required AuthSession session,
    required String runId,
    CancelToken? cancelToken,
  }) async {
    statusCalls += 1;
    return _snapshot(runId: runId, result: _completedAnswer);
  }
}
