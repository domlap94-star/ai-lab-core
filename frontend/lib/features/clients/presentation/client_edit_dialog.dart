import 'package:flutter/material.dart';

import '../../../core/formatters/polish_date_time.dart';
import '../domain/client.dart';
import '../domain/industry.dart';

enum ClientEditSection { name, basic, registration, contact, address, system }

class ClientEditDialog extends StatefulWidget {
  const ClientEditDialog({
    required this.client,
    this.section,
    this.industries = const <Industry>[],
    super.key,
  });
  final Client client;
  final ClientEditSection? section;
  final List<Industry> industries;

  @override
  State<ClientEditDialog> createState() => _ClientEditDialogState();
}

class _ClientEditDialogState extends State<ClientEditDialog> {
  final _formKey = GlobalKey<FormState>();
  late ClientType _type;
  late int? _industryId;
  late DateTime? _clientAddedAt;
  bool _explicitDateCleared = false;
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
    _industryId = c.industryId;
    _clientAddedAt = c.clientAddedAt;
    _fields = <String, TextEditingController>{
      'name': TextEditingController(text: c.name),
      'legal_name': TextEditingController(text: c.legalName),
      'tax_id': TextEditingController(text: c.taxId),
      'registration_number': TextEditingController(text: c.registrationNumber),
      'website': TextEditingController(text: c.website),
    };
    final Iterable<String?> emailValues = c.genericEmails.isNotEmpty
        ? c.genericEmails.map<String?>((contact) => contact.value)
        : <String?>[c.primaryEmail];
    final Iterable<String?> phoneValues = c.genericPhones.isNotEmpty
        ? c.genericPhones.map<String?>((contact) => contact.value)
        : <String?>[c.primaryPhone];
    _emails = emailValues
        .whereType<String>()
        .map((value) => TextEditingController(text: value))
        .toList();
    _phones = phoneValues
        .whereType<String>()
        .map((value) => TextEditingController(text: value))
        .toList();
    _primaryEmail = _initialPrimary(c.genericEmails, _emails);
    _primaryPhone = _initialPrimary(c.genericPhones, _phones);
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

