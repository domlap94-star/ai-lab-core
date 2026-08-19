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
  final List<String> cc;
  final String? bodyText;
  final List<GlobalMailAttachment> attachments;
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
