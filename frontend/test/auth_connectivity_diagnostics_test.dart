import 'dart:convert';
import 'dart:typed_data';

import 'package:ai_lab/core/network/api_client.dart';
import 'package:ai_lab/features/auth/application/auth_diagnostics.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test(
    'health probe uses the application Dio client and bounded output',
    () async {
      final Dio dio = Dio(BaseOptions(baseUrl: 'https://example.invalid'))
        ..httpClientAdapter = _HealthAdapter();
      final ProviderContainer container = ProviderContainer(
        overrides: [
          apiBaseUrlProvider.overrideWithValue('https://example.invalid'),
          dioProvider.overrideWithValue(dio),
        ],
      );
      addTearDown(container.dispose);

      await container
          .read(authDiagnosticControllerProvider.notifier)
          .probeHealth();
      final AuthDiagnosticState state = container.read(
        authDiagnosticControllerProvider,
      );
      expect(state.effectiveApiBaseUrl, 'https://example.invalid');
      expect(state.health?.httpStatus, 200);
      expect(state.health?.result, 'ok');
      expect(state.health?.safeLines.join('\n'), isNot(contains('Bearer')));
    },
  );

  test('socket and TLS errors receive distinct bounded classifications', () {
    final RequestOptions request = RequestOptions(path: '/health');
    final SafeAuthDiagnostic socket = AuthDiagnosticController.fromError(
      'APP_HEALTH',
      request.path,
      DioException.connectionError(
        requestOptions: request,
        reason: 'private socket detail',
      ),
    );
    expect(socket.transport, 'socket');
    expect(socket.dioType, 'connectionError');
    expect(socket.safeLines.join('\n'), isNot(contains('private socket')));

    final SafeAuthDiagnostic tls = AuthDiagnosticController.fromError(
      'APP_HEALTH',
      request.path,
      DioException(
        requestOptions: request,
        type: DioExceptionType.unknown,
        error: const _SyntheticHandshakeException(),
      ),
    );
    expect(tls.transport, 'tls');
  });
}

class _SyntheticHandshakeException implements Exception {
  const _SyntheticHandshakeException();
}

class _HealthAdapter implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    expect(options.baseUrl, 'https://example.invalid');
    expect(options.path, '/health');
    return ResponseBody.fromBytes(
      utf8.encode('{"status":"ok"}'),
      200,
      headers: <String, List<String>>{
        Headers.contentTypeHeader: <String>['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}
