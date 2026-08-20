import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/application/auth_state.dart';
import '../../auth/domain/auth_session.dart';
import '../data/trash_api.dart';
import '../domain/trash_entry.dart';

final trashApiProvider = Provider<TrashApi>(
  (ref) => TrashApi(ref.watch(dioProvider)),
);

AuthSession requireTrashSession(Ref ref) {
  return requireTrashSessionFromAuth(ref.read(authControllerProvider));
}

AuthSession requireTrashSessionFromAuth(AsyncValue<AuthState> auth) {
  final session = auth.value?.session;
  if (session == null || !session.isAuthenticated) {
    throw StateError('Brak aktywnej sesji.');
  }
  return session;
}

final trashPageProvider = FutureProvider.autoDispose
    .family<TrashPageData, TrashEntityType>((ref, entityType) {
      return ref
          .watch(trashApiProvider)
          .fetch(session: requireTrashSession(ref), entityType: entityType);
    });
