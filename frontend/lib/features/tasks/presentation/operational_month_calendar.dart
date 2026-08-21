import 'package:flutter/material.dart';
import '../../../core/formatters/polish_date_time.dart';
import '../domain/work_item.dart';

class CalendarPresentation {
  static String label(String type) => switch (type) {
    'task' => 'Zadanie',
    'order' => 'Zlecenie',
    'realization' => 'Realizacja',
    'reminder' => 'Przypomnienie',
    'event' => 'Wydarzenie',
    'absence' => 'Absencja',
    _ => type,
  };
  static IconData icon(String type) => switch (type) {
    'task' => Icons.task_alt,
    'order' => Icons.assignment_outlined,
    'realization' => Icons.construction,
    'reminder' => Icons.alarm,
    'event' => Icons.event,
    'absence' => Icons.beach_access,
    _ => Icons.circle,
  };
  static Color color(String type) => switch (type) {
    'task' => Colors.blue,
    'order' => Colors.deepPurple,
    'realization' => Colors.teal,
    'reminder' => Colors.orange,
    'event' => Colors.indigo,
    'absence' => Colors.pink,
    _ => Colors.grey,
  };
}

class OperationalMonthCalendar extends StatelessWidget {
  const OperationalMonthCalendar({
    required this.month,
    required this.items,
    required this.selectedDay,
    required this.onSelectedDay,
    required this.onPrevious,
    required this.onNext,
    required this.onToday,
    this.onEntry,
    super.key,
  });
  final DateTime month, selectedDay;
  final List<CalendarEntry> items;
  final ValueChanged<DateTime> onSelectedDay;
  final VoidCallback onPrevious, onNext, onToday;
  final ValueChanged<CalendarEntry>? onEntry;
  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, c) {
        final density = c.maxWidth >= 1200
            ? 4
            : c.maxWidth >= 600
            ? 3
            : 2;
        final first = DateTime(month.year, month.month, 1);
        final gridStart = first.subtract(Duration(days: first.weekday - 1));
        final days = List.generate(42, (i) => gridStart.add(Duration(days: i)));
        final selected = items.where((e) => e.covers(selectedDay)).toList();
        final wide = c.maxWidth >= 850;
        final grid = Column(
          children: [
            Row(
              children: [
                IconButton(
                  tooltip: 'Poprzedni miesiąc',
                  onPressed: onPrevious,
                  icon: const Icon(Icons.chevron_left),
                ),
                Expanded(
                  child: Text(
                    '${_months[month.month - 1]} ${month.year}',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                TextButton(onPressed: onToday, child: const Text('Dzisiaj')),
                IconButton(
                  tooltip: 'Następny miesiąc',
                  onPressed: onNext,
                  icon: const Icon(Icons.chevron_right),
                ),
              ],
            ),
            Row(
              children: [
                for (final d in const [
                  'Pn',
                  'Wt',
                  'Śr',
                  'Cz',
                  'Pt',
                  'Sb',
                  'Nd',
                ])
                  Expanded(child: Text(d, textAlign: TextAlign.center)),
              ],
            ),
            for (var week = 0; week < 6; week++)
              _CalendarWeekRow(
                days: days.sublist(week * 7, week * 7 + 7),
                month: month,
                selectedDay: selectedDay,
                items: items,
                laneCapacity: density,
                onSelectedDay: onSelectedDay,
                onEntry: onEntry,
              ),
          ],
        );
        final agenda = _Agenda(
          day: selectedDay,
          items: selected,
          onEntry: onEntry,
        );
        return wide
            ? Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 3, child: grid),
                  const SizedBox(width: 16),
                  Expanded(child: agenda),
                ],
              )
            : Column(children: [grid, const SizedBox(height: 12), agenda]);
      },
    );
  }

  static const _months = [
    'styczeń',
    'luty',
    'marzec',
    'kwiecień',
    'maj',
    'czerwiec',
    'lipiec',
    'sierpień',
    'wrzesień',
    'październik',
    'listopad',
    'grudzień',
  ];
}

class _WeekSegment {
  const _WeekSegment(this.entry, this.startColumn, this.endColumn, this.lane);
  final CalendarEntry entry;
  final int startColumn, endColumn, lane;
}

class _CalendarWeekRow extends StatelessWidget {
  const _CalendarWeekRow({
    required this.days,
    required this.month,
    required this.selectedDay,
    required this.items,
    required this.laneCapacity,
    required this.onSelectedDay,
    this.onEntry,
  });
  final List<DateTime> days;
  final DateTime month, selectedDay;
  final List<CalendarEntry> items;
  final int laneCapacity;
  final ValueChanged<DateTime> onSelectedDay;
  final ValueChanged<CalendarEntry>? onEntry;

