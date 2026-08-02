import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../data/clients_api.dart';
import 'clients_repository.dart';

final clientsApiProvider = Provider<ClientsApi>((Ref ref) {
  return ClientsApi(ref.watch(dioProvider));
});

final clientsRepositoryProvider = Provider<ClientsRepository>((Ref ref) {
  return ClientsRepository(ref.watch(clientsApiProvider));
});
