import '../domain/client_email.dart';

class ClientEmailAttachmentResponse {
  const ClientEmailAttachmentResponse({
    required this.documentId,
    required this.contentType,
    required this.fileSize,
    this.originalFilename,
  });

  final int documentId;
  final String? originalFilename;
  final String contentType;
  final int fileSize;

  factory ClientEmailAttachmentResponse.fromJson(Map<String, dynamic> json) {
    return ClientEmailAttachmentResponse(
      documentId: _requiredInt(json['document_id']),
      originalFilename: _nullableString(json['original_filename']),
      contentType: json['content_type']?.toString() ?? '',
      fileSize: _requiredInt(json['file_size']),
    );
  }

  ClientEmailAttachment toDomain() => ClientEmailAttachment(
    documentId: documentId,
    originalFilename: originalFilename,
    contentType: contentType,
    fileSize: fileSize,
  );
}

class ClientEmailResponse {
  const ClientEmailResponse({
    required this.id,
    required this.externalId,
    required this.messageId,
    required this.direction,
    required this.toAddresses,
    required this.ccAddresses,
    required this.attachmentCount,
    required this.attachments,
    required this.createdAt,
    this.ignored = false,
    this.threadId,
    this.messageAt,
    this.fromName,
    this.fromAddress,
    this.subject,
    this.bodyText,
    this.sourceUrl,
  });

  final int id;
  final String externalId;
  final String messageId;
  final String? threadId;
  final ClientEmailDirection direction;
  final DateTime? messageAt;
  final String? fromName;
  final String? fromAddress;
  final List<String> toAddresses;
  final List<String> ccAddresses;
  final String? subject;
  final String? bodyText;
  final String? sourceUrl;
  final int attachmentCount;
  final List<ClientEmailAttachmentResponse> attachments;
  final DateTime createdAt;
  final bool ignored;

  factory ClientEmailResponse.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawAttachments = json['attachments'] is List<dynamic>
        ? json['attachments'] as List<dynamic>
        : const <dynamic>[];
    return ClientEmailResponse(
      id: _requiredInt(json['id']),
      externalId: json['external_id']?.toString() ?? '',
      messageId: json['message_id']?.toString() ?? '',
      threadId: _nullableString(json['thread_id']),
      direction: _parseDirection(json['direction']),
      messageAt: _nullableDateTime(json['message_at']),
      fromName: _nullableString(json['from_name']),
      fromAddress: _nullableString(json['from_address']),
      toAddresses: _stringList(json['to_addresses']),
      ccAddresses: _stringList(json['cc_addresses']),
      subject: _nullableString(json['subject']),
      bodyText: _nullableString(json['body_text']),
      sourceUrl: _nullableString(json['source_url']),
      attachmentCount: _requiredInt(json['attachment_count']),
      attachments: rawAttachments
          .whereType<Map<String, dynamic>>()
          .map(ClientEmailAttachmentResponse.fromJson)
          .toList(growable: false),
      createdAt:
          _nullableDateTime(json['created_at']) ??
          DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
      ignored: json['ignored'] == true,
    );
  }

  ClientEmail toDomain() => ClientEmail(
    id: id,
    externalId: externalId,
    messageId: messageId,
    threadId: threadId,
    direction: direction,
    messageAt: messageAt,
    fromName: fromName,
    fromAddress: fromAddress,
    toAddresses: toAddresses,
    ccAddresses: ccAddresses,
    subject: subject,
    bodyText: bodyText,
    sourceUrl: sourceUrl,
    attachmentCount: attachmentCount,
    attachments: attachments
        .map((item) => item.toDomain())
        .toList(growable: false),
    createdAt: createdAt,
    ignored: ignored,
  );
}

int _requiredInt(dynamic value) {
  if (value is int) return value;
  return int.tryParse(value?.toString() ?? '') ?? 0;
}

String? _nullableString(dynamic value) {
  final String? normalized = value?.toString().trim();
  return normalized == null || normalized.isEmpty ? null : normalized;
}

DateTime? _nullableDateTime(dynamic value) {
  if (value == null) return null;
  return DateTime.tryParse(value.toString());
}

List<String> _stringList(dynamic value) {
  if (value is! List<dynamic>) return const <String>[];
  return value
      .map((dynamic item) => item?.toString().trim() ?? '')
      .where((String item) => item.isNotEmpty)
      .toList(growable: false);
}

ClientEmailDirection _parseDirection(dynamic value) {
  return switch (value?.toString()) {
    'sent' => ClientEmailDirection.sent,
    'received' => ClientEmailDirection.received,
    _ => ClientEmailDirection.unknown,
  };
}
