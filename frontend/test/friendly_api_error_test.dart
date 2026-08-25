import 'package:ai_lab/core/network/friendly_api_error.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('maps API and transport errors without exposing Dio internals', () {
    expect(
      friendlyApiError(_responseError(403)),
      'Nie masz uprawnień do wykonania tej operacji.',
    );
    expect(
      friendlyApiError(_responseError(404)),
      'Nie znaleziono żądanego elementu.',
    );
    expect(
      friendlyApiError(_responseError(409)),
      'Operacja jest w konflikcie z aktualnym stanem danych.',
    );
    expect(
      friendlyApiError(_responseError(422, detail: 'Niepoprawna data.')),
      'Niepoprawna data.',
    );
    expect(
      friendlyApiError(
        _responseError(422, detail: 'DioException RequestOptions token'),
      ),
      'Sprawdź poprawność wprowadzonych danych.',
    );
    expect(
      friendlyApiError(_responseError(500)),
      'Wystąpił błąd serwera. Spróbuj ponownie.',
    );
    expect(
      friendlyApiError(
        DioException.connectionError(
          requestOptions: RequestOptions(path: '/projects'),
          reason: 'offline',
        ),
      ),
      'Brak połączenia z serwerem. Sprawdź sieć i spróbuj ponownie.',
    );
    expect(
      friendlyApiError(
        DioException(
          requestOptions: RequestOptions(path: '/ai'),
          type: DioExceptionType.connectionTimeout,
        ),
      ),
      'Nie udało się połączyć z serwerem w wymaganym czasie.',
    );
    expect(
      friendlyApiError(
        DioException(
          requestOptions: RequestOptions(path: '/ai'),
          type: DioExceptionType.receiveTimeout,
        ),
      ),
      'Serwer nie zakończył operacji w wymaganym czasie.',
    );
    expect(
      friendlyApiError(StateError('secret implementation detail')),
      'Nie udało się wykonać operacji.',
    );
  });
}

DioException _responseError(int status, {String? detail}) {
  final RequestOptions request = RequestOptions(path: '/protected');
  return DioException.badResponse(
    statusCode: status,
    requestOptions: request,
    response: Response<Map<String, dynamic>>(
      requestOptions: request,
      statusCode: status,
      data: detail == null ? <String, dynamic>{} : {'detail': detail},
    ),
  );
}
