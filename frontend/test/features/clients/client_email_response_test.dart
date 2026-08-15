import 'package:ai_lab/features/clients/data/client_email_response.dart';
import 'package:ai_lab/features/clients/domain/client_email.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('email parser accepts nullable public fields', () {
    final ClientEmail email = ClientEmailResponse.fromJson(<String, dynamic>{
      'id': 7,
      'external_id': 'gmail-7',
      'message_id': 'gmail-7',
      'thread_id': null,
      'direction': 'unexpected',
      'message_at': null,
      'from_name': null,
      'from_address': null,
      'to_addresses': null,
      'cc_addresses': <dynamic>[],
      'subject': '   ',
      'body_text': null,
      'source_url': null,
      'attachment_count': 1,
      'attachments': <Map<String, dynamic>>[
        <String, dynamic>{
          'document_id': 91,
          'original_filename': null,
          'content_type': 'application/pdf',
          'file_size': 2048,
        },
      ],
      'created_at': '2026-08-15T10:00:00Z',
    }).toDomain();

    expect(email.direction, ClientEmailDirection.unknown);
    expect(email.messageAt, isNull);
    expect(email.toAddresses, isEmpty);
    expect(email.displaySubject, '(bez tematu)');
    expect(email.attachments.single.documentId, 91);
    expect(email.attachments.single.displayName, 'Załącznik #91');
  });
}
