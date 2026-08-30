import 'dart:async';

import 'package:ai_lab/features/ai/application/assistant_run_controller.dart';
import 'package:ai_lab/features/ai/application/assistant_conversation_controller.dart';
import 'package:ai_lab/features/ai/data/assistant_conversation_repository.dart';
import 'package:ai_lab/features/ai/data/assistant_run_repository.dart';
import 'package:ai_lab/features/ai/domain/assistant_conversation.dart';
import 'package:ai_lab/features/ai/data/unified_assistant_api.dart';
import 'package:ai_lab/features/ai/domain/assistant_run.dart';
import 'package:ai_lab/features/ai/domain/unified_assistant.dart';
import 'package:ai_lab/features/ai/presentation/unified_assistant_page.dart';
import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/clients/presentation/searchable_client_picker.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues(<String, String>{});
  });
  testWidgets(
    'chat-first layout removes legacy form and keeps fixed composer',
    (tester) async {
      await _pump(tester);
      expect(find.text('Jeden asystent, pełny kontekst'), findsNothing);
      expect(find.byKey(const Key('ai-mode-selector')), findsNothing);
      expect(find.text('Podsumuj ten przypadek'), findsNothing);
      expect(
        find.byKey(const Key('assistant-chat-transcript')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('assistant-fixed-composer')), findsOneWidget);
      expect(find.byKey(const Key('assistant-empty-title')), findsOneWidget);
      expect(find.byKey(const Key('assistant-client-add')), findsOneWidget);
      expect(find.byType(SearchableClientPicker), findsNothing);
    },
  );

  for (final width in <double>[360, 390, 600, 1200]) {
    testWidgets('chat history remains usable at width $width', (tester) async {
      tester.view.devicePixelRatio = 1;
      tester.view.physicalSize = Size(width, 900);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetPhysicalSize);
      await _pump(tester);
      await tester.tap(find.byKey(const Key('assistant-history-menu')));
      await tester.pumpAndSettle();
      expect(find.text('Historia rozmów'), findsOneWidget);
      expect(
        find.byKey(const Key('assistant-history-new-chat')),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('optional Client context is compact and initialClientId clears', (
    tester,
  ) async {
    await _pump(tester, page: const UnifiedAssistantPage(initialClientId: 77));
    expect(find.byKey(const Key('assistant-client-chip')), findsOneWidget);
    expect(find.textContaining('Klient #77'), findsOneWidget);
    await tester.tap(find.byKey(const Key('assistant-client-clear')));
    await tester.pump();
    expect(find.byKey(const Key('assistant-client-add')), findsOneWidget);
    await tester.tap(find.byKey(const Key('assistant-client-add')));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('assistant-client-picker-modal')),
      findsOneWidget,
    );
  });

  testWidgets('selected Client context is sent as canonical clientId', (
    tester,
  ) async {
    final runs = _RecordingRepository();
    await _pump(
      tester,
      repository: runs,
      page: const UnifiedAssistantPage(initialClientId: 77),
    );
    await tester.enterText(
      find.byKey(const Key('unified-ai-question')),
      'Pytanie w wybranym kontekście klienta',
    );
    await tester.tap(find.byKey(const Key('unified-ai-send')));
    await tester.pumpAndSettle();
    expect(runs.clientIds, <int?>[77]);
  });

  testWidgets('three-dot action opens server-backed chat history', (
    tester,
  ) async {
    await _pump(tester);
    await tester.tap(find.byKey(const Key('assistant-history-menu')));
    await tester.pumpAndSettle();
    expect(find.text('Historia rozmów'), findsOneWidget);
    expect(find.byKey(const Key('assistant-history-empty')), findsOneWidget);
    expect(find.byKey(const Key('assistant-history-new-chat')), findsOneWidget);
  });

  testWidgets('history exposes bounded loading and error retry states', (
    tester,
  ) async {
    final slow = _SlowConversationRepository();
    await _pump(tester, conversationRepository: slow, settle: false);
    await tester.pump();
    await tester.tap(find.byKey(const Key('assistant-history-menu')));
    await tester.pump();
    expect(find.byKey(const Key('assistant-history-loading')), findsOneWidget);
    slow.complete();
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('assistant-history-empty')), findsOneWidget);

    await tester.pumpWidget(const SizedBox.shrink());
    final failing = _FailingConversationRepository();
    await _pump(tester, conversationRepository: failing);
    await tester.tap(find.byKey(const Key('assistant-history-menu')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('assistant-history-error')), findsOneWidget);
    failing.fail = false;
    await tester.tap(find.byKey(const Key('assistant-history-retry')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('assistant-history-empty')), findsOneWidget);
  });

  testWidgets('rename is server-backed and survives history refetch', (
    tester,
  ) async {
    final history = _RenameConversationRepository();
    await _pump(tester, conversationRepository: history);
    await tester.tap(find.byKey(const Key('assistant-history-menu')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('assistant-history-actions-41')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Zmień nazwę'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('assistant-history-rename-input')),
      'Nowa nazwa serwerowa',
    );
    await tester.tap(find.byKey(const Key('assistant-history-rename-save')));
    await tester.pumpAndSettle();
    expect(history.renamedTitle, 'Nowa nazwa serwerowa');
    expect(find.text('Nowa nazwa serwerowa'), findsWidgets);
    await tester.tap(find.byTooltip('Zamknij'));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('assistant-active-conversation-title')),
      findsOneWidget,
    );
    expect(find.text('Nowa nazwa serwerowa'), findsOneWidget);
  });

  testWidgets('new chat is server-created and becomes selected', (
    tester,
  ) async {
    final history = _ConversationRepository();
    await _pump(tester, conversationRepository: history);
    await tester.tap(find.byKey(const Key('assistant-history-menu')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('assistant-history-new-chat')));
    await tester.pumpAndSettle();
    expect(history.created, 1);
    expect(find.text('Nowa rozmowa'), findsOneWidget);
  });

  testWidgets('switching chats never renders Chat A result in Chat B', (
    tester,
  ) async {
    final history = _MultiConversationRepository();
    await _pump(tester, conversationRepository: history);
    expect(find.text('Odpowiedź Chat A'), findsOneWidget);
    await tester.tap(find.byKey(const Key('assistant-history-menu')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('assistant-history-chat-2')));
    await tester.pumpAndSettle();
    expect(find.text('Odpowiedź Chat B'), findsOneWidget);
    expect(find.text('Odpowiedź Chat A'), findsNothing);
  });

  testWidgets('deleting active chat warns and never invokes run cancel', (
    tester,
  ) async {
    final runs = _PendingRepository();
    final history = _ActiveConversationRepository();
    await _pump(tester, repository: runs, conversationRepository: history);
    await tester.tap(find.byKey(const Key('assistant-history-menu')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('assistant-history-actions-7')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Usuń').last);
    await tester.pumpAndSettle();
    expect(
      find.textContaining('Usunięcie rozmowy nie anuluje trwającej analizy.'),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('assistant-history-delete-confirm')));
    await tester.pumpAndSettle();
    expect(history.deleted, 1);
    expect(runs.cancelledRunId, isNull);
  });

  testWidgets('hidden active run stays controllable through global banner', (
    tester,
  ) async {
    final runs = _HiddenRunRepository();
    await _pump(
      tester,
      repository: runs,
      conversationRepository: _EmptyConversationRepository(),
    );
    expect(
      find.byKey(const Key('assistant-hidden-active-run')),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('assistant-hidden-active-cancel')));
    await tester.pumpAndSettle();
    expect(runs.cancelledRunId, 'hidden-run');
    expect(find.byKey(const Key('assistant-hidden-active-run')), findsNothing);
  });

  testWidgets(
    'active run is an Assistant bubble and user bubble has no status',
    (tester) async {
      final runs = _PendingRepository();
      final history = _RunStateConversationRepository(status: 'waiting');
      await _pump(
        tester,
        repository: runs,
        conversationRepository: history,
        settle: false,
      );
      await tester.pump(const Duration(milliseconds: 100));
      expect(
        find.byKey(const Key('assistant-run-status-bubble')),
        findsOneWidget,
      );
      expect(find.text('Oczekuję na analizę.'), findsOneWidget);
      expect(
        find.byKey(const Key('assistant-message-status-701')),
        findsNothing,
      );
    },
  );

  for (final status in <String>['review_required', 'failed', 'cancelled']) {
    testWidgets('$status without answer is a terminal Assistant bubble', (
      tester,
    ) async {
      await _pump(
        tester,
        conversationRepository: _RunStateConversationRepository(status: status),
      );
      expect(
        find.byKey(ValueKey<String>('assistant-run-terminal-$status')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('assistant-message-status-701')),
        findsNothing,
      );
    });
  }

  testWidgets('persisted final response replaces temporary run state once', (
    tester,
  ) async {
    await _pump(
      tester,
      conversationRepository: _CompletedConversationRepository(),
    );
    expect(find.text('Gotowa odpowiedź rozmowy.'), findsOneWidget);
    expect(find.byKey(const Key('assistant-run-status-bubble')), findsNothing);
    expect(
      find.byKey(const ValueKey<String>('assistant-run-terminal-completed')),
      findsNothing,
    );
  });

  testWidgets(
    'dispose and recreate restores the same server run without cancel',
    (tester) async {
      final runs = _LifecycleRunRepository();
      final history = _LifecycleConversationRepository(runs);
      await _pump(
        tester,
        repository: runs,
        conversationRepository: history,
        settle: false,
      );
      await tester.pump(const Duration(milliseconds: 100));
      expect(runs.lastRequestedRunId, 'lifecycle-run');
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
      expect(runs.cancelledRunId, isNull);

      runs.completed = true;
      await _pump(tester, repository: runs, conversationRepository: history);
      expect(find.text('Wynik po ponownym otwarciu.'), findsOneWidget);
      expect(runs.cancelledRunId, isNull);
    },
  );

  testWidgets('repeated resume refresh starts only one replacement poller', (
    tester,
  ) async {
    final runs = _LifecycleRunRepository();
    final history = _LifecycleConversationRepository(runs);
    await _pump(
      tester,
      repository: runs,
      conversationRepository: history,
      settle: false,
    );
    await tester.pump(const Duration(milliseconds: 100));
    final before = runs.getCalls;
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump(const Duration(milliseconds: 100));
    expect(runs.getCalls, before + 1);
    expect(runs.maxConcurrentGets, 1);
    expect(runs.cancelledRunId, isNull);
  });

  testWidgets('server auto-title refreshes AppBar after first run creation', (
    tester,
  ) async {
    final history = _AutoTitleConversationRepository();
    await _pump(tester, conversationRepository: history);
    await tester.enterText(
      find.byKey(const Key('unified-ai-question')),
      'Jakie są typowe przyczyny osiadania fundamentów?',
    );
    await tester.tap(find.byKey(const Key('unified-ai-send')));
    await tester.pumpAndSettle();
    expect(find.text('Typowe przyczyny osiadania fundamentów'), findsOneWidget);
    expect(history.getCalls, greaterThanOrEqualTo(1));
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
    expect(find.text('Nowa rozmowa'), findsOneWidget);
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
      expect(
        find.byKey(
          const ValueKey<String>('assistant-run-terminal-review_required'),
        ),
        findsOneWidget,
      );
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
  AssistantConversationRepository? conversationRepository,
  UnifiedAssistantPage page = const UnifiedAssistantPage(),
  bool settle = true,
}) async {
  final runRepository = repository ?? _RunRepository();
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authControllerProvider.overrideWith(_Auth.new),
        assistantRunRepositoryProvider.overrideWithValue(runRepository),
        assistantConversationRepositoryProvider.overrideWithValue(
          conversationRepository ??
              (runRepository is _PendingRepository ||
                      runRepository is _TerminalFailureRepository
                  ? _EmptyConversationRepository()
                  : _ConversationRepository()),
        ),
      ],
      child: MaterialApp(home: page),
    ),
  );
  if (settle) {
    await tester.pumpAndSettle();
  } else {
    await tester.pump();
  }
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
    int? conversationId,
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
  final clientIds = <int?>[];

  @override
  Future<AssistantRunSnapshot> create({
    required AuthSession session,
    required String question,
    required String attemptId,
    required List<Map<String, String>> conversation,
    int? conversationId,
    int? clientId,
    int? candidateId,
    int? documentId,
    int? mailSourceId,
    int? inspectionId,
  }) async {
    conversations.add(
      conversation.map(Map<String, String>.from).toList(growable: false),
    );
    clientIds.add(clientId);
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
    int? conversationId,
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
    int? conversationId,
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
    int? conversationId,
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

AssistantConversationDetail _chat({
  int id = 1,
  String title = 'Nowa rozmowa',
  String? answer,
  UnifiedAssistantAnswer? runResult,
  bool active = false,
  String? latestRunId,
  String? latestRunStatus,
}) => AssistantConversationDetail(
  id: id,
  title: title,
  createdAt: DateTime.utc(2026, 8, 29),
  lastActivityAt: DateTime.utc(2026, 8, 29),
  active: active,
  latestRunId: latestRunId,
  latestRunStatus: latestRunStatus,
  messages: answer == null && runResult == null
      ? const <AssistantConversationMessage>[]
      : <AssistantConversationMessage>[
          AssistantConversationMessage(
            id: id * 10,
            role: 'assistant',
            content: runResult?.answer ?? answer!,
            assistantRunId: 'run-$id',
            runStatus: 'completed',
            runResult:
                runResult ??
                UnifiedAssistantAnswer(
                  requestId: 'run-$id',
                  answer: answer!,
                  status: 'accepted_local',
                  progress: 'complete',
                  targetScope: 'TARGET_01',
                  claims: const <UnifiedAssistantClaim>[],
                  sources: const <UnifiedAssistantSource>[],
                  usedTools: const <String>[],
                  externalAnalysisUsed: false,
                ),
            createdAt: DateTime.utc(2026, 8, 29),
          ),
        ],
  hasOlder: false,
);

class _ConversationRepository extends AssistantConversationRepository {
  _ConversationRepository() : super(Dio());
  int created = 0;

  @override
  Future<List<AssistantConversationSummary>> listChats({
    required AuthSession session,
    int limit = 20,
  }) async => const <AssistantConversationSummary>[];

  @override
  Future<AssistantConversationDetail> createChat({
    required AuthSession session,
    String? title,
  }) async {
    created += 1;
    return _chat(title: title ?? 'Nowa rozmowa');
  }

  @override
  Future<AssistantConversationDetail> getChat({
    required AuthSession session,
    required int conversationId,
  }) async => _chat(runResult: _completedAnswer);
}

class _EmptyConversationRepository extends _ConversationRepository {
  @override
  Future<AssistantConversationDetail> getChat({
    required AuthSession session,
    required int conversationId,
  }) async => _chat(id: conversationId);
}

class _SlowConversationRepository extends _ConversationRepository {
  final Completer<List<AssistantConversationSummary>> _completer =
      Completer<List<AssistantConversationSummary>>();

  void complete() {
    if (!_completer.isCompleted) {
      _completer.complete(const <AssistantConversationSummary>[]);
    }
  }

  @override
  Future<List<AssistantConversationSummary>> listChats({
    required AuthSession session,
    int limit = 20,
  }) => _completer.future;
}

class _FailingConversationRepository extends _ConversationRepository {
  bool fail = true;

  @override
  Future<List<AssistantConversationSummary>> listChats({
    required AuthSession session,
    int limit = 20,
  }) async {
    if (fail) throw StateError('synthetic history failure');
    return const <AssistantConversationSummary>[];
  }
}

class _RenameConversationRepository extends _ConversationRepository {
  String title = 'Nazwa początkowa';
  String? renamedTitle;

  AssistantConversationDetail get detail =>
      _chat(id: 41, title: title, answer: 'Zapisana odpowiedź.');

  @override
  Future<List<AssistantConversationSummary>> listChats({
    required AuthSession session,
    int limit = 20,
  }) async => <AssistantConversationSummary>[detail];

  @override
  Future<AssistantConversationDetail> getChat({
    required AuthSession session,
    required int conversationId,
  }) async => detail;

  @override
  Future<AssistantConversationDetail> renameChat({
    required AuthSession session,
    required int conversationId,
    required String title,
  }) async {
    renamedTitle = title;
    this.title = title;
    return detail;
  }
}

class _MultiConversationRepository extends _ConversationRepository {
  @override
  Future<List<AssistantConversationSummary>> listChats({
    required AuthSession session,
    int limit = 20,
  }) async => <AssistantConversationSummary>[
    _chat(id: 1, title: 'Chat A', answer: 'Odpowiedź Chat A'),
    _chat(id: 2, title: 'Chat B', answer: 'Odpowiedź Chat B'),
  ];

  @override
  Future<AssistantConversationDetail> getChat({
    required AuthSession session,
    required int conversationId,
  }) async => conversationId == 1
      ? _chat(id: 1, title: 'Chat A', answer: 'Odpowiedź Chat A')
      : _chat(id: 2, title: 'Chat B', answer: 'Odpowiedź Chat B');
}

class _RunStateConversationRepository extends _ConversationRepository {
  _RunStateConversationRepository({required this.status});
  final String status;

  AssistantConversationDetail get detail => AssistantConversationDetail(
    id: 70,
    title: 'Stan trwałej analizy',
    createdAt: DateTime.utc(2026, 8, 30),
    lastActivityAt: DateTime.utc(2026, 8, 30),
    active: <String>{
      'created',
      'queued',
      'running',
      'waiting',
    }.contains(status),
    latestRunId: 'pending-run',
    latestRunStatus: status,
    messages: <AssistantConversationMessage>[
      AssistantConversationMessage(
        id: 701,
        role: 'user',
        content: 'Pytanie użytkownika bez etykiety stanu.',
        assistantRunId: 'pending-run',
        runStatus: status,
        createdAt: DateTime.utc(2026, 8, 30),
      ),
    ],
    hasOlder: false,
  );

  @override
  Future<List<AssistantConversationSummary>> listChats({
    required AuthSession session,
    int limit = 20,
  }) async => <AssistantConversationSummary>[detail];

  @override
  Future<AssistantConversationDetail> getChat({
    required AuthSession session,
    required int conversationId,
  }) async => detail;
}

class _CompletedConversationRepository extends _ConversationRepository {
  AssistantConversationDetail get detail => AssistantConversationDetail(
    id: 71,
    title: 'Zakończona rozmowa',
    createdAt: DateTime.utc(2026, 8, 30),
    lastActivityAt: DateTime.utc(2026, 8, 30),
    active: false,
    latestRunId: 'completed-state-run',
    latestRunStatus: 'completed',
    messages: <AssistantConversationMessage>[
      AssistantConversationMessage(
        id: 711,
        role: 'user',
        content: 'Pytanie zakończone.',
        assistantRunId: 'completed-state-run',
        runStatus: 'completed',
        createdAt: DateTime.utc(2026, 8, 30),
      ),
      AssistantConversationMessage(
        id: 712,
        role: 'assistant',
        content: 'Gotowa odpowiedź rozmowy.',
        assistantRunId: 'completed-state-run',
        runStatus: 'completed',
        runResult: const UnifiedAssistantAnswer(
          requestId: 'completed-state-run',
          answer: 'Gotowa odpowiedź rozmowy.',
          status: 'accepted_local',
          progress: 'complete',
          targetScope: 'TARGET_01',
          claims: <UnifiedAssistantClaim>[],
          sources: <UnifiedAssistantSource>[],
          usedTools: <String>[],
          externalAnalysisUsed: false,
        ),
        createdAt: DateTime.utc(2026, 8, 30),
      ),
    ],
    hasOlder: false,
  );

  @override
  Future<List<AssistantConversationSummary>> listChats({
    required AuthSession session,
    int limit = 20,
  }) async => <AssistantConversationSummary>[detail];

  @override
  Future<AssistantConversationDetail> getChat({
    required AuthSession session,
    required int conversationId,
  }) async => detail;
}

class _AutoTitleConversationRepository extends _ConversationRepository {
  int getCalls = 0;

  @override
  Future<AssistantConversationDetail> createChat({
    required AuthSession session,
    String? title,
  }) async => _chat(id: 81, title: 'Nowa rozmowa');

  @override
  Future<AssistantConversationDetail> getChat({
    required AuthSession session,
    required int conversationId,
  }) async {
    getCalls += 1;
    return AssistantConversationDetail(
      id: 81,
      title: 'Typowe przyczyny osiadania fundamentów',
      createdAt: DateTime.utc(2026, 8, 30),
      lastActivityAt: DateTime.utc(2026, 8, 30),
      active: false,
      latestRunId: 'completed-run',
      latestRunStatus: 'completed',
      messages: <AssistantConversationMessage>[
        AssistantConversationMessage(
          id: 811,
          role: 'user',
          content: 'Jakie są typowe przyczyny osiadania fundamentów?',
          assistantRunId: 'completed-run',
          runStatus: 'completed',
          createdAt: DateTime.utc(2026, 8, 30),
        ),
        AssistantConversationMessage(
          id: 812,
          role: 'assistant',
          content: _completedAnswer.answer,
          assistantRunId: 'completed-run',
          runStatus: 'completed',
          runResult: _completedAnswer,
          createdAt: DateTime.utc(2026, 8, 30),
        ),
      ],
      hasOlder: false,
    );
  }
}

class _ActiveConversationRepository extends _ConversationRepository {
  int deleted = 0;
  int listCalls = 0;

  @override
  Future<List<AssistantConversationSummary>> listChats({
    required AuthSession session,
    int limit = 20,
  }) async {
    listCalls += 1;
    if (listCalls == 1) return const <AssistantConversationSummary>[];
    return <AssistantConversationSummary>[
      _chat(
        id: 7,
        title: 'Aktywna rozmowa',
        active: true,
        latestRunId: 'pending-run',
        latestRunStatus: 'waiting',
      ),
    ];
  }

  @override
  Future<AssistantConversationDetail> getChat({
    required AuthSession session,
    required int conversationId,
  }) async => _chat(
    id: 7,
    title: 'Aktywna rozmowa',
    active: true,
    latestRunId: 'pending-run',
    latestRunStatus: 'waiting',
  );

  @override
  Future<AssistantConversationDeleteResult> deleteChat({
    required AuthSession session,
    required int conversationId,
  }) async {
    deleted += 1;
    return AssistantConversationDeleteResult(
      id: conversationId,
      deletedAt: DateTime.utc(2026, 8, 29),
      activeRunId: 'pending-run',
      message: 'Usunięcie rozmowy nie anuluje trwającej analizy.',
    );
  }
}

class _HiddenRunRepository extends _PendingRepository {
  @override
  Future<List<AssistantRunSnapshot>> listActive({
    required AuthSession session,
  }) async => <AssistantRunSnapshot>[
    AssistantRunSnapshot(
      runId: 'hidden-run',
      attemptId: 'hidden_attempt',
      conversationId: 99,
      conversationDeleted: true,
      status: 'waiting',
      currentStage: 'analyzing_local',
      complexity: 'standard',
      progress: const AssistantRunProgress(message: 'Analiza trwa.'),
      canCancel: true,
      pollAfterMs: 30000,
      recoveryGeneration: 0,
      createdAt: DateTime.utc(2026, 8, 29),
      updatedAt: DateTime.utc(2026, 8, 29),
    ),
  ];
}

class _LifecycleRunRepository extends _PendingRepository {
  bool completed = false;
  String? lastRequestedRunId;
  int getCalls = 0;
  int concurrentGets = 0;
  int maxConcurrentGets = 0;

  @override
  Future<AssistantRunSnapshot> get({
    required AuthSession session,
    required String runId,
    CancelToken? cancelToken,
  }) async {
    getCalls += 1;
    concurrentGets += 1;
    if (concurrentGets > maxConcurrentGets) maxConcurrentGets = concurrentGets;
    await Future<void>.delayed(const Duration(milliseconds: 10));
    concurrentGets -= 1;
    lastRequestedRunId = runId;
    if (!completed) {
      return AssistantRunSnapshot(
        runId: runId,
        attemptId: 'lifecycle_attempt',
        conversationId: 51,
        status: 'waiting',
        currentStage: 'analyzing_local',
        complexity: 'standard',
        progress: const AssistantRunProgress(message: 'Analiza trwa.'),
        canCancel: true,
        pollAfterMs: 30000,
        recoveryGeneration: 0,
        createdAt: DateTime.utc(2026, 8, 29),
        updatedAt: DateTime.utc(2026, 8, 29),
      );
    }
    return AssistantRunSnapshot(
      runId: runId,
      attemptId: 'lifecycle_attempt',
      conversationId: 51,
      status: 'completed',
      complexity: 'standard',
      progress: const AssistantRunProgress(message: 'Analiza zakończona.'),
      canCancel: false,
      pollAfterMs: 500,
      recoveryGeneration: 0,
      result: const UnifiedAssistantAnswer(
        requestId: 'lifecycle-run',
        answer: 'Wynik po ponownym otwarciu.',
        status: 'accepted_local',
        progress: 'complete',
        targetScope: 'TARGET_01',
        claims: <UnifiedAssistantClaim>[],
        sources: <UnifiedAssistantSource>[],
        usedTools: <String>[],
        externalAnalysisUsed: false,
      ),
      createdAt: DateTime.utc(2026, 8, 29),
      updatedAt: DateTime.utc(2026, 8, 29),
    );
  }
}

class _LifecycleConversationRepository extends _ConversationRepository {
  _LifecycleConversationRepository(this.runs);
  final _LifecycleRunRepository runs;

  AssistantConversationDetail get detail => _chat(
    id: 51,
    title: 'Rozmowa trwała',
    active: !runs.completed,
    latestRunId: 'lifecycle-run',
    latestRunStatus: runs.completed ? 'completed' : 'waiting',
    answer: runs.completed ? 'Wynik po ponownym otwarciu.' : null,
  );

  @override
  Future<List<AssistantConversationSummary>> listChats({
    required AuthSession session,
    int limit = 20,
  }) async => <AssistantConversationSummary>[detail];

  @override
  Future<AssistantConversationDetail> getChat({
    required AuthSession session,
    required int conversationId,
  }) async => detail;
}
