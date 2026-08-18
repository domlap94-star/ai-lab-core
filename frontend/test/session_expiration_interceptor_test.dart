import 'dart:async';
import 'dart:typed_data';

import 'package:ai_lab/core/network/api_client.dart';
import 'package:ai_lab/core/network/session_expiration_coordinator.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('successful protected request keeps the active session', () async {
    int expirationCount = 0;
    final SessionExpirationCoordinator coordinator =
        SessionExpirationCoordinator()
          ..registerHandler((_) async => expirationCount++);
    coordinator.markSessionActive('A');
    final Dio dio = _dio(statusCode: 200, coordinator: coordinator);

    await dio.get<void>(
      '/protected',
      options: Options(headers: <String, Object>{'Authorization': 'Bearer A'}),
    );

    expect(expirationCount, 0);
  });

  test('protected 401 expires the rejected token once', () async {
    int expirationCount = 0;
    String? rejectedToken;
    final SessionExpirationCoordinator coordinator =
        SessionExpirationCoordinator()..registerHandler((String token) async {
          expirationCount++;
          rejectedToken = token;
        });
    coordinator.markSessionActive('expired-token');
    final Dio dio = _dio(statusCode: 401, coordinator: coordinator);

    await expectLater(
      dio.get<void>(
        '/protected',
        options: Options(
          headers: <String, Object>{'Authorization': 'Bearer expired-token'},
        ),
      ),
      throwsA(isA<DioException>()),
    );

    expect(expirationCount, 1);
    expect(rejectedToken, 'expired-token');
  });

  test(
    'three concurrent 401 responses produce one logical expiration',
    () async {
      int expirationCount = 0;
      final Completer<void> started = Completer<void>();
      final Completer<void> release = Completer<void>();
      final SessionExpirationCoordinator coordinator =
          SessionExpirationCoordinator()..registerHandler((_) async {
            expirationCount++;
            if (!started.isCompleted) {
              started.complete();
            }
            await release.future;
          });
      coordinator.markSessionActive('same-token');
      final Dio dio = _dio(statusCode: 401, coordinator: coordinator);

      final List<Future<void>> requests = List<Future<void>>.generate(
        3,
        (_) => dio
            .get<void>(
              '/protected',
              options: Options(
                headers: <String, Object>{'Authorization': 'Bearer same-token'},
              ),
            )
            .then<void>((_) {}, onError: (_) {}),
      );
      await started.future;
      expect(expirationCount, 1);
      release.complete();
      await Future.wait<void>(requests);
      expect(expirationCount, 1);
    },
  );

  test('login 401 without Authorization does not expire a session', () async {
    int expirationCount = 0;
    final SessionExpirationCoordinator coordinator =
        SessionExpirationCoordinator()
          ..registerHandler((_) async => expirationCount++);
    final Dio dio = _dio(statusCode: 401, coordinator: coordinator);

    await expectLater(
      dio.post<void>('/api/v1/auth/login'),
      throwsA(isA<DioException>()),
    );

    expect(expirationCount, 0);
  });

  for (final int statusCode in <int>[403, 404, 409, 422, 500]) {
    test('HTTP $statusCode does not expire a session', () async {
      int expirationCount = 0;
      final SessionExpirationCoordinator coordinator =
          SessionExpirationCoordinator()
            ..registerHandler((_) async => expirationCount++);
      coordinator.markSessionActive('active-token');
      final Dio dio = _dio(statusCode: statusCode, coordinator: coordinator);

      await expectLater(
        dio.get<void>(
          '/protected',
          options: Options(
            headers: <String, Object>{'Authorization': 'Bearer active-token'},
          ),
        ),
        throwsA(isA<DioException>()),
      );

      expect(expirationCount, 0);
    });
  }

  test('network error does not expire a session', () async {
    int expirationCount = 0;
    final SessionExpirationCoordinator coordinator =
        SessionExpirationCoordinator()
          ..registerHandler((_) async => expirationCount++);
    coordinator.markSessionActive('active-token');
    final Dio dio = Dio()..httpClientAdapter = _ThrowingAdapter();
    installSessionExpirationInterceptor(dio, coordinator);

    await expectLater(
      dio.get<void>(
        '/protected',
        options: Options(
          headers: <String, Object>{'Authorization': 'Bearer active-token'},
        ),
      ),
      throwsA(isA<DioException>()),
    );

    expect(expirationCount, 0);
  });

  test('a newly activated identical token can expire again', () async {
    int expirationCount = 0;
    final SessionExpirationCoordinator coordinator =
        SessionExpirationCoordinator()
          ..registerHandler((_) async => expirationCount++);

    coordinator.markSessionActive('token');
    int? generation = coordinator.captureGeneration('token');
    await coordinator.handleUnauthorized(
      'token',
      requestGeneration: generation,
    );
    await coordinator.handleUnauthorized(
      'token',
      requestGeneration: generation,
    );
    expect(expirationCount, 1);

    coordinator.markSessionActive('token');
    generation = coordinator.captureGeneration('token');
    await coordinator.handleUnauthorized(
      'token',
      requestGeneration: generation,
    );
    expect(expirationCount, 2);
  });

  test('stale 401 cannot expire a newer generation with same token', () async {
    int expirationCount = 0;
    final SessionExpirationCoordinator coordinator =
        SessionExpirationCoordinator()
          ..registerHandler((_) async => expirationCount++);

    coordinator.markSessionActive('same-token');
    final int? staleGeneration = coordinator.captureGeneration('same-token');
    coordinator.markSessionActive('same-token');

    await coordinator.handleUnauthorized(
      'same-token',
      requestGeneration: staleGeneration,
    );
    expect(expirationCount, 0);

    await coordinator.handleUnauthorized(
      'same-token',
      requestGeneration: coordinator.captureGeneration('same-token'),
    );
    expect(expirationCount, 1);
  });

  test('request started before relogin cannot clear the new session', () async {
    int expirationCount = 0;
    final SessionExpirationCoordinator coordinator =
        SessionExpirationCoordinator()
          ..registerHandler((_) async => expirationCount++);
    coordinator.markSessionActive('same-token');
    final _DelayedStatusAdapter adapter = _DelayedStatusAdapter(401);
    final Dio dio = Dio()..httpClientAdapter = adapter;
    installSessionExpirationInterceptor(dio, coordinator);

    final Future<void> staleRequest = dio
        .get<void>(
          '/protected',
          options: Options(
            headers: <String, Object>{'Authorization': 'Bearer same-token'},
          ),
        )
        .then<void>((_) {}, onError: (_) {});
    await adapter.started.future;

    coordinator.markSessionActive('same-token');
    adapter.release.complete();
    await staleRequest;

    expect(expirationCount, 0);
    expect(coordinator.captureGeneration('same-token'), isNotNull);
  });
}

Dio _dio({
  required int statusCode,
  required SessionExpirationCoordinator coordinator,
}) {
  final Dio dio = Dio()..httpClientAdapter = _StatusAdapter(statusCode);
  installSessionExpirationInterceptor(dio, coordinator);
  return dio;
}

class _StatusAdapter implements HttpClientAdapter {
  _StatusAdapter(this.statusCode);

  final int statusCode;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    return ResponseBody.fromString('{}', statusCode);
  }

  @override
  void close({bool force = false}) {}
}

class _ThrowingAdapter implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) {
    throw DioException.connectionError(
      requestOptions: options,
      reason: 'offline',
    );
  }

  @override
  void close({bool force = false}) {}
}

class _DelayedStatusAdapter implements HttpClientAdapter {
  _DelayedStatusAdapter(this.statusCode);

  final int statusCode;
  final Completer<void> started = Completer<void>();
  final Completer<void> release = Completer<void>();

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    started.complete();
    await release.future;
    return ResponseBody.fromString('{}', statusCode);
  }

  @override
  void close({bool force = false}) {}
}
