import 'package:ai_lab/features/documents/data/document_page_response.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('document page parser preserves nullable public fields', () {
    final DocumentPageResponse page = DocumentPageResponse.fromJson(
      <String, dynamic>{
        'items': <Map<String, dynamic>>[
          <String, dynamic>{
            'id': 42,
            'original_filename': null,
            'content_type': 'application/pdf',
            'file_size': 2048,
            'source_type': 'gmail',
            'client_id': null,
            'client_name': null,
            'candidate_id': '7',
            'candidate_name': 'Jan Kowalski',
            'processing_status': 'processed',
            'metadata_status': 'complete',
            'match_status': 'suggested',
            'match_confidence': '0.75',
            'captured_at': null,
            'parent_document_id': null,
            'archive_member_path': 'folder/invoice.pdf',
            'archive_depth': 1,
            'created_at': '2026-08-14T12:00:00Z',
            'updated_at': '2026-08-14T12:01:00Z',
          },
        ],
        'total': 5899,
        'skip': 50,
        'limit': 50,
      },
    );

    expect(page.total, 5899);
    expect(page.items.single.originalFilename, isNull);
    expect(page.items.single.candidateId, 7);
    expect(page.items.single.matchConfidence, 0.75);
    expect(page.items.single.capturedAt, isNull);
    expect(page.items.single.toDomain().displayName, 'folder/invoice.pdf');
  });
}
