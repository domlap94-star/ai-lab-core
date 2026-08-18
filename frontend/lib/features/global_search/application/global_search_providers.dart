import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../data/global_search_api.dart';

final globalSearchGatewayProvider = Provider<GlobalSearchGateway>(
  (Ref ref) => GlobalSearchApi(ref.watch(dioProvider)),
);
