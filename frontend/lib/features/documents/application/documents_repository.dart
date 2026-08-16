import '../../auth/domain/auth_session.dart';
import '../data/document_content.dart';
import '../data/documents_api.dart';
import '../domain/document.dart';
import '../domain/document_filters.dart';
import '../domain/document_client_match.dart';
import '../domain/document_page.dart';

abstract class DocumentsRepository {
  Future<DocumentPage> fetchDocuments({
    required AuthSession session,
    required DocumentFilters filters,
    String search,
    int skip,
    int limit,
  });

  Future<RepositoryDocument> fetchDocument({
    required AuthSession session,
    required int documentId,
  });

  Future<DocumentContent> fetchContent({
    required AuthSession session,
    required RepositoryDocument document,
    void Function(int received, int total)? onProgress,
  });
  Future<DocumentClientMatch> fetchClientMatch({
    required AuthSession session,
    required int documentId,
  }) => throw UnsupportedError('Document matching is not implemented.');

  Future<void> linkClient({
    required AuthSession session,
    required int documentId,
    required int clientId,
    required bool move,
    required bool confirmConflict,
  }) => throw UnsupportedError('Document matching is not implemented.');

  Future<void> unlinkClient({
    required AuthSession session,
    required int documentId,
  }) => throw UnsupportedError('Document matching is not implemented.');

  Future<void> undoClientLink({
    required AuthSession session,
    required int documentId,
  }) => throw UnsupportedError('Document matching is not implemented.');
}

class ApiDocumentsRepository implements DocumentsRepository {
  const ApiDocumentsRepository(this._api);

  final DocumentsApi _api;

  @override
  Future<DocumentPage> fetchDocuments({
    required AuthSession session,
    required DocumentFilters filters,
    String search = '',
    int skip = 0,
    int limit = 50,
  }) async {
    final response = await _api.fetchDocuments(
      accessToken: session.accessToken,
      tokenType: session.tokenType,
      filters: filters,
      search: search,
      skip: skip,
      limit: limit,
    );
    return DocumentPage(
      items: response.items
          .map((item) => item.toDomain())
          .toList(growable: false),
      total: response.total,
      skip: response.skip,
      limit: response.limit,
    );
  }

  @override
  Future<RepositoryDocument> fetchDocument({
    required AuthSession session,
    required int documentId,
  }) async {
    final response = await _api.fetchDocument(
      documentId: documentId,
      accessToken: session.accessToken,
      tokenType: session.tokenType,
    );
    return response.toDomain();
  }

  @override
  Future<DocumentContent> fetchContent({
    required AuthSession session,
    required RepositoryDocument document,
    void Function(int received, int total)? onProgress,
  }) {
    return _api.fetchContent(
      documentId: document.id,
      fileName: document.displayName,
      contentType: document.contentType,
      accessToken: session.accessToken,
      tokenType: session.tokenType,
      onProgress: onProgress,
    );
  }

  @override
  Future<DocumentClientMatch> fetchClientMatch({
    required AuthSession session,
    required int documentId,
  }) => _api.fetchClientMatch(
    documentId: documentId,
    accessToken: session.accessToken,
    tokenType: session.tokenType,
  );

  @override
  Future<void> linkClient({
    required AuthSession session,
    required int documentId,
    required int clientId,
    required bool move,
    required bool confirmConflict,
  }) => _api.linkClient(
    documentId: documentId,
    clientId: clientId,
    move: move,
    confirmConflict: confirmConflict,
    accessToken: session.accessToken,
    tokenType: session.tokenType,
  );

  @override
  Future<void> unlinkClient({
    required AuthSession session,
    required int documentId,
  }) => _api.unlinkClient(
    documentId: documentId,
    accessToken: session.accessToken,
    tokenType: session.tokenType,
  );

  @override
  Future<void> undoClientLink({
    required AuthSession session,
    required int documentId,
  }) => _api.undoClientLink(
    documentId: documentId,
    accessToken: session.accessToken,
    tokenType: session.tokenType,
  );
}
