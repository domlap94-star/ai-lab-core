import 'dart:convert';

import 'package:ai_lab/core/network/api_client.dart';
import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/data/auth_token_storage.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/auth/domain/current_user.dart';
import 'package:ai_lab/features/system_control/data/supervisor_api.dart';
import 'package:ai_lab/features/system_control/presentation/system_control_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues(<String, String>{
      'auth_access_token': 'synthetic-token',
      'auth_token_type': 'Bearer',
    });
  });

  tearDown(() {
    debugDefaultTargetPlatformOverride = null;
  });

  test('unknown projection does not become offline', () {
    final status = SupervisorStatus.fromJson(<String, dynamic>{
      'backend': <String, dynamic>{'state': 'online'},
      'supervisor': <String, dynamic>{'state': 'unknown'},
      'next_stabil': <String, dynamic>{'state': 'unknown'},
      'services': <String, dynamic>{},
    });
    expect(status.backend, RuntimeState.online);
    expect(status.supervisor, RuntimeState.unknown);
    expect(status.nextStabil, RuntimeState.unknown);
  });

  test('host controls are disabled on Android', () {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    final api = SupervisorApi(Dio(), _storage());
    expect(api.supportsHostControl, isFalse);
  });

  testWidgets('Android renders projected state and disables host controls', (
    tester,
  ) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    final dio = Dio(BaseOptions(baseUrl: 'https://example.invalid'));
    dio.httpClientAdapter = _StatusAdapter();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          dioProvider.overrideWithValue(dio),
          authControllerProvider.overrideWith(_AdminAuthController.new),
        ],
        child: const MaterialApp(home: SystemControlPage()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Backend'), findsOneWidget);
    expect(find.text('Supervisor'), findsOneWidget);
    expect(find.text('NEXT Stabil'), findsOneWidget);
    expect(find.text('online'), findsNWidgets(3));
    expect(find.textContaining('tylko na komputerze hosta'), findsOneWidget);
    final start = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Uruchom system'),
    );
    expect(start.onPressed, isNull);
    expect(find.text('offline'), findsNothing);
    debugDefaultTargetPlatformOverride = null;
  });

  testWidgets('unreachable projection renders unknown rather than offline', (
    tester,
  ) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    final dio = Dio(BaseOptions(baseUrl: 'https://example.invalid'));
    dio.httpClientAdapter = _StatusAdapter(unknown: true);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          dioProvider.overrideWithValue(dio),
          authControllerProvider.overrideWith(_AdminAuthController.new),
        ],
        child: const MaterialApp(home: SystemControlPage()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('nieznany / nieosiągalny'), findsNWidgets(2));
    expect(find.text('offline'), findsNothing);
    debugDefaultTargetPlatformOverride = null;
  });
}

AuthTokenStorage _storage() {
  return const AuthTokenStorage(FlutterSecureStorage());
}

const _session = AuthSession(accessToken: 'token', tokenType: 'Bearer');
const _admin = CurrentUser(
  id: 1,
  username: 'admin',
  email: 'admin@example.invalid',
  role: 'Administrator',
  isActive: true,
  mustChangePassword: false,
  passwordResetRequested: false,
);

class _AdminAuthController extends AuthController {
  @override
  Future<AuthState> build() async =>
      const AuthState(session: _session, user: _admin);
}

class _StatusAdapter implements HttpClientAdapter {
  _StatusAdapter({this.unknown = false});
  final bool unknown;

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final state = unknown ? 'unknown' : 'online';
    final body = jsonEncode(<String, dynamic>{
      'backend': <String, dynamic>{'state': 'online'},
      'supervisor': <String, dynamic>{'state': state},
      'next_stabil': <String, dynamic>{'state': state},
      'services': <String, dynamic>{},
      'remote_control': <String, dynamic>{'state': 'private_host_only'},
    });
    return ResponseBody.fromString(
      body,
      200,
      headers: <String, List<String>>{
        Headers.contentTypeHeader: <String>['application/json'],
      },
    );
  }
}
