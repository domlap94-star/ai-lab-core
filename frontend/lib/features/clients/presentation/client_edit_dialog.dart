import 'package:flutter/material.dart';

import '../domain/client.dart';

class ClientEditDialog extends StatefulWidget {
  const ClientEditDialog({required this.client, super.key});
  final Client client;

  @override
  State<ClientEditDialog> createState() => _ClientEditDialogState();
}

class _ClientEditDialogState extends State<ClientEditDialog> {
  final _formKey = GlobalKey<FormState>();
  late ClientType _type;
  late final Map<String, TextEditingController> _fields;
  late List<TextEditingController> _emails;
  late List<TextEditingController> _phones;
  late List<_AddressControllers> _addresses;
  int? _primaryEmail;
  int? _primaryPhone;

  @override
  void initState() {
    super.initState();
    final c = widget.client;
    _type = c.clientType;
    _fields = <String, TextEditingController>{
      'name': TextEditingController(text: c.name),
      'legal_name': TextEditingController(text: c.legalName),
      'tax_id': TextEditingController(text: c.taxId),
      'website': TextEditingController(text: c.website),
    };
    final Iterable<String?> emailValues = c.emails.isNotEmpty
        ? c.emails.map<String?>((contact) => contact.value)
        : <String?>[c.primaryEmail];
    final Iterable<String?> phoneValues = c.phones.isNotEmpty
        ? c.phones.map<String?>((contact) => contact.value)
        : <String?>[c.primaryPhone];
    _emails = emailValues
        .whereType<String>()
        .map((value) => TextEditingController(text: value))
        .toList();
    _phones = phoneValues
        .whereType<String>()
        .map((value) => TextEditingController(text: value))
        .toList();
    _primaryEmail = _initialPrimary(c.emails, _emails);
    _primaryPhone = _initialPrimary(c.phones, _phones);
    _addresses = c.addresses.isNotEmpty
        ? c.addresses.map(_AddressControllers.fromAddress).toList()
        : c.hasStructuredAddressData
        ? <_AddressControllers>[_AddressControllers.fromLegacy(c)]
        : <_AddressControllers>[];
  }

  int? _initialPrimary(
    List<ClientContactPoint> points,
    List<TextEditingController> controllers,
  ) {
    if (controllers.isEmpty) return null;
    final index = points.indexWhere((item) => item.isPrimary);
    return index < 0 ? 0 : index;
  }

  @override
  void dispose() {
    for (final c in <TextEditingController>[
      ..._fields.values,
      ..._emails,
      ..._phones,
    ]) {
      c.dispose();
    }
    for (final address in _addresses) {
      address.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Edytuj klienta'),
    content: SizedBox(
      width: 720,
      child: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              DropdownButtonFormField<ClientType>(
                initialValue: _type,
                decoration: const InputDecoration(labelText: 'Typ klienta'),
                items: ClientType.values
                    .map(
                      (v) => DropdownMenuItem(
                        value: v,
                        child: Text(v.displayName),
                      ),
                    )
                    .toList(),
                onChanged: (v) => setState(() => _type = v ?? _type),
              ),
              ..._fields.entries.map(
                (e) => Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: TextFormField(
                    controller: e.value,
                    decoration: InputDecoration(labelText: _label(e.key)),
                    validator: e.key == 'name'
                        ? (v) => v?.trim().isEmpty == true
                              ? 'Nazwa jest wymagana.'
                              : null
                        : null,
                  ),
                ),
              ),
              const SizedBox(height: 20),
              _ContactEditor(
                title: 'E-maile',
                controllers: _emails,
                primary: _primaryEmail,
                keyboardType: TextInputType.emailAddress,
                onAdd: () => setState(() {
                  _emails.add(TextEditingController());
                  _primaryEmail ??= 0;
                }),
                onPrimary: (i) => setState(() => _primaryEmail = i),
                onRemove: (i) => setState(() {
                  _emails.removeAt(i).dispose();
                  _primaryEmail = _emails.isEmpty ? null : 0;
                }),
              ),
              _AddressEditor(
                addresses: _addresses,
                onAdd: () => setState(() {
                  final hasPrimary = _addresses.any((item) => item.isPrimary);
                  _addresses.add(_AddressControllers(isPrimary: !hasPrimary));
                }),
                onRemove: (index) => setState(() {
                  final removedPrimary = _addresses[index].isPrimary;
                  _addresses.removeAt(index).dispose();
                  if (removedPrimary && _addresses.isNotEmpty) {
                    for (final item in _addresses) {
                      item.isPrimary = false;
                    }
                    _addresses.first.isPrimary = true;
                  }
                }),
                onPrimary: (index) => setState(() {
                  for (var i = 0; i < _addresses.length; i++) {
                    _addresses[i].isPrimary = i == index;
                  }
                }),
              ),
              _ContactEditor(
                title: 'Telefony',
                controllers: _phones,
                primary: _primaryPhone,
                keyboardType: TextInputType.phone,
                onAdd: () => setState(() {
                  _phones.add(TextEditingController());
                  _primaryPhone ??= 0;
                }),
                onPrimary: (i) => setState(() => _primaryPhone = i),
                onRemove: (i) => setState(() {
                  _phones.removeAt(i).dispose();
                  _primaryPhone = _phones.isEmpty ? null : 0;
                }),
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
      FilledButton(onPressed: _submit, child: const Text('Zapisz')),
    ],
  );

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    List<Map<String, dynamic>> contacts(
      List<TextEditingController> list,
      int? primary,
    ) => List.generate(
      list.length,
      (i) => <String, dynamic>{
        'value': list[i].text.trim(),
        'is_primary': i == primary,
      },
    );
    final data = <String, dynamic>{'client_type': _type.value};
    for (final entry in _fields.entries) {
      data[entry.key] = entry.value.text.trim().isEmpty
          ? null
          : entry.value.text.trim();
    }
    data['emails'] = contacts(_emails, _primaryEmail);
    data['phones'] = contacts(_phones, _primaryPhone);
    data['addresses'] = _addresses.map((item) => item.toJson()).toList();
    Navigator.pop(context, data);
  }

