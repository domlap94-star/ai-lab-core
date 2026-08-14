import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../data/account_api.dart';

final accountApiProvider = Provider<AccountApi>((Ref ref) {
  return AccountApi(ref.watch(dioProvider));
});
