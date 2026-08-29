class GlobalMailItem {
  const GlobalMailItem({
    required this.sourceId,
    required this.messageId,
    required this.direction,
    required this.readState,
    required this.recipients,
    required this.occurredAt,
    required this.hasAttachments,
    required this.attachmentCount,
    this.ignored = false,
    this.threadId,
    this.sender,
    this.subject,
    this.clientId,
    this.clientName,
    this.reviewState,
    this.cc = const <String>[],
    this.bodyText,
    this.attachments = const <GlobalMailAttachment>[],
  });

  factory GlobalMailItem.fromJson(Map<String, dynamic> json) {
    return GlobalMailItem(
      sourceId: (json['source_id'] as num).toInt(),
      messageId: json['message_id']?.toString() ?? '',
      threadId: json['thread_id']?.toString(),
      direction: json['direction']?.toString() ?? 'unknown',
      readState: json['read_state']?.toString() ?? 'unknown',
      sender: json['sender']?.toString(),
      recipients: (json['recipients'] as List<dynamic>? ?? const <dynamic>[])
          .map((dynamic value) => value.toString())
          .toList(growable: false),
      subject: json['subject']?.toString(),
      occurredAt: DateTime.parse(json['occurred_at'].toString()),
      clientId: (json['client_id'] as num?)?.toInt(),
      clientName: json['client_name']?.toString(),
      reviewState: json['review_state']?.toString(),
      hasAttachments: json['has_attachments'] == true,
      attachmentCount: (json['attachment_count'] as num?)?.toInt() ?? 0,
      ignored: json['ignored'] == true,
      cc: (json['cc'] as List<dynamic>? ?? const <dynamic>[])
          .map((dynamic value) => value.toString())
          .toList(growable: false),
      bodyText: json['body_text']?.toString(),
      attachments: (json['attachments'] as List<dynamic>? ?? const <dynamic>[])
          .whereType<Map<String, dynamic>>()
          .map(GlobalMailAttachment.fromJson)
          .toList(growable: false),
    );
  }

  final int sourceId;
  final String messageId;
  final String? threadId;
  final String direction;
  final String readState;
  final String? sender;
  final List<String> recipients;
  final String? subject;
  final DateTime occurredAt;
  final int? clientId;
  final String? clientName;
  final String? reviewState;
  final bool hasAttachments;
  final int attachmentCount;
  final bool ignored;
  final List<String> cc;
  final String? bodyText;
  final List<GlobalMailAttachment> attachments;
}

class IgnoredMailSourceRule {
  const IgnoredMailSourceRule({
    required this.id,
    required this.ruleType,
    required this.normalizedValue,
    required this.isActive,
    required this.createdAt,
    required this.updatedAt,
  });
  factory IgnoredMailSourceRule.fromJson(Map<String, dynamic> json) =>
      IgnoredMailSourceRule(
        id: (json['id'] as num).toInt(),
        ruleType: json['rule_type']?.toString() ?? 'email',
        normalizedValue: json['normalized_value']?.toString() ?? '',
        isActive: json['is_active'] == true,
        createdAt: DateTime.parse(json['created_at'].toString()).toLocal(),
        updatedAt: DateTime.parse(json['updated_at'].toString()).toLocal(),
      );
  final int id;
  final String ruleType;
  final String normalizedValue;
  final bool isActive;
  final DateTime createdAt;
  final DateTime updatedAt;
}

class GlobalMailAttachment {
  const GlobalMailAttachment({
    required this.documentId,
    required this.processingStatus,
    this.filename,
    this.mimeType,
    this.size,
  });

  factory GlobalMailAttachment.fromJson(Map<String, dynamic> json) {
    return GlobalMailAttachment(
      documentId: (json['document_id'] as num).toInt(),
      filename: json['filename']?.toString(),
      mimeType: json['mime_type']?.toString(),
      size: (json['size'] as num?)?.toInt(),
      processingStatus: json['processing_status']?.toString() ?? 'unknown',
    );
  }

