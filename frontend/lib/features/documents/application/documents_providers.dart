import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/application/auth_state.dart';
import '../../auth/domain/auth_session.dart';
import '../data/documents_api.dart';
import '../domain/document.dart';
import 'document_open_service.dart';
import 'documents_repository.dart';

final documentsApiProvider = Provider<DocumentsApi>((Ref ref) {
  return DocumentsApi(ref.watch(dioProvider));
});

final documentsRepositoryProvider = Provider<DocumentsRepository>((Ref ref) {
  return ApiDocumentsRepository(ref.watch(documentsApiProvider));
});

final documentOpenServiceProvider = Provider<DocumentOpenService>((Ref ref) {
  return DocumentOpenService(ref.watch(documentsRepositoryProvider));
});

final documentDetailsProvider = FutureProvider.family<RepositoryDocument, int>((
  Ref ref,
  int documentId,
) async {
  return ref
      .watch(documentsRepositoryProvider)
      .fetchDocument(
        session: requireDocumentSession(ref),
        documentId: documentId,
      );
});

AuthSession requireDocumentSession(Ref ref) {
  return requireDocumentSessionFromAuth(ref.read(authControllerProvider));
}

AuthSession requireDocumentSessionFromAuth(AsyncValue<AuthState> auth) {
  final AuthSession? session = auth.value?.session;
  if (session == null || !session.isAuthenticated) {
    throw const DocumentsAuthenticationException(
      'Brak aktywnej sesji użytkownika.',
    );
  }
  return session;
}

class DocumentsAuthenticationException implements Exception {
  const DocumentsAuthenticationException(this.message);
  final String message;
  @override
  String toString() => message;
}
