import 'dart:async';

import 'package:ai_lab/features/ai/application/business_assistant_providers.dart';
import 'package:ai_lab/features/ai/application/technical_assistant_providers.dart';
import 'package:ai_lab/features/ai/data/business_assistant_api.dart';
import 'package:ai_lab/features/ai/data/technical_assistant_api.dart';
import 'package:ai_lab/features/ai/domain/business_assistant.dart';
import 'package:ai_lab/features/ai/domain/technical_assistant.dart';
import 'package:ai_lab/features/ai/presentation/ai_page.dart';
import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/inspections/application/inspections_providers.dart';
import 'package:ai_lab/features/inspections/data/inspections_api.dart';
import 'package:ai_lab/features/inspections/domain/inspection.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

void main() {
  for (final size in <Size>[
    const Size(360, 800),
    const Size(390, 900),
    const Size(600, 900),
    const Size(1200, 900),
  ]) {
    testWidgets('technical mode is responsive at ${size.width}', (
      tester,
    ) async {
      await _pump(tester, _TechnicalGateway(), size: size);
      expect(
        find.text('Asystent techniczny oparty na dowodach'),
        findsOneWidget,
      );
      expect(find.byKey(const Key('technical-ai-question')), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('selector preserves Business mode and switches to Technical', (
    tester,
  ) async {
    await _pump(tester, _TechnicalGateway(), initialMode: AiMode.business);
    expect(find.byKey(const Key('business-ai-question')), findsOneWidget);
    await tester.tap(find.text('Techniczny'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('technical-ai-question')), findsOneWidget);
  });

  testWidgets(
    'submits scoped question and renders facts inference missing data and source',
    (tester) async {
      final gateway = _TechnicalGateway();
      await _pump(tester, gateway, clientId: 7, inspectionId: 9);
      await tester.enterText(
        find.byKey(const Key('technical-ai-question')),
        'Podsumuj przypadek',
      );
      await tester.testTextInput.receiveAction(TextInputAction.send);
      await tester.pumpAndSettle();
      expect(gateway.clientIds, <int?>[7]);
      expect(gateway.inspectionIds, <int?>[9]);
      expect(find.byKey(const Key('technical-ai-answer')), findsOneWidget);
      expect(find.text('Fakty'), findsOneWidget);
      expect(find.text('Wnioski / hipotezy'), findsOneWidget);
      expect(find.text('Brakujące dane'), findsOneWidget);
      await tester.ensureVisible(
        find.byKey(const Key('business-ai-source-inspection-9')),
      );
      await tester.tap(
        find.byKey(const Key('business-ai-source-inspection-9')),
      );
      await tester.pumpAndSettle();
      expect(find.text('Źródło wizji 9'), findsOneWidget);
      final context = tester.element(find.text('Źródło wizji 9'));
      GoRouter.of(context).pop();
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('technical-ai-answer')), findsOneWidget);
    },
  );

  testWidgets(
    'clearing client clears inspection context and starts a new scope',
    (tester) async {
      final gateway = _TechnicalGateway();
      await _pump(tester, gateway, clientId: 7, inspectionId: 9);
      await tester.tap(find.byKey(const Key('client-picker-clear')));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('technical-inspection-picker')),
        findsNothing,
      );
      await tester.enterText(
        find.byKey(const Key('technical-ai-question')),
        'Jakich danych brakuje?',
      );
      await tester.testTextInput.receiveAction(TextInputAction.send);
      await tester.pumpAndSettle();
      expect(gateway.clientIds.last, isNull);
      expect(gateway.inspectionIds.last, isNull);
    },
  );

  testWidgets('cancelled technical response cannot overwrite page', (
    tester,
  ) async {
    final gateway = _SlowTechnicalGateway();
    await _pumpGateway(tester, gateway, size: const Size(390, 900));
    await tester.enterText(
      find.byKey(const Key('technical-ai-question')),
      'Podsumuj technicznie',
    );
    await tester.testTextInput.receiveAction(TextInputAction.send);
    await tester.pump();
    await tester.tap(find.byKey(const Key('business-ai-cancel')));
    gateway.complete();
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('technical-ai-answer')), findsNothing);
  });
}

