import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/auth/domain/current_user.dart';
import 'package:ai_lab/features/client_candidates/application/client_candidates_providers.dart';
import 'package:ai_lab/features/client_candidates/application/client_candidates_repository.dart';
import 'package:ai_lab/features/client_candidates/data/client_candidates_api.dart';
import 'package:ai_lab/features/client_candidates/domain/client_candidate_context.dart';
import 'package:ai_lab/features/client_candidates/presentation/client_candidate_details_page.dart';
import 'package:ai_lab/features/mail/data/global_mail_api.dart';
import 'package:ai_lab/features/mail/domain/global_mail.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

const CandidateDuplicateMatch _match = CandidateDuplicateMatch(
  clientId: 44,
  clientName: 'Istniejący klient',
  workflowStatus: 'inspection',
  workflowStatusLabel: 'Oględziny',
  confidence: 'certain',
  reasons: <String>['exact_email', 'exact_phone'],
);

final ClientCandidateContext _context = ClientCandidateContext(
  candidate: <String, dynamic>{
    'id': 7,
    'name': 'Kandydat testowy',
    'client_type': 'company',
    'primary_email': 'test@example.invalid',
    'status': 'pending',
    'confidence': 0.9,
  },
  gmailMessages: const <Map<String, dynamic>>[],
  sheetsRows: const <Map<String, dynamic>>[],
  documents: const <Map<String, dynamic>>[],
  otherSources: const <Map<String, dynamic>>[],
  metadata: const <String, dynamic>{
    'gmail_message_count': 0,
    'sheets_row_count': 0,
    'document_count': 0,
    'source_count': 0,
  },
);

final CandidateMergePreview _preview = CandidateMergePreview(
  candidate: const <String, dynamic>{'id': 7, 'name': 'Kandydat testowy'},
  target: const <String, dynamic>{'id': 44, 'name': 'Istniejący klient'},
  match: _match,
  fieldProposals: const <Map<String, dynamic>>[
    <String, dynamic>{
      'field': 'name',
      'candidate_value': 'Kandydat testowy',
      'target_value': 'Istniejący klient',
      'proposed_action': 'manual_conflict',
      'required_resolution': true,
    },
    <String, dynamic>{
      'field': 'primary_email',
      'candidate_value': 'test@example.invalid',
      'target_value': 'test@example.invalid',
      'proposed_action': 'keep_existing',
      'required_resolution': false,
    },
  ],
  relationCounts: const <String, dynamic>{
    'documents_relinked': 2,
    'emails_relinked': 1,
    'sources_preserved': 3,
  },
  expectedCandidateVersion: '2026-08-19T12:00:00+00:00',
  blockedReasons: const <String>['name:manual_resolution_required'],
);

class _AuthController extends AuthController {
  @override
  Future<AuthState> build() async => const AuthState(
    session: AuthSession(accessToken: 'token', tokenType: 'Bearer'),
    user: CurrentUser(
      id: 1,
      username: 'tester',
      email: 'tester@example.invalid',
      role: 'User',
      isActive: true,
      mustChangePassword: false,
      passwordResetRequested: false,
    ),
  );
}

class _AdminAuthController extends AuthController {
  @override
  Future<AuthState> build() async => const AuthState(
    session: AuthSession(accessToken: 'token', tokenType: 'Bearer'),
    user: CurrentUser(
      id: 2,
      username: 'candidate-admin',
      email: 'candidate-admin@example.invalid',
      role: 'Administrator',
      isActive: true,
      mustChangePassword: false,
      passwordResetRequested: false,
    ),
  );
}

class _IgnoreApi extends GlobalMailApi {
  _IgnoreApi() : super(Dio());

  final List<(String, String)> created = <(String, String)>[];

  @override
  Future<IgnoredMailSourceRule> ignoreSender(
    AuthSession session, {
    required String value,
    String ruleType = 'email',
  }) async {
    created.add((ruleType, value));
    return IgnoredMailSourceRule(
      id: 1,
      ruleType: ruleType,
      normalizedValue: value,
      isActive: true,
      createdAt: DateTime(2026, 8, 29),
      updatedAt: DateTime(2026, 8, 29),
    );
  }
}

