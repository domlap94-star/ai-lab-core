import 'package:dio/dio.dart';

import '../../auth/data/auth_token_storage.dart';

enum RuntimeState { online, offline, unknown, unavailable }

RuntimeState _runtimeState(dynamic value) {
  return switch (value?.toString().trim().toLowerCase()) {
    'online' => RuntimeState.online,
    'offline' => RuntimeState.offline,
    'unavailable' => RuntimeState.unavailable,
    _ => RuntimeState.unknown,
  };
}

class SupervisorStatus {
  const SupervisorStatus({
    required this.backend,
    required this.supervisor,
    required this.nextStabil,
    required this.services,
    required this.remoteControlAvailable,
    this.reason,
  });

  factory SupervisorStatus.fromJson(Map<String, dynamic> json) {
    RuntimeState component(String key) {
      final dynamic raw = json[key];
      return raw is Map ? _runtimeState(raw['state']) : RuntimeState.unknown;
    }

    final dynamic rawServices = json['services'];

    final Map<String, RuntimeState> services = rawServices is Map
        ? rawServices.map(
            (dynamic key, dynamic value) =>
                MapEntry(key.toString(), _runtimeState(value)),
          )
        : <String, RuntimeState>{};
    final dynamic supervisor = json['supervisor'];
    final dynamic remoteControl = json['remote_control'];

    return SupervisorStatus(
      backend: component('backend'),
      supervisor: component('supervisor'),
      nextStabil: component('next_stabil'),
      services: services,
      remoteControlAvailable:
          remoteControl is Map && remoteControl['state'] == 'available',
      reason: supervisor is Map ? supervisor['reason']?.toString() : null,
    );
  }

  final RuntimeState backend;
  final RuntimeState supervisor;
  final RuntimeState nextStabil;
  final Map<String, RuntimeState> services;
  final bool remoteControlAvailable;
  final String? reason;
}

class SupervisorApi {
  SupervisorApi(this._publicDio, this._tokenStorage);

  final AuthTokenStorage _tokenStorage;
  final Dio _publicDio;

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
    final Response<dynamic> response = await _publicDio.get<dynamic>(
      '/api/v1/admin/system-status',
      options: await _authorizedOptions(),
    );

    if (response.data is! Map) {
      throw const FormatException('Nieprawidłowa odpowiedź stanu systemu.');
    }

    return SupervisorStatus.fromJson(
      Map<String, dynamic>.from(response.data as Map),
    );
  }

  Future<Map<String, dynamic>> startSystem() => _control('start');

  Future<Map<String, dynamic>> restartSystem() => _control('restart');

  Future<Map<String, dynamic>> stopSystem() => _control('stop');

  Future<Map<String, dynamic>> _control(String command) async {
    final Options options = await _authorizedOptions();
    final Response<Map<String, dynamic>> preflight = await _publicDio
        .post<Map<String, dynamic>>(
          '/api/v1/admin/system-status/control/preflight',
          data: <String, dynamic>{'command': command},
          options: options,
        );
    final String token = preflight.data?['token']?.toString() ?? '';
    if (token.isEmpty) {
      throw const FormatException('Nieprawidłowy token polecenia.');
    }
    final Response<Map<String, dynamic>> result = await _publicDio
        .post<Map<String, dynamic>>(
          '/api/v1/admin/system-status/control/execute',
          data: <String, dynamic>{'command': command, 'token': token},
          options: options,
        );
    return result.data ?? const <String, dynamic>{};
  }
}