Future<void> _pump(
  WidgetTester tester,
  TechnicalAssistantGateway gateway, {
  Size size = const Size(390, 900),
  AiMode initialMode = AiMode.technical,
  int? clientId,
  int? inspectionId,
}) => _pumpGateway(
  tester,
  gateway,
  size: size,
  initialMode: initialMode,
  clientId: clientId,
  inspectionId: inspectionId,
);

Future<void> _pumpGateway(
  WidgetTester tester,
  TechnicalAssistantGateway gateway, {
  required Size size,
  AiMode initialMode = AiMode.technical,
  int? clientId,
  int? inspectionId,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final router = GoRouter(
    initialLocation: '/ai',
    routes: <RouteBase>[
      GoRoute(
        path: '/ai',
        builder: (_, _) => AiPage(
          initialMode: initialMode,
          initialClientId: clientId,
          initialInspectionId: inspectionId,
        ),
      ),
      GoRoute(
        path: '/inspections/:id',
        builder: (_, state) =>
            Scaffold(body: Text('Źródło wizji ${state.pathParameters['id']}')),
      ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authControllerProvider.overrideWith(_TestAuthController.new),
        technicalAssistantGatewayProvider.overrideWithValue(gateway),
        businessAssistantGatewayProvider.overrideWithValue(_BusinessGateway()),
        inspectionsApiProvider.overrideWithValue(_InspectionsApi()),
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

class _TechnicalGateway implements TechnicalAssistantGateway {
  final clientIds = <int?>[];
  final inspectionIds = <int?>[];
  @override
  Future<TechnicalAssistantAnswer> ask({
    required AuthSession session,
    required String question,
    int? clientId,
    int? inspectionId,
    List<Map<String, String>> conversation = const [],
    CancelToken? cancelToken,
  }) async {
    clientIds.add(clientId);
    inspectionIds.add(inspectionId);
    return const TechnicalAssistantAnswer(
      answer: 'Analiza techniczna.',
      facts: <String>['Opisano rysę ściany.'],
      inferences: <String>['Przyczyna wymaga potwierdzenia.'],
      missingInformation: <String>['Brakuje pomiarów.'],
      sources: <TechnicalAssistantSource>[
        TechnicalAssistantSource(
          sourceType: 'inspection',
          sourceId: 9,
          title: 'Wizja testowa',
          snippet: 'Rysa ściany.',
          route: '/inspections/9',
        ),
      ],
      limitations: <String>['To nie jest formalna ekspertyza.'],
      intent: 'case_summary',
      semanticStatus: 'limited',
      model: 'llama3.2',
    );
  }
}

class _SlowTechnicalGateway implements TechnicalAssistantGateway {
  final _completer = Completer<TechnicalAssistantAnswer>();
  void complete() => _completer.complete(
    const TechnicalAssistantAnswer(
      answer: 'Spóźniona',
      facts: [],
      inferences: [],
      missingInformation: [],
      sources: [],
      limitations: [],
      intent: 'case_summary',
      semanticStatus: 'not_used',
    ),
  );
  @override
  Future<TechnicalAssistantAnswer> ask({
    required AuthSession session,
    required String question,
    int? clientId,
    int? inspectionId,
    List<Map<String, String>> conversation = const [],
    CancelToken? cancelToken,
  }) => _completer.future;
}

class _BusinessGateway implements BusinessAssistantGateway {
  @override
  Future<BusinessAssistantAnswer> ask({
    required AuthSession session,
    required String question,
    List<Map<String, String>> conversation = const [],
    CancelToken? cancelToken,
  }) async => const BusinessAssistantAnswer(
    answer: 'Biznes',
    sources: [],
    limitations: [],
    intent: 'analytics',
    directAnswer: true,
    semanticStatus: 'not_used',
  );
}

class _InspectionsApi extends InspectionsApi {
  _InspectionsApi() : super(Dio());
  @override
  Future<InspectionPage> list(
    AuthSession session, {
    String search = '',
    int? projectId,
    int? clientId,
    InspectionStatus? status,
    DateTime? dateFrom,
    DateTime? dateTo,
    int skip = 0,
    int limit = 50,
  }) async => InspectionPage(
    items: <Inspection>[_inspection],
    total: 1,
    skip: 0,
    limit: 50,
  );
}

final _inspection = Inspection(
  id: 9,
  clientId: 7,
  clientName: 'Klient 7',
  title: 'Wizja testowa',
  status: InspectionStatus.planned,
  createdAt: DateTime(2026),
  updatedAt: DateTime(2026),
);
