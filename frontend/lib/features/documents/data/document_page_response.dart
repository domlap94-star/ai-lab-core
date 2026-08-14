import 'document_response.dart';

class DocumentPageResponse {
  const DocumentPageResponse({
    required this.items,
    required this.total,
    required this.skip,
    required this.limit,
  });

  final List<DocumentResponse> items;
  final int total;
  final int skip;
  final int limit;

  factory DocumentPageResponse.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawItems = json['items'] is List<dynamic>
        ? json['items'] as List<dynamic>
        : const <dynamic>[];

    return DocumentPageResponse(
      items: rawItems
          .whereType<Map>()
          .map(
            (Map<dynamic, dynamic> item) =>
                DocumentResponse.fromJson(Map<String, dynamic>.from(item)),
          )
          .toList(growable: false),
      total: _int(json['total']),
      skip: _int(json['skip']),
      limit: _int(json['limit']),
    );
  }
}

int _int(dynamic value) {
  if (value is int) return value;
  return int.tryParse(value?.toString() ?? '') ?? 0;
}