  List<Industry> get _availableIndustries {
    final result = <Industry>[...widget.industries];
    final current = widget.client.industry;
    if (current != null && !result.any((item) => item.id == current.id)) {
      result.add(current);
    }
    return result;
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
    title: Text(_dialogTitle),
    content: SizedBox(
      width: 720,
      child: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              if (_shows(ClientEditSection.basic))
                DropdownButtonFormField<ClientType>(
                  isExpanded: true,
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
              if (_shows(ClientEditSection.basic))
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: DropdownButtonFormField<int?>(
                    key: const Key('client-industry-field'),
                    isExpanded: true,
                    initialValue: _industryId,
                    decoration: const InputDecoration(labelText: 'Branża'),
                    items: <DropdownMenuItem<int?>>[
                      const DropdownMenuItem<int?>(
                        value: null,
                        child: Text('Brak branży'),
                      ),
                      ..._availableIndustries
                          .where(
                            (item) => item.isActive || item.id == _industryId,
                          )
                          .map(
                            (item) => DropdownMenuItem<int?>(
                              value: item.id,
                              child: Text(
                                item.name,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ),
                    ],
                    onChanged: (value) => setState(() => _industryId = value),
                  ),
                ),
              if (_shows(ClientEditSection.system))
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: InputDecorator(
                    key: const Key('client-added-date-field'),
                    decoration: const InputDecoration(
                      labelText: 'Data dodania',
                      border: OutlineInputBorder(),
                    ),
                    child: Row(
                      children: <Widget>[
                        Expanded(
                          child: Text(
                            _clientAddedAt == null
                                ? _explicitDateCleared
                                      ? 'Po zapisie: data źródłowa lub techniczna'
                                      : 'Automatyczna: ${formatPolishDate(widget.client.effectiveAddedDate)}'
                                : formatPolishDate(_clientAddedAt!),
                          ),
                        ),
                        IconButton(
                          key: const Key('client-added-date-picker'),
                          tooltip: 'Wybierz datę dodania',
                          onPressed: _selectAddedDate,
                          icon: const Icon(Icons.calendar_today_outlined),
                        ),
                        if (_clientAddedAt != null)
                          IconButton(
                            key: const Key('client-added-date-clear'),
                            tooltip:
                                'Wyczyść i wróć do daty źródłowej lub technicznej',
                            onPressed: () => setState(() {
                              _clientAddedAt = null;
                              _explicitDateCleared = true;
                            }),
                            icon: const Icon(Icons.clear),
                          ),
                      ],
                    ),
                  ),
                ),
              ..._visibleFieldKeys
                  .map((key) => MapEntry(key, _fields[key]!))
                  .map(
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
              if (_shows(ClientEditSection.contact)) ...<Widget>[
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
              if (_shows(ClientEditSection.address))
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
    final data = <String, dynamic>{};
    if (_shows(ClientEditSection.basic)) {
      data['client_type'] = _type.value;
      data['industry_id'] = _industryId;
    }
    if (_shows(ClientEditSection.system)) {
      data['client_added_at'] = _clientAddedAt == null
          ? null
          : _dateToIso(_clientAddedAt!);
    }
    for (final key in _visibleFieldKeys) {
      final entry = MapEntry(key, _fields[key]!);
      data[entry.key] = entry.value.text.trim().isEmpty
          ? null
          : entry.value.text.trim();
    }
    if (_shows(ClientEditSection.contact)) {
      data['emails'] = contacts(_emails, _primaryEmail);
      data['phones'] = contacts(_phones, _primaryPhone);
    }
    if (_shows(ClientEditSection.address)) {
      data['addresses'] = _addresses.map((item) => item.toJson()).toList();
    }
    Navigator.pop(context, data);
  }

  bool _shows(ClientEditSection section) =>
      widget.section == null || widget.section == section;

  List<String> get _visibleFieldKeys => switch (widget.section) {
    ClientEditSection.name => const <String>['name'],
    ClientEditSection.registration => const <String>[
      'legal_name',
      'tax_id',
      'registration_number',
    ],
    ClientEditSection.contact => const <String>['website'],
    null => const <String>[
      'name',
      'legal_name',
      'tax_id',
      'registration_number',
      'website',
    ],
    _ => const <String>[],
  };

  String get _dialogTitle => switch (widget.section) {
    ClientEditSection.name => 'Edytuj nazwę klienta',
    ClientEditSection.basic => 'Edytuj dane podstawowe',
    ClientEditSection.registration => 'Edytuj dane rejestrowe',
    ClientEditSection.contact => 'Edytuj kontakt',
    ClientEditSection.address => 'Edytuj adres',
    ClientEditSection.system => 'Edytuj datę dodania',
    null => 'Edytuj klienta',
  };

  Future<void> _selectAddedDate() async {
    final DateTime today = DateUtils.dateOnly(DateTime.now());
    final DateTime selected =
        _clientAddedAt ?? widget.client.effectiveAddedDate;
    final DateTime initialDate = selected.isAfter(today) ? today : selected;
    final DateTime? value = await showDatePicker(
      context: context,
      initialDate: initialDate,
      firstDate: DateTime(1900),
      lastDate: today,
      helpText: 'Wybierz datę dodania klienta',
    );
    if (value != null && mounted) {
      setState(() {
        _clientAddedAt = DateUtils.dateOnly(value);
        _explicitDateCleared = false;
      });
    }
  }

  String _dateToIso(DateTime value) =>
      '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';

  String _label(String key) => <String, String>{
    'name': 'Nazwa / imię i nazwisko',
    'legal_name': 'Nazwa prawna',
    'tax_id': 'NIP / tax ID',
    'registration_number': 'Numer rejestracyjny',
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
                  textCapitalization: TextCapitalization.characters,
                  validator: (value) => value?.trim().length == 2
                      ? null
                      : 'Kod kraju musi mieć dokładnie 2 znaki.',
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
      LayoutBuilder(
        builder: (BuildContext context, BoxConstraints constraints) {
          final Widget heading = Text(
            title,
            style: Theme.of(context).textTheme.titleMedium,
          );
          final Widget addButton = TextButton.icon(
            onPressed: onAdd,
            icon: const Icon(Icons.add),
            label: Text('Dodaj ${title == 'E-maile' ? 'e-mail' : 'telefon'}'),
          );
          if (constraints.maxWidth < 280) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                heading,
                Align(alignment: Alignment.centerRight, child: addButton),
              ],
            );
          }
          return Row(
            children: <Widget>[
              Expanded(child: heading),
              addButton,
            ],
          );
        },
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
