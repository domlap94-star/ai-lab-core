import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/client_ai_knowledge/application/client_ai_knowledge_providers.dart';
import 'package:ai_lab/features/client_ai_knowledge/data/client_ai_knowledge_api.dart';
import 'package:ai_lab/features/client_ai_knowledge/domain/client_ai_knowledge.dart';
import 'package:ai_lab/features/client_ai_knowledge/presentation/client_ai_knowledge_panel.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

void main() {
  testWidgets('client AI is idle until a scoped question is submitted', (
    WidgetTester tester,
  ) async {
    final gateway = _Gateway();
    await _pump(tester, gateway, const Size(360, 800));
    expect(find.text('Zapytaj AI o klienta'), findsOneWidget);
    expect(gateway.calls, isEmpty);

    await tester.enterText(
      find.byKey(const Key('client-ai-question')),
      'Jaki jest telefon klienta?',
    );
    await tester.testTextInput.receiveAction(TextInputAction.send);
    await tester.pumpAndSettle();

    expect(gateway.calls, hasLength(1));
    expect(gateway.calls.single.clientId, 7);
    expect(find.byKey(const Key('client-ai-answer')), findsOneWidget);
    expect(find.text('Telefon klienta: 500 600 700.'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('sources use existing deep routes and Back returns to AI panel', (
    WidgetTester tester,
  ) async {
    final gateway = _Gateway();
    await _pump(tester, gateway, const Size(390, 900));
    await tester.enterText(
      find.byKey(const Key('client-ai-question')),
      'O czym była ostatnia korespondencja?',
    );
    await tester.testTextInput.receiveAction(TextInputAction.send);
    await tester.pumpAndSettle();
    await tester.ensureVisible(
      find.byKey(const Key('client-ai-source-email-55')),
    );
    await tester.tap(find.byKey(const Key('client-ai-source-email-55')));
    await tester.pumpAndSettle();
    expect(find.text('email-source=55'), findsOneWidget);

    final context = tester.element(find.text('email-source=55'));
    GoRouter.of(context).pop();
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('client-ai-answer')), findsOneWidget);
  });

  testWidgets('friendly error has retry and never exposes DioException', (
    WidgetTester tester,
  ) async {
    final gateway = _Gateway(failOnce: true);
    await _pump(tester, gateway, const Size(600, 900));
    await tester.enterText(
      find.byKey(const Key('client-ai-question')),
      'Podsumuj współpracę',
    );
    await tester.testTextInput.receiveAction(TextInputAction.send);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('client-ai-error')), findsOneWidget);
    expect(find.textContaining('DioException'), findsNothing);
    await tester.tap(find.byKey(const Key('client-ai-retry')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('client-ai-answer')), findsOneWidget);
    expect(gateway.calls, hasLength(2));
  });

  testWidgets('long answer and source title do not overflow on mobile', (
    WidgetTester tester,
  ) async {
    final gateway = _Gateway(longContent: true);
    await _pump(tester, gateway, const Size(360, 800));
    await tester.enterText(
      find.byKey(const Key('client-ai-question')),
      'Historia',
    );
    await tester.testTextInput.receiveAction(TextInputAction.send);
    await tester.pumpAndSettle();
    await tester.drag(
      find.byType(SingleChildScrollView),
      const Offset(0, -500),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('client-ai-answer')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}

Future<void> _pump(WidgetTester tester, _Gateway gateway, Size size) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final router = GoRouter(
    initialLocation: '/client',
    routes: <RouteBase>[
      GoRoute(
        path: '/client',
        builder: (context, state) => const Scaffold(
          body: SingleChildScrollView(
            child: ClientAiKnowledgePanel(
              clientId: 7,
              clientName: 'Klient Test',
            ),
          ),
        ),
      ),
      GoRoute(
        path: '/clients/:id',
        builder: (_, state) => Scaffold(
          body: Text(
            'email-source=${state.uri.queryParameters['email_source_id']}',
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
        clientAiKnowledgeGatewayProvider.overrideWithValue(gateway),
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

class _Call {
  const _Call(this.clientId, this.question);
  final int clientId;
  final String question;
}

class _Gateway implements ClientAiKnowledgeGateway {
  _Gateway({this.failOnce = false, this.longContent = false});
  final bool failOnce;
  final bool longContent;
  final List<_Call> calls = <_Call>[];

  @override
  Future<ClientAiAnswer> ask({
    required AuthSession session,
    required int clientId,
    required String question,
    List<Map<String, String>> conversation = const <Map<String, String>>[],
    CancelToken? cancelToken,
  }) async {
    calls.add(_Call(clientId, question));
    if (failOnce && calls.length == 1) {
      throw DioException(
        requestOptions: RequestOptions(path: '/ai'),
        type: DioExceptionType.connectionError,
      );
    }
    final repeated = longContent
        ? List<String>.filled(
            120,
            'Długa odpowiedź oparta na danych.',
          ).join(' ')
        : 'Telefon klienta: 500 600 700.';
    return ClientAiAnswer(
      answer: repeated,
      sources: <ClientAiSource>[
        ClientAiSource(
          sourceType: 'email',
          sourceId: 55,
          title: longContent
              ? List<String>.filled(30, 'Bardzo długi tytuł').join(' ')
              : 'Wiadomość testowa',
          route: '/clients/7?email_source_id=55',
          snippet: 'Bezpieczny fragment wiadomości.',
        ),
      ],
      coverage: const ClientAiCoverage(
        emailsSearched: 1,
        documentsLexicalSearched: 1,
        documentVectorsUsed: 0,
        projectsConsidered: 0,
        inspectionsConsidered: 0,
        timelineEventsConsidered: 0,
      ),
      semanticStatus: 'limited',
      limitations: const <String>[
        'Nie wszystkie dokumenty mają indeks semantyczny.',
      ],
      directAnswer: false,
    );
  }
}
