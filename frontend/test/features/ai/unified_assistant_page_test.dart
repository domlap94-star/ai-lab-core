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
}

Future<void> _pump(WidgetTester tester) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authControllerProvider.overrideWith(_Auth.new),
        unifiedAssistantApiProvider.overrideWithValue(_Api()),
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
