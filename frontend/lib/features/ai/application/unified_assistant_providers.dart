import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../data/unified_assistant_api.dart';

final unifiedAssistantApiProvider = Provider<UnifiedAssistantApi>(
  (Ref ref) => UnifiedAssistantApi(ref.watch(dioProvider)),
);