  String _label(String key) => <String, String>{
    'name': 'Nazwa / imię i nazwisko',
    'legal_name': 'Nazwa prawna',
    'tax_id': 'NIP / tax ID',
    'website': 'Strona WWW',
  }[key]!;
}

class _AddressControllers {
  _AddressControllers({this.isPrimary = false})
    : label = TextEditingController(text: 'Adres'),
      street = TextEditingController(),
      buildingNumber = TextEditingController(),
      unitNumber = TextEditingController(),
      postalCode = TextEditingController(),
      city = TextEditingController(),
      countryCode = TextEditingController(text: 'PL');

  _AddressControllers.fromAddress(ClientAddress address)
    : label = TextEditingController(text: address.label),
      street = TextEditingController(text: address.street),
      buildingNumber = TextEditingController(text: address.buildingNumber),
      unitNumber = TextEditingController(text: address.unitNumber),
      postalCode = TextEditingController(text: address.postalCode),
      city = TextEditingController(text: address.city),
      countryCode = TextEditingController(text: address.countryCode),
      isPrimary = address.isPrimary;

  _AddressControllers.fromLegacy(Client client)
    : label = TextEditingController(text: 'Adres główny'),
      street = TextEditingController(text: client.street),
      buildingNumber = TextEditingController(text: client.buildingNumber),
      unitNumber = TextEditingController(text: client.unitNumber),
      postalCode = TextEditingController(text: client.postalCode),
      city = TextEditingController(text: client.city),
      countryCode = TextEditingController(text: client.countryCode),
      isPrimary = true;

  final TextEditingController label;
  final TextEditingController street;
  final TextEditingController buildingNumber;
  final TextEditingController unitNumber;
  final TextEditingController postalCode;
  final TextEditingController city;
  final TextEditingController countryCode;
  bool isPrimary;

  Map<String, dynamic> toJson() => <String, dynamic>{
    'label': label.text.trim(),
    'street': street.text.trim().isEmpty ? null : street.text.trim(),
    'building_number': buildingNumber.text.trim().isEmpty
        ? null
        : buildingNumber.text.trim(),
    'unit_number': unitNumber.text.trim().isEmpty
        ? null
        : unitNumber.text.trim(),
    'postal_code': postalCode.text.trim().isEmpty
        ? null
        : postalCode.text.trim(),
    'city': city.text.trim().isEmpty ? null : city.text.trim(),
    'country_code': countryCode.text.trim().toUpperCase(),
    'is_primary': isPrimary,
  };

  void dispose() {
    for (final controller in <TextEditingController>[
      label,
      street,
      buildingNumber,
      unitNumber,
      postalCode,
      city,
      countryCode,
    ]) {
      controller.dispose();
    }
  }
}

