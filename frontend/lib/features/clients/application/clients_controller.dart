import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/application/auth_controller.dart';
import '../../auth/application/auth_state.dart';
import '../../auth/domain/auth_session.dart';
import '../data/client_create_request.dart';
import '../domain/client.dart';
import '../domain/client_page.dart';
import 'client_list_filter.dart';
import 'clients_providers.dart';
import 'clients_repository.dart';

final clientsControllerProvider =
    AsyncNotifierProvider<ClientsController, ClientPage>(ClientsController.new);

class ClientsController extends AsyncNotifier<ClientPage> {
  static const int pageSize = 50;
  late final ClientsRepository _repository;

  String _searchQuery = '';
  ClientType? _clientType;
  int? _industryId;
  ClientSortOrder _sortOrder = ClientSortOrder.newestFirst;
  int _skip = 0;

  String get searchQuery => _searchQuery;
  ClientType? get clientType => _clientType;
  int? get industryId => _industryId;
  ClientSortOrder get sortOrder => _sortOrder;

  @override
  Future<ClientPage> build() async {
    _repository = ref.read(clientsRepositoryProvider);

    return _loadClients();
  }

  Future<ClientPage> _loadClients() async {
    final AuthSession session = _requireSession();

    return _repository.fetchClients(
      session: session,
      search: _searchQuery,
      clientType: _clientType,
      industryId: _industryId,
      sortOrder: _sortOrder.apiValue,
      skip: _skip,
      limit: pageSize,
    );
  }

  Future<void> refresh() async {
    state = const AsyncLoading<ClientPage>();

    state = await AsyncValue.guard<ClientPage>(_loadClients);
  }

  Future<void> search(String query) async {
    _searchQuery = query.trim();
    _skip = 0;

    state = const AsyncLoading<ClientPage>();

    state = await AsyncValue.guard<ClientPage>(_loadClients);
  }

  Future<void> clearSearch() async {
    if (_searchQuery.isEmpty) {
      return;
    }

    _searchQuery = '';
    _skip = 0;

    state = const AsyncLoading<ClientPage>();

    state = await AsyncValue.guard<ClientPage>(_loadClients);
  }

  Future<void> setFilters({
    ClientType? clientType,
    int? industryId,
    ClientSortOrder? sortOrder,
  }) async {
    _clientType = clientType;
    _industryId = industryId;
    if (sortOrder != null) {
      _sortOrder = sortOrder;
    }
    _skip = 0;
    state = const AsyncLoading<ClientPage>();
    state = await AsyncValue.guard<ClientPage>(_loadClients);
  }

  Future<void> setSortOrder(ClientSortOrder sortOrder) async {
    if (_sortOrder == sortOrder) {
      return;
    }

    _sortOrder = sortOrder;
    _skip = 0;
    state = const AsyncLoading<ClientPage>();
    state = await AsyncValue.guard<ClientPage>(_loadClients);
  }

  Future<void> nextPage() async {
    final ClientPage? current = state.value;
    if (current == null || !current.hasNextPage) return;
    _skip += pageSize;
    state = const AsyncLoading<ClientPage>();
    state = await AsyncValue.guard<ClientPage>(_loadClients);
  }

  Future<void> previousPage() async {
    if (_skip <= 0) return;
    _skip = (_skip - pageSize).clamp(0, 1 << 31);
    state = const AsyncLoading<ClientPage>();
    state = await AsyncValue.guard<ClientPage>(_loadClients);
  }

  Future<Client> createClient(ClientCreateRequest request) async {
    final AuthSession session = _requireSession();

    final Client createdClient = await _repository.createClient(
      session: session,
      request: request,
    );

    await refresh();

    return createdClient;
  }

  AuthSession _requireSession() {
    final AsyncValue<AuthState> authValue = ref.read(authControllerProvider);

    final AuthSession? session = authValue.value?.session;

    if (session == null || !session.isAuthenticated) {
      throw const ClientsAuthenticationException(
        'Brak aktywnej sesji użytkownika.',
      );
    }

    return session;
  }
}
