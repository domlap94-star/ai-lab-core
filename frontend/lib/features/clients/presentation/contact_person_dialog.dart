import 'package:flutter/material.dart';

import '../domain/client.dart';

class ContactPersonDialog extends StatefulWidget {
  const ContactPersonDialog({required this.client, this.person, super.key});

  final Client client;
  final ContactPerson? person;

  @override
  State<ContactPersonDialog> createState() => _ContactPersonDialogState();
}

class _ContactPersonDialogState extends State<ContactPersonDialog> {
  late final TextEditingController _name;
  late final TextEditingController _role;
  late final TextEditingController _notes;
  final List<TextEditingController> _emails = <TextEditingController>[];
  final List<TextEditingController> _phones = <TextEditingController>[];
  late final Set<int> _selectedPointIds;
  late bool _preferred;
  late bool _decisionMaker;
  String? _error;

  @override
  void initState() {
    super.initState();
    final person = widget.person;
    _name = TextEditingController(text: person?.displayName ?? '');
    _role = TextEditingController(text: person?.role ?? '');
    _notes = TextEditingController(text: person?.notes ?? '');
    _selectedPointIds =
        person?.contactPoints.map((item) => item.id).toSet() ?? <int>{};
    _preferred = person?.isPreferred ?? false;
    _decisionMaker = person?.isDecisionMaker ?? false;
  }

  @override
  void dispose() {
    _name.dispose();
    _role.dispose();
    _notes.dispose();
    for (final controller in <TextEditingController>[..._emails, ..._phones]) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final available = <ClientContactPoint>{
      ...widget.client.genericEmails,
      ...widget.client.genericPhones,
      ...?widget.person?.contactPoints,
    }.toList()..sort((a, b) => a.id.compareTo(b.id));
    return AlertDialog(
      title: Text(
        widget.person == null
            ? 'Dodaj osobę kontaktową'
            : 'Edytuj osobę kontaktową',
      ),
      content: SizedBox(
        width: 620,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              TextField(
                key: const Key('contact-person-name'),
                controller: _name,
                maxLength: 200,
                decoration: const InputDecoration(
                  labelText: 'Nazwa / imię i nazwisko *',
                ),
              ),
              TextField(
                key: const Key('contact-person-role'),
                controller: _role,
                maxLength: 200,
                decoration: const InputDecoration(
                  labelText: 'Rola / stanowisko',
                ),
              ),
              SwitchListTile.adaptive(
                key: const Key('contact-person-preferred'),
                contentPadding: EdgeInsets.zero,
                title: const Text('Preferowana osoba'),
                value: _preferred,
                onChanged: (value) => setState(() => _preferred = value),
              ),
              SwitchListTile.adaptive(
                key: const Key('contact-person-decision-maker'),
                contentPadding: EdgeInsets.zero,
                title: const Text('Decydent'),
                value: _decisionMaker,
                onChanged: (value) => setState(() => _decisionMaker = value),
              ),
              if (available.isNotEmpty) ...<Widget>[
                const SizedBox(height: 8),
                Text(
                  'Przypisz istniejące kontakty',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                ...available.map(
                  (point) => CheckboxListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    value: _selectedPointIds.contains(point.id),
                    title: Text(point.value),
                    subtitle: Text(
                      point.value.contains('@') ? 'E-mail' : 'Telefon',
                    ),
                    onChanged: (selected) => setState(() {
                      if (selected == true) {
                        _selectedPointIds.add(point.id);
                      } else {
                        _selectedPointIds.remove(point.id);
                      }
                    }),
                  ),
                ),
              ],
              const SizedBox(height: 8),
              _CoordinateEditor(
                title: 'Nowe adresy e-mail',
                hint: 'kontakt@example.pl',
                controllers: _emails,
                onChanged: () => setState(() {}),
              ),
              const SizedBox(height: 12),
              _CoordinateEditor(
                title: 'Nowe telefony',
                hint: '+48 500 000 000',
                controllers: _phones,
                onChanged: () => setState(() {}),
              ),
              const SizedBox(height: 12),
              TextField(
                key: const Key('contact-person-notes'),
                controller: _notes,
                maxLength: 4000,
                minLines: 3,
                maxLines: 6,
                decoration: const InputDecoration(
                  labelText: 'Notatki',
                  border: OutlineInputBorder(),
                ),
              ),
              if (_error != null)
                Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
            ],
          ),
        ),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Anuluj'),
        ),
        FilledButton(
          key: const Key('contact-person-save'),
          onPressed: _submit,
          child: const Text('Zapisz'),
        ),
      ],
    );
  }

  void _submit() {
    final name = _name.text.trim().replaceAll(RegExp(r'\s+'), ' ');
    if (name.isEmpty) {
      setState(() => _error = 'Nazwa osoby jest wymagana.');
      return;
    }
    Navigator.pop(context, <String, dynamic>{
      'display_name': name,
      'role': _nullable(_role.text),
      'is_preferred': _preferred,
      'is_decision_maker': _decisionMaker,
      'notes': _nullable(_notes.text),
      'contact_point_ids': _selectedPointIds.toList()..sort(),
      'emails': _values(_emails),
      'phones': _values(_phones),
    });
  }

  static String? _nullable(String value) =>
      value.trim().isEmpty ? null : value.trim();
  static List<Map<String, dynamic>> _values(
    List<TextEditingController> controllers,
  ) => controllers
      .map((item) => item.text.trim())
      .where((item) => item.isNotEmpty)
      .map((item) => <String, dynamic>{'value': item, 'is_primary': false})
      .toList(growable: false);
}

class _CoordinateEditor extends StatelessWidget {
  const _CoordinateEditor({
    required this.title,
    required this.hint,
    required this.controllers,
    required this.onChanged,
  });

  final String title;
  final String hint;
  final List<TextEditingController> controllers;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: <Widget>[
      Row(
        children: <Widget>[
          Expanded(
            child: Text(title, style: Theme.of(context).textTheme.titleSmall),
          ),
          TextButton.icon(
            onPressed: () {
              controllers.add(TextEditingController());
              onChanged();
            },
            icon: const Icon(Icons.add),
            label: const Text('Dodaj'),
          ),
        ],
      ),
      ...List<Widget>.generate(
        controllers.length,
        (index) => Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Row(
            children: <Widget>[
              Expanded(
                child: TextField(
                  controller: controllers[index],
                  decoration: InputDecoration(hintText: hint),
                ),
              ),
              IconButton(
                tooltip: 'Usuń pole',
                onPressed: () {
                  controllers[index].dispose();
                  controllers.removeAt(index);
                  onChanged();
                },
                icon: const Icon(Icons.remove_circle_outline),
              ),
            ],
          ),
        ),
      ),
    ],
  );
}
