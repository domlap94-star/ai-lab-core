import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/inspections/application/inspection_field_services.dart';
import 'package:ai_lab/features/inspections/application/inspections_providers.dart';
import 'package:ai_lab/features/inspections/data/inspections_api.dart';
import 'package:ai_lab/features/inspections/domain/inspection.dart';
import 'package:ai_lab/features/inspections/presentation/inspection_details_page.dart';
import 'package:ai_lab/features/inspections/presentation/inspection_form_dialog.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

const AuthSession _session = AuthSession(
  accessToken: 'test-token',
  tokenType: 'bearer',
);

Map<String, dynamic> _json({String notes = 'Pierwsza notatka'}) =>
    <String, dynamic>{
      'id': 12,
      'project_id': null,
      'project_name': null,
      'client_id': 3,
      'client_name': 'Klient A',
      'title': 'Wizja lokalna — Klient A',
      'status': 'planned',
      'scheduled_at': null,
      'started_at': null,
      'completed_at': null,
      'notes': notes,
      'latitude': null,
      'longitude': null,
      'location_accuracy_m': null,
      'created_at': '2026-08-17T10:00:00Z',
      'updated_at': '2026-08-17T10:00:00Z',
      'deleted_at': null,
    };

class _AuthController extends AuthController {
  @override
  Future<AuthState> build() async =>
      const AuthState(session: _session, user: null);
}

class _LocationService implements InspectionLocationService {
  _LocationService(this.result);
  final FieldLocationResult result;
  int settingsCalls = 0;

  @override
  Future<FieldLocationResult> currentLocation() async => result;
  @override
  Future<bool> openAppSettings() async {
    settingsCalls++;
    return true;
  }

  @override
  Future<bool> openLocationSettings() async {
    settingsCalls++;
    return true;
  }
}

class _SpeechService implements InspectionSpeechService {
  ValueChanged<String>? finalResult;
  VoidCallback? stopped;
  int cancelCalls = 0;

  @override
  bool get isSupportedPlatform => true;

  @override
  Future<SpeechStartStatus> start({
    required ValueChanged<String> onFinalResult,
    required VoidCallback onStopped,
  }) async {
    finalResult = onFinalResult;
    stopped = onStopped;
    return SpeechStartStatus.listening;
  }

  void emit(String text) {
    finalResult?.call(text);
    stopped?.call();
  }

  @override
  Future<void> cancel() async {
    cancelCalls++;
    stopped?.call();
  }

  @override
  Future<bool> openAppSettings() async => true;

  @override
  Future<void> stop() async => stopped?.call();
}

Future<({GoRouter router, List<Map<String, dynamic>> patches})> _pump(
  WidgetTester tester, {
  required InspectionLocationService location,
  required InspectionSpeechService speech,
}) async {
  final List<Map<String, dynamic>> patches = <Map<String, dynamic>>[];
  final Dio dio = Dio(BaseOptions(baseUrl: 'https://example.test'));
  dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) {
        if (options.method == 'PATCH') {
          patches.add(Map<String, dynamic>.from(options.data as Map));
        }
        handler.resolve(
          Response<Map<String, dynamic>>(
            requestOptions: options,
            statusCode: 200,
            data: _json(
              notes: patches.isEmpty
                  ? 'Pierwsza notatka'
                  : patches.last['notes']?.toString() ?? '',
            ),
          ),
        );
      },
    ),
  );
  final GoRouter router = GoRouter(
    initialLocation: '/inspections/12',
    routes: <RouteBase>[
      GoRoute(
        path: '/inspections',
        builder: (_, _) => const Scaffold(body: Text('Lista wizji')),
      ),
      GoRoute(
        path: '/inspections/:id',
        builder: (_, _) => const InspectionDetailsPage(inspectionId: 12),
      ),
    ],
  );
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authControllerProvider.overrideWith(_AuthController.new),
        inspectionDetailsProvider(12).overrideWith((ref) async {
          await ref.watch(authControllerProvider.future);
          return Inspection.fromJson(_json());
        }),
        inspectionsApiProvider.overrideWithValue(InspectionsApi(dio)),
        inspectionLocationServiceProvider.overrideWithValue(location),
        inspectionSpeechServiceProvider.overrideWithValue(speech),
      ],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
  return (router: router, patches: patches);
}

