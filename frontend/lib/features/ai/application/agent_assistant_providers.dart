import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../data/agent_assistant_api.dart';

final agentAssistantGatewayProvider = Provider<AgentAssistantGateway>(
  (Ref ref) => AgentAssistantApi(ref.watch(dioProvider)),
);
