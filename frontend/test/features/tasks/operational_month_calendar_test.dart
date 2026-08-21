import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ai_lab/features/tasks/domain/work_item.dart';
import 'package:ai_lab/features/tasks/presentation/operational_month_calendar.dart';

void main() {
  final day = DateTime(2026, 8, 20);
  final items = List.generate(
    5,
    (index) => CalendarEntry(
      id: index + 1,
      kind: index == 4 ? 'absence' : 'work_item',
      type: const [
        'task',
        'order',
        'realization',
        'reminder',
        'absence',
      ][index],
      title: 'Pozycja kalendarza ${index + 1}',
      start: day,
      end: day,
      status: index == 4 ? 'requested' : 'todo',
    ),
  );

  for (final width in [360.0, 390.0, 600.0, 1200.0]) {
    testWidgets('month calendar is responsive at ${width.toInt()}', (
      tester,
    ) async {
      tester.view.physicalSize = Size(width, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: OperationalMonthCalendar(
                month: day,
                items: items,
                selectedDay: day,
                onSelectedDay: (_) {},
                onPrevious: () {},
                onNext: () {},
                onToday: () {},
              ),
            ),
          ),
        ),
      );
      await tester.pump();
      expect(tester.takeException(), isNull);
      expect(find.text('Dzisiaj'), findsOneWidget);
      expect(find.byKey(const Key('calendar-day-2026-08-20')), findsOneWidget);
      final expectedVisible = width >= 1200
          ? 4
          : width >= 600
          ? 3
          : 2;
      for (var index = 1; index <= expectedVisible; index++) {
        expect(find.text('Pozycja kalendarza $index'), findsWidgets);
      }
      expect(
        find.text('+${items.length - expectedVisible} więcej'),
        findsOneWidget,
      );
    });
  }

  test('presentation contract covers every calendar type', () {
    for (final type in [
      'task',
      'order',
      'realization',
      'reminder',
      'event',
      'absence',
    ]) {
      expect(CalendarPresentation.label(type), isNotEmpty);
      expect(CalendarPresentation.icon(type), isNotNull);
      expect(CalendarPresentation.color(type), isNotNull);
    }
  });

  testWidgets('multi-day entries use one segment per intersected week', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(600, 1100);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    final sameWeek = CalendarEntry(
      id: 101,
      kind: 'work_item',
      type: 'realization',
      title: 'Fundament 600kg',
      start: DateTime(2026, 8, 25),
      end: DateTime(2026, 8, 28),
      status: 'todo',
    );
    final crossing = CalendarEntry(
      id: 102,
      kind: 'work_item',
      type: 'task',
      title: 'Przez granicę tygodnia',
      start: DateTime(2026, 8, 28),
      end: DateTime(2026, 9, 1),
      status: 'todo',
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: OperationalMonthCalendar(
              month: DateTime(2026, 8),
              items: [sameWeek, crossing],
              selectedDay: DateTime(2026, 8, 25),
              onSelectedDay: (_) {},
              onPrevious: () {},
              onNext: () {},
              onToday: () {},
            ),
          ),
        ),
      ),
    );
    await tester.pump();
    expect(
      find.byKey(const Key('calendar-segment-work_item-101-2026-08-24')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('calendar-segment-work_item-102-2026-08-24')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('calendar-segment-work_item-102-2026-08-31')),
      findsOneWidget,
    );
    expect(find.textContaining('25.08.2026 – 28.08.2026'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
