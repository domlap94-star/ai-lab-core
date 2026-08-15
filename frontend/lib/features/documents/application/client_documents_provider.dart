import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../domain/document_filters.dart';
import '../domain/document_page.dart';
import 'documents_providers.dart';

class ClientDocumentsPageRequest {
  const ClientDocumentsPageRequest({
    required this.clientId,
    this.skip = 0,
    this.limit = 10,
  });

  final int clientId;
  final int skip;
  final int limit;

  @override
  bool operator ==(Object other) {
    return other is ClientDocumentsPageRequest &&
        other.clientId == clientId &&
        other.skip == skip &&
        other.limit == limit;
  }

  @override
  int get hashCode => Object.hash(clientId, skip, limit);
}

final clientDocumentsPageProvider = FutureProvider.autoDispose
    .family<DocumentPage, ClientDocumentsPageRequest>((
      Ref ref,
      ClientDocumentsPageRequest request,
    ) {
      return ref
          .watch(documentsRepositoryProvider)
          .fetchDocuments(
            session: requireDocumentSession(ref),
            filters: DocumentFilters(clientId: request.clientId),
            skip: request.skip,
            limit: request.limit,
          );
    });
