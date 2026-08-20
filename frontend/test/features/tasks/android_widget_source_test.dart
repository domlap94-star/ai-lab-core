import 'dart:io';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('native widget uses private sanitized snapshot and safe deep links', () {
    final kotlin = File(
      'android/app/src/main/kotlin/com/example/frontend/CalendarAppWidget.kt',
    ).readAsStringSync();
    final activity = File(
      'android/app/src/main/kotlin/com/example/frontend/MainActivity.kt',
    ).readAsStringSync();
    final manifest = File(
      'android/app/src/main/AndroidManifest.xml',
    ).readAsStringSync();
    final appShell = File('lib/core/widgets/app_shell.dart').readAsStringSync();
    expect(kotlin, contains('AppWidgetProvider'));
    expect(kotlin, contains('RemoteViews'));
    expect(kotlin, contains('/tasks?create=1'));
    expect(kotlin, contains('/tasks?absence=1'));
    expect(kotlin, contains('end_date'));
    expect(kotlin, contains('guard < 42'));
    expect(kotlin, contains('/tasks?date='));
    expect(kotlin, contains('dayIds.forEachIndexed'));
    expect(kotlin, contains('typeMarker'));
    expect(kotlin, contains('LocalDate.now()'));
    expect(kotlin, isNot(contains('Authorization')));
    expect(activity, contains('MODE_PRIVATE'));
    expect(activity, contains('schema_version'));
    expect(activity, contains('client_name'));
    expect(activity, contains('access_token'));
    expect(manifest, isNot(contains('READ_CALENDAR')));
    expect(manifest, isNot(contains('WRITE_CALENDAR')));
    expect(manifest, isNot(contains('POST_NOTIFICATIONS')));
    expect(appShell, contains('AppLifecycleState.resumed'));
    expect(appShell, isNot(contains('_widgetSyncTimer')));
  });
}
