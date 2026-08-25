import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/api_config.dart';
import '../../../core/network/api_client.dart';

class SafeAuthDiagnostic {
  const SafeAuthDiagnostic({
    required this.operation,
    required this.path,
    required this.network,
    this.httpStatus,
    this.dioType = 'none',
    this.transport = 'none',
    this.result = 'not_available',
  });

  final String operation;
  final String path;
  final String network;
  final int? httpStatus;
  final String dioType;
  final String transport;
  final String result;

  List<String> get safeLines => <String>[
    'OPERATION=$operation',
    'PATH=$path',
    'REQUEST_REACHED_NETWORK=$network',
    'HTTP_STATUS=${httpStatus ?? 'none'}',
    'DIO_EXCEPTION_TYPE=$dioType',
    'TRANSPORT_CATEGORY=$transport',
    'RESULT=$result',
  ];
}

class AuthDiagnosticState {
  const AuthDiagnosticState({
    required this.effectiveApiBaseUrl,
    required this.apiSource,
    required this.buildMode,
    this.health,
    this.session,
    this.login,
    this.healthRunning = false,
  });

  final String effectiveApiBaseUrl;
  final String apiSource;
  final String buildMode;
  final SafeAuthDiagnostic? health;
  final SafeAuthDiagnostic? session;
  final SafeAuthDiagnostic? login;
  final bool healthRunning;

  AuthDiagnosticState copyWith({
    SafeAuthDiagnostic? health,
    SafeAuthDiagnostic? session,
    SafeAuthDiagnostic? login,
    bool? healthRunning,
  }) => AuthDiagnosticState(
    effectiveApiBaseUrl: effectiveApiBaseUrl,
    apiSource: apiSource,
    buildMode: buildMode,
    health: health ?? this.health,
    session: session ?? this.session,
    login: login ?? this.login,
    healthRunning: healthRunning ?? this.healthRunning,
  );
}

final authDiagnosticControllerProvider =
    NotifierProvider<AuthDiagnosticController, AuthDiagnosticState>(
      AuthDiagnosticController.new,
    );

class AuthDiagnosticController extends Notifier<AuthDiagnosticState> {
  @override
  AuthDiagnosticState build() => AuthDiagnosticState(
    effectiveApiBaseUrl: ref.watch(apiBaseUrlProvider),
    apiSource: ApiConfig.sourceDescription,
    buildMode: ApiConfig.buildMode,
  );

  Future<void> probeHealth() async {
    if (state.healthRunning) return;
    state = state.copyWith(healthRunning: true);
    try {
      final Response<Map<String, dynamic>> response = await ref
          .read(dioProvider)
          .get<Map<String, dynamic>>('/health');
      state = state.copyWith(
        healthRunning: false,
        health: SafeAuthDiagnostic(
          operation: 'APP_HEALTH',
          path: '/health',
          network: 'yes',
          httpStatus: response.statusCode,
          result: response.data?['status'] == 'ok' ? 'ok' : 'invalid_schema',
        ),
      );
    } catch (error) {
      state = state.copyWith(
        healthRunning: false,
        health: fromError('APP_HEALTH', '/health', error),
      );
    }
  }

  void recordNoSession() => state = state.copyWith(
    session: const SafeAuthDiagnostic(
      operation: 'STARTUP_SESSION',
      path: '/api/v1/auth/me',
      network: 'no',
      result: 'no_stored_session',
    ),
  );

  void recordSessionSuccess() => state = state.copyWith(
    session: const SafeAuthDiagnostic(
      operation: 'STARTUP_SESSION',
      path: '/api/v1/auth/me',
      network: 'yes',
      httpStatus: 200,
      result: 'ok',
    ),
  );

  void recordSessionFailure(Object error) => state = state.copyWith(
    session: fromError('STARTUP_SESSION', '/api/v1/auth/me', error),
  );

  void recordLoginSuccess() => state = state.copyWith(
    login: const SafeAuthDiagnostic(
      operation: 'LOGIN',
      path: '/api/v1/auth/login + /api/v1/auth/me',
      network: 'yes',
      httpStatus: 200,
      result: 'ok',
    ),
  );

  void recordLoginFailure(Object error, String path) =>
      state = state.copyWith(login: fromError('LOGIN', path, error));

  static SafeAuthDiagnostic fromError(
    String operation,
    String path,
    Object error,
  ) {
    if (error is FormatException) {
      return SafeAuthDiagnostic(
        operation: operation,
        path: path,
        network: 'yes',
        transport: 'response_schema',
        result: 'invalid_schema',
      );
    }
    if (error is! DioException) {
      return SafeAuthDiagnostic(
        operation: operation,
        path: path,
        network: 'unknown',
        transport: 'other',
        result: 'client_error',
      );
    }
    final String underlying = error.error.runtimeType.toString().toLowerCase();
    final String transport;
    if (error.type == DioExceptionType.badCertificate ||
        underlying.contains('handshake') ||
        underlying.contains('certificate')) {
      transport = 'tls';
    } else if (error.type == DioExceptionType.connectionError ||
        underlying.contains('socket')) {
      transport = 'socket';
    } else if (<DioExceptionType>{
      DioExceptionType.connectionTimeout,
      DioExceptionType.sendTimeout,
      DioExceptionType.receiveTimeout,
      DioExceptionType.transformTimeout,
    }.contains(error.type)) {
      transport = 'timeout';
    } else if (error.response != null) {
      transport = 'http';
    } else {
      transport = error.type.name;
    }
    return SafeAuthDiagnostic(
      operation: operation,
      path: path,
      network: error.response != null ? 'yes' : 'unknown',
      httpStatus: error.response?.statusCode,
      dioType: error.type.name,
      transport: transport,
      result: error.response == null ? 'transport_failure' : 'http_error',
    );
  }
}
