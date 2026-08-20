import 'package:flutter/material.dart';
import '../domain/work_item.dart';

class AbsenceFormDialog extends StatefulWidget {
  const AbsenceFormDialog({this.item, super.key});
  final AbsenceRequestItem? item;
  @override
  State<AbsenceFormDialog> createState() => _State();
}

class _State extends State<AbsenceFormDialog> {
  late DateTime start = widget.item?.start ?? DateTime.now();
  late DateTime end = widget.item?.end ?? DateTime.now();
  late String type = widget.item?.type ?? 'vacation';
  late final note = TextEditingController(text: widget.item?.note ?? '');
  @override
  void dispose() {
    note.dispose();
    super.dispose();
  }

  Future<DateTime> pick(DateTime v) async =>
      (await showDatePicker(
        context: context,
        firstDate: DateTime(2020),
        lastDate: DateTime(2100),
        initialDate: v,
      )) ??
      v;
  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(widget.item == null ? 'Dodaj absencję' : 'Edytuj absencję'),
    content: SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          DropdownButtonFormField(
            initialValue: type,
            decoration: const InputDecoration(labelText: 'Typ'),
            items:
                const {
                      'vacation': 'Urlop',
                      'day_off': 'Dzień wolny',
                      'sick_leave': 'Chorobowe',
                      'other': 'Inne',
                    }.entries
                    .map(
                      (e) =>
                          DropdownMenuItem(value: e.key, child: Text(e.value)),
                    )
                    .toList(),
            onChanged: (v) => setState(() => type = v ?? type),
          ),
          ListTile(
            title: const Text('Od'),
            subtitle: Text(start.toIso8601String().split('T').first),
            onTap: () async {
              final value = await pick(start);
              if (mounted) setState(() => start = value);
            },
          ),
          ListTile(
            title: const Text('Do'),
            subtitle: Text(end.toIso8601String().split('T').first),
            onTap: () async {
              final value = await pick(end);
              if (mounted) setState(() => end = value);
            },
          ),
          TextField(
            controller: note,
            maxLines: 3,
            decoration: const InputDecoration(labelText: 'Notatka opcjonalna'),
          ),
        ],
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Anuluj'),
      ),
      FilledButton(
        onPressed: end.isBefore(start)
            ? null
            : () => Navigator.pop(context, {
                'absence_type': type,
                'start_date': start.toIso8601String().split('T').first,
                'end_date': end.toIso8601String().split('T').first,
                'note': note.text.trim().isEmpty ? null : note.text.trim(),
                if (widget.item != null)
                  'expected_version': widget.item!.version,
              }),
        child: Text(widget.item == null ? 'Wyślij' : 'Zapisz'),
      ),
    ],
  );
}
