import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/documents/application/documents_repository.dart';
import 'package:ai_lab/features/documents/presentation/document_intake_dialog.dart';
import 'package:ai_lab/features/inspections/application/inspection_field_services.dart';

class _Repository extends DocumentsRepository {
  final List<Map<String, dynamic>> uploads = <Map<String, dynamic>>[];

  @override
  Future<void> upload({
    required AuthSession session,
    required String name,
    String? path,
    Uint8List? bytes,
    int? clientId,
    int? projectId,
    int? inspectionId,
    String origin = 'manual_upload',
    DateTime? capturedAt,
    double? latitude,
    double? longitude,
    double? accuracy,
    String? deviceModel,
    String? comment,
    void Function(int, int)? onProgress,
  }) async {
    uploads.add(<String, dynamic>{
      'client_id': clientId,
      'project_id': projectId,
      'inspection_id': inspectionId,
      'origin': origin,
      'captured_at': capturedAt,
      'latitude': latitude,
      'longitude': longitude,
      'accuracy': accuracy,
    });
    onProgress?.call(1, 1);
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _ImagePicker implements DocumentImagePicker {
  _ImagePicker(this.origin);
  final String origin;

  IntakeFile _file() => IntakeFile(
    name: 'field.jpg',
    bytes: Uint8List.fromList(<int>[1, 2, 3]),
    origin: origin,
    capturedAt: DateTime.utc(2026, 8, 18, 12),
  );

  @override
  Future<IntakeFile?> captureCamera() async => _file();

  @override
  Future<List<IntakeFile>> pickGallery() async => <IntakeFile>[_file()];
}

class _DeniedLocation implements InspectionLocationService {
  @override
  Future<FieldLocationResult> currentLocation() async =>
      const FieldLocationResult.status(FieldLocationStatus.denied);
  @override
  Future<bool> openAppSettings() async => true;
  @override
  Future<bool> openLocationSettings() async => true;
}

class _SuccessfulLocation extends _DeniedLocation {
  @override
  Future<FieldLocationResult> currentLocation() async =>
      const FieldLocationResult.success(
        latitude: 52.2297,
        longitude: 21.0122,
        accuracy: 6,
      );
}

void main() {
  const session = AuthSession(accessToken: 'token', tokenType: 'Bearer');

  testWidgets('camera action is Android-only and intake is responsive', (
    tester,
  ) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: DocumentIntakeDialog(
            repository: _Repository(),
            session: session,
            clientId: 7,
          ),
        ),
      ),
    );
    expect(find.text('Dodaj pliki'), findsOneWidget);
    expect(find.text('Dodaj zdjęcie'), findsOneWidget);
    expect(find.text('Zrób zdjęcie'), findsOneWidget);
    expect(find.textContaining('odmowa nie blokuje'), findsOneWidget);
    expect(tester.takeException(), isNull);
    debugDefaultTargetPlatformOverride = null;
  });

  testWidgets(
    'inspection intake declares automatic best-effort GPS and no manual toggle',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: DocumentIntakeDialog(
              repository: _Repository(),
              session: session,
              clientId: 7,
              inspectionId: 12,
              locationService: _DeniedLocation(),
            ),
          ),
        ),
      );
      expect(find.text('Dołącz bieżącą lokalizację'), findsNothing);
      expect(find.textContaining('automatycznie dołączyć'), findsOneWidget);
      expect(find.textContaining('Brak GPS nie blokuje'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('inspection camera sends foreground GPS metadata', (
    tester,
  ) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    final repository = _Repository();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: DocumentIntakeDialog(
            repository: repository,
            session: session,
            clientId: 7,
            inspectionId: 12,
            locationService: _SuccessfulLocation(),
            imagePicker: _ImagePicker('camera_capture'),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Zrób zdjęcie'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Prześlij'));
    await tester.pumpAndSettle();
    expect(repository.uploads.single, containsPair('client_id', 7));
    expect(repository.uploads.single, containsPair('inspection_id', 12));
    expect(repository.uploads.single['project_id'], isNull);
    expect(repository.uploads.single, containsPair('latitude', 52.2297));
    expect(repository.uploads.single, containsPair('longitude', 21.0122));
    expect(repository.uploads.single, containsPair('accuracy', 6.0));
    expect(repository.uploads.single['captured_at'], isNotNull);
    debugDefaultTargetPlatformOverride = null;
  });

  testWidgets('gallery upload continues when location is denied', (
    tester,
  ) async {
    final repository = _Repository();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: DocumentIntakeDialog(
            repository: repository,
            session: session,
            clientId: 7,
            inspectionId: 12,
            locationService: _DeniedLocation(),
            imagePicker: _ImagePicker('gallery_upload'),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Dodaj zdjęcie'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Prześlij'));
    await tester.pumpAndSettle();
    expect(repository.uploads, hasLength(1));
    expect(repository.uploads.single['latitude'], isNull);
    expect(repository.uploads.single['longitude'], isNull);
    expect(repository.uploads.single['captured_at'], isNotNull);
  });
}