void main() {
  testWidgets('location patch contains only coordinates and reports success', (
    tester,
  ) async {
    final location = _LocationService(
      const FieldLocationResult.success(
        latitude: 52.1,
        longitude: 21.2,
        accuracy: 8,
      ),
    );
    final result = await _pump(
      tester,
      location: location,
      speech: _SpeechService(),
    );
    addTearDown(result.router.dispose);

    await tester.tap(find.byKey(const Key('inspection-share-location')));
    await tester.pumpAndSettle();

    expect(result.patches, hasLength(1));
    expect(result.patches.single, <String, dynamic>{
      'latitude': 52.1,
      'longitude': 21.2,
      'location_accuracy_m': 8.0,
    });
    expect(find.text('Lokalizacja zapisana'), findsOneWidget);
  });

  testWidgets('permanent location denial offers application settings', (
    tester,
  ) async {
    final location = _LocationService(
      const FieldLocationResult.status(FieldLocationStatus.deniedForever),
    );
    final result = await _pump(
      tester,
      location: location,
      speech: _SpeechService(),
    );
    addTearDown(result.router.dispose);
    await tester.tap(find.byKey(const Key('inspection-share-location')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Ustawienia aplikacji'), findsOneWidget);
    await tester.tap(find.text('Ustawienia aplikacji'));
    await tester.pumpAndSettle();
    expect(location.settingsCalls, 1);
    expect(result.patches, isEmpty);
  });

  testWidgets('notes autosave is debounced and latest edit wins', (
    tester,
  ) async {
    final result = await _pump(
      tester,
      location: _LocationService(
        const FieldLocationResult.status(FieldLocationStatus.denied),
      ),
      speech: _SpeechService(),
    );
    addTearDown(result.router.dispose);
    final Finder notes = find.byKey(const Key('inspection-inline-notes'));

    await tester.enterText(notes, 'Pierwsza zmiana');
    await tester.pump(const Duration(milliseconds: 400));
    await tester.enterText(notes, 'Najnowsza zmiana');
    await tester.pump(const Duration(milliseconds: 799));
    expect(result.patches, isEmpty);
    await tester.pump(const Duration(milliseconds: 2));
    await tester.pumpAndSettle();

    expect(result.patches, hasLength(1));
    expect(result.patches.single, <String, dynamic>{
      'notes': 'Najnowsza zmiana',
    });
    expect(find.text('Zapisano'), findsOneWidget);
  });

  testWidgets('Back immediately after typing flushes the pending autosave', (
    tester,
  ) async {
    final result = await _pump(
      tester,
      location: _LocationService(
        const FieldLocationResult.status(FieldLocationStatus.denied),
      ),
      speech: _SpeechService(),
    );
    addTearDown(result.router.dispose);
    await tester.enterText(
      find.byKey(const Key('inspection-inline-notes')),
      'Tekst przed Back',
    );
    await tester.tap(find.byIcon(Icons.arrow_back));
    await tester.pumpAndSettle();
    expect(result.patches.single, <String, dynamic>{
      'notes': 'Tekst przed Back',
    });
    expect(find.text('Lista wizji'), findsOneWidget);
  });

  testWidgets('Polish speech is appended and saved through the same autosave', (
    tester,
  ) async {
    final speech = _SpeechService();
    final result = await _pump(
      tester,
      location: _LocationService(
        const FieldLocationResult.status(FieldLocationStatus.denied),
      ),
      speech: speech,
    );
    addTearDown(result.router.dispose);
    await tester.tap(find.byKey(const Key('inspection-notes-microphone')));
    await tester.pump();
    expect(find.text('Słucham…'), findsOneWidget);

    speech.emit('Zmierzyć poziom posadzki w salonie.');
    await tester.pump(const Duration(milliseconds: 801));
    await tester.pumpAndSettle();

    expect(
      result.patches.single['notes'],
      'Pierwsza notatka\nZmierzyć poziom posadzki w salonie.',
    );
    expect(find.text('Słucham…'), findsNothing);
  });

  testWidgets('manual GPS inputs are absent from create and edit forms', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: InspectionFormDialog(clientId: 3, clientName: 'Klient A'),
        ),
      ),
    );
    expect(find.text('Szerokość geograficzna'), findsNothing);
    expect(find.text('Długość geograficzna'), findsNothing);
    expect(find.text('Dokładność GPS (m)'), findsNothing);
  });
}
