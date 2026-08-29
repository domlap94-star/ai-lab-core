import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../data/assistant_conversation_repository.dart';

final assistantConversationRepositoryProvider =
    Provider<AssistantConversationRepository>(
      (Ref ref) => AssistantConversationRepository(ref.watch(dioProvider)),
    );
