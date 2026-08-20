import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/widgets/app_shell.dart';
import '../../auth/application/auth_controller.dart';
import '../../clients/presentation/searchable_client_picker.dart';
import '../application/calendar_widget_snapshot.dart';
import '../application/tasks_providers.dart';
import '../domain/work_item.dart';
import 'absence_form_dialog.dart';
import 'operational_month_calendar.dart';
import 'work_item_form_dialog.dart';

class TasksPage extends ConsumerStatefulWidget {
  const TasksPage({
    this.initialDate,
    this.initialAbsenceId,
    this.openCreate = false,
    this.openAbsence = false,
    super.key,
  });
  final DateTime? initialDate;
  final int? initialAbsenceId;
  final bool openCreate, openAbsence;
  @override
  ConsumerState<TasksPage> createState() => _TasksPageState();
}

class _TasksPageState extends ConsumerState<TasksPage> {
  late DateTime month = DateTime(
    widget.initialDate?.year ?? DateTime.now().year,
    widget.initialDate?.month ?? DateTime.now().month,
  );
  late DateTime selected = widget.initialDate ?? DateTime.now();
  late bool listMode = widget.initialAbsenceId != null;
  bool _opened = false;
  String? typeFilter, statusFilter, priorityFilter;
  int? assigneeFilter, clientFilter;
  DateTime? dateFrom, dateTo;

