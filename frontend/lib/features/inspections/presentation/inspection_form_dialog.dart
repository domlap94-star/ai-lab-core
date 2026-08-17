import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../clients/presentation/searchable_client_picker.dart';
import '../../projects/application/projects_providers.dart';
import '../../projects/domain/project.dart';
import '../domain/inspection.dart';

class InspectionFormDialog extends StatefulWidget {
  const InspectionFormDialog({
    super.key,
    this.inspection,
    this.project,
    this.clientId,
    this.clientName,
  });
  final Inspection? inspection;
  final Project? project;
  final int? clientId;
  final String? clientName;
  @override
  State<InspectionFormDialog> createState() => _InspectionFormDialogState();
}

class _InspectionFormDialogState extends State<InspectionFormDialog> {
  late int? _projectId = widget.project?.id ?? widget.inspection?.projectId;
  late int? _clientId =
      widget.project?.clientId ??
      widget.inspection?.clientId ??
      widget.clientId;
  late final _title = TextEditingController(
    text: widget.inspection?.title ?? '',
  );
  late final _scheduled = TextEditingController(
    text: widget.inspection?.scheduledAt?.toIso8601String() ?? '',
  );
  late final _started = TextEditingController(
    text: widget.inspection?.startedAt?.toIso8601String() ?? '',
  );
  late final _notes = TextEditingController(
    text: widget.inspection?.notes ?? '',
  );
  late final _latitude = TextEditingController(
    text: widget.inspection?.latitude?.toString() ?? '',
  );
  late final _longitude = TextEditingController(
    text: widget.inspection?.longitude?.toString() ?? '',
  );
  late final _accuracy = TextEditingController(
    text: widget.inspection?.locationAccuracyM?.toString() ?? '',
  );
  late InspectionStatus _status =
      widget.inspection?.status ?? InspectionStatus.planned;
  final _form = GlobalKey<FormState>();
  @override
  void dispose() {
    for (final value in <TextEditingController>[
      _title,
      _scheduled,
      _started,
      _notes,
      _latitude,
      _longitude,
      _accuracy,
    ]) {
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
  void _useProjectLocation() {
    final project = widget.project;
    if (project?.latitude == null || project?.longitude == null) return;
    setState(() {
      _latitude.text = project!.latitude.toString();
      _longitude.text = project.longitude.toString();
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
              if (widget.project != null)
                InputDecorator(
                  decoration: const InputDecoration(
                    labelText: 'Klient / realizacja',
                  ),
                  child: Text(
                    '${widget.project!.clientName} • ${widget.project!.name}',
                  ),
                )
              else
                _ClientProjectSelection(
                  initialClientId: _clientId,
                  initialClientName:
                      widget.inspection?.clientName ?? widget.clientName,
                  initialProjectId: _projectId,
                  onChanged: (clientId, projectId) {
                    _clientId = clientId;
                    _projectId = projectId;
                  },
                ),
              TextFormField(
                controller: _title,
                decoration: const InputDecoration(labelText: 'Nazwa wizji'),
                validator: (value) => value == null || value.trim().isEmpty
                    ? 'Podaj nazwę'
                    : null,
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
              TextFormField(
                controller: _notes,
                maxLines: 4,
                decoration: const InputDecoration(
                  labelText: 'Notatki wizji lokalnej',
                ),
              ),
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerLeft,
                child: Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: <Widget>[
                    const Text('Lokalizacja GPS'),
                    if (widget.project?.latitude != null)
                      TextButton(
                        onPressed: _useProjectLocation,
                        child: const Text('Użyj lokalizacji realizacji'),
                      ),
                  ],
                ),
              ),
              TextFormField(
                controller: _latitude,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                  signed: true,
                ),
                decoration: const InputDecoration(
                  labelText: 'Szerokość geograficzna',
                ),
              ),
              TextFormField(
                controller: _longitude,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                  signed: true,
                ),
                decoration: const InputDecoration(
                  labelText: 'Długość geograficzna',
                ),
              ),
              TextFormField(
                controller: _accuracy,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(
                  labelText: 'Dokładność GPS (m)',
                ),
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
          if (_clientId == null || _projectId == null) return;
          Navigator.pop(context, <String, dynamic>{
            'project_id': _projectId,
            'client_id': _clientId,
            'title': _title.text.trim(),
            'status': _status.apiValue,
            'scheduled_at': _scheduled.text.trim().isEmpty
                ? null
                : _scheduled.text.trim(),
            'started_at': _started.text.trim().isEmpty
                ? null
                : _started.text.trim(),
            'notes': _notes.text.trim().isEmpty ? null : _notes.text.trim(),
            'latitude': double.tryParse(_latitude.text.trim()),
            'longitude': double.tryParse(_longitude.text.trim()),
            'location_accuracy_m': double.tryParse(_accuracy.text.trim()),
          });
        },
        child: const Text('Zapisz'),
      ),
    ],
  );
}

class _ClientProjectSelection extends ConsumerStatefulWidget {
  const _ClientProjectSelection({
    required this.onChanged,
    this.initialClientId,
    this.initialClientName,
    this.initialProjectId,
  });
  final int? initialClientId;
  final String? initialClientName;
  final int? initialProjectId;
  final void Function(int? clientId, int? projectId) onChanged;

  @override
  ConsumerState<_ClientProjectSelection> createState() =>
      _ClientProjectSelectionState();
}

class _ClientProjectSelectionState
    extends ConsumerState<_ClientProjectSelection> {
  late int? _clientId = widget.initialClientId;
  late int? _projectId = widget.initialProjectId;

  @override
  Widget build(BuildContext context) {
    final projects = _clientId == null
        ? null
        : ref.watch(
            projectsPageProvider(ProjectQuery(clientId: _clientId, limit: 100)),
          );
    return Column(
      children: <Widget>[
        SearchableClientPicker(
          initialClientId: _clientId,
          initialClientName: widget.initialClientName,
          onChanged: (selection) {
            setState(() {
              _clientId = selection?.id;
              _projectId = null;
            });
            widget.onChanged(_clientId, _projectId);
          },
        ),
        const SizedBox(height: 12),
        if (_clientId == null)
          const Align(
            alignment: Alignment.centerLeft,
            child: Text('Najpierw wybierz klienta.'),
          )
        else if (projects?.isLoading == true)
          const LinearProgressIndicator()
        else if (projects?.hasError == true)
          const Text('Nie udało się wczytać realizacji klienta.')
        else
          DropdownButtonFormField<int>(
            key: ValueKey<int?>(_clientId),
            initialValue: _projectId,
            decoration: const InputDecoration(labelText: 'Realizacja'),
            items: (projects?.value?.items ?? const <Project>[])
                .map(
                  (project) => DropdownMenuItem<int>(
                    value: project.id,
                    child: Text(project.name),
                  ),
                )
                .toList(growable: false),
            onChanged: (value) {
              setState(() => _projectId = value);
              widget.onChanged(_clientId, _projectId);
            },
            validator: (_) =>
                _projectId == null ? 'Wybierz realizację klienta' : null,
          ),
      ],
    );
  }
}
