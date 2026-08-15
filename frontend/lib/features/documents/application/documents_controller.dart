import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../domain/document_filters.dart';
import '../domain/document_page.dart';
import 'documents_providers.dart';
import 'documents_repository.dart';

final documentsControllerProvider =
    AsyncNotifierProvider<DocumentsController, DocumentPage>(
      DocumentsController.new,
    );

class DocumentsController extends AsyncNotifier<DocumentPage> {
  DocumentsController({
    DocumentFilters initialFilters = const DocumentFilters(),
  }) : _filters = initialFilters;

  static const int pageSize = 50;
  late final DocumentsRepository _repository;

  String _searchQuery = '';
  DocumentFilters _filters;
  int _skip = 0;

  String get searchQuery => _searchQuery;
  DocumentFilters get filters => _filters;

  @override
  Future<DocumentPage> build() async {
    _repository = ref.read(documentsRepositoryProvider);
    return _load();
  }

  Future<DocumentPage> _load() {
    return _repository.fetchDocuments(
      session: requireDocumentSession(ref),
      filters: _filters,
      search: _searchQuery,
      skip: _skip,
      limit: pageSize,
    );
  }

  Future<void> refresh() async {
    state = const AsyncLoading<DocumentPage>();
    state = await AsyncValue.guard<DocumentPage>(_load);
  }

  Future<void> search(String query) async {
    _searchQuery = query.trim();
    _skip = 0;
    await refresh();
  }

  Future<void> setFilters(DocumentFilters filters) async {
    _filters = filters;
    _skip = 0;
    await refresh();
  }

  Future<void> clearFilters() => setFilters(const DocumentFilters());

  Future<void> filterByClient(int clientId, String clientName) {
    return setFilters(
      _filters.copyWith(clientId: clientId, clientName: clientName),
    );
  }

  Future<void> nextPage() async {
    final DocumentPage? page = state.value;
    if (page == null || !page.hasNextPage) return;
    _skip += pageSize;
    await refresh();
  }

  Future<void> previousPage() async {
    if (_skip == 0) return;
    _skip = (_skip - pageSize).clamp(0, 1 << 31);
    await refresh();
  }
}
