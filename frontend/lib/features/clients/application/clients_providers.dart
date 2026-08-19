import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/application/auth_state.dart';
import '../../auth/domain/auth_session.dart';
import '../data/clients_api.dart';
import '../domain/client.dart';
import '../domain/industry.dart';
import 'client_workflow_status.dart';
import 'clients_repository.dart';

final clientsApiProvider = Provider<ClientsApi>((Ref ref) {
  return ClientsApi(ref.watch(dioProvider));
});

final clientsRepositoryProvider = Provider<ClientsRepository>((Ref ref) {
  return ClientsRepository(ref.watch(clientsApiProvider));
});

final clientDetailsProvider = FutureProvider.family<Client, int>((
  Ref ref,
  int clientId,
) async {
  final AsyncValue<AuthState> authValue = ref.watch(authControllerProvider);

  final AuthSession? session = authValue.value?.session;

  if (session == null || !session.isAuthenticated) {
    throw const ClientsAuthenticationException(
      'Brak aktywnej sesji użytkownika.',
    );
  }

  final ClientsRepository repository = ref.watch(clientsRepositoryProvider);

  return repository.fetchClient(session: session, clientId: clientId);
});

final clientWorkflowStatusesProvider =
    FutureProvider.family<Map<int, ClientWorkflowStatus>, String>((
      Ref ref,
      String clientIdsKey,
    ) async {
      final AuthSession? session = ref
          .watch(authControllerProvider)
          .value
          ?.session;
      if (session == null || !session.isAuthenticated) {
        return const <int, ClientWorkflowStatus>{};
      }
      final List<int> clientIds = clientIdsKey
          .split(',')
          .map(int.tryParse)
          .whereType<int>()
          .toList(growable: false);
      if (clientIds.isEmpty) return const <int, ClientWorkflowStatus>{};
      final rows = await ref
          .watch(clientsRepositoryProvider)
          .fetchWorkflowStatuses(session: session, clientIds: clientIds);
      return <int, ClientWorkflowStatus>{
        for (final row in rows)
          if (row['client_id'] is int)
            row['client_id'] as int: ClientWorkflowStatus(
              state: ClientWorkflowState.fromApi(
                row['status']?.toString() ?? '',
              ),
              date: DateTime.tryParse(row['effective_date']?.toString() ?? ''),
              serverLabel: row['label']?.toString(),
            ),
      };
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
