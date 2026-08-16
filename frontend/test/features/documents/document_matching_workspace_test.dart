import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/documents/application/documents_providers.dart';
import 'package:ai_lab/features/documents/application/documents_repository.dart';
import 'package:ai_lab/features/documents/data/document_content.dart';
import 'package:ai_lab/features/documents/domain/document.dart';
import 'package:ai_lab/features/documents/domain/document_client_match.dart';
import 'package:ai_lab/features/documents/domain/document_filters.dart';
import 'package:ai_lab/features/documents/domain/document_page.dart';
import 'package:ai_lab/features/documents/presentation/documents_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('matching workspace is responsive and shows conflict evidence', (
    WidgetTester tester,
  ) async {
    final repository = _MatchingRepository(conflict: true);
    await _pump(tester, repository);

    expect(find.text('Powiązanie z klientem'), findsOneWidget);
    expect(find.text('Konflikt'), findsOneWidget);
    expect(
      find.textContaining('Bardzo długie deterministyczne evidence'),
      findsOneWidget,
    );
    expect(find.text('Przenieś tutaj'), findsOneWidget);
    expect(find.text('Odepnij'), findsOneWidget);
    expect(find.text('Cofnij ostatnią zmianę'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'link conflict, unlink cancellation and undo use explicit controls',
    (WidgetTester tester) async {
      final repository = _MatchingRepository(conflict: true);
      await _pump(tester, repository);

      await tester.tap(find.text('Przenieś tutaj'));
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Dowody wskazują innego klienta'),
        findsOneWidget,
      );
      await tester.tap(find.text('Potwierdź'));
      await tester.pumpAndSettle();
      expect(repository.linkCalls, 1);
      expect(repository.lastConflictConfirmation, isTrue);

      await tester.tap(find.text('Odepnij'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Anuluj'));
      await tester.pumpAndSettle();
      expect(repository.unlinkCalls, 0);

      await tester.tap(find.text('Odepnij'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Potwierdź'));
      await tester.pumpAndSettle();
      expect(repository.unlinkCalls, 1);

      await tester.tap(find.text('Cofnij ostatnią zmianę'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Potwierdź'));
      await tester.pumpAndSettle();
      expect(repository.undoCalls, 1);
    },
  );
}

Future<void> _pump(WidgetTester tester, _MatchingRepository repository) async {
  tester.view.physicalSize = const Size(390, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authControllerProvider.overrideWith(_TestAuthController.new),
        documentsRepositoryProvider.overrideWithValue(repository),
      ],
      child: MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: DocumentClientMatchPanel(document: repository.document),
          ),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

class _MatchingRepository extends DocumentsRepository {
  _MatchingRepository({required this.conflict});
  final bool conflict;
  int linkCalls = 0;
  int unlinkCalls = 0;
  int undoCalls = 0;
  bool? lastConflictConfirmation;

  final RepositoryDocument document = RepositoryDocument(
    id: 42,
    originalFilename: 'document.pdf',
    contentType: 'application/pdf',
    fileSize: 100,
    sourceType: 'gmail_attachment',
    clientId: 7,
    clientName: 'Obecny klient',
    candidateId: 9,
    candidateName: 'Kandydat',
    processingStatus: 'processed',
    metadataStatus: 'processed',
    matchStatus: 'confirmed',
    archiveDepth: 0,
    createdAt: DateTime.utc(2026, 8, 17),
    updatedAt: DateTime.utc(2026, 8, 17),
  );

  @override
  Future<DocumentClientMatch> fetchClientMatch({
    required AuthSession session,
    required int documentId,
  }) async => DocumentClientMatch(
    documentId: documentId,
    currentClientId: 7,
    currentClientName: 'Obecny klient',
    candidateId: 9,
    status: conflict ? 'CONFLICT' : 'ASSIGNED',
    confidence: conflict ? 'CONFLICT' : 'HIGH',
    conflict: conflict,
    history: const <int>[1],
    suggestions: const <DocumentClientSuggestion>[
      DocumentClientSuggestion(
        clientId: 8,
        clientName: 'Sugerowany klient',
        confidence: 'CONFLICT',
        evidence: <DocumentMatchEvidence>[
          DocumentMatchEvidence(
            kind: 'candidate_match',
            description:
                'Bardzo długie deterministyczne evidence potwierdzające zachowanie mobilnego układu bez overflow.',
            clientId: 8,
          ),
        ],
      ),
    ],
    evidence: const <DocumentMatchEvidence>[],
  );

  @override
  Future<RepositoryDocument> fetchDocument({
    required AuthSession session,
    required int documentId,
  }) async => document;

  @override
  Future<DocumentContent> fetchContent({
    required AuthSession session,
    required RepositoryDocument document,
    void Function(int received, int total)? onProgress,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<void> linkClient({
    required AuthSession session,
    required int documentId,
    required int clientId,
    required bool move,
    required bool confirmConflict,
  }) async {
    linkCalls++;
    lastConflictConfirmation = confirmConflict;
  }

  @override
  Future<void> unlinkClient({
    required AuthSession session,
    required int documentId,
  }) async {
    unlinkCalls++;
  }

  @override
  Future<void> undoClientLink({
    required AuthSession session,
    required int documentId,
  }) async {
    undoCalls++;
  }

  @override
  Future<DocumentPage> fetchDocuments({
    required AuthSession session,
    required DocumentFilters filters,
    String search = '',
    int skip = 0,
    int limit = 50,
  }) async => DocumentPage(
    items: const <RepositoryDocument>[],
    total: 0,
    skip: 0,
    limit: 50,
  );
}

const AuthSession _session = AuthSession(
  accessToken: 'token',
  tokenType: 'Bearer',
);

class _TestAuthController extends AuthController {
  @override
  Future<AuthState> build() async =>
      const AuthState(session: _session, user: null);
}
