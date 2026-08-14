import 'document.dart';

class DocumentPage {
  const DocumentPage({
    required this.items,
    required this.total,
    required this.skip,
    required this.limit,
  });

  final List<RepositoryDocument> items;
  final int total;
  final int skip;
  final int limit;

  bool get hasPreviousPage => skip > 0;
  bool get hasNextPage => skip + items.length < total;
  int get currentPage => total == 0 ? 0 : (skip ~/ limit) + 1;
  int get pageCount => total == 0 ? 0 : ((total - 1) ~/ limit) + 1;
}
