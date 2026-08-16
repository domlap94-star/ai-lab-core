class DocumentMatchEvidence {
  const DocumentMatchEvidence({
    required this.kind,
    required this.description,
    this.clientId,
  });
  final String kind;
  final String description;
  final int? clientId;
}

class DocumentClientSuggestion {
  const DocumentClientSuggestion({
    required this.clientId,
    required this.clientName,
    required this.confidence,
    required this.evidence,
  });
  final int clientId;
  final String clientName;
  final String confidence;
  final List<DocumentMatchEvidence> evidence;
}

class DocumentClientMatch {
  const DocumentClientMatch({
    required this.documentId,
    required this.status,
    required this.confidence,
    required this.suggestions,
    required this.evidence,
    required this.conflict,
    required this.history,
    this.currentClientId,
    this.currentClientName,
    this.candidateId,
  });
  final int documentId;
  final int? currentClientId;
  final String? currentClientName;
  final int? candidateId;
  final String status;
  final String confidence;
  final List<DocumentClientSuggestion> suggestions;
  final List<DocumentMatchEvidence> evidence;
  final bool conflict;
  final List<int> history;

  factory DocumentClientMatch.fromJson(Map<String, dynamic> json) {
    DocumentMatchEvidence evidence(dynamic item) {
      final map = Map<String, dynamic>.from(item as Map);
      return DocumentMatchEvidence(
        kind: map['kind']?.toString() ?? '',
        description: map['description']?.toString() ?? '',
        clientId: _int(map['client_id']),
      );
    }

    return DocumentClientMatch(
      documentId: _int(json['document_id']) ?? 0,
      currentClientId: _int(json['current_client_id']),
      currentClientName: json['current_client_name']?.toString(),
      candidateId: _int(json['candidate_id']),
      status: json['status']?.toString() ?? 'UNMATCHED',
      confidence: json['confidence']?.toString() ?? 'NONE',
      conflict: json['conflict'] == true,
      history: (json['history'] as List? ?? const [])
          .map((dynamic item) => _int((item as Map)['id']) ?? 0)
          .toList(growable: false),
      evidence: (json['evidence'] as List? ?? const [])
          .map(evidence)
          .toList(growable: false),
      suggestions: (json['suggestions'] as List? ?? const [])
          .map((dynamic item) {
            final map = Map<String, dynamic>.from(item as Map);
            return DocumentClientSuggestion(
              clientId: _int(map['client_id']) ?? 0,
              clientName: map['client_name']?.toString() ?? '',
              confidence: map['confidence']?.toString() ?? 'NONE',
              evidence: (map['evidence'] as List? ?? const [])
                  .map(evidence)
                  .toList(growable: false),
            );
          })
          .toList(growable: false),
    );
  }
}

int? _int(dynamic value) =>
    value is int ? value : int.tryParse(value?.toString() ?? '');
