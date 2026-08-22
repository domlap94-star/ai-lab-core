import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';

class AuthDiagnostics {
  AuthDiagnostics._();

  static const bool enabled = bool.fromEnvironment(
    'ANDROID_AUTH_DIAGNOSTICS',
    defaultValue: false,
  );
}

class SafeAuthRequestDiagnostic {
  const SafeAuthRequestDiagnostic({
    required this.operation,
    required this.method,
    required this.path,
    required this.requestReachedNetwork,
    this.tokenExisted,
    this.httpStatus,
    this.dioExceptionType = 'none',
    this.transportCategory = 'none',
    this.safeErrorCode = 'none',
    this.parseResult = 'not_applicable',
  });

  final String operation;
  final String method;
  final String path;
  final String requestReachedNetwork;
  final bool? tokenExisted;
  final int? httpStatus;
  final String dioExceptionType;
  final String transportCategory;
  final String safeErrorCode;
  final String parseResult;

  List<String> get safeLines => <String>[
    'OPERATION=$operation',
    'METHOD=$method',
    'PATH=$path',
    if (tokenExisted != null) 'TOKEN_EXISTED=${tokenExisted! ? 'yes' : 'no'}',
    'REQUEST_REACHED_NETWORK=$requestReachedNetwork',
    'HTTP_STATUS=${httpStatus ?? 'none'}',
    'DIO_EXCEPTION_TYPE=$dioExceptionType',
    'TRANSPORT_CATEGORY=$transportCategory',
    'SAFE_ERROR_CODE=$safeErrorCode',
    'PARSE_RESULT=$parseResult',
  ];
}

class AuthDiagnosticState {
  const AuthDiagnosticState({
    this.apiHost = 'unknown',
    this.health,
    this.session,
    this.login,
    this.healthRunning = false,
  });

  final String apiHost;
  final SafeAuthRequestDiagnostic? health;
  final SafeAuthRequestDiagnostic? session;
  final SafeAuthRequestDiagnostic? login;
  final bool healthRunning;

  AuthDiagnosticState copyWith({
    String? apiHost,
    SafeAuthRequestDiagnostic? health,
    SafeAuthRequestDiagnostic? session,
    SafeAuthRequestDiagnostic? login,
    bool? healthRunning,
  }) {
    return AuthDiagnosticState(
      apiHost: apiHost ?? this.apiHost,
      health: health ?? this.health,
      session: session ?? this.session,
      login: login ?? this.login,
      healthRunning: healthRunning ?? this.healthRunning,
    );
  }
}

final authDiagnosticControllerProvider =
    NotifierProvider<AuthDiagnosticController, AuthDiagnosticState>(
      AuthDiagnosticController.new,
    );

class AuthDiagnosticController extends Notifier<AuthDiagnosticState> {
  @override
  AuthDiagnosticState build() {
    final String baseUrl = ref.watch(apiBaseUrlProvider);
    return AuthDiagnosticState(apiHost: _safeHost(baseUrl));
  }

  Future<void> probeHealth() async {
    if (state.healthRunning) return;
    state = state.copyWith(healthRunning: true);
    try {
      final Response<Map<String, dynamic>> response = await ref
          .read(dioProvider)
          .get<Map<String, dynamic>>('/health');
      final bool schemaValid = response.data?['status'] == 'ok';
      state = state.copyWith(
        healthRunning: false,
        health: SafeAuthRequestDiagnostic(
          operation: 'APP_HEALTH',
          method: 'GET',
          path: '/health',
          requestReachedNetwork: 'yes',
          httpStatus: response.statusCode,
          parseResult: schemaValid ? 'ok' : 'invalid_health_schema',
        ),
      );
    } catch (error) {
      state = state.copyWith(
        healthRunning: false,
        health: diagnosticFromError(
          operation: 'APP_HEALTH',
          method: 'GET',
          path: '/health',
          error: error,
        ),
      );
    }
  }

  void recordNoStoredSession() {
    state = state.copyWith(
      session: const SafeAuthRequestDiagnostic(
        operation: 'STARTUP_SESSION',
        method: 'GET',
        path: '/api/v1/auth/me',
        requestReachedNetwork: 'no',
        tokenExisted: false,
        safeErrorCode: 'no_stored_session',
      ),
    );
  }

  void recordSessionSuccess() {
    state = state.copyWith(
      session: const SafeAuthRequestDiagnostic(
        operation: 'STARTUP_SESSION',
        method: 'GET',
        path: '/api/v1/auth/me',
        requestReachedNetwork: 'yes',
        tokenExisted: true,
        httpStatus: 200,
        parseResult: 'ok',
      ),
    );
  }

