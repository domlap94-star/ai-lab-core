import '../../auth/domain/auth_session.dart';
import '../data/client_create_request.dart';
import '../data/clients_api.dart';
import '../domain/client.dart';
import '../domain/client_page.dart';
import '../domain/industry.dart';

class ClientsRepository {
  const ClientsRepository(this._api);

  final ClientsApi _api;

  Future<ClientPage> fetchClients({
    required AuthSession session,
    String? search,
    ClientType? clientType,
    int? industryId,
    int skip = 0,
    int limit = 50,
  }) async {
    final response = await _api.fetchClients(
      accessToken: session.accessToken,
      tokenType: session.tokenType,
      search: search,
      clientType: clientType?.value,
      industryId: industryId,
      skip: skip,
      limit: limit,
    );

    return ClientPage(
      items: response.items
          .map<Client>((item) => item.toDomain())
          .toList(growable: false),
      total: response.total,
      skip: response.skip,
      limit: response.limit,
    );
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

  Future<Client> createClient({
    required AuthSession session,
    required ClientCreateRequest request,
  }) async {
    final response = await _api.createClient(
      request: request,
      accessToken: session.accessToken,
      tokenType: session.tokenType,
    );

    return response.toDomain();
  }
}
