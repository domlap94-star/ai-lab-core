enum DocumentLinkState {
  all('ALL', 'Wszystkie'),
  linked('LINKED', 'Połączone z klientem'),
  candidateOnly('CANDIDATE_ONLY', 'Tylko kandydat'),
  unlinked('UNLINKED', 'Niepowiązane');

  const DocumentLinkState(this.queryValue, this.label);

  final String queryValue;
  final String label;
}

class DocumentFilters {
  const DocumentFilters({
    this.linkState = DocumentLinkState.all,
    this.sourceType,
    this.matchStatus,
    this.processingStatus,
    this.contentType,
    this.clientId,
    this.clientName,
  });

  final DocumentLinkState linkState;
  final String? sourceType;
  final String? matchStatus;
  final String? processingStatus;
  final String? contentType;
  final int? clientId;
  final String? clientName;

  bool get isActive =>
      linkState != DocumentLinkState.all ||
      sourceType != null ||
      matchStatus != null ||
      processingStatus != null ||
      contentType != null ||
      clientId != null;

  DocumentFilters copyWith({
    DocumentLinkState? linkState,
    String? sourceType,
    bool clearSourceType = false,
    String? matchStatus,
    bool clearMatchStatus = false,
    String? processingStatus,
    bool clearProcessingStatus = false,
    String? contentType,
    bool clearContentType = false,
    int? clientId,
    String? clientName,
    bool clearClient = false,
  }) {
    return DocumentFilters(
      linkState: linkState ?? this.linkState,
      sourceType: clearSourceType ? null : sourceType ?? this.sourceType,
      matchStatus: clearMatchStatus ? null : matchStatus ?? this.matchStatus,
      processingStatus: clearProcessingStatus
          ? null
          : processingStatus ?? this.processingStatus,
      contentType: clearContentType ? null : contentType ?? this.contentType,
      clientId: clearClient ? null : clientId ?? this.clientId,
      clientName: clearClient ? null : clientName ?? this.clientName,
    );
  }
}