class _Repository extends ClientCandidatesRepository {
  _Repository() : super(ClientCandidatesApi(Dio()));

  int previewCalls = 0;
  int mergeCalls = 0;

  @override
  Future<CandidateAcceptResult> accept({
    required AuthSession session,
    required int candidateId,
  }) {
    throw const CandidateDuplicateException(
      clientId: 44,
      matchedBy: 'email',
      matches: <CandidateDuplicateMatch>[_match],
    );
  }

  @override
  Future<CandidateMergePreview> fetchMergePreview({
    required AuthSession session,
    required int candidateId,
    required int targetClientId,
  }) async {
    previewCalls++;
    return _preview;
  }

  @override
  Future<CandidateMergeResult> merge({
    required AuthSession session,
    required int candidateId,
    required int targetClientId,
    required String operationId,
    required String expectedCandidateVersion,
    required Map<String, String> fieldDecisions,
  }) async {
    mergeCalls++;
    expect(operationId.length, 36);
    expect(fieldDecisions['name'], 'keep_existing');
    return const CandidateMergeResult(
      clientId: 44,
      clientName: 'Istniejący klient',
      idempotentReplay: false,
    );
  }
}

Future<void> _pump(
  WidgetTester tester,
  _Repository repository, {
  required Size size,
  ClientCandidateContext? contextData,
  GlobalMailApi? mailApi,
  bool admin = false,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final router = GoRouter(
    initialLocation: '/client-candidates/7',
    routes: <RouteBase>[
      GoRoute(
        path: '/client-candidates/7',
        builder: (_, _) => const ClientCandidateDetailsPage(candidateId: 7),
      ),
      GoRoute(
        path: '/clients/:id',
        builder: (_, state) =>
            Scaffold(body: Text('Klient ${state.pathParameters['id']}')),
      ),
      GoRoute(
        path: '/client-candidates',
        builder: (_, _) => const Scaffold(body: Text('Kandydaci')),
      ),
    ],
  );
  addTearDown(router.dispose);
  final container = ProviderContainer(
    overrides: [
      authControllerProvider.overrideWith(
        admin ? _AdminAuthController.new : _AuthController.new,
      ),
      clientCandidatesRepositoryProvider.overrideWithValue(repository),
      clientCandidateContextProvider.overrideWith(
        (_, _) async => contextData ?? _context,
      ),
      if (mailApi != null) globalMailApiProvider.overrideWithValue(mailApi),
    ],
  );
  addTearDown(container.dispose);
  await container.read(authControllerProvider.future);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _openDuplicate(WidgetTester tester) async {
  await tester.tap(find.text('Zatwierdź jako klienta'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Zatwierdź'));
  await tester.pumpAndSettle();
}

void main() {
  test('multi-match domain contract parses bounded reasons', () {
    final match = CandidateDuplicateMatch.fromJson(<String, dynamic>{
      'client_id': 44,
      'client_name': 'Istniejący klient',
      'workflow_status': 'inspection',
      'workflow_status_label': 'Oględziny',
      'confidence': 'certain',
      'reasons': <String>['exact_email', 'exact_phone'],
    });
    expect(match.clientId, 44);
    expect(match.reasons, <String>['exact_email', 'exact_phone']);
  });

  testWidgets('duplicate dialog shows reasons and cancel has zero writes', (
    tester,
  ) async {
    final repository = _Repository();
    await _pump(tester, repository, size: const Size(360, 900));
    await _openDuplicate(tester);
    expect(find.text('Znaleziono istniejącego klienta'), findsOneWidget);
    expect(find.textContaining('identyczny e-mail'), findsOneWidget);
    expect(find.textContaining('identyczny telefon'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.tap(find.text('Anuluj').last);
    await tester.pumpAndSettle();
    expect(repository.previewCalls, 0);
    expect(repository.mergeCalls, 0);
  });

  testWidgets('preview requires conflict choice and second confirmation', (
    tester,
  ) async {
    final repository = _Repository();
    await _pump(tester, repository, size: const Size(1200, 1000));
    await _openDuplicate(tester);
    await tester.tap(find.text('Połącz'));
    await tester.pumpAndSettle();
    expect(find.text('Podgląd połączenia'), findsOneWidget);
    expect(find.text('Nazwa'), findsWidgets);
    expect(repository.previewCalls, 1);
    expect(repository.mergeCalls, 0);
    final Finder conflictChoice = find.byType(DropdownButton<String>);
    await tester.ensureVisible(conflictChoice);
    await tester.pumpAndSettle();
    await tester.tap(conflictChoice);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Zachowaj klienta').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Dalej'));
    await tester.pumpAndSettle();
    expect(find.text('Potwierdź połączenie'), findsOneWidget);
    expect(repository.mergeCalls, 0);
    await tester.tap(find.text('Połącz'));
    await tester.pumpAndSettle();
    expect(repository.mergeCalls, 1);
    expect(find.text('Klient 44'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('merge preview remains responsive at 360', (tester) async {
    final repository = _Repository();
    await _pump(tester, repository, size: const Size(360, 1000));
    await _openDuplicate(tester);
    await tester.tap(find.text('Połącz'));
    await tester.pumpAndSettle();
    expect(find.text('Podgląd połączenia'), findsOneWidget);
    expect(find.text('Wybierz'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.tap(find.text('Anuluj').last);
    await tester.pumpAndSettle();
    expect(repository.mergeCalls, 0);
  });

  for (final width in <double>[390, 600]) {
    testWidgets('Candidate details remains responsive at ${width.toInt()}', (
      tester,
    ) async {
      final repository = _Repository();
      await _pump(tester, repository, size: Size(width, 1000));
      expect(find.text('Kandydat testowy'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('Candidate Details ignores only the candidate source sender', (
    tester,
  ) async {
    final _Repository repository = _Repository();
    final _IgnoreApi api = _IgnoreApi();
    final ClientCandidateContext contextData = ClientCandidateContext(
      candidate: const <String, dynamic>{
        'id': 7,
        'name': 'Kandydat testowy',
        'client_type': 'company',
        'primary_email': 'sender@example.com',
        'status': 'pending',
        'confidence': 0.9,
      },
      gmailMessages: const <Map<String, dynamic>>[
        <String, dynamic>{
          'source_id': 71,
          'subject': 'Wiadomość przychodząca',
          'from': <String, dynamic>{'address': 'Sender@Example.COM'},
        },
        <String, dynamic>{
          'source_id': 72,
          'subject': 'Wiadomość wychodząca',
          'from': <String, dynamic>{'address': 'our-mail@example.invalid'},
        },
      ],
      sheetsRows: const <Map<String, dynamic>>[],
      documents: const <Map<String, dynamic>>[],
      otherSources: const <Map<String, dynamic>>[],
      metadata: const <String, dynamic>{
        'gmail_message_count': 2,
        'sheets_row_count': 0,
        'document_count': 0,
        'source_count': 2,
      },
    );
    await _pump(
      tester,
      repository,
      size: const Size(390, 1000),
      contextData: contextData,
      mailApi: api,
      admin: true,
    );
    expect(find.text('Ignoruj ten mail'), findsOneWidget);
    expect(find.byKey(const Key('candidate-ignore-mail-71')), findsOneWidget);
    expect(find.byKey(const Key('candidate-ignore-mail-72')), findsNothing);
    await tester.scrollUntilVisible(
      find.byKey(const Key('candidate-ignore-mail-71')),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('candidate-ignore-mail-71')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-ignore-mail-rule')));
    await tester.pumpAndSettle();
    expect(api.created, <(String, String)>[('email', 'sender@example.com')]);
  });
}
