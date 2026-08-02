import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/application/auth_state.dart';
import '../../auth/domain/auth_session.dart';
import '../data/clients_api.dart';
import '../domain/industry.dart';
import 'clients_repository.dart';

final clientsApiProvider = Provider<ClientsApi>((Ref ref) {
  return ClientsApi(ref.watch(dioProvider));
});

final clientsRepositoryProvider = Provider<ClientsRepository>((Ref ref) {
  return ClientsRepository(ref.watch(clientsApiProvider));
});

final industriesProvider = FutureProvider<List<Industry>>((Ref ref) async {
  final AsyncValue<AuthState> authValue = ref.watch(authControllerProvider);

  final AuthSession? session = authValue.value?.session;

  if (session == null || !session.isAuthenticated) {
    throw const ClientsAuthenticationException(
      'Brak aktywnej sesji użytkownika.',
    );
  }

  final ClientsRepository repository = ref.watch(clientsRepositoryProvider);

  return repository.fetchIndustries(session: session);
});

class ClientsAuthenticationException implements Exception {
  const ClientsAuthenticationException(this.message);

  final String message;

  @override
  String toString() => message;
}
