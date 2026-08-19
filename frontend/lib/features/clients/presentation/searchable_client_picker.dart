import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/application/auth_controller.dart';
import '../application/clients_providers.dart';
import '../domain/client.dart';

class ClientPickerSelection {
  const ClientPickerSelection({required this.id, required this.name});
  final int id;
  final String name;
}

class SearchableClientPicker extends ConsumerStatefulWidget {
  const SearchableClientPicker({
    required this.onChanged,
    this.initialClientId,
    this.initialClientName,
    this.enabled = true,
    super.key,
  });

  final ValueChanged<ClientPickerSelection?> onChanged;
  final int? initialClientId;
  final String? initialClientName;
  final bool enabled;

  @override
  ConsumerState<SearchableClientPicker> createState() =>
      _SearchableClientPickerState();
}

class _SearchableClientPickerState
    extends ConsumerState<SearchableClientPicker> {
  final TextEditingController _query = TextEditingController();
  Timer? _debounce;
  List<Client> _results = const <Client>[];
  ClientPickerSelection? _selected;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (widget.initialClientId != null) {
      _selected = ClientPickerSelection(
        id: widget.initialClientId!,
        name: widget.initialClientName?.trim().isNotEmpty == true
            ? widget.initialClientName!.trim()
            : 'Klient #${widget.initialClientId}',
      );
    }
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _query.dispose();
    super.dispose();
  }

  void _scheduleSearch(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () => _search(value));
  }

  Future<void> _search(String value) async {
    final text = value.trim();
    if (text.isEmpty) {
      if (mounted) setState(() => _results = const <Client>[]);
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final session = ref.read(authControllerProvider).value?.session;
      if (session == null) throw StateError('Brak aktywnej sesji.');
      final page = await ref
          .read(clientsRepositoryProvider)
          .fetchClients(session: session, search: text, limit: 20);
      if (mounted) setState(() => _results = page.items);
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Nie udało się wyszukać klientów.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_selected != null) {
      return InputDecorator(
        decoration: const InputDecoration(labelText: 'Klient'),
        child: Row(
          children: <Widget>[
            Expanded(child: Text(_selected!.name)),
            if (widget.enabled)
              IconButton(
                key: const Key('client-picker-clear'),
                tooltip: 'Wyczyść wybór',
                onPressed: () {
                  setState(() => _selected = null);
                  widget.onChanged(null);
                },
                icon: const Icon(Icons.close),
              ),
          ],
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        TextField(
          key: const Key('searchable-client-picker'),
          controller: _query,
          enabled: widget.enabled,
          onChanged: _scheduleSearch,
          decoration: InputDecoration(
            labelText: 'Wyszukaj klienta',
            hintText: 'Nazwa, e-mail, telefon, adres lub NIP',
            suffixIcon: _loading
                ? const Padding(
                    padding: EdgeInsets.all(12),
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.search),
          ),
        ),
        if (_error != null)
          Row(
            children: <Widget>[
              Expanded(child: Text(_error!)),
              TextButton(
                onPressed: () => _search(_query.text),
                child: const Text('Spróbuj ponownie'),
              ),
            ],
          ),
        if (!_loading && _query.text.trim().isNotEmpty && _results.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Text('Brak wyników.'),
          ),
        ..._results.map(
          (client) => ListTile(
            dense: true,
            title: Text(client.displayName),
            subtitle: Text(
              <String>[
                client.workflowStatusLabel,
                if ((client.availableAddress ?? client.primaryEmail)
                    case final String detail when detail.trim().isNotEmpty)
                  detail,
              ].join(' · '),
            ),
            onTap: () {
              final selected = ClientPickerSelection(
                id: client.id,
                name: client.displayName,
              );
              setState(() {
                _selected = selected;
                _results = const <Client>[];
              });
              widget.onChanged(selected);
            },
          ),
        ),
      ],
    );
  }
}
