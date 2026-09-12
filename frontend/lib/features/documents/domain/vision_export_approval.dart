import 'dart:typed_data';

class VisionExportDocumentScope {
  const VisionExportDocumentScope({
    required this.documentId,
    this.clientId,
    this.projectId,
    this.inspectionId,
    this.candidateId,
  });

  factory VisionExportDocumentScope.fromJson(Map<String, dynamic> json) {
    if (json['schema'] != 'VISUAL_EXPORT_DOCUMENT_SCOPE_V1') {
      throw const FormatException('Nieobsługiwany zakres eksportu Visual.');
    }
    return VisionExportDocumentScope(
      documentId: _requiredInt(json, 'document_id'),
      clientId: _nullableInt(json, 'client_id'),
      projectId: _nullableInt(json, 'project_id'),
      inspectionId: _nullableInt(json, 'inspection_id'),
      candidateId: _nullableInt(json, 'candidate_id'),
    );
  }

  final int documentId;
  final int? clientId;
  final int? projectId;
  final int? inspectionId;
  final int? candidateId;
}

class VisionExportApprovalSource {
  const VisionExportApprovalSource({
    required this.sourceRef,
    required this.sourceEntityType,
    required this.sourceEntityId,
    required this.documentId,
    required this.scope,
    required this.sensitivity,
    required this.originalSha256,
    required this.finalSha256,
    required this.previewContentType,
    required this.previewSize,
  });

  factory VisionExportApprovalSource.fromJson(Map<String, dynamic> json) {
    final Object? rawScope = json['document_scope'];
    if (rawScope is! Map<String, dynamic>) {
      throw const FormatException('Brak zakresu źródła eksportu Visual.');
    }
    return VisionExportApprovalSource(
      sourceRef: _requiredString(json, 'source_ref'),
      sourceEntityType: _requiredString(json, 'source_entity_type'),
      sourceEntityId: _requiredString(json, 'source_entity_id'),
      documentId: _requiredInt(json, 'document_id'),
      scope: VisionExportDocumentScope.fromJson(rawScope),
      sensitivity: _requiredString(json, 'sensitivity'),
      originalSha256: _requiredHash(json, 'original_sha256'),
      finalSha256: _requiredHash(json, 'final_sha256'),
      previewContentType: _requiredString(json, 'preview_content_type'),
      previewSize: _requiredInt(json, 'preview_size'),
    );
  }

  final String sourceRef;
  final String sourceEntityType;
  final String sourceEntityId;
  final int documentId;
  final VisionExportDocumentScope scope;
  final String sensitivity;
  final String originalSha256;
  final String finalSha256;
  final String previewContentType;
  final int previewSize;
}

class VisionExportApprovalCandidate {
  const VisionExportApprovalCandidate({
    required this.analysisJobId,
    required this.policyVersion,
    required this.channel,
    required this.packageSha256,
    required this.bindingSha256,
    required this.selectedSourceCount,
    required this.omittedSourceCount,
    required this.completeSourceCoverage,
    required this.approvalState,
    required this.canApprove,
    required this.canRevoke,
    required this.sources,
    this.approvalKind,
    this.approvalExpiresAt,
  });

