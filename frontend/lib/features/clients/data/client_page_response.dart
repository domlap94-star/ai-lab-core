import 'client_response.dart';

class ClientPageResponse {
  const ClientPageResponse({
    required this.items,
    required this.total,
    required this.skip,
    required this.limit,
  });

  factory ClientPageResponse.fromJson(Map<String, dynamic> json) {
    final dynamic rawItems = json['items'];

    if (rawItems is! List<dynamic>) {
      throw const FormatException(
        'Pole items listy klientów jest nieprawidłowe.',
      );
    }

    return ClientPageResponse(
      items: rawItems
          .map<ClientResponse>(
            (dynamic item) =>
                ClientResponse.fromJson(Map<String, dynamic>.from(item as Map)),
          )
          .toList(growable: false),
      total: _requiredInt(json, 'total'),
      skip: _requiredInt(json, 'skip'),
      limit: _requiredInt(json, 'limit'),
    );
  }

  final List<ClientResponse> items;
  final int total;
  final int skip;
  final int limit;

  static int _requiredInt(Map<String, dynamic> json, String key) {
    final dynamic value = json[key];
    if (value is int) return value;
    if (value is num) return value.toInt();
    throw FormatException('Pole $key listy klientów jest nieprawidłowe.');
  }
}
