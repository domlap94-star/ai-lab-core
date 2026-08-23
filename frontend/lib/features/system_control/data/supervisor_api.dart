import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

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

    return SupervisorStatus(
      backend: component('backend'),
      supervisor: component('supervisor'),
      nextStabil: component('next_stabil'),
      services: services,
      reason: supervisor is Map ? supervisor['reason']?.toString() : null,
    );
  }

  final RuntimeState backend;
  final RuntimeState supervisor;
  final RuntimeState nextStabil;
  final Map<String, RuntimeState> services;
  final String? reason;
}

class SupervisorApi {
  SupervisorApi(this._publicDio, this._tokenStorage)
    : _controlDio = Dio(
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
  final Dio _publicDio;
  final Dio _controlDio;

  bool get supportsHostControl {
    return !kIsWeb && defaultTargetPlatform == TargetPlatform.windows;
  }

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

  Future<void> startSystem() => _control('/start');

  Future<void> restartSystem() => _control('/restart');

  Future<void> stopSystem() => _control('/stop');

  Future<void> _control(String path) async {
    if (!supportsHostControl) {
      throw StateError('Sterowanie jest dostępne tylko na komputerze hosta.');
    }
    await _controlDio.post<void>(path, options: await _authorizedOptions());
  }
}
