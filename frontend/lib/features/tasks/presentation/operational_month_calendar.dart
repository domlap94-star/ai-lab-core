import 'package:flutter/material.dart';
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
        final dayCellAspectRatio = c.maxWidth >= 850
            ? .95
            : c.maxWidth >= 600
            ? .72
            : .58;
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
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 7,
                childAspectRatio: dayCellAspectRatio,
              ),
              itemCount: 42,
              itemBuilder: (context, i) {
                final day = days[i];
                final dayItems = items.where((e) => e.covers(day)).toList();
                final today = DateUtils.isSameDay(day, DateTime.now());
                final isSelected = DateUtils.isSameDay(day, selectedDay);
                return InkWell(
                  key: Key(
                    'calendar-day-${day.toIso8601String().split('T').first}',
                  ),
                  onTap: () => onSelectedDay(day),
                  child: Container(
                    margin: const EdgeInsets.all(1),
                    padding: const EdgeInsets.all(3),
                    decoration: BoxDecoration(
                      border: Border.all(
                        color: isSelected
                            ? Theme.of(context).colorScheme.primary
                            : Colors.grey.shade300,
                        width: isSelected ? 2 : 1,
                      ),
                      color: today
                          ? Theme.of(context).colorScheme.primaryContainer
                          : null,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          '${day.day}',
                          style: TextStyle(
                            fontWeight: today ? FontWeight.bold : null,
                            color: day.month == month.month
                                ? null
                                : Colors.grey,
                          ),
                        ),
                        for (final e in dayItems.take(density))
                          Container(
                            margin: const EdgeInsets.only(top: 2),
                            padding: const EdgeInsets.symmetric(
                              horizontal: 3,
                              vertical: 1,
                            ),
                            decoration: BoxDecoration(
                              color: CalendarPresentation.color(
                                e.type,
                              ).withValues(alpha: .16),
                              borderRadius: BorderRadius.circular(3),
                            ),
                            child: Text(
                              e.title,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 10),
                            ),
                          ),
                        if (dayItems.length > density)
                          Text(
                            '+${dayItems.length - density} więcej',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 9,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                      ],
                    ),
                  ),
                );
              },
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
                subtitle: Text(
                  '${CalendarPresentation.label(e.type)} • ${e.status}',
                ),
                onTap: () => onEntry?.call(e),
              ),
        ],
      ),
    ),
  );
}