class _AddressEditor extends StatelessWidget {
  const _AddressEditor({
    required this.addresses,
    required this.onAdd,
    required this.onRemove,
    required this.onPrimary,
  });

  final List<_AddressControllers> addresses;
  final VoidCallback onAdd;
  final ValueChanged<int> onRemove;
  final ValueChanged<int> onPrimary;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: <Widget>[
      const SizedBox(height: 18),
      Wrap(
        alignment: WrapAlignment.spaceBetween,
        runSpacing: 8,
        children: <Widget>[
          Text('Adresy', style: Theme.of(context).textTheme.titleMedium),
          TextButton.icon(
            key: const Key('add-client-address'),
            onPressed: onAdd,
            icon: const Icon(Icons.add),
            label: const Text('Dodaj adres'),
          ),
        ],
      ),
      ...List.generate(addresses.length, (index) {
        final item = addresses[index];
        return Card(
          key: Key('client-address-editor-$index'),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              children: <Widget>[
                Wrap(
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: <Widget>[
                    Checkbox(
                      value: item.isPrimary,
                      onChanged: (_) => onPrimary(index),
                    ),
                    const Text('Adres główny'),
                    IconButton(
                      tooltip: 'Usuń adres',
                      onPressed: () => onRemove(index),
                      icon: const Icon(Icons.delete_outline),
                    ),
                  ],
                ),
                TextFormField(
                  controller: item.label,
                  decoration: const InputDecoration(labelText: 'Etykieta'),
                ),
                TextFormField(
                  controller: item.street,
                  decoration: const InputDecoration(labelText: 'Ulica'),
                ),
                Row(
                  children: <Widget>[
                    Expanded(
                      child: TextFormField(
                        controller: item.buildingNumber,
                        decoration: const InputDecoration(
                          labelText: 'Nr budynku',
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: TextFormField(
                        controller: item.unitNumber,
                        decoration: const InputDecoration(
                          labelText: 'Nr lokalu',
                        ),
                      ),
                    ),
                  ],
                ),
                Row(
                  children: <Widget>[
                    Expanded(
                      child: TextFormField(
                        controller: item.postalCode,
                        decoration: const InputDecoration(
                          labelText: 'Kod pocztowy',
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: TextFormField(
                        controller: item.city,
                        decoration: const InputDecoration(
                          labelText: 'Miejscowość',
                        ),
                      ),
                    ),
                  ],
                ),
                TextFormField(
                  controller: item.countryCode,
                  decoration: const InputDecoration(labelText: 'Kod kraju'),
                ),
              ],
            ),
          ),
        );
      }),
    ],
  );
}

class _ContactEditor extends StatelessWidget {
  const _ContactEditor({
    required this.title,
    required this.controllers,
    required this.primary,
    required this.keyboardType,
    required this.onAdd,
    required this.onPrimary,
    required this.onRemove,
  });
  final String title;
  final List<TextEditingController> controllers;
  final int? primary;
  final TextInputType keyboardType;
  final VoidCallback onAdd;
  final ValueChanged<int> onPrimary;
  final ValueChanged<int> onRemove;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: <Widget>[
      const SizedBox(height: 18),
      Row(
        children: <Widget>[
          Expanded(
            child: Text(title, style: Theme.of(context).textTheme.titleMedium),
          ),
          TextButton.icon(
            onPressed: onAdd,
            icon: const Icon(Icons.add),
            label: Text('Dodaj ${title == 'E-maile' ? 'e-mail' : 'telefon'}'),
          ),
        ],
      ),
      RadioGroup<int>(
        groupValue: primary,
        onChanged: (value) {
          if (value != null) onPrimary(value);
        },
        child: Column(
          children: <Widget>[
            ...List.generate(
              controllers.length,
              (i) => Row(
                children: <Widget>[
                  Radio<int>(value: i),
                  Expanded(
                    child: TextFormField(
                      controller: controllers[i],
                      keyboardType: keyboardType,
                      decoration: InputDecoration(
                        labelText: i == primary
                            ? 'Główny'
                            : title.substring(0, title.length - 1),
                      ),
                      validator: (v) => v?.trim().isEmpty == true
                          ? 'Wartość nie może być pusta.'
                          : null,
                    ),
                  ),
                  IconButton(
                    tooltip: 'Usuń',
                    onPressed: () => onRemove(i),
                    icon: const Icon(Icons.delete_outline),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    ],
  );
}