  factory VisionExportApprovalCandidate.fromJson(Map<String, dynamic> json) {
    final Object? rawSources = json['sources'];
    if (rawSources is! List || rawSources.isEmpty) {
      throw const FormatException('Brak źródeł kandydata eksportu Visual.');
    }
    final List<VisionExportApprovalSource> sources = rawSources
        .map((Object? item) {
          if (item is! Map<String, dynamic>) {
            throw const FormatException(
              'Nieprawidłowe źródło eksportu Visual.',
            );
          }
          return VisionExportApprovalSource.fromJson(item);
        })
        .toList(growable: false);
    final int selected = _requiredInt(json, 'selected_source_count');
    if (selected != sources.length) {
      throw const FormatException('Niespójna liczba źródeł eksportu Visual.');
    }
    final String state = _requiredString(json, 'approval_state');
    if (!const <String>{
      'not_approved',
      'approved',
      'revoked',
      'expired',
    }.contains(state)) {
      throw const FormatException(
        'Nieznany stan dopuszczenia eksportu Visual.',
      );
    }
    return VisionExportApprovalCandidate(
      analysisJobId: _requiredString(json, 'analysis_job_id'),
      policyVersion: _requiredString(json, 'policy_version'),
      channel: _requiredString(json, 'channel'),
      packageSha256: _requiredHash(json, 'package_sha256'),
      bindingSha256: _requiredHash(json, 'binding_sha256'),
      selectedSourceCount: selected,
      omittedSourceCount: _requiredInt(json, 'omitted_source_count'),
      completeSourceCoverage: _requiredBool(json, 'complete_source_coverage'),
      approvalState: state,
      approvalKind: json['approval_kind']?.toString(),
      approvalExpiresAt: json['approval_expires_at'] == null
          ? null
          : DateTime.parse(json['approval_expires_at'].toString()),
      canApprove: _requiredBool(json, 'can_approve'),
      canRevoke: _requiredBool(json, 'can_revoke'),
      sources: sources,
    );
  }

  final String analysisJobId;
  final String policyVersion;
  final String channel;
  final String packageSha256;
  final String bindingSha256;
  final int selectedSourceCount;
  final int omittedSourceCount;
  final bool completeSourceCoverage;
  final String approvalState;
  final String? approvalKind;
  final DateTime? approvalExpiresAt;
  final bool canApprove;
  final bool canRevoke;
  final List<VisionExportApprovalSource> sources;
}

class VisionExportApprovalPreview {
  VisionExportApprovalPreview({
    required this.sourceRef,
    required this.sourceSha256,
    required this.packageSha256,
    required this.contentType,
    required Uint8List bytes,
  }) : bytes = Uint8List.fromList(bytes);

  final String sourceRef;
  final String sourceSha256;
  final String packageSha256;
  final String contentType;
  final Uint8List bytes;
}

class VisionExportApprovalResult {
  const VisionExportApprovalResult({
    required this.documentId,
    required this.analysisJobId,
    required this.state,
    required this.reason,
  });

  factory VisionExportApprovalResult.fromJson(Map<String, dynamic> json) {
    return VisionExportApprovalResult(
      documentId: _requiredInt(json, 'document_id'),
      analysisJobId: _requiredString(json, 'analysis_job_id'),
      state: _requiredString(json, 'state'),
      reason: _requiredString(json, 'reason'),
    );
  }

  final int documentId;
  final String analysisJobId;
  final String state;
  final String reason;
}

String _requiredString(Map<String, dynamic> json, String key) {
  final Object? value = json[key];
  if (value is! String || value.trim().isEmpty) {
    throw FormatException('Brak pola $key w kontrakcie eksportu Visual.');
  }
  return value;
}

String _requiredHash(Map<String, dynamic> json, String key) {
  final String value = _requiredString(json, key).toLowerCase();
  if (!RegExp(r'^[a-f0-9]{64}$').hasMatch(value)) {
    throw FormatException('Nieprawidłowy hash $key w kontrakcie Visual.');
  }
  return value;
}

int _requiredInt(Map<String, dynamic> json, String key) {
  final Object? value = json[key];
  if (value is! int) {
    throw FormatException('Brak pola liczbowego $key w kontrakcie Visual.');
  }
  return value;
}

int? _nullableInt(Map<String, dynamic> json, String key) {
  final Object? value = json[key];
  if (value == null) return null;
  if (value is! int) {
    throw FormatException('Nieprawidłowe pole $key w kontrakcie Visual.');
  }
  return value;
}

bool _requiredBool(Map<String, dynamic> json, String key) {
  final Object? value = json[key];
  if (value is! bool) {
    throw FormatException('Brak pola logicznego $key w kontrakcie Visual.');
  }
  return value;
}
