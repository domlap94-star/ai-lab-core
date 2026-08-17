import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/domain/auth_session.dart';
import '../data/client_emails_api.dart';
import '../domain/client_email_page.dart';
import 'client_emails_repository.dart';

class ClientEmailsPageRequest {
  const ClientEmailsPageRequest({
    required this.clientId,
    this.skip = 0,
    this.limit = 10,
    this.sourceId,
  });

  final int clientId;
  final int skip;
  final int limit;
  final int? sourceId;

  @override
  bool operator ==(Object other) {
    return other is ClientEmailsPageRequest &&
        other.clientId == clientId &&
        other.skip == skip &&
        other.limit == limit &&
        other.sourceId == sourceId;
  }

  @override
  int get hashCode => Object.hash(clientId, skip, limit, sourceId);
}

final clientEmailsApiProvider = Provider<ClientEmailsApi>((Ref ref) {
  return ClientEmailsApi(ref.watch(dioProvider));
});

final clientEmailsRepositoryProvider = Provider<ClientEmailsRepository>((
  Ref ref,
) {
  return ApiClientEmailsRepository(ref.watch(clientEmailsApiProvider));
});

final clientEmailsPageProvider = FutureProvider.autoDispose
    .family<ClientEmailPage, ClientEmailsPageRequest>((
      Ref ref,
      ClientEmailsPageRequest request,
    ) {
      return ref
          .watch(clientEmailsRepositoryProvider)
          .fetchEmails(
            session: requireClientEmailSession(ref),
            clientId: request.clientId,
            skip: request.skip,
            limit: request.limit,
            sourceId: request.sourceId,
          );
    });

AuthSession requireClientEmailSession(Ref ref) {
  final AuthSession? session = ref.read(authControllerProvider).value?.session;
  if (session == null || !session.isAuthenticated) {
    throw const ClientEmailsAuthenticationException(
      'Brak aktywnej sesji użytkownika.',
    );
  }
  return session;
}

class ClientEmailsAuthenticationException implements Exception {
  const ClientEmailsAuthenticationException(this.message);
  final String message;
  @override
  String toString() => message;
}
