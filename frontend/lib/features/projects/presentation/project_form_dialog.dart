import 'package:flutter/material.dart';
import '../../clients/presentation/searchable_client_picker.dart';
import '../domain/project.dart';

class ProjectFormDialog extends StatefulWidget {
  const ProjectFormDialog({super.key, this.project, this.clientId});
  final Project? project;
  final int? clientId;
  @override
  State<ProjectFormDialog> createState() => _ProjectFormDialogState();
}

class _ProjectFormDialogState extends State<ProjectFormDialog> {
  late int? _clientId = widget.clientId ?? widget.project?.clientId;
  late final _name = TextEditingController(text: widget.project?.name ?? '');
  late final _description = TextEditingController(
    text: widget.project?.description ?? '',
  );
  late final _street = TextEditingController(
    text: widget.project?.street ?? '',
  );
  late final _building = TextEditingController(
    text: widget.project?.buildingNumber ?? '',
  );
  late final _postal = TextEditingController(
    text: widget.project?.postalCode ?? '',
  );
  late final _city = TextEditingController(text: widget.project?.city ?? '');
  late final _unit = TextEditingController(
    text: widget.project?.unitNumber ?? '',
  );
  late final _start = TextEditingController(
    text: widget.project?.startDate?.toIso8601String().split('T').first ?? '',
  );
  late final _end = TextEditingController(
    text: widget.project?.endDate?.toIso8601String().split('T').first ?? '',
  );
  late ProjectStatus _status = widget.project?.status ?? ProjectStatus.planned;
  final _form = GlobalKey<FormState>();
  @override
  void dispose() {
    for (final value in <TextEditingController>[
      _name,
      _description,
      _street,
      _building,
      _unit,
      _postal,
      _city,
      _start,
      _end,
    ]) {
      value.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(
      widget.project == null ? 'Dodaj realizację' : 'Edytuj realizację',
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
                enabled: widget.clientId == null && widget.project == null,
                initialClientId: _clientId,
                initialClientName: widget.project?.clientName,
                onChanged: (selection) =>
                    setState(() => _clientId = selection?.id),
              ),
              TextFormField(
                controller: _name,
                decoration: const InputDecoration(
                  labelText: 'Nazwa realizacji',
                ),
                validator: (value) => value == null || value.trim().isEmpty
                    ? 'Podaj nazwę'
                    : null,
              ),
              DropdownButtonFormField<ProjectStatus>(
                initialValue: _status,
                decoration: const InputDecoration(labelText: 'Status'),
                items: ProjectStatus.values
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
                controller: _description,
                maxLines: 3,
                decoration: const InputDecoration(labelText: 'Opis / notatki'),
              ),
              TextFormField(
                controller: _start,
                decoration: const InputDecoration(
                  labelText: 'Data rozpoczęcia (RRRR-MM-DD)',
                ),
                validator: _dateValidator,
              ),
              TextFormField(
                controller: _end,
                decoration: const InputDecoration(
                  labelText: 'Data zakończenia (RRRR-MM-DD)',
                ),
                validator: _dateValidator,
              ),
              const SizedBox(height: 8),
              const Align(
                alignment: Alignment.centerLeft,
                child: Text('Lokalizacja realizacji'),
              ),
              TextFormField(
                controller: _street,
                decoration: const InputDecoration(labelText: 'Ulica'),
              ),
              TextFormField(
                controller: _building,
                decoration: const InputDecoration(labelText: 'Numer budynku'),
              ),
              TextFormField(
                controller: _unit,
                decoration: const InputDecoration(labelText: 'Numer lokalu'),
              ),
              TextFormField(
                controller: _postal,
                decoration: const InputDecoration(labelText: 'Kod pocztowy'),
              ),
              TextFormField(
                controller: _city,
                decoration: const InputDecoration(labelText: 'Miasto'),
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
          if (_form.currentState!.validate()) {
            if (_clientId == null) {
              ScaffoldMessenger.of(
                context,
              ).showSnackBar(const SnackBar(content: Text('Wybierz klienta.')));
              return;
            }
            Navigator.pop(context, <String, dynamic>{
              'client_id': _clientId,
              'name': _name.text.trim(),
              'description': _description.text.trim().isEmpty
                  ? null
                  : _description.text.trim(),
              'status': _status.name,
              'start_date': _start.text.trim().isEmpty
                  ? null
                  : _start.text.trim(),
              'end_date': _end.text.trim().isEmpty ? null : _end.text.trim(),
              'street': _street.text.trim().isEmpty
                  ? null
                  : _street.text.trim(),
              'building_number': _building.text.trim().isEmpty
                  ? null
                  : _building.text.trim(),
              'unit_number': _unit.text.trim().isEmpty
                  ? null
                  : _unit.text.trim(),
              'postal_code': _postal.text.trim().isEmpty
                  ? null
                  : _postal.text.trim(),
              'city': _city.text.trim().isEmpty ? null : _city.text.trim(),
              'country_code': 'PL',
            });
          }
        },
        child: const Text('Zapisz'),
      ),
    ],
  );

  String? _dateValidator(String? value) {
    if (value == null || value.trim().isEmpty) return null;
    return DateTime.tryParse(value.trim()) == null
        ? 'Nieprawidłowa data'
        : null;
  }
}
