import 'client.dart';

class ClientPage {
  const ClientPage({
    required this.items,
    required this.total,
    required this.skip,
    required this.limit,
  });

  final List<Client> items;
  final int total;
  final int skip;
  final int limit;

  bool get hasPreviousPage => skip > 0;
  bool get hasNextPage => skip + limit < total;
  int get pageNumber => total == 0 ? 1 : (skip ~/ limit) + 1;
  int get pageCount => total == 0 ? 1 : ((total - 1) ~/ limit) + 1;
}