  WorkItemListFilter get filter => WorkItemListFilter(
    type: typeFilter,
    status: statusFilter,
    priority: priorityFilter,
    assigneeUserId: assigneeFilter,
    clientId: clientFilter,
    dateFrom: dateFrom,
    dateTo: dateTo,
  );
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_opened) {
      _opened = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (widget.openCreate) _create();
        if (widget.openAbsence) _absence();
      });
    }
  }

  Future<void> _create() async {
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => const WorkItemFormDialog(),
    );
    if (data == null || !mounted) return;
    final session = ref.read(authControllerProvider).value?.session;
    if (session == null) return;
    await ref.read(workItemsApiProvider).create(session, data);
    await CalendarWidgetSnapshot.refreshCurrent(ref);
    ref.invalidate(calendarMonthProvider(month));
    ref.invalidate(workItemsProvider(null));
    ref.invalidate(filteredWorkItemsProvider);
  }

  Future<void> _absence() async {
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => const AbsenceFormDialog(),
    );
    if (data == null || !mounted) return;
    final session = ref.read(authControllerProvider).value?.session;
    if (session == null) return;
    await ref.read(workItemsApiProvider).createAbsence(session, data);
    await CalendarWidgetSnapshot.refreshCurrent(ref);
    ref.invalidate(calendarMonthProvider(month));
    ref.invalidate(absencesProvider);
  }

  @override
  Widget build(BuildContext context) {
    final calendar = ref.watch(calendarMonthProvider(month));
    final list = ref.watch(filteredWorkItemsProvider(filter));
    return Scaffold(
      appBar: AppBar(
        leading: AppShell.mobileNavigationLeading(context),
        title: const Text('Zadania'),
        actions: [
          IconButton(
            tooltip: 'Odśwież',
            onPressed: () {
              ref.invalidate(calendarMonthProvider(month));
              ref.invalidate(workItemsProvider(null));
              ref.invalidate(filteredWorkItemsProvider(filter));
              ref.invalidate(absencesProvider);
            },
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _create,
        icon: const Icon(Icons.add),
        label: const Text('Dodaj zadanie'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Wrap(
              spacing: 8,
              children: [
                SegmentedButton<bool>(
                  segments: const [
                    ButtonSegment(
                      value: false,
                      label: Text('Miesiąc'),
                      icon: Icon(Icons.calendar_month),
                    ),
                    ButtonSegment(
                      value: true,
                      label: Text('Lista'),
                      icon: Icon(Icons.list),
                    ),
                  ],
                  selected: {listMode},
                  onSelectionChanged: (v) => setState(() => listMode = v.first),
                ),
                OutlinedButton.icon(
                  onPressed: _absence,
                  icon: const Icon(Icons.beach_access),
                  label: const Text('Dodaj absencję'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (listMode) ...[
              _TaskFilters(
                type: typeFilter,
                status: statusFilter,
                priority: priorityFilter,
                assigneeUserId: assigneeFilter,
                clientId: clientFilter,
                dateFrom: dateFrom,
                dateTo: dateTo,
                onChanged: (value) => setState(() {
                  typeFilter = value.type;
                  statusFilter = value.status;
                  priorityFilter = value.priority;
                  assigneeFilter = value.assigneeUserId;
                  clientFilter = value.clientId;
                  dateFrom = value.dateFrom;
                  dateTo = value.dateTo;
                }),
              ),
              const SizedBox(height: 12),
            ],
            Expanded(
              child: listMode
                  ? list.when(
                      data: (items) => ListView.builder(
                        itemCount: items.length + 1,
                        itemBuilder: (_, i) => i == 0
                            ? _AbsencePanel(
                                selectedAbsenceId: widget.initialAbsenceId,
                              )
                            : _WorkTile(items[i - 1]),
                      ),
                      loading: () =>
                          const Center(child: CircularProgressIndicator()),
                      error: (e, _) =>
                          Center(child: Text('Nie udało się pobrać zadań: $e')),
                    )
                  : calendar.when(
                      data: (data) {
                        CalendarWidgetSnapshot.publish(data);
                        return SingleChildScrollView(
                          child: Column(
                            children: [
                              if (data.truncated)
                                const MaterialBanner(
                                  content: Text(
                                    'Miesiąc zawiera więcej pozycji niż bezpieczny limit widoku. Zawęź zakres w liście.',
                                  ),
                                  actions: [SizedBox.shrink()],
                                ),
                              OperationalMonthCalendar(
                                month: month,
                                items: data.items,
                                selectedDay: selected,
                                onSelectedDay: (v) =>
                                    setState(() => selected = v),
                                onPrevious: () => setState(
                                  () => month = DateTime(
                                    month.year,
                                    month.month - 1,
                                  ),
                                ),
                                onNext: () => setState(
                                  () => month = DateTime(
                                    month.year,
                                    month.month + 1,
                                  ),
                                ),
                                onToday: () => setState(() {
                                  selected = DateTime.now();
                                  month = DateTime(
                                    selected.year,
                                    selected.month,
                                  );
                                }),
                                onEntry: (e) => context.push(
                                  e.kind == 'work_item'
                                      ? '/tasks/${e.id}'
                                      : '/tasks?absence_id=${e.id}',
                                ),
                              ),
                            ],
                          ),
                        );
                      },
                      loading: () =>
                          const Center(child: CircularProgressIndicator()),
                      error: (e, _) => Center(
                        child: Text('Nie udało się pobrać kalendarza: $e'),
                      ),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _WorkTile extends StatelessWidget {
  const _WorkTile(this.item);
  final WorkItem item;
  @override
  Widget build(BuildContext context) => Card(
    child: ListTile(
      leading: Icon(
        CalendarPresentation.icon(item.type.name),
        color: CalendarPresentation.color(item.type.name),
      ),
      title: Text(item.title),
      subtitle: Text(
        '${item.type.label} • ${item.status.name} • ${item.priority.name}',
      ),
      trailing: const Icon(Icons.chevron_right),
      onTap: () => context.push('/tasks/${item.id}'),
    ),
  );
}

class _TaskFilters extends ConsumerWidget {
  const _TaskFilters({
    required this.type,
    required this.status,
    required this.priority,
    required this.assigneeUserId,
    required this.clientId,
    required this.dateFrom,
    required this.dateTo,
    required this.onChanged,
  });

  final String? type, status, priority;
  final int? assigneeUserId, clientId;
  final DateTime? dateFrom, dateTo;
  final ValueChanged<WorkItemListFilter> onChanged;

  WorkItemListFilter value({
    String? type,
    String? status,
    String? priority,
    int? assigneeUserId,
    int? clientId,
    DateTime? dateFrom,
    DateTime? dateTo,
  }) => WorkItemListFilter(
    type: type ?? this.type,
    status: status ?? this.status,
    priority: priority ?? this.priority,
    assigneeUserId: assigneeUserId ?? this.assigneeUserId,
    clientId: clientId ?? this.clientId,
    dateFrom: dateFrom ?? this.dateFrom,
    dateTo: dateTo ?? this.dateTo,
  );

  Future<DateTime?> pick(BuildContext context, DateTime? initial) async {
    final date = await showDatePicker(
      context: context,
      firstDate: DateTime(2020),
      lastDate: DateTime(2100),
      initialDate: initial ?? DateTime.now(),
    );
    return date;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final assignees = ref.watch(workAssigneesProvider);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Wrap(
          spacing: 10,
          runSpacing: 10,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            DropdownButton<String?>(
              value: type,
              hint: const Text('Typ'),
              items: [
                const DropdownMenuItem(
                  value: null,
                  child: Text('Wszystkie typy'),
                ),
                ...WorkItemType.values.map(
                  (item) => DropdownMenuItem(
                    value: item.name,
                    child: Text(item.label),
                  ),
                ),
              ],
              onChanged: (selected) => onChanged(
                WorkItemListFilter(
                  type: selected,
                  status: status,
                  priority: priority,
                  assigneeUserId: assigneeUserId,
                  clientId: clientId,
                  dateFrom: dateFrom,
                  dateTo: dateTo,
                ),
              ),
            ),
            DropdownButton<String?>(
              value: status,
              hint: const Text('Status'),
              items: const [
                DropdownMenuItem(value: null, child: Text('Wszystkie statusy')),
                DropdownMenuItem(value: 'todo', child: Text('Do zrobienia')),
                DropdownMenuItem(value: 'in_progress', child: Text('W toku')),
                DropdownMenuItem(value: 'completed', child: Text('Zakończone')),
                DropdownMenuItem(value: 'cancelled', child: Text('Anulowane')),
              ],
              onChanged: (selected) => onChanged(
                WorkItemListFilter(
                  type: type,
                  status: selected,
                  priority: priority,
                  assigneeUserId: assigneeUserId,
                  clientId: clientId,
                  dateFrom: dateFrom,
                  dateTo: dateTo,
                ),
              ),
            ),
            DropdownButton<String?>(
              value: priority,
              hint: const Text('Priorytet'),
              items: const [
                DropdownMenuItem(
                  value: null,
                  child: Text('Wszystkie priorytety'),
                ),
                DropdownMenuItem(value: 'low', child: Text('Niski')),
                DropdownMenuItem(value: 'normal', child: Text('Normalny')),
                DropdownMenuItem(value: 'high', child: Text('Wysoki')),
                DropdownMenuItem(value: 'urgent', child: Text('Pilny')),
              ],
              onChanged: (selected) => onChanged(
                WorkItemListFilter(
                  type: type,
                  status: status,
                  priority: selected,
                  assigneeUserId: assigneeUserId,
                  clientId: clientId,
                  dateFrom: dateFrom,
                  dateTo: dateTo,
                ),
              ),
            ),
            assignees.when(
              data: (users) => DropdownButton<int?>(
                value: assigneeUserId,
                hint: const Text('Przypisana osoba'),
                items: [
                  const DropdownMenuItem(value: null, child: Text('Wszyscy')),
                  ...users.map(
                    (user) => DropdownMenuItem(
                      value: user.id,
                      child: Text(user.username),
                    ),
                  ),
                ],
                onChanged: (selected) => onChanged(
                  WorkItemListFilter(
                    type: type,
                    status: status,
                    priority: priority,
                    assigneeUserId: selected,
                    clientId: clientId,
                    dateFrom: dateFrom,
                    dateTo: dateTo,
                  ),
                ),
              ),
              loading: () => const SizedBox.square(
                dimension: 24,
                child: CircularProgressIndicator(),
              ),
              error: (_, _) => const Text('Brak listy osób'),
            ),
            SizedBox(
              width: 260,
              child: SearchableClientPicker(
                key: ValueKey('task-client-filter-$clientId'),
                initialClientId: clientId,
                onChanged: (selected) => onChanged(
                  WorkItemListFilter(
                    type: type,
                    status: status,
                    priority: priority,
                    assigneeUserId: assigneeUserId,
                    clientId: selected?.id,
                    dateFrom: dateFrom,
                    dateTo: dateTo,
                  ),
                ),
              ),
            ),
            TextButton(
              onPressed: () async {
                final selected = await pick(context, dateFrom);
                if (selected != null) onChanged(value(dateFrom: selected));
              },
              child: Text(
                dateFrom == null
                    ? 'Od daty'
                    : 'Od ${dateFrom!.toIso8601String().split('T').first}',
              ),
            ),
            TextButton(
              onPressed: () async {
                final selected = await pick(context, dateTo);
                if (selected != null) {
                  onChanged(
                    value(
                      dateTo: DateTime(
                        selected.year,
                        selected.month,
                        selected.day,
                        23,
                        59,
                        59,
                      ),
                    ),
                  );
                }
              },
              child: Text(
                dateTo == null
                    ? 'Do daty'
                    : 'Do ${dateTo!.toIso8601String().split('T').first}',
              ),
            ),
            TextButton.icon(
              onPressed: () => onChanged(const WorkItemListFilter()),
              icon: const Icon(Icons.clear),
              label: const Text('Wyczyść'),
            ),
          ],
        ),
      ),
    );
  }
}

class _AbsencePanel extends ConsumerWidget {
  const _AbsencePanel({this.selectedAbsenceId});

  final int? selectedAbsenceId;

  Future<void> action(
    WidgetRef ref,
    AbsenceRequestItem item,
    String action,
  ) async {
    final session = ref.read(authControllerProvider).value?.session;
    if (session == null) {
      return;
    }
    final api = ref.read(workItemsApiProvider);
    if (action == 'approve') {
      await api.reviewAbsence(session, item.id, item.version, approve: true);
    }
    if (action == 'reject') {
      await api.reviewAbsence(session, item.id, item.version, approve: false);
    }
    if (action == 'cancel') {
      await api.cancelAbsence(session, item.id, item.version);
    }
    ref.invalidate(absencesProvider);
    ref.invalidate(calendarMonthProvider);
    await CalendarWidgetSnapshot.refreshCurrent(ref);
  }

  Future<void> edit(
    BuildContext context,
    WidgetRef ref,
    AbsenceRequestItem item,
  ) async {
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => AbsenceFormDialog(item: item),
    );
    if (data == null || !context.mounted) return;
    final session = ref.read(authControllerProvider).value?.session;
    if (session == null) return;
    await ref.read(workItemsApiProvider).updateAbsence(session, item.id, data);
    ref.invalidate(absencesProvider);
    ref.invalidate(calendarMonthProvider);
    await CalendarWidgetSnapshot.refreshCurrent(ref);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final value = ref.watch(absencesProvider);
    final auth = ref.watch(authControllerProvider).value;
    final isAdmin = auth?.user?.role == 'Administrator';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              isAdmin ? 'Wnioski o absencję' : 'Moje absencje',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            value.when(
              data: (items) => items.isEmpty
                  ? const Padding(
                      padding: EdgeInsets.all(12),
                      child: Text('Brak wniosków.'),
                    )
                  : Column(
                      children: [
                        for (final item in items)
                          ListTile(
                            key: Key('absence-request-${item.id}'),
                            tileColor: item.id == selectedAbsenceId
                                ? Theme.of(context).colorScheme.primaryContainer
                                : null,
                            leading: const Icon(Icons.beach_access),
                            title: Text(
                              '${item.type} • ${item.start.toIso8601String().split('T').first} – ${item.end.toIso8601String().split('T').first}',
                            ),
                            subtitle: Text(item.status),
                            trailing: item.status != 'requested'
                                ? null
                                : Wrap(
                                    children: [
                                      if (item.requesterUserId ==
                                          auth?.user?.id)
                                        IconButton(
                                          tooltip: 'Edytuj wniosek',
                                          onPressed: () =>
                                              edit(context, ref, item),
                                          icon: const Icon(Icons.edit),
                                        ),
                                      if (isAdmin &&
                                          item.requesterUserId !=
                                              auth?.user?.id)
                                        IconButton(
                                          tooltip: 'Zatwierdź',
                                          onPressed: () =>
                                              action(ref, item, 'approve'),
                                          icon: const Icon(Icons.check),
                                        ),
                                      if (isAdmin &&
                                          item.requesterUserId !=
                                              auth?.user?.id)
                                        IconButton(
                                          tooltip: 'Odrzuć',
                                          onPressed: () =>
                                              action(ref, item, 'reject'),
                                          icon: const Icon(Icons.close),
                                        ),
                                      if (!isAdmin ||
                                          item.requesterUserId ==
                                              auth?.user?.id)
                                        IconButton(
                                          tooltip: 'Anuluj wniosek',
                                          onPressed: () =>
                                              action(ref, item, 'cancel'),
                                          icon: const Icon(
                                            Icons.cancel_outlined,
                                          ),
                                        ),
                                    ],
                                  ),
                          ),
                      ],
                    ),
              loading: () => const LinearProgressIndicator(),
              error: (error, _) =>
                  Text('Nie udało się pobrać absencji: $error'),
            ),
          ],
        ),
      ),
    );
  }
}
