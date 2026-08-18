import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../data/client_ai_knowledge_api.dart';

final clientAiKnowledgeGatewayProvider = Provider<ClientAiKnowledgeGateway>(
  (Ref ref) => ClientAiKnowledgeApi(ref.watch(dioProvider)),
);
