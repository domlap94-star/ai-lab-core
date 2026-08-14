import 'package:ai_lab/features/documents/data/documents_api.dart';
import 'package:ai_lab/features/documents/domain/document_filters.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test(
    'query parameters contain only active filters and server pagination',
    () {
      final Map<String, dynamic> query = DocumentsApi.buildQueryParameters(
        search: '  faktura  ',
        filters: const DocumentFilters(
          linkState: DocumentLinkState.linked,
          sourceType: 'gmail',
          matchStatus: 'matched',
          processingStatus: 'processed',
          contentType: 'application/pdf',
          clientId: 2152,
        ),
        skip: 100,
        limit: 50,
      );

      expect(query, <String, dynamic>{
        'search': 'faktura',
        'client_id': 2152,
        'source_type': 'gmail',
        'match_status': 'matched',
        'processing_status': 'processed',
        'content_type': 'application/pdf',
        'link_state': 'LINKED',
        'skip': 100,
        'limit': 50,
      });
    },
  );
}
