import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:ai_lab/core/formatters/polish_date_time.dart';

void main() {
  test('Task Detail owner UX contract stays compact and canonical', () {
    final source = File(
      'lib/features/tasks/presentation/task_detail_page.dart',
    ).readAsStringSync();
    expect(source, isNot(contains("title: const Text('Szczegóły zadania')")));
    expect(source, isNot(contains('Chip(label: Text(item.type.label))')));
    expect(source, contains('value.value?.title'));
    expect(source, contains('formatPolishDateRange'));
    expect(source, contains("label: const Text('Zadzwoń')"));
    expect(source, contains("label: const Text('Otwórz w Mapach')"));
    expect(source, contains("Key('work-item-documents-collapsed')"));
    expect(source, contains("label: const Text('Otwórz realizację')"));
  });

  test('inclusive date range presentation does not alter endpoints', () {
    final start = DateTime(2026, 8, 25);
    final due = DateTime(2026, 8, 28);
    expect(formatPolishDateRange(start, due), '25.08.2026 – 28.08.2026');
    expect(start, DateTime(2026, 8, 25));
    expect(due, DateTime(2026, 8, 28));
  });
}
