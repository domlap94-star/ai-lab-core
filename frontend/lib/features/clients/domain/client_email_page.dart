import 'client_email.dart';

class ClientEmailPage {
  const ClientEmailPage({
    required this.items,
    required this.total,
    required this.skip,
    required this.limit,
  });

  final List<ClientEmail> items;
  final int total;
  final int skip;
  final int limit;

  bool get hasPreviousPage => skip > 0;
  bool get hasNextPage => skip + items.length < total;
}
