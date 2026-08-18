import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/api_config.dart';
import 'session_expiration_coordinator.dart';

final apiBaseUrlProvider = Provider<String>((Ref ref) => ApiConfig.baseUrl);

final sessionExpirationCoordinatorProvider =
    Provider<SessionExpirationCoordinator>((Ref ref) {
      return SessionExpirationCoordinator();
    });

final dioProvider = Provider<Dio>((Ref ref) {
  final String baseUrl = ref.watch(apiBaseUrlProvider);
  final SessionExpirationCoordinator coordinator = ref.watch(
    sessionExpirationCoordinatorProvider,
  );

  final Dio dio = Dio(
    BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 5),
      receiveTimeout: const Duration(seconds: 10),
      sendTimeout: const Duration(seconds: 10),
      responseType: ResponseType.json,
      headers: const <String, Object>{'Accept': 'application/json'},
    ),
  );

  installSessionExpirationInterceptor(dio, coordinator);
  return dio;
});

void installSessionExpirationInterceptor(
  Dio dio,
  SessionExpirationCoordinator coordinator,
) {
  const String sessionGenerationKey = 'auth_session_generation';
  dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (RequestOptions options, RequestInterceptorHandler handler) {
        final String? accessToken = _authorizedAccessToken(options.headers);
        if (accessToken != null) {
          options.extra[sessionGenerationKey] = coordinator.captureGeneration(
            accessToken,
          );
        }
        handler.next(options);
      },
      onError: (DioException error, ErrorInterceptorHandler handler) async {
        if (error.response?.statusCode == 401) {
          final String? accessToken = _authorizedAccessToken(
            error.requestOptions.headers,
          );
          if (accessToken != null) {
            try {
              await coordinator.handleUnauthorized(
                accessToken,
                requestGeneration:
                    error.requestOptions.extra[sessionGenerationKey] as int?,
              );
            } finally {
              handler.next(error);
            }
            return;
          }
        }
        handler.next(error);
      },
    ),
  );
}

String? _authorizedAccessToken(Map<String, dynamic> headers) {
  Object? authorization;
  for (final MapEntry<String, dynamic> entry in headers.entries) {
    if (entry.key.toLowerCase() == 'authorization') {
      authorization = entry.value;
      break;
    }
  }
  if (authorization is! String) {
    return null;
  }

  final RegExpMatch? match = RegExp(
    r'^\s*Bearer\s+(.+?)\s*$',
    caseSensitive: false,
  ).firstMatch(authorization);
  final String? token = match?.group(1)?.trim();
  return token == null || token.isEmpty ? null : token;
}
