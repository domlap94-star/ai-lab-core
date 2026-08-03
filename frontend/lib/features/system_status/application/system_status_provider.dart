import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../data/system_status_repository.dart';
import '../domain/backend_status.dart';

final systemStatusRepositoryProvider = Provider<SystemStatusRepository>((
  Ref ref,
) {
  return SystemStatusRepository(
    ref.watch(dioProvider),
    ref.watch(apiBaseUrlProvider),
  );
});

final backendStatusProvider = FutureProvider<BackendStatus>((Ref ref) {
  return ref.watch(systemStatusRepositoryProvider).fetchStatus();
});
