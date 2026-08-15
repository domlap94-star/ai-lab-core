import '../domain/client_email_page.dart';
import 'client_email_response.dart';

class ClientEmailPageResponse {
  const ClientEmailPageResponse({
    required this.items,
    required this.total,
    required this.skip,
    required this.limit,
  });

  final List<ClientEmailResponse> items;
  final int total;
  final int skip;
  final int limit;

  factory ClientEmailPageResponse.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawItems = json['items'] is List<dynamic>
        ? json['items'] as List<dynamic>
        : const <dynamic>[];
    return ClientEmailPageResponse(
      items: rawItems
          .whereType<Map<String, dynamic>>()
          .map(ClientEmailResponse.fromJson)
          .toList(growable: false),
      total: _int(json['total']),
      skip: _int(json['skip']),
      limit: _int(json['limit']),
    );
  }

  ClientEmailPage toDomain() => ClientEmailPage(
    items: items.map((item) => item.toDomain()).toList(growable: false),
    total: total,
    skip: skip,
    limit: limit,
  );
}

int _int(dynamic value) {
  if (value is int) return value;
  return int.tryParse(value?.toString() ?? '') ?? 0;
}
