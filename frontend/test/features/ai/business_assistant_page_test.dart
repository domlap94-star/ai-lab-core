import 'package:ai_lab/features/ai/application/business_assistant_providers.dart';
import 'package:ai_lab/features/ai/data/business_assistant_api.dart';
import 'package:ai_lab/features/ai/domain/business_assistant.dart';
import 'package:ai_lab/features/ai/presentation/ai_page.dart';
import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'dart:async';

void main() {
  for (final size in <Size>[
    const Size(360, 800),
    const Size(390, 900),
    const Size(600, 900),
    const Size(1200, 900),
  ]) {
    testWidgets('business assistant is responsive at ${size.width}', (
      tester,
    ) async {
      await _pump(tester, _Gateway(), size);
      expect(
        find.text('Globalny asystent biznesowy tylko do odczytu'),
        findsOneWidget,
      );
      expect(find.byKey(const Key('business-ai-question')), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('submits direct answer and opens a bounded source', (
    tester,
  ) async {
    final gateway = _Gateway();
    await _pump(tester, gateway, const Size(390, 900));
    await tester.enterText(
      find.byKey(const Key('business-ai-question')),
      'Ilu mamy aktywnych klientów?',
    );
    await tester.testTextInput.receiveAction(TextInputAction.send);
    await tester.pumpAndSettle();
    expect(gateway.questions, <String>['Ilu mamy aktywnych klientów?']);
    expect(find.byKey(const Key('business-ai-answer')), findsOneWidget);
    await tester.ensureVisible(
      find.byKey(const Key('business-ai-source-client-7')),
    );
    await tester.tap(find.byKey(const Key('business-ai-source-client-7')));
    await tester.pumpAndSettle();
    expect(find.text('Klient 7'), findsOneWidget);
    final context = tester.element(find.text('Klient 7'));
    GoRouter.of(context).pop();
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('business-ai-answer')), findsOneWidget);
  });

  testWidgets('example chip submits and friendly retry recovers', (
    tester,
  ) async {
    final gateway = _Gateway(failOnce: true);
    await _pump(tester, gateway, const Size(360, 800));
    await tester.tap(find.text('Ilu klientów ma status Oględziny?'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('business-ai-error')), findsOneWidget);
    expect(find.textContaining('DioException'), findsNothing);
    await tester.ensureVisible(find.byKey(const Key('business-ai-retry')));
    await tester.tap(find.byKey(const Key('business-ai-retry')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('business-ai-answer')), findsOneWidget);
  });

  testWidgets('cancelled response cannot overwrite the current AI page', (
    tester,
  ) async {
    final gateway = _SlowGateway();
    await _pumpGateway(tester, gateway, const Size(390, 900));
    await tester.enterText(
      find.byKey(const Key('business-ai-question')),
      'Podsumuj firmę',
    );
    await tester.testTextInput.receiveAction(TextInputAction.send);
    await tester.pump();
    expect(find.byKey(const Key('business-ai-cancel')), findsOneWidget);
    await tester.tap(find.byKey(const Key('business-ai-cancel')));
    gateway.complete();
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('business-ai-answer')), findsNothing);
  });
}

Future<void> _pump(WidgetTester tester, _Gateway gateway, Size size) async {
  await _pumpGateway(tester, gateway, size);
}

Future<void> _pumpGateway(
  WidgetTester tester,
  BusinessAssistantGateway gateway,
  Size size,
) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final router = GoRouter(
    initialLocation: '/ai',
    routes: <RouteBase>[
      GoRoute(path: '/ai', builder: (_, _) => const AiPage()),
      GoRoute(
        path: '/clients/:id',
        builder: (_, state) =>
            Scaffold(body: Text('Klient ${state.pathParameters['id']}')),
      ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authControllerProvider.overrideWith(_TestAuthController.new),
        businessAssistantGatewayProvider.overrideWithValue(gateway),
      ],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
}

const _session = AuthSession(accessToken: 'token', tokenType: 'Bearer');

class _TestAuthController extends AuthController {
  @override
  Future<AuthState> build() async =>
      const AuthState(session: _session, user: null);
}

class _Gateway implements BusinessAssistantGateway {
  _Gateway({this.failOnce = false});
  final bool failOnce;
  final questions = <String>[];
  @override
  Future<BusinessAssistantAnswer> ask({
    required AuthSession session,
    required String question,
    List<Map<String, String>> conversation = const [],
    CancelToken? cancelToken,
  }) async {
    questions.add(question);
    if (failOnce && questions.length == 1) {
      throw DioException(
        requestOptions: RequestOptions(path: '/ai/business/ask'),
        type: DioExceptionType.connectionError,
      );
    }
    return const BusinessAssistantAnswer(
      answer: 'Mamy 10 aktywnych klientów.',
      sources: <BusinessAssistantSource>[
        BusinessAssistantSource(
          sourceType: 'client',
          sourceId: 7,
          title: 'Klient testowy',
          snippet: 'Bezpieczny fragment.',
          route: '/clients/7',
        ),
      ],
      limitations: <String>['Pokrycie semantyczne jest ograniczone.'],
      intent: 'analytics',
      directAnswer: true,
      semanticStatus: 'not_used',
    );
  }
}

class _SlowGateway implements BusinessAssistantGateway {
  final _completer = Completer<BusinessAssistantAnswer>();
  void complete() => _completer.complete(_answer);
  @override
  Future<BusinessAssistantAnswer> ask({
    required AuthSession session,
    required String question,
    List<Map<String, String>> conversation = const [],
    CancelToken? cancelToken,
  }) => _completer.future;
}

const _answer = BusinessAssistantAnswer(
  answer: 'Spóźniona odpowiedź.',
  sources: <BusinessAssistantSource>[],
  limitations: <String>[],
  intent: 'general_summary',
  directAnswer: false,
  semanticStatus: 'not_used',
);
