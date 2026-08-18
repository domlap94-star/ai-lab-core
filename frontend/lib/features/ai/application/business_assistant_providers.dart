import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../data/business_assistant_api.dart';

final businessAssistantGatewayProvider = Provider<BusinessAssistantGateway>(
  (Ref ref) => BusinessAssistantApi(ref.watch(dioProvider)),
);
