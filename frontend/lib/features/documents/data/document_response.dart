import '../domain/document.dart';

class DocumentResponse {
  const DocumentResponse({
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
    this.projectId,
    this.inspectionId,
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
  final int? projectId;
  final int? inspectionId;
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

  factory DocumentResponse.fromJson(Map<String, dynamic> json) {
    return DocumentResponse(
      id: _requiredInt(json['id']),
      originalFilename: _nullableString(json['original_filename']),
      contentType: json['content_type']?.toString() ?? '',
      fileSize: _requiredInt(json['file_size']),
      sourceType: json['source_type']?.toString() ?? '',
      clientId: _nullableInt(json['client_id']),
      clientName: _nullableString(json['client_name']),
      projectId: _nullableInt(json['project_id']),
      inspectionId: _nullableInt(json['inspection_id']),
      candidateId: _nullableInt(json['candidate_id']),
      candidateName: _nullableString(json['candidate_name']),
      processingStatus: json['processing_status']?.toString() ?? '',
      metadataStatus: json['metadata_status']?.toString() ?? '',
      matchStatus: json['match_status']?.toString() ?? '',
      matchConfidence: _nullableDouble(json['match_confidence']),
      capturedAt: _nullableDateTime(json['captured_at']),
      parentDocumentId: _nullableInt(json['parent_document_id']),
      archiveMemberPath: _nullableString(json['archive_member_path']),
      archiveDepth: _requiredInt(json['archive_depth']),
      createdAt: _requiredDateTime(json['created_at']),
      updatedAt: _requiredDateTime(json['updated_at']),
    );
  }

  RepositoryDocument toDomain() => RepositoryDocument(
    id: id,
    originalFilename: originalFilename,
    contentType: contentType,
    fileSize: fileSize,
    sourceType: sourceType,
    clientId: clientId,
    clientName: clientName,
    projectId: projectId,
    inspectionId: inspectionId,
    candidateId: candidateId,
    candidateName: candidateName,
    processingStatus: processingStatus,
    metadataStatus: metadataStatus,
    matchStatus: matchStatus,
    matchConfidence: matchConfidence,
    capturedAt: capturedAt,
    parentDocumentId: parentDocumentId,
    archiveMemberPath: archiveMemberPath,
    archiveDepth: archiveDepth,
    createdAt: createdAt,
    updatedAt: updatedAt,
  );
}

int _requiredInt(dynamic value) {
  if (value is int) return value;
  return int.tryParse(value?.toString() ?? '') ?? 0;
}

int? _nullableInt(dynamic value) {
  if (value == null) return null;
  if (value is int) return value;
  return int.tryParse(value.toString());
}

double? _nullableDouble(dynamic value) {
  if (value == null) return null;
  if (value is num) return value.toDouble();
  return double.tryParse(value.toString());
}

String? _nullableString(dynamic value) {
  final String? result = value?.toString().trim();
  return result == null || result.isEmpty ? null : result;
}

DateTime _requiredDateTime(dynamic value) =>
    DateTime.tryParse(value?.toString() ?? '') ??
    DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);

DateTime? _nullableDateTime(dynamic value) =>
    value == null ? null : DateTime.tryParse(value.toString());
