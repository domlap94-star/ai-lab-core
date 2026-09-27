import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../auth/application/auth_controller.dart';
import '../data/client_access_repository.dart';

class ClientShareUser {
  const ClientShareUser({required this.id, required this.displayName});

  final int id;
  final String displayName;
}

bool canManageClientAccess(String? role) {
  final String normalized = role?.trim().toLowerCase() ?? '';
  return normalized == 'user' ||
      normalized == 'admin' ||
      normalized == 'administrator';
}

final clientAccessRepositoryProvider = Provider<ClientAccessRepository>((
  Ref ref,
) {
  return ClientAccessRepository(ref.watch(dioProvider));
});

final sharedClientsProvider = FutureProvider<List<Map<String, dynamic>>>((
  Ref ref,
) async {
  final session = ref.watch(authControllerProvider).value?.session;
  if (session == null) return const <Map<String, dynamic>>[];
  return ref.watch(clientAccessRepositoryProvider).fetchSharedClients(session);
});

final clientGrantHistoryProvider = FutureProvider<List<Map<String, dynamic>>>((
  Ref ref,
) async {
  final session = ref.watch(authControllerProvider).value?.session;
  if (session == null) return const <Map<String, dynamic>>[];
  return ref.watch(clientAccessRepositoryProvider).fetchGrantHistory(session);
});

final clientAccessManagerOptionsProvider =
    FutureProvider<Map<String, List<Map<String, dynamic>>>>((Ref ref) async {
      final session = ref.watch(authControllerProvider).value?.session;
      if (session == null) {
        return const <String, List<Map<String, dynamic>>>{
          'clients': <Map<String, dynamic>>[],
          'external_users': <Map<String, dynamic>>[],
        };
      }
      return ref
          .watch(clientAccessRepositoryProvider)
          .fetchManagerOptions(session);
    });

final availableClientShareUsersProvider =
    FutureProvider.family<List<ClientShareUser>, int>((
      Ref ref,
      int clientId,
    ) async {
      final Map<String, List<Map<String, dynamic>>> options = await ref.watch(
        clientAccessManagerOptionsProvider.future,
      );
      final List<Map<String, dynamic>> grants = await ref.watch(
        clientGrantHistoryProvider.future,
      );

      final Set<int> activeUserIds = grants
          .where(
            (Map<String, dynamic> grant) =>
                grant['client_id'] == clientId && grant['active'] == true,
          )
          .map((Map<String, dynamic> grant) => grant['external_user_id'])
          .whereType<int>()
          .toSet();

      final List<ClientShareUser> users =
          (options['external_users'] ?? const <Map<String, dynamic>>[])
              .map((Map<String, dynamic> row) {
                final Object? rawId = row['id'];
                if (rawId is! int) return null;
                final String name = (row['username'] ?? row['name'] ?? '')
                    .toString()
                    .trim();
                if (name.isEmpty || activeUserIds.contains(rawId)) return null;
                return ClientShareUser(id: rawId, displayName: name);
              })
              .whereType<ClientShareUser>()
              .toList(growable: false)
            ..sort(
              (ClientShareUser left, ClientShareUser right) => left.displayName
                  .toLowerCase()
                  .compareTo(right.displayName.toLowerCase()),
            );
      return users;
    });

void invalidateClientAccess(WidgetRef ref, int clientId) {
  ref.invalidate(clientGrantHistoryProvider);
  ref.invalidate(clientAccessManagerOptionsProvider);
  ref.invalidate(availableClientShareUsersProvider(clientId));
}
