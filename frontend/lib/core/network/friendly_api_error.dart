import 'package:dio/dio.dart';

const String _networkMessage =
    'Brak połączenia z serwerem. Sprawdź sieć i spróbuj ponownie.';

String friendlyApiError(
  Object error, {
  String fallback = 'Nie udało się wykonać operacji.',
}) {
  if (error is! DioException) return fallback;

  if (<DioExceptionType>{
    DioExceptionType.connectionError,
    DioExceptionType.unknown,
  }.contains(error.type)) {
    return _networkMessage;
  }
  if (error.type == DioExceptionType.connectionTimeout) {
    return 'Nie udało się połączyć z serwerem w wymaganym czasie.';
  }
  if (error.type == DioExceptionType.sendTimeout) {
    return 'Nie udało się wysłać żądania w wymaganym czasie.';
  }
  if (error.type == DioExceptionType.receiveTimeout) {
    return 'Serwer nie zakończył operacji w wymaganym czasie.';
  }

  final int? statusCode = error.response?.statusCode;
  return switch (statusCode) {
    401 => 'Sesja wygasła. Zaloguj się ponownie.',
    403 => 'Nie masz uprawnień do wykonania tej operacji.',
    404 => 'Nie znaleziono żądanego elementu.',
    409 =>
      _safeDetail(error.response?.data) ??
          'Operacja jest w konflikcie z aktualnym stanem danych.',
    422 =>
      _safeDetail(error.response?.data) ??
          'Sprawdź poprawność wprowadzonych danych.',
    int code when code >= 500 => 'Wystąpił błąd serwera. Spróbuj ponownie.',
    _ => fallback,
  };
}

String? _safeDetail(Object? data) {
  final Object? detail = data is Map ? data['detail'] : null;
  if (detail is! String) return null;
  final String value = detail.trim();
  if (value.isEmpty || value.length > 200 || value.contains('\n')) return null;
  final String lower = value.toLowerCase();
  const forbidden = <String>[
    'dioexception',
    'traceback',
    'stack trace',
    'requestoptions',
    'authorization',
    'access_token',
    'refresh_token',
    '<html',
  ];
  return forbidden.any(lower.contains) ? null : value;
}
