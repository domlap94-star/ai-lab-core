import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../data/technical_assistant_api.dart';

final technicalAssistantGatewayProvider = Provider<TechnicalAssistantGateway>(
  (Ref ref) => TechnicalAssistantApi(ref.watch(dioProvider)),
);
