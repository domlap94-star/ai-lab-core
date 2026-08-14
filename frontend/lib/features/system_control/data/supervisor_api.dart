import 'package:dio/dio.dart';

import '../../auth/data/auth_token_storage.dart';

class SupervisorStatus {
  const SupervisorStatus({
    required this.supervisorOnline,
    required this.systemRunning,
    required this.services,
  });

  factory SupervisorStatus.fromJson(Map<String, dynamic> json) {
    final dynamic rawServices = json['services'];

    final Map<String, bool> services = rawServices is Map
        ? rawServices.map(
            (dynamic key, dynamic value) =>
                MapEntry(key.toString(), value == true),
          )
        : <String, bool>{};

    return SupervisorStatus(
      supervisorOnline: json['supervisor_online'] == true,
      systemRunning: json['system_running'] == true,
      services: services,
    );
  }

  final bool supervisorOnline;
  final bool systemRunning;
  final Map<String, bool> services;
}

class SupervisorApi {
  SupervisorApi(this._tokenStorage)
    : _dio = Dio(
        BaseOptions(
          baseUrl: const String.fromEnvironment(
            'SUPERVISOR_BASE_URL',
            defaultValue: 'http://127.0.0.1:8787',
          ),
          connectTimeout: const Duration(seconds: 3),
          receiveTimeout: const Duration(seconds: 30),
        ),
      );

  final AuthTokenStorage _tokenStorage;
  final Dio _dio;

  Future<Options> _authorizedOptions() async {
    final String? token = await _tokenStorage.readAccessToken();

    if (token == null || token.isEmpty) {
      throw StateError('Brak aktywnego tokenu administratora.');
    }

    return Options(
      headers: <String, dynamic>{'Authorization': 'Bearer $token'},
    );
  }

  Future<SupervisorStatus> getStatus() async {
    final Response<dynamic> response = await _dio.get<dynamic>(
      '/status',
      options: await _authorizedOptions(),
    );

    if (response.data is! Map) {
      throw const FormatException('Nieprawidłowa odpowiedź supervisora.');
    }

    return SupervisorStatus.fromJson(
      Map<String, dynamic>.from(response.data as Map),
    );
  }

  Future<void> startSystem() async {
    await _dio.post<void>('/start', options: await _authorizedOptions());
  }

  Future<void> restartSystem() async {
    await _dio.post<void>('/restart', options: await _authorizedOptions());
  }

  Future<void> stopSystem() async {
    await _dio.post<void>('/stop', options: await _authorizedOptions());
  }
}
