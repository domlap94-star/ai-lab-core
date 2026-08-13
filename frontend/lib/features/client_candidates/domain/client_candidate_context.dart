class ClientCandidateContext {
  const ClientCandidateContext({
    required this.candidate,
    required this.gmailMessages,
    required this.sheetsRows,
    required this.documents,
    required this.otherSources,
    required this.metadata,
  });

  final Map<String, dynamic> candidate;
  final List<Map<String, dynamic>> gmailMessages;
  final List<Map<String, dynamic>> sheetsRows;
  final List<Map<String, dynamic>> documents;
  final List<Map<String, dynamic>> otherSources;
  final Map<String, dynamic> metadata;

  int get gmailCount => _intValue(metadata['gmail_message_count']);
  int get sheetsCount => _intValue(metadata['sheets_row_count']);
  int get documentCount => _intValue(metadata['document_count']);
  int get sourceCount => _intValue(metadata['source_count']);

  static int _intValue(dynamic value) {
    if (value is int) {
      return value;
    }

    return int.tryParse(value?.toString() ?? '') ?? 0;
  }
}

class CandidateAcceptResult {
  const CandidateAcceptResult({
    required this.candidateId,
    required this.clientId,
    required this.clientName,
  });

  final int candidateId;
  final int clientId;
  final String clientName;
}

class CandidateDuplicateException implements Exception {
  const CandidateDuplicateException({
    required this.clientId,
    required this.matchedBy,
  });

  final int clientId;
  final String matchedBy;

  @override
  String toString() {
    return 'Kandydat pasuje do istniejącego klienta #$clientId '
        'na podstawie: $matchedBy.';
  }
}
