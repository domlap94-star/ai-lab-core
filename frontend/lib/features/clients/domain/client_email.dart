class ClientEmailAttachment {
  const ClientEmailAttachment({
    required this.documentId,
    required this.contentType,
    required this.fileSize,
    this.originalFilename,
  });

  final int documentId;
  final String? originalFilename;
  final String contentType;
  final int fileSize;

  String get displayName => originalFilename ?? 'Załącznik #$documentId';
}

enum ClientEmailDirection { sent, received, unknown }

class ClientEmail {
  const ClientEmail({
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
  final List<ClientEmailAttachment> attachments;
  final DateTime createdAt;
  final bool ignored;

  String get displaySubject => subject ?? '(bez tematu)';
}
