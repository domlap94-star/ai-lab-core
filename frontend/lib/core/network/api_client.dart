import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/api_config.dart';

final apiBaseUrlProvider = Provider<String>((Ref ref) => ApiConfig.baseUrl);

final dioProvider = Provider<Dio>((Ref ref) {
  final String baseUrl = ref.watch(apiBaseUrlProvider);

  return Dio(
    BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 5),
      receiveTimeout: const Duration(seconds: 10),
      sendTimeout: const Duration(seconds: 10),
      responseType: ResponseType.json,
      headers: const <String, Object>{'Accept': 'application/json'},
    ),
  );
});
