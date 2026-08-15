import 'package:dio/dio.dart';

import '../domain/backend_status.dart';

class SystemStatusRepository {
  const SystemStatusRepository(this._dio, this._baseUrl);

  final Dio _dio;
  final String _baseUrl;

  Future<BackendStatus> fetchStatus() async {
    final Stopwatch stopwatch = Stopwatch()..start();

    final List<Response<dynamic>> responses =
        await Future.wait<Response<dynamic>>(<Future<Response<dynamic>>>[
          _dio.get<dynamic>('/health'),
          _dio.get<dynamic>('/version'),
        ]);

    stopwatch.stop();

    final Map<String, dynamic> health = _asJsonMap(
      responses[0].data,
      endpoint: '/health',
    );

    final Map<String, dynamic> version = _asJsonMap(
      responses[1].data,
      endpoint: '/version',
    );

    final String healthStatus = health['status']?.toString() ?? '';

    return BackendStatus(
      isOnline: healthStatus.toLowerCase() == 'ok',
      application: version['application']?.toString() ?? 'NEXT Stabil',
      version: version['version']?.toString() ?? 'nieznana',
      environment: version['environment']?.toString() ?? 'nieznane',
      debug: version['debug'] == true,
      latencyMilliseconds: stopwatch.elapsedMilliseconds,
      baseUrl: _baseUrl,
    );
  }

  Map<String, dynamic> _asJsonMap(dynamic value, {required String endpoint}) {
    if (value is Map<String, dynamic>) {
      return value;
    }

    if (value is Map) {
      return Map<String, dynamic>.from(value);
    }

    throw FormatException(
      'Endpoint $endpoint zwrócił nieprawidłowy format danych.',
    );
  }
}
