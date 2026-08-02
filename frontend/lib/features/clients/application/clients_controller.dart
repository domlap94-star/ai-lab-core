import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/application/auth_controller.dart';
import '../../auth/application/auth_state.dart';
import '../../auth/domain/auth_session.dart';
import '../domain/client.dart';
import 'clients_providers.dart';
import 'clients_repository.dart';

final clientsControllerProvider =
    AsyncNotifierProvider<ClientsController, List<Client>>(
      ClientsController.new,
    );

class ClientsController extends AsyncNotifier<List<Client>> {
  late final ClientsRepository _repository;

  String _searchQuery = '';

  String get searchQuery => _searchQuery;

  @override
  Future<List<Client>> build() async {
    _repository = ref.read(clientsRepositoryProvider);

    return _loadClients();
  }

  Future<List<Client>> _loadClients() async {
    final AuthSession session = _requireSession();

    return _repository.fetchClients(session: session, search: _searchQuery);
  }

  Future<void> refresh() async {
    state = const AsyncLoading<List<Client>>();

    state = await AsyncValue.guard<List<Client>>(_loadClients);
  }

  Future<void> search(String query) async {
    _searchQuery = query.trim();

    state = const AsyncLoading<List<Client>>();

    state = await AsyncValue.guard<List<Client>>(_loadClients);
  }

  Future<void> clearSearch() async {
    if (_searchQuery.isEmpty) {
      return;
    }

    _searchQuery = '';

    state = const AsyncLoading<List<Client>>();

    state = await AsyncValue.guard<List<Client>>(_loadClients);
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

class ClientsAuthenticationException implements Exception {
  const ClientsAuthenticationException(this.message);

  final String message;

  @override
  String toString() => message;
}
