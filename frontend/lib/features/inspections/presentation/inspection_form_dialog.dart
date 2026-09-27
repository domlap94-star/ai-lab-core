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
  late DateTime? _scheduledDate =
      widget.inspection?.scheduledDate ?? _todayDate();
  late final _scheduled = TextEditingController(
    text: _scheduledDate == null ? '' : inspectionDateDisplay(_scheduledDate!),
  );
  late InspectionStatus _status =
      widget.inspection?.status ?? InspectionStatus.planned;
  final _form = GlobalKey<FormState>();

  static DateTime _todayDate() {
    final now = DateTime.now();
    return DateTime(now.year, now.month, now.day);
  }

  @override
  void dispose() {
    _scheduled.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _scheduledDate ?? DateTime(now.year, now.month, now.day),
      firstDate: DateTime(2000),
      lastDate: DateTime(2100),
    );
    if (picked == null || !mounted) return;
    setState(() {
      _scheduledDate = DateTime(picked.year, picked.month, picked.day);
      _scheduled.text = inspectionDateDisplay(_scheduledDate!);
    });
  }

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
                key: const Key('inspection-scheduled-date'),
                controller: _scheduled,
                readOnly: true,
                onTap: _pickDate,
                decoration: InputDecoration(
                  labelText: 'Termin wizji *',
                  suffixIcon: IconButton(
                    key: const Key('inspection-scheduled-date-picker'),
                    onPressed: _pickDate,
                    icon: const Icon(Icons.calendar_month),
                  ),
                ),
                validator: (_) => _scheduledDate == null
                    ? 'Wybierz termin wizji lokalnej.'
                    : null,
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
            'scheduled_date': inspectionDateApi(_scheduledDate!),
          });
        },
        child: const Text('Zapisz'),
      ),
    ],
  );
}
