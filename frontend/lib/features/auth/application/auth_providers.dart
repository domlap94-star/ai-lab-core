import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../../core/network/api_client.dart';
import '../data/auth_api.dart';
import '../data/auth_token_storage.dart';
import 'auth_repository.dart';

final secureStorageProvider = Provider<FlutterSecureStorage>((Ref ref) {
  return const FlutterSecureStorage();
});

final authTokenStorageProvider = Provider<AuthTokenStorage>((Ref ref) {
  return AuthTokenStorage(ref.watch(secureStorageProvider));
});

final authApiProvider = Provider<AuthApi>((Ref ref) {
  return AuthApi(ref.watch(dioProvider));
});

final authRepositoryProvider = Provider<AuthRepository>((Ref ref) {
  return AuthRepository(ref.watch(authApiProvider));
});
