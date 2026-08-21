import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/domain/auth_session.dart';
import '../data/knowledge_base_api.dart';

final knowledgeBaseApiProvider = Provider<KnowledgeBaseApi>(
  (Ref ref) => KnowledgeBaseApi(ref.watch(dioProvider)),
);
AuthSession requireKnowledgeBaseSession(WidgetRef ref) {
  final session = ref.read(authControllerProvider).value?.session;
  if (session == null || !session.isAuthenticated) {
    throw StateError('Brak aktywnej sesji.');
  }
  return session;
}
