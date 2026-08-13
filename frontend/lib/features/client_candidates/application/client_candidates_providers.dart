import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/application/auth_state.dart';
import '../../auth/domain/auth_session.dart';
import '../data/client_candidates_api.dart';
import '../domain/client_candidate.dart';
import '../domain/client_candidate_context.dart';
import 'client_candidates_repository.dart';

final clientCandidatesApiProvider = Provider<ClientCandidatesApi>((Ref ref) {
  return ClientCandidatesApi(ref.watch(dioProvider));
});

final clientCandidatesRepositoryProvider = Provider<ClientCandidatesRepository>(
  (Ref ref) {
    return ClientCandidatesRepository(ref.watch(clientCandidatesApiProvider));
  },
);

AuthSession requireCandidateSession(Ref ref) {
  final AsyncValue<AuthState> authValue = ref.watch(authControllerProvider);
  final AuthSession? session = authValue.value?.session;

  if (session == null || !session.isAuthenticated) {
    throw const ClientCandidatesAuthenticationException(
      'Brak aktywnej sesji użytkownika.',
    );
  }

  return session;
}

final clientCandidatesProvider = FutureProvider<List<ClientCandidate>>((
  Ref ref,
) async {
  final AuthSession session = requireCandidateSession(ref);

  return ref
      .watch(clientCandidatesRepositoryProvider)
      .fetchCandidates(session: session);
});

final clientCandidateContextProvider =
    FutureProvider.family<ClientCandidateContext, int>((
      Ref ref,
      int candidateId,
    ) async {
      final AuthSession session = requireCandidateSession(ref);

      return ref
          .watch(clientCandidatesRepositoryProvider)
          .fetchContext(session: session, candidateId: candidateId);
    });

class ClientCandidatesAuthenticationException implements Exception {
  const ClientCandidatesAuthenticationException(this.message);

  final String message;

  @override
  String toString() => message;
}
