import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/formatters/polish_date_time.dart';
import '../../clients/presentation/searchable_client_picker.dart';
import '../application/tasks_providers.dart';
import '../domain/work_item.dart';

class WorkItemFormDialog extends ConsumerStatefulWidget {
  const WorkItemFormDialog({this.item, this.initialClientId, super.key});
  final WorkItem? item;
  final int? initialClientId;
  @override
  ConsumerState<WorkItemFormDialog> createState() => _State();
}

class _State extends ConsumerState<WorkItemFormDialog> {
  final form = GlobalKey<FormState>();
  late final title = TextEditingController(text: widget.item?.title ?? '');
  late final description = TextEditingController(
    text: widget.item?.description ?? '',
  );
  late final party = TextEditingController(text: widget.item?.partyName ?? '');
  late WorkItemType type = widget.item?.type ?? WorkItemType.task;
  late WorkItemPriority priority =
      widget.item?.priority ?? WorkItemPriority.normal;
  late WorkItemStatus status = widget.item?.status ?? WorkItemStatus.todo;
  late int? clientId = widget.initialClientId ?? widget.item?.clientId;
  late int? assigneeId = widget.item?.assigneeUserId;
  late bool allDay = widget.item?.allDay ?? false;
  String? timeError;
  DateTime? start, due;
  @override
  void initState() {
    super.initState();
    start = widget.item?.startAt;
    due = widget.item?.dueAt;
  }

  @override
  void dispose() {
    title.dispose();
    description.dispose();
    party.dispose();
    super.dispose();
  }

  Future<DateTime?> pick(DateTime? current) async {
    final d = await showDatePicker(
      context: context,
      firstDate: DateTime(2020),
      lastDate: DateTime(2100),
      initialDate: current ?? DateTime.now(),
      locale: const Locale('pl', 'PL'),
    );
    if (d == null) return current;
    if (allDay) return DateTime(d.year, d.month, d.day);
    if (!mounted) return current;
    final selectedTime = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(
        current ?? DateTime(d.year, d.month, d.day, 9),
      ),
    );
    if (selectedTime == null) return current;
    return DateTime(
      d.year,
      d.month,
      d.day,
      selectedTime.hour,
      selectedTime.minute,
    );
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(widget.item == null ? 'Dodaj zadanie' : 'Edytuj zadanie'),
    content: SizedBox(
      width: 600,
      child: Form(
        key: form,
        child: SingleChildScrollView(
          child: Column(
            children: [
              DropdownButtonFormField(
                initialValue: type,
                decoration: const InputDecoration(labelText: 'Typ'),
                items: WorkItemType.values
                    .map(
                      (v) => DropdownMenuItem(value: v, child: Text(v.label)),
                    )
                    .toList(),
                onChanged: (v) => setState(() => type = v ?? type),
              ),
              TextFormField(
                controller: title,
                decoration: const InputDecoration(labelText: 'Tytuł'),
                validator: (v) =>
                    v == null || v.trim().isEmpty ? 'Podaj tytuł' : null,
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Cały dzień'),
                value: allDay,
                onChanged: (value) => setState(() => allDay = value),
              ),
              TextFormField(
                controller: description,
                maxLines: 3,
                decoration: const InputDecoration(labelText: 'Opis'),
              ),
              DropdownButtonFormField(
                initialValue: priority,
                decoration: const InputDecoration(labelText: 'Priorytet'),
                items: WorkItemPriority.values
                    .map((v) => DropdownMenuItem(value: v, child: Text(v.name)))
                    .toList(),
                onChanged: (v) => setState(() => priority = v ?? priority),
              ),
              DropdownButtonFormField<WorkItemStatus>(
                initialValue: status,
                decoration: const InputDecoration(labelText: 'Status'),
                items: WorkItemStatus.values
                    .map(
                      (value) => DropdownMenuItem(
                        value: value,
                        child: Text(value.name),
                      ),
                    )
                    .toList(),
                onChanged: (value) => setState(() => status = value ?? status),
              ),
              ref
                  .watch(workAssigneesProvider)
                  .when(
                    data: (users) => DropdownButtonFormField<int?>(
                      initialValue: assigneeId,
                      decoration: const InputDecoration(
                        labelText: 'Przypisana osoba',
                      ),
                      items: [
                        const DropdownMenuItem<int?>(
                          value: null,
                          child: Text('Nieprzypisane'),
                        ),
                        ...users.map(
                          (user) => DropdownMenuItem<int?>(
                            value: user.id,
                            child: Text(user.username),
                          ),
                        ),
                      ],
                      onChanged: (value) => assigneeId = value,
                    ),
                    loading: () => const LinearProgressIndicator(),
                    error: (_, _) =>
                        const Text('Nie udało się pobrać użytkowników.'),
                  ),
              SearchableClientPicker(
                initialClientId: clientId,
                initialClientName: widget.item?.clientName,
                onChanged: (v) => setState(() => clientId = v?.id),
              ),
              if (type == WorkItemType.realization && clientId == null)
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    'Realizacja musi być przypisana do klienta.',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              TextFormField(
                controller: party,
                decoration: const InputDecoration(
                  labelText: 'Strona / nazwa opcjonalna',
                ),
              ),
              Wrap(
                spacing: 8,
                children: [
                  TextButton(
                    onPressed: () async {
                      final value = await pick(start);
                      if (mounted) setState(() => start = value);
                    },
                    child: Text(
                      start == null
                          ? 'Początek'
                          : 'Od ${formatPolishDate(start!)}',
                    ),
                  ),
                  TextButton(
                    onPressed: () async {
                      final value = await pick(due);
                      if (mounted) setState(() => due = value);
                    },
                    child: Text(
                      due == null ? 'Termin' : 'Do ${formatPolishDate(due!)}',
                    ),
                  ),
                ],
              ),
              if (timeError != null)
                Text(
                  timeError!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
            ],
          ),
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Anuluj'),
      ),
      FilledButton(
        onPressed: () {
          if (!form.currentState!.validate()) return;
          if (type == WorkItemType.realization && clientId == null) {
            setState(
              () => timeError = 'Realizacja musi być przypisana do klienta.',
            );
            return;
          }
          final invalid = due != null && start != null && due!.isBefore(start!);
          if (invalid ||
              (type == WorkItemType.event && start == null) ||
              (type == WorkItemType.reminder && due == null) ||
              (allDay && (start == null || due == null))) {
            setState(() {
              timeError = invalid
                  ? 'Termin nie może poprzedzać początku.'
                  : allDay
                  ? 'Dla całego dnia wybierz początek i koniec.'
                  : type == WorkItemType.event
                  ? 'Wydarzenie wymaga początku.'
                  : 'Przypomnienie wymaga terminu.';
            });
            return;
          }
          Navigator.pop(context, {
            'item_type': type.name,
            'title': title.text.trim(),
            'description': description.text.trim().isEmpty
                ? null
                : description.text.trim(),
            'start_at': start?.toUtc().toIso8601String(),
            'due_at': due?.toUtc().toIso8601String(),
            'all_day': allDay,
            'timezone_name': allDay ? 'Europe/Warsaw' : null,
            'status': status.name.replaceAll('inProgress', 'in_progress'),
            'priority': priority.name,
            'client_id': clientId,
            'assignee_user_id': assigneeId,
            'party_name': party.text.trim().isEmpty ? null : party.text.trim(),
            if (widget.item != null) 'expected_version': widget.item!.version,
          });
        },
        child: const Text('Zapisz'),
      ),
    ],
  );
}
