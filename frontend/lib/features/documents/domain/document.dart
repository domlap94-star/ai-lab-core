class RepositoryDocument {
  const RepositoryDocument({
    required this.id,
    required this.contentType,
    required this.fileSize,
    required this.sourceType,
    required this.processingStatus,
    required this.metadataStatus,
    required this.matchStatus,
    required this.archiveDepth,
    required this.createdAt,
    required this.updatedAt,
    this.originalFilename,
    this.clientId,
    this.clientName,
    this.candidateId,
    this.candidateName,
    this.matchConfidence,
    this.capturedAt,
    this.parentDocumentId,
    this.archiveMemberPath,
  });

  final int id;
  final String? originalFilename;
  final String contentType;
  final int fileSize;
  final String sourceType;
  final int? clientId;
  final String? clientName;
  final int? candidateId;
  final String? candidateName;
  final String processingStatus;
  final String metadataStatus;
  final String matchStatus;
  final double? matchConfidence;
  final DateTime? capturedAt;
  final int? parentDocumentId;
  final String? archiveMemberPath;
  final int archiveDepth;
  final DateTime createdAt;
  final DateTime updatedAt;

  String get displayName =>
      originalFilename ?? archiveMemberPath ?? 'Dokument #$id';

  String get linkedEntityName => clientName ?? candidateName ?? 'Niepowiązany';
}