  void recordSessionFailure(Object error) {
    state = state.copyWith(
      session: diagnosticFromError(
        operation: 'STARTUP_SESSION',
        method: 'GET',
        path: '/api/v1/auth/me',
        error: error,
        tokenExisted: true,
      ),
    );
  }

  void recordLoginStarted() {
    state = state.copyWith(
      login: const SafeAuthRequestDiagnostic(
        operation: 'LOGIN',
        method: 'POST',
        path: '/api/v1/auth/login',
        requestReachedNetwork: 'unknown',
        safeErrorCode: 'request_started',
      ),
    );
  }

  void recordLoginTokenResponse() {
    state = state.copyWith(
      login: const SafeAuthRequestDiagnostic(
        operation: 'LOGIN',
        method: 'POST',
        path: '/api/v1/auth/login',
        requestReachedNetwork: 'yes',
        httpStatus: 200,
        parseResult: 'token_schema_ok',
      ),
    );
  }

  void recordLoginConfirmed() {
    state = state.copyWith(
      login: const SafeAuthRequestDiagnostic(
        operation: 'LOGIN_SESSION_CONFIRMATION',
        method: 'GET',
        path: '/api/v1/auth/me',
        requestReachedNetwork: 'yes',
        tokenExisted: true,
        httpStatus: 200,
        parseResult: 'user_schema_ok',
      ),
    );
  }

  void recordLoginFailure(Object error, {required String path}) {
    state = state.copyWith(
      login: diagnosticFromError(
        operation: path.endsWith('/me')
            ? 'LOGIN_SESSION_CONFIRMATION'
            : 'LOGIN',
        method: path.endsWith('/me') ? 'GET' : 'POST',
        path: path,
        error: error,
        tokenExisted: path.endsWith('/me') ? true : null,
      ),
    );
  }

  static SafeAuthRequestDiagnostic diagnosticFromError({
    required String operation,
    required String method,
    required String path,
    required Object error,
    bool? tokenExisted,
  }) {
    if (error is DioException) {
      final int? status = error.response?.statusCode;
      return SafeAuthRequestDiagnostic(
        operation: operation,
        method: method,
        path: path,
        tokenExisted: tokenExisted,
        requestReachedNetwork: status != null ? 'yes' : _requestReach(error),
        httpStatus: status,
        dioExceptionType: error.type.name,
        transportCategory: _transportCategory(error),
        safeErrorCode: _safeBackendCode(error.response?.data),
        parseResult: status == null ? 'not_available' : 'http_error',
      );
    }
    if (error is FormatException) {
      return SafeAuthRequestDiagnostic(
        operation: operation,
        method: method,
        path: path,
        tokenExisted: tokenExisted,
        requestReachedNetwork: 'yes',
        transportCategory: 'response_schema',
        safeErrorCode: 'response_schema_invalid',
        parseResult: 'invalid',
      );
    }
    return SafeAuthRequestDiagnostic(
      operation: operation,
      method: method,
      path: path,
      tokenExisted: tokenExisted,
      requestReachedNetwork: 'unknown',
      transportCategory: 'other',
      safeErrorCode: 'unclassified_client_error',
      parseResult: 'unknown',
    );
  }

  static String _safeHost(String baseUrl) {
    final Uri? uri = Uri.tryParse(baseUrl);
    return uri?.host.isNotEmpty == true ? uri!.host : 'invalid';
  }

  static String _requestReach(DioException error) {
    switch (error.type) {
      case DioExceptionType.badResponse:
        return 'yes';
      case DioExceptionType.connectionError:
      case DioExceptionType.badCertificate:
        return 'no';
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.cancel:
      case DioExceptionType.transformTimeout:
      case DioExceptionType.unknown:
        return 'unknown';
    }
  }

  static String _transportCategory(DioException error) {
    final String underlying = error.error.runtimeType.toString().toLowerCase();
    if (underlying.contains('handshake') ||
        error.type == DioExceptionType.badCertificate) {
      return 'tls_handshake';
    }
    if (underlying.contains('socket') ||
        error.type == DioExceptionType.connectionError) {
      return 'socket';
    }
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.transformTimeout:
        return 'timeout';
      case DioExceptionType.badResponse:
        return 'http';
      case DioExceptionType.cancel:
        return 'cancelled';
      case DioExceptionType.badCertificate:
        return 'tls_handshake';
      case DioExceptionType.connectionError:
        return 'socket';
      case DioExceptionType.unknown:
        return 'unknown';
    }
  }

  static String _safeBackendCode(Object? data) {
    if (data is! Map) return 'none';
    for (final String key in const <String>['error_code', 'code']) {
      final Object? candidate = data[key];
      if (candidate is String &&
          RegExp(r'^[A-Za-z0-9_.-]{1,64}$').hasMatch(candidate)) {
        return candidate;
      }
    }
    return 'none';
  }
}
