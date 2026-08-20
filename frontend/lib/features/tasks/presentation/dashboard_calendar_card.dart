import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../application/tasks_providers.dart';
import 'operational_month_calendar.dart';

class DashboardCalendarCard extends ConsumerStatefulWidget {
  const DashboardCalendarCard({super.key});
  @override
  ConsumerState<DashboardCalendarCard> createState() => _State();
}

class _State extends ConsumerState<DashboardCalendarCard> {
  DateTime month = DateTime(DateTime.now().year, DateTime.now().month),
      selected = DateTime.now();
  @override
  Widget build(BuildContext context) {
    final value = ref.watch(calendarMonthProvider(month));
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Kalendarz i zadania',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                TextButton(
                  onPressed: () => context.push('/tasks'),
                  child: const Text('Zobacz wszystkie'),
                ),
              ],
            ),
            const SizedBox(height: 8),
            value.when(
              data: (d) => Column(
                children: [
                  if (d.truncated)
                    const Text(
                      'Widok miesiąca jest ograniczony — otwórz Zadania, aby zawęzić listę.',
                    ),
                  OperationalMonthCalendar(
                    month: month,
                    items: d.items,
                    selectedDay: selected,
                    onSelectedDay: (v) => setState(() => selected = v),
                    onPrevious: () => setState(
                      () => month = DateTime(month.year, month.month - 1),
                    ),
                    onNext: () => setState(
                      () => month = DateTime(month.year, month.month + 1),
                    ),
                    onToday: () => setState(() {
                      selected = DateTime.now();
                      month = DateTime(selected.year, selected.month);
                    }),
                    onEntry: (e) => context.push(
                      e.kind == 'work_item'
                          ? '/tasks/${e.id}'
                          : '/tasks?absence_id=${e.id}',
                    ),
                  ),
                ],
              ),
              loading: () => const Padding(
                padding: EdgeInsets.all(40),
                child: CircularProgressIndicator(),
              ),
              error: (e, _) => Text('Kalendarz niedostępny: $e'),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [
                FilledButton.icon(
                  onPressed: () => context.push('/tasks?create=1'),
                  icon: const Icon(Icons.add_task),
                  label: const Text('Dodaj zadanie'),
                ),
                OutlinedButton.icon(
                  onPressed: () => context.push('/tasks?absence=1'),
                  icon: const Icon(Icons.beach_access),
                  label: const Text('Dodaj absencję'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
