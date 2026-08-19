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
    required this.matches,
  });

  final int clientId;
  final String matchedBy;
  final List<CandidateDuplicateMatch> matches;

  @override
  String toString() {
    return 'Kandydat pasuje do istniejącego klienta #$clientId '
        'na podstawie: $matchedBy.';
  }
}

class CandidateDuplicateMatch {
  const CandidateDuplicateMatch({
    required this.clientId,
    required this.clientName,
    required this.workflowStatus,
    required this.workflowStatusLabel,
    required this.confidence,
    required this.reasons,
  });

  factory CandidateDuplicateMatch.fromJson(Map<String, dynamic> json) {
    return CandidateDuplicateMatch(
      clientId: (json['client_id'] as num).toInt(),
      clientName: json['client_name']?.toString() ?? '',
      workflowStatus: json['workflow_status']?.toString() ?? 'untouched',
      workflowStatusLabel:
          json['workflow_status_label']?.toString() ?? 'Brak modyfikacji',
      confidence: json['confidence']?.toString() ?? 'certain',
      reasons: (json['reasons'] as List<dynamic>? ?? const <dynamic>[])
          .map((dynamic value) => value.toString())
          .toList(growable: false),
    );
  }

  final int clientId;
  final String clientName;
  final String workflowStatus;
  final String workflowStatusLabel;
  final String confidence;
  final List<String> reasons;
}

class CandidateMergePreview {
  const CandidateMergePreview({
    required this.candidate,
    required this.target,
    required this.match,
    required this.fieldProposals,
    required this.relationCounts,
    required this.expectedCandidateVersion,
    required this.blockedReasons,
  });

  factory CandidateMergePreview.fromJson(Map<String, dynamic> json) {
    return CandidateMergePreview(
      candidate: Map<String, dynamic>.from(json['candidate'] as Map),
      target: Map<String, dynamic>.from(json['target'] as Map),
      match: CandidateDuplicateMatch.fromJson(
        Map<String, dynamic>.from(json['match'] as Map),
      ),
      fieldProposals:
          (json['field_proposals'] as List<dynamic>? ?? const <dynamic>[])
              .map((dynamic value) => Map<String, dynamic>.from(value as Map))
              .toList(growable: false),
      relationCounts: Map<String, dynamic>.from(json['relation_counts'] as Map),
      expectedCandidateVersion: json['expected_candidate_version'].toString(),
      blockedReasons:
          (json['blocked_reasons'] as List<dynamic>? ?? const <dynamic>[])
              .map((dynamic value) => value.toString())
              .toList(growable: false),
    );
  }

  final Map<String, dynamic> candidate;
  final Map<String, dynamic> target;
  final CandidateDuplicateMatch match;
  final List<Map<String, dynamic>> fieldProposals;
  final Map<String, dynamic> relationCounts;
  final String expectedCandidateVersion;
  final List<String> blockedReasons;
}

class CandidateMergeResult {
  const CandidateMergeResult({
    required this.clientId,
    required this.clientName,
    required this.idempotentReplay,
  });

  final int clientId;
  final String clientName;
  final bool idempotentReplay;
}
