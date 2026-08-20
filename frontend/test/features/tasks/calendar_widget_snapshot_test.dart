import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ai_lab/features/tasks/application/calendar_widget_snapshot.dart';
import 'package:ai_lab/features/tasks/domain/work_item.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'widget snapshot is bounded and excludes auth and sensitive projections',
    () async {
      String? raw;
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(
            const MethodChannel('pl.ailab.app/calendar_widget'),
            (call) async {
              raw = call.arguments as String;
              return null;
            },
          );
      final day = DateTime(2026, 8, 20);
      await CalendarWidgetSnapshot.publish(
        CalendarMonthData(
          year: 2026,
          month: 8,
          total: 2,
          dayCounts: const {'2026-08-20': 2},
          truncated: false,
          items: [
            CalendarEntry(
              id: 1,
              kind: 'work_item',
              type: 'task',
              title: 'Bezpieczny skrócony tytuł',
              start: day,
              end: day,
              status: 'todo',
              clientId: 999,
            ),
            CalendarEntry(
              id: 2,
              kind: 'absence',
              type: 'absence',
              title: 'Absencja — Employee Private',
              start: day,
              end: day,
              status: 'approved',
            ),
          ],
        ),
      );
      final encoded = raw!;
      final data = jsonDecode(encoded) as Map<String, dynamic>;
      expect(data['schema_version'], 1);
      expect(encoded, isNot(contains('access_token')));
      expect(encoded, isNot(contains('refresh_token')));
      expect(encoded, isNot(contains('client')));
      expect(encoded, isNot(contains('Employee Private')));
      expect((data['items'] as List).last['title'], 'Absencja');
      expect((data['items'] as List).last['end_date'], '2026-08-20');
    },
  );
}
