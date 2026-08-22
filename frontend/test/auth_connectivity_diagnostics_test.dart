import 'dart:convert';
import 'dart:typed_data';

import 'package:ai_lab/core/network/api_client.dart';
import 'package:ai_lab/features/auth/application/auth_diagnostics.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test(
    'health probe uses canonical Dio and returns safe metadata only',
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
      expect(state.apiHost, 'example.invalid');
      expect(state.health?.httpStatus, 200);
      expect(state.health?.parseResult, 'ok');
      expect(state.health?.safeLines.join('\n'), isNot(contains('password')));
      expect(state.health?.safeLines.join('\n'), isNot(contains('Bearer')));
    },
  );

  test('Dio transport and HTTP failures have bounded classifications', () {
    final RequestOptions request = RequestOptions(path: '/api/v1/auth/login');
    final SafeAuthRequestDiagnostic socket =
        AuthDiagnosticController.diagnosticFromError(
          operation: 'LOGIN',
          method: 'POST',
          path: request.path,
          error: DioException.connectionError(
            requestOptions: request,
            reason: 'synthetic socket detail must not be rendered',
          ),
        );
    expect(socket.dioExceptionType, 'connectionError');
    expect(socket.transportCategory, 'socket');
    expect(socket.safeLines.join('\n'), isNot(contains('synthetic socket')));

    final SafeAuthRequestDiagnostic unauthorized =
        AuthDiagnosticController.diagnosticFromError(
          operation: 'LOGIN',
          method: 'POST',
          path: request.path,
          error: DioException.badResponse(
            statusCode: 401,
            requestOptions: request,
            response: Response<Map<String, dynamic>>(
              requestOptions: request,
              statusCode: 401,
              data: const <String, dynamic>{
                'code': 'AUTH_INVALID',
                'detail': 'private response detail',
              },
            ),
          ),
        );
    expect(unauthorized.httpStatus, 401);
    expect(unauthorized.safeErrorCode, 'AUTH_INVALID');
    expect(
      unauthorized.safeLines.join('\n'),
      isNot(contains('private response detail')),
    );
  });

  test('response schema failures are distinct from transport failures', () {
    final SafeAuthRequestDiagnostic result =
        AuthDiagnosticController.diagnosticFromError(
          operation: 'LOGIN',
          method: 'POST',
          path: '/api/v1/auth/login',
          error: const FormatException('private malformed body detail'),
        );
    expect(result.transportCategory, 'response_schema');
    expect(result.parseResult, 'invalid');
    expect(result.safeLines.join('\n'), isNot(contains('private malformed')));
  });
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