  final int documentId;
  final String? filename;
  final String? mimeType;
  final int? size;
  final String processingStatus;
}

class GlobalMailPageData {
  const GlobalMailPageData({required this.items, required this.hasMore});

  factory GlobalMailPageData.fromJson(Map<String, dynamic> json) {
    return GlobalMailPageData(
      items: (json['items'] as List<dynamic>? ?? const <dynamic>[])
          .whereType<Map<String, dynamic>>()
          .map(GlobalMailItem.fromJson)
          .toList(growable: false),
      hasMore: json['has_more'] == true,
    );
  }

  final List<GlobalMailItem> items;
  final bool hasMore;
}

class MailReconciliationDryRun {
  const MailReconciliationDryRun({
    required this.windowDays,
    required this.messagesExamined,
    required this.alreadyPresent,
    required this.missingCount,
    required this.expectedCandidates,
    required this.expectedDocuments,
    required this.dryRunToken,
  });

  factory MailReconciliationDryRun.fromJson(Map<String, dynamic> json) =>
      MailReconciliationDryRun(
        windowDays: (json['window_days'] as num?)?.toInt() ?? 7,
        messagesExamined: (json['messages_examined'] as num?)?.toInt() ?? 0,
        alreadyPresent: (json['already_present'] as num?)?.toInt() ?? 0,
        missingCount: (json['missing_count'] as num?)?.toInt() ?? 0,
        expectedCandidates: (json['expected_candidates'] as num?)?.toInt() ?? 0,
        expectedDocuments: (json['expected_documents'] as num?)?.toInt() ?? 0,
        dryRunToken: json['dry_run_token']?.toString() ?? '',
      );

  final int windowDays;
  final int messagesExamined;
  final int alreadyPresent;
  final int missingCount;
  final int expectedCandidates;
  final int expectedDocuments;
  final String dryRunToken;
}

class MailReconciliationResult {
  const MailReconciliationResult({
    required this.messagesExamined,
    required this.alreadyPresent,
    required this.newMessagesIngested,
    required this.failed,
  });

  factory MailReconciliationResult.fromJson(Map<String, dynamic> json) =>
      MailReconciliationResult(
        messagesExamined: (json['messages_examined'] as num?)?.toInt() ?? 0,
        alreadyPresent: (json['already_present'] as num?)?.toInt() ?? 0,
        newMessagesIngested:
            (json['new_messages_ingested'] as num?)?.toInt() ?? 0,
        failed: (json['failed'] as num?)?.toInt() ?? 0,
      );

  factory MailReconciliationResult.current(MailReconciliationDryRun dryRun) =>
      MailReconciliationResult(
        messagesExamined: dryRun.messagesExamined,
        alreadyPresent: dryRun.alreadyPresent,
        newMessagesIngested: 0,
        failed: 0,
      );

  final int messagesExamined;
  final int alreadyPresent;
  final int newMessagesIngested;
  final int failed;

  String get userSummary {
    if (newMessagesIngested == 0 && failed == 0) {
      return 'Wiadomości są aktualne. Sprawdzono $messagesExamined.';
    }
    final String base =
        'Sprawdzono $messagesExamined wiadomości. '
        'Dodano $newMessagesIngested brakujące. '
        '$alreadyPresent były już zsynchronizowane.';
    return failed == 0 ? base : '$base Nie udało się dodać: $failed.';
  }
}

class MailSendResult {
  const MailSendResult({
    required this.operationId,
    required this.status,
    this.canonicalSourceId,
    this.errorCode,
  });
  factory MailSendResult.fromJson(Map<String, dynamic> json) => MailSendResult(
    operationId: json['operation_id']?.toString() ?? '',
    status: json['status']?.toString() ?? 'unknown',
    canonicalSourceId: (json['canonical_source_id'] as num?)?.toInt(),
    errorCode: json['error_code']?.toString(),
  );
  final String operationId;
  final String status;
  final int? canonicalSourceId;
  final String? errorCode;
}