  List<_WeekSegment> _segments() {
    final weekStart = DateUtils.dateOnly(days.first);
    final weekEnd = DateUtils.dateOnly(days.last);
    final candidates =
        items.where((entry) {
          final start = DateUtils.dateOnly(entry.start);
          final end = DateUtils.dateOnly(entry.end);
          return !end.isBefore(weekStart) && !start.isAfter(weekEnd);
        }).toList()..sort((a, b) {
          final aSpan = DateUtils.dateOnly(
            a.end,
          ).difference(DateUtils.dateOnly(a.start)).inDays;
          final bSpan = DateUtils.dateOnly(
            b.end,
          ).difference(DateUtils.dateOnly(b.start)).inDays;
          final bySpan = bSpan.compareTo(aSpan);
          if (bySpan != 0) return bySpan;
          final byStart = a.start.compareTo(b.start);
          if (byStart != 0) return byStart;
          final byEnd = a.end.compareTo(b.end);
          return byEnd != 0 ? byEnd : a.id.compareTo(b.id);
        });
    final laneEnds = <int>[];
    final result = <_WeekSegment>[];
    for (final entry in candidates) {
      final start = DateUtils.dateOnly(entry.start).isBefore(weekStart)
          ? weekStart
          : DateUtils.dateOnly(entry.start);
      final end = DateUtils.dateOnly(entry.end).isAfter(weekEnd)
          ? weekEnd
          : DateUtils.dateOnly(entry.end);
      final first = start.difference(weekStart).inDays;
      final last = end.difference(weekStart).inDays;
      var lane = 0;
      while (lane < laneEnds.length && laneEnds[lane] >= first) {
        lane++;
      }
      if (lane == laneEnds.length) {
        laneEnds.add(last);
      } else {
        laneEnds[lane] = last;
      }
      result.add(_WeekSegment(entry, first, last, lane));
    }
    return result;
  }

  @override
  Widget build(BuildContext context) {
    final segments = _segments();
    final hiddenPerDay = List<int>.filled(7, 0);
    for (final segment in segments.where(
      (segment) => segment.lane >= laneCapacity,
    )) {
      for (
        var column = segment.startColumn;
        column <= segment.endColumn;
        column++
      ) {
        hiddenPerDay[column]++;
      }
    }
    final rowHeight = 34.0 + laneCapacity * 20.0 + 18.0;
    return SizedBox(
      height: rowHeight,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final cellWidth = constraints.maxWidth / 7;
          return Stack(
            clipBehavior: Clip.none,
            children: [
              Row(
                children: [
                  for (var index = 0; index < days.length; index++)
                    Expanded(
                      child: InkWell(
                        key: Key(
                          'calendar-day-${days[index].toIso8601String().split('T').first}',
                        ),
                        onTap: () => onSelectedDay(days[index]),
                        child: Container(
                          margin: const EdgeInsets.all(1),
                          padding: const EdgeInsets.all(3),
                          decoration: BoxDecoration(
                            border: Border.all(
                              color:
                                  DateUtils.isSameDay(days[index], selectedDay)
                                  ? Theme.of(context).colorScheme.primary
                                  : Colors.grey.shade300,
                              width:
                                  DateUtils.isSameDay(days[index], selectedDay)
                                  ? 2
                                  : 1,
                            ),
                            color:
                                DateUtils.isSameDay(days[index], DateTime.now())
                                ? Theme.of(context).colorScheme.primaryContainer
                                : null,
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Align(
                            alignment: Alignment.topLeft,
                            child: Text(
                              '${days[index].day}',
                              style: TextStyle(
                                fontWeight:
                                    DateUtils.isSameDay(
                                      days[index],
                                      DateTime.now(),
                                    )
                                    ? FontWeight.bold
                                    : null,
                                color: days[index].month == month.month
                                    ? null
                                    : Colors.grey,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                ],
              ),
              for (final segment in segments.where(
                (segment) => segment.lane < laneCapacity,
              ))
                Positioned(
                  key: Key(
                    'calendar-segment-${segment.entry.kind}-${segment.entry.id}-${days.first.toIso8601String().split('T').first}',
                  ),
                  left: segment.startColumn * cellWidth + 3,
                  width:
                      (segment.endColumn - segment.startColumn + 1) *
                          cellWidth -
                      6,
                  top: 27 + segment.lane * 20,
                  height: 18,
                  child: Material(
                    color: CalendarPresentation.color(
                      segment.entry.type,
                    ).withValues(alpha: .22),
                    borderRadius: BorderRadius.circular(4),
                    child: InkWell(
                      borderRadius: BorderRadius.circular(4),
                      onTap: () => onEntry?.call(segment.entry),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 4,
                          vertical: 1,
                        ),
                        child: Text(
                          segment.entry.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              for (var index = 0; index < hiddenPerDay.length; index++)
                if (hiddenPerDay[index] > 0)
                  Positioned(
                    left: index * cellWidth + 3,
                    width: cellWidth - 6,
                    bottom: 2,
                    child: Text(
                      '+${hiddenPerDay[index]} więcej',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 9,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
            ],
          );
        },
      ),
    );
  }
}

class _Agenda extends StatelessWidget {
  const _Agenda({required this.day, required this.items, this.onEntry});
  final DateTime day;
  final List<CalendarEntry> items;
  final ValueChanged<CalendarEntry>? onEntry;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Plan dnia ${day.day}.${day.month}.${day.year}',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          if (items.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Text('Brak wpisów'),
            )
          else
            for (final e in items)
              ListTile(
                dense: true,
                leading: Icon(
                  CalendarPresentation.icon(e.type),
                  color: CalendarPresentation.color(e.type),
                ),
                title: Text(e.title),
                subtitle: Text(formatPolishDateRange(e.start, e.end)),
                onTap: () => onEntry?.call(e),
              ),
        ],
      ),
    ),
  );
}
