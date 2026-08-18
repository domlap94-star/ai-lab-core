import 'package:flutter/material.dart';
import '../../clients/presentation/searchable_client_picker.dart';
import '../domain/inspection.dart';

class InspectionFormDialog extends StatefulWidget {
  const InspectionFormDialog({
    super.key,
    this.inspection,
    this.clientId,
    this.clientName,
  });
  final Inspection? inspection;
  final int? clientId;
  final String? clientName;
  @override
  State<InspectionFormDialog> createState() => _InspectionFormDialogState();
}

class _InspectionFormDialogState extends State<InspectionFormDialog> {
  late int? _clientId = widget.inspection?.clientId ?? widget.clientId;
  bool _clientMissing = false;
  late final _scheduled = TextEditingController(
    text: widget.inspection?.scheduledAt?.toIso8601String() ?? '',
  );
  late final _started = TextEditingController(
    text: widget.inspection?.startedAt?.toIso8601String() ?? '',
  );
  late InspectionStatus _status =
      widget.inspection?.status ?? InspectionStatus.planned;
  final _form = GlobalKey<FormState>();
  @override
  void dispose() {
    for (final value in <TextEditingController>[_scheduled, _started]) {
      value.dispose();
    }
    super.dispose();
  }

  String? _date(String? value) =>
      value == null ||
          value.trim().isEmpty ||
          DateTime.tryParse(value.trim()) != null
      ? null
      : 'Nieprawidłowa data i czas';
  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(
      widget.inspection == null
          ? 'Dodaj wizję lokalną'
          : 'Edytuj wizję lokalną',
    ),
    content: SizedBox(
      width: 560,
      child: Form(
        key: _form,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              SearchableClientPicker(
                initialClientId: _clientId,
                initialClientName:
                    widget.inspection?.clientName ?? widget.clientName,
                onChanged: (selection) => setState(() {
                  _clientId = selection?.id;
                  _clientMissing = false;
                }),
              ),
              if (_clientMissing)
                const Align(
                  alignment: Alignment.centerLeft,
                  child: Padding(
                    padding: EdgeInsets.only(top: 6),
                    child: Text(
                      'Wybierz klienta.',
                      style: TextStyle(color: Colors.red),
                    ),
                  ),
                ),
              DropdownButtonFormField<InspectionStatus>(
                initialValue: _status,
                decoration: const InputDecoration(labelText: 'Status'),
                items: InspectionStatus.values
                    .map(
                      (value) => DropdownMenuItem(
                        value: value,
                        child: Text(value.label),
                      ),
                    )
                    .toList(),
                onChanged: (value) =>
                    setState(() => _status = value ?? _status),
              ),
              TextFormField(
                controller: _scheduled,
                decoration: const InputDecoration(
                  labelText: 'Termin (ISO, opcjonalnie)',
                ),
                validator: _date,
              ),
              TextFormField(
                controller: _started,
                decoration: const InputDecoration(
                  labelText: 'Rozpoczęto (ISO, opcjonalnie)',
                ),
                validator: _date,
              ),
            ],
          ),
        ),
      ),
    ),
    actions: <Widget>[
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Anuluj'),
      ),
      FilledButton(
        onPressed: () {
          if (!_form.currentState!.validate()) return;
          if (_clientId == null) {
            setState(() => _clientMissing = true);
            return;
          }
          Navigator.pop(context, <String, dynamic>{
            'client_id': _clientId,
            'status': _status.apiValue,
            'scheduled_at': _scheduled.text.trim().isEmpty
                ? null
                : _scheduled.text.trim(),
            'started_at': _started.text.trim().isEmpty
                ? null
                : _started.text.trim(),
          });
        },
        child: const Text('Zapisz'),
      ),
    ],
  );
}
