import 'dart:typed_data';

import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/documents/application/documents_controller.dart';
import 'package:ai_lab/features/documents/application/document_open_service.dart';
import 'package:ai_lab/features/documents/application/documents_providers.dart';
import 'package:ai_lab/features/documents/application/documents_repository.dart';
import 'package:ai_lab/features/documents/data/document_content.dart';
import 'package:ai_lab/features/documents/domain/document.dart';
import 'package:ai_lab/features/documents/domain/document_filters.dart';
import 'package:ai_lab/features/documents/domain/document_page.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('controller resets pagination for search and filters', () async {
    final _FakeDocumentsRepository repository = _FakeDocumentsRepository();
    final ProviderContainer container = ProviderContainer(
      overrides: [
        authControllerProvider.overrideWith(_TestAuthController.new),
        documentsRepositoryProvider.overrideWithValue(repository),
      ],
    );
    addTearDown(container.dispose);

    await container.read(authControllerProvider.future);
    await container.read(documentsControllerProvider.future);
    await container.read(documentsControllerProvider.notifier).nextPage();
    expect(repository.calls.last.skip, 50);

    await container
        .read(documentsControllerProvider.notifier)
        .search(' raport ');
    expect(repository.calls.last.skip, 0);
    expect(repository.calls.last.search, 'raport');

    await container
        .read(documentsControllerProvider.notifier)
        .setFilters(
          const DocumentFilters(linkState: DocumentLinkState.unlinked),
        );
    expect(repository.calls.last.skip, 0);
    expect(repository.calls.last.filters.linkState, DocumentLinkState.unlinked);
  });

  test(
    'controller loads a route-provided client filter on its first request',
    () async {
      final _FakeDocumentsRepository repository = _FakeDocumentsRepository();
      final ProviderContainer container = ProviderContainer(
        overrides: [
          authControllerProvider.overrideWith(_TestAuthController.new),
          documentsRepositoryProvider.overrideWithValue(repository),
          documentsControllerProvider.overrideWith(
            () => DocumentsController(
              initialFilters: const DocumentFilters(
                clientId: 7,
                clientName: 'Klient Test',
              ),
            ),
          ),
        ],
      );
      addTearDown(container.dispose);

      await container.read(authControllerProvider.future);
      await container.read(documentsControllerProvider.future);

      expect(repository.calls, hasLength(1));
      expect(repository.calls.single.filters.clientId, 7);
      expect(repository.calls.single.filters.clientName, 'Klient Test');
    },
  );

  test(
    'open service uses authenticated repository bytes and injectable opener',
    () async {
      final _FakeDocumentsRepository repository = _FakeDocumentsRepository();
      DocumentContent? opened;
      final service = DocumentOpenService(
        repository,
        opener: (DocumentContent content, int documentId) async {
          expect(documentId, 1);
          opened = content;
        },
      );

      await service.open(session: _session, document: _document);

      expect(opened?.bytes, Uint8List.fromList(<int>[1, 2, 3]));
      expect(repository.contentSession, same(_session));
    },
  );
}

const AuthSession _session = AuthSession(
  accessToken: 'token',
  tokenType: 'Bearer',
);

final RepositoryDocument _document = RepositoryDocument(
  id: 1,
  originalFilename: 'faktura.pdf',
  contentType: 'application/pdf',
  fileSize: 3,
  sourceType: 'gmail',
  processingStatus: 'processed',
  metadataStatus: 'complete',
  matchStatus: 'matched',
  archiveDepth: 0,
  createdAt: DateTime.utc(2026, 8, 14),
  updatedAt: DateTime.utc(2026, 8, 14),
);

class _TestAuthController extends AuthController {
  @override
  Future<AuthState> build() async =>
      const AuthState(session: _session, user: null);
}

class _Call {
  const _Call(this.search, this.filters, this.skip);
  final String search;
  final DocumentFilters filters;
  final int skip;
}

class _FakeDocumentsRepository implements DocumentsRepository {
  final List<_Call> calls = <_Call>[];
  AuthSession? contentSession;

  @override
  Future<DocumentPage> fetchDocuments({
    required AuthSession session,
    required DocumentFilters filters,
    String search = '',
    int skip = 0,
    int limit = 50,
  }) async {
    calls.add(_Call(search, filters, skip));
    return DocumentPage(
      items: <RepositoryDocument>[_document],
      total: 101,
      skip: skip,
      limit: limit,
    );
  }

  @override
  Future<RepositoryDocument> fetchDocument({
    required AuthSession session,
    required int documentId,
  }) async => _document;

  @override
  Future<DocumentContent> fetchContent({
    required AuthSession session,
    required RepositoryDocument document,
    void Function(int received, int total)? onProgress,
  }) async {
    contentSession = session;
    onProgress?.call(3, 3);
    return DocumentContent(
      bytes: Uint8List.fromList(<int>[1, 2, 3]),
      fileName: document.displayName,
      contentType: document.contentType,
    );
  }
}
