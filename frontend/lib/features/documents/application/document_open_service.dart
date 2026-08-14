import '../../auth/domain/auth_session.dart';
import '../data/document_content.dart';
import '../domain/document.dart';
import 'documents_repository.dart';
import 'open_document_stub.dart'
    if (dart.library.io) 'open_document_io.dart'
    if (dart.library.html) 'open_document_web.dart'
    as platform;

typedef DocumentPayloadOpener =
    Future<void> Function(DocumentContent content, int documentId);

class DocumentOpenService {
  DocumentOpenService(this._repository, {DocumentPayloadOpener? opener})
    : _opener = opener ?? platform.openDocumentContent;

  final DocumentsRepository _repository;
  final DocumentPayloadOpener _opener;

  Future<void> open({
    required AuthSession session,
    required RepositoryDocument document,
    void Function(int received, int total)? onProgress,
  }) async {
    final DocumentContent content = await _repository.fetchContent(
      session: session,
      document: document,
      onProgress: onProgress,
    );
    await _opener(content, document.id);
  }
}
