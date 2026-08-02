import '../../auth/domain/auth_session.dart';
import '../data/clients_api.dart';
import '../domain/client.dart';
import '../domain/industry.dart';

class ClientsRepository {
  const ClientsRepository(this._api);

  final ClientsApi _api;

  Future<List<Client>> fetchClients({
    required AuthSession session,
    String? search,
    int skip = 0,
    int limit = 100,
  }) async {
    final responses = await _api.fetchClients(
      accessToken: session.accessToken,
      tokenType: session.tokenType,
      search: search,
      skip: skip,
      limit: limit,
    );

    return responses
        .map<Client>((response) => response.toDomain())
        .toList(growable: false);
  }

  Future<Client> fetchClient({
    required AuthSession session,
    required int clientId,
  }) async {
    final response = await _api.fetchClient(
      clientId: clientId,
      accessToken: session.accessToken,
      tokenType: session.tokenType,
    );

    return response.toDomain();
  }

  Future<List<Industry>> fetchIndustries({required AuthSession session}) async {
    final responses = await _api.fetchIndustries(
      accessToken: session.accessToken,
      tokenType: session.tokenType,
    );

    return responses
        .map<Industry>((response) => response.toDomain())
        .toList(growable: false);
  }
}
