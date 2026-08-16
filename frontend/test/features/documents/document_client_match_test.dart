import 'package:ai_lab/features/documents/domain/document_client_match.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test(
    'parses deterministic suggestion, conflict and evidence without raw payload',
    () {
      final match = DocumentClientMatch.fromJson(<String, dynamic>{
        'document_id': 42,
        'current_client_id': null,
        'current_client_name': null,
        'candidate_id': 7,
        'status': 'CONFLICT',
        'confidence': 'CONFLICT',
        'conflict': true,
        'suggestions': <Map<String, dynamic>>[
          <String, dynamic>{
            'client_id': 11,
            'client_name': 'Klient A',
            'confidence': 'CONFLICT',
            'evidence': <Map<String, dynamic>>[
              <String, dynamic>{
                'kind': 'candidate_match',
                'description': 'Kandydat #7 jest przypisany do klienta #11',
                'client_id': 11,
              },
            ],
          },
        ],
        'evidence': <Map<String, dynamic>>[],
        'history': <Map<String, dynamic>>[
          <String, dynamic>{'id': 3},
        ],
      });

      expect(match.conflict, isTrue);
      expect(match.suggestions.single.clientId, 11);
      expect(match.suggestions.single.evidence.single.kind, 'candidate_match');
      expect(match.history, <int>[3]);
    },
  );
}
