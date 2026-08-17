import '../../auth/domain/auth_session.dart';
import '../data/client_emails_api.dart';
import '../domain/client_email_page.dart';

abstract class ClientEmailsRepository {
  Future<ClientEmailPage> fetchEmails({
    required AuthSession session,
    required int clientId,
    int skip,
    int limit,
    int? sourceId,
  });
}

class ApiClientEmailsRepository implements ClientEmailsRepository {
  const ApiClientEmailsRepository(this._api);

  final ClientEmailsApi _api;

  @override
  Future<ClientEmailPage> fetchEmails({
    required AuthSession session,
    required int clientId,
    int skip = 0,
    int limit = 20,
    int? sourceId,
  }) async {
    final response = await _api.fetchEmails(
      clientId: clientId,
      accessToken: session.accessToken,
      tokenType: session.tokenType,
      skip: skip,
      limit: limit,
      sourceId: sourceId,
    );
    return response.toDomain();
  }
}
