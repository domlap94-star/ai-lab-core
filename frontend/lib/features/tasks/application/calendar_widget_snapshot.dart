import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../auth/application/auth_controller.dart';
import 'tasks_providers.dart';
import '../domain/work_item.dart';

class CalendarWidgetSnapshot {
  static const _channel = MethodChannel('pl.ailab.app/calendar_widget');
  static Future<void> publish(CalendarMonthData data) async {
    final now = DateTime.now();
    if (data.year != now.year || data.month != now.month) return;
    final today = DateTime(now.year, now.month, now.day);
    final upcoming =
        data.items
            .where(
              (entry) => !DateTime(
                entry.end.year,
                entry.end.month,
                entry.end.day,
              ).isBefore(today),
            )
            .toList()
          ..sort((a, b) => a.start.compareTo(b.start));
    final safe = {
      'schema_version': 1,
      'year': data.year,
      'month': data.month,
      'updated_at': DateTime.now().toUtc().toIso8601String(),
      'items': upcoming
          .take(40)
          .map(
            (e) => {
              'date': e.start.toIso8601String().split('T').first,
              'end_date': e.end.toIso8601String().split('T').first,
              'type': e.type,
              'title': e.kind == 'absence'
                  ? 'Absencja'
                  : (e.title.length > 48 ? e.title.substring(0, 48) : e.title),
              'status': e.status,
              'priority': e.priority,
              'id': e.id,
              'kind': e.kind,
            },
          )
          .toList(),
    };
    try {
      await _channel.invokeMethod<void>('saveSnapshot', jsonEncode(safe));
    } on MissingPluginException {
      /* Android only. */
    }
  }

  static Future<void> refreshCurrent(WidgetRef ref) async {
    final session = ref.read(authControllerProvider).value?.session;
    if (session == null) return;
    final now = DateTime.now();
    try {
      final data = await ref
          .read(workItemsApiProvider)
          .month(session, DateTime(now.year, now.month));
      await publish(data);
    } catch (_) {
      // The native widget deliberately keeps its last safe snapshot offline.
    }
  }
}
