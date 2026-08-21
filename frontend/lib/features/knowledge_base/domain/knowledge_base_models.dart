class KnowledgeBaseItem {
  const KnowledgeBaseItem({
    required this.id,
    required this.title,
    required this.source,
    required this.category,
    required this.tags,
    required this.status,
    this.supersedesId,
    required this.originalFilename,
    required this.fileSize,
    required this.processingStatus,
    required this.pages,
    this.publisher,
    this.version,
    this.effectiveDate,
    this.processingMethod,
    this.processingError,
  });
  final int id;
  final String title;
  final String source;
  final String? publisher;
  final String? version;
  final String? effectiveDate;
  final String category;
  final List<String> tags;
  final String status;
  final int? supersedesId;
  final String originalFilename;
  final int fileSize;
  final String processingStatus;
  final String? processingMethod;
  final String? processingError;
  final List<KnowledgeBasePageExcerpt> pages;
  factory KnowledgeBaseItem.fromJson(Map<String, dynamic> json) =>
      KnowledgeBaseItem(
        id: json['id'] as int,
        title: json['title'] as String,
        source: json['source'] as String,
        publisher: json['publisher'] as String?,
        version: json['version'] as String?,
        effectiveDate: json['effective_date'] as String?,
        category: json['category'] as String,
        tags: ((json['tags'] as List<dynamic>?) ?? const <dynamic>[])
            .cast<String>(),
        status: json['status'] as String,
        supersedesId: json['supersedes_id'] as int?,
        originalFilename: json['original_filename'] as String,
        fileSize: json['file_size'] as int,
        processingStatus: json['processing_status'] as String,
        processingMethod: json['processing_method'] as String?,
        processingError: json['processing_error'] as String?,
        pages: ((json['pages'] as List<dynamic>?) ?? const <dynamic>[])
            .map(
              (dynamic value) => KnowledgeBasePageExcerpt.fromJson(
                value as Map<String, dynamic>,
              ),
            )
            .toList(growable: false),
      );
}

class KnowledgeBasePageExcerpt {
  const KnowledgeBasePageExcerpt({
    required this.page,
    required this.method,
    this.text,
  });
  final int page;
  final String method;
  final String? text;
  factory KnowledgeBasePageExcerpt.fromJson(Map<String, dynamic> json) =>
      KnowledgeBasePageExcerpt(
        page: json['page_number'] as int,
        method: json['extraction_method'] as String,
        text: json['text'] as String?,
      );
}

class KnowledgeBaseListResult {
  const KnowledgeBaseListResult(this.items, this.total);
  final List<KnowledgeBaseItem> items;
  final int total;
}
