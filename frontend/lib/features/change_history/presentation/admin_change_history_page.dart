import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../auth/application/account_providers.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/data/account_api.dart';
import '../../auth/domain/auth_session.dart';
import '../data/change_history_api.dart';
import '../domain/change_history.dart';

class AdminChangeHistoryPage extends ConsumerStatefulWidget {
  const AdminChangeHistoryPage({super.key});

  @override
  ConsumerState<AdminChangeHistoryPage> createState() =>
      _AdminChangeHistoryPageState();
}

class _AdminChangeHistoryPageState
    extends ConsumerState<AdminChangeHistoryPage> {
  static const int _pageSize = 50;
  final List<ChangeHistoryItem> _items = <ChangeHistoryItem>[];
  List<ManagedUser> _actors = const <ManagedUser>[];
  String? _entityType;
  String? _action;
  int? _actorUserId;
  DateTimeRange? _dates;
  int _total = 0;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _reload());
  }

  bool _isAdmin(String role) {
    final String value = role.trim().toLowerCase();
    return value == 'admin' || value == 'administrator';
  }

  Future<void> _reload() async {
    _items.clear();
    _total = 0;
    await _load(more: false);
  }

  Future<void> _load({required bool more}) async {
    if (_loading) return;
    final auth = ref.read(authControllerProvider).value;
    final AuthSession? session = auth?.session;
    if (session == null || !_isAdmin(auth?.user?.role ?? '')) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      if (_actors.isEmpty) {
        _actors = await ref
            .read(accountApiProvider)
            .fetchUsers(session: session);
      }
      final ChangeHistoryPageData page = await ref
          .read(changeHistoryApiProvider)
          .fetch(
            session: session,
            entityType: _entityType,
            actorUserId: _actorUserId,
            action: _action,
            dateFrom: _dates?.start,
            dateTo: _dates == null
                ? null
                : DateTime(
                    _dates!.end.year,
                    _dates!.end.month,
                    _dates!.end.day,
                    23,
                    59,
                    59,
                    999,
                  ),
            skip: more ? _items.length : 0,
            limit: _pageSize,
          );
      if (!mounted) return;
      setState(() {
        if (!more) _items.clear();
        _items.addAll(page.items);
        _total = page.total;
      });
    } on DioException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = switch (error.response?.statusCode) {
          401 => 'Sesja wygasła. Zaloguj się ponownie.',
          403 => 'Brak uprawnień administratora.',
          _ => 'Nie udało się pobrać historii zmian.',
        };
      });
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Nie udało się pobrać historii zmian.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _pickDates() async {
    final DateTimeRange? value = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2020),
      lastDate: DateTime.now(),
      initialDateRange: _dates,
    );
    if (value != null) {
      setState(() => _dates = value);
      await _reload();
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authControllerProvider).value;
    if (!_isAdmin(auth?.user?.role ?? '')) {
      return Scaffold(
        appBar: AppBar(title: const Text('Historia zmian')),
        body: const Center(child: Text('Brak uprawnień administratora.')),
      );
    }
    return Scaffold(
      appBar: AppBar(title: const Text('Historia zmian')),
      body: Column(
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.all(16),
            child: Wrap(
              spacing: 12,
              runSpacing: 12,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: <Widget>[
                _stringFilter(
                  key: const Key('history-entity-filter'),
                  label: 'Encja',
                  value: _entityType,
                  values: const <String>[
                    'client',
                    'client_contact',
                    'client_address',
                    'client_workflow_status',
                    'client_candidate',
                    'candidate_merge',
                    'document',
                    'user',
                  ],
                  onChanged: (String? value) async {
                    setState(() => _entityType = value);
                    await _reload();
                  },
                ),
                _stringFilter(
                  key: const Key('history-action-filter'),
                  label: 'Operacja',
                  value: _action,
                  values: const <String>[
                    'created',
                    'updated',
                    'deleted',
                    'status_changed',
                    'accepted',
                    'rejected',
                    'merged',
                    'linked',
                    'unlinked',
                    'moved',
                    'deactivated',
                  ],
                  onChanged: (String? value) async {
                    setState(() => _action = value);
                    await _reload();
                  },
                ),
                SizedBox(
                  width: 220,
                  child: DropdownButtonFormField<int?>(
                    key: const Key('history-actor-filter'),
                    initialValue: _actorUserId,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Użytkownik',
                      border: OutlineInputBorder(),
                    ),
                    items: <DropdownMenuItem<int?>>[
                      const DropdownMenuItem<int?>(
                        value: null,
                        child: Text('Wszyscy'),
                      ),
                      ..._actors.map(
                        (ManagedUser user) => DropdownMenuItem<int?>(
                          value: user.id,
                          child: Text(
                            user.username,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ),
                    ],
                    onChanged: (int? value) async {
                      setState(() => _actorUserId = value);
                      await _reload();
                    },
                  ),
                ),
                OutlinedButton.icon(
                  key: const Key('history-date-filter'),
                  onPressed: _pickDates,
                  icon: const Icon(Icons.date_range),
                  label: Text(
                    _dates == null
                        ? 'Zakres dat'
                        : '${_date(_dates!.start)} – ${_date(_dates!.end)}',
                  ),
                ),
                if (_dates != null)
                  IconButton(
                    tooltip: 'Wyczyść zakres dat',
                    onPressed: () async {
                      setState(() => _dates = null);
                      await _reload();
                    },
                    icon: const Icon(Icons.clear),
                  ),
              ],
            ),
          ),
          if (_error != null)
            MaterialBanner(
              content: Text(_error!),
              actions: <Widget>[
                TextButton(onPressed: _reload, child: const Text('Ponów')),
              ],
            ),
          Expanded(
            child: _items.isEmpty && _loading
                ? const Center(child: CircularProgressIndicator())
                : _items.isEmpty
                ? const Center(child: Text('Brak zapisanych zmian.'))
                : ListView.builder(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                    itemCount: _items.length + (_items.length < _total ? 1 : 0),
                    itemBuilder: (BuildContext context, int index) {
                      if (index == _items.length) {
                        return Center(
                          child: OutlinedButton(
                            key: const Key('history-load-more'),
                            onPressed: _loading
                                ? null
                                : () => _load(more: true),
                            child: const Text('Pokaż więcej'),
                          ),
                        );
                      }
                      return _HistoryTile(item: _items[index]);
                    },
                  ),
          ),
        ],
      ),
    );
  }

  Widget _stringFilter({
    required Key key,
    required String label,
    required String? value,
    required List<String> values,
    required ValueChanged<String?> onChanged,
  }) {
    return SizedBox(
      width: 220,
      child: DropdownButtonFormField<String?>(
        key: key,
        initialValue: value,
        isExpanded: true,
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
        ),
        items: <DropdownMenuItem<String?>>[
          const DropdownMenuItem<String?>(
            value: null,
            child: Text('Wszystkie'),
          ),
          ...values.map(
            (String item) =>
                DropdownMenuItem<String?>(value: item, child: Text(item)),
          ),
        ],
        onChanged: onChanged,
      ),
    );
  }
}

class _HistoryTile extends StatelessWidget {
  const _HistoryTile({required this.item});
  final ChangeHistoryItem item;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ExpansionTile(
        key: Key('history-${item.stableKey}'),
        leading: const Icon(Icons.history),
        title: Text('${_action(item.action)} · ${item.entityLabel}'),
        subtitle: Text(
          '${_dateTime(item.createdAt)} · ${item.actorDisplayName ?? 'System / użytkownik #${item.actorUserId ?? '—'}'}\n${item.changedFields.join(', ')}',
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        children: <Widget>[
          for (final String field in item.changedFields)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Expanded(flex: 2, child: Text(field)),
                  Expanded(
                    child: Text(_displayValue(item.beforeValues[field])),
                  ),
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 8),
                    child: Icon(Icons.arrow_forward, size: 16),
                  ),
                  Expanded(child: Text(_displayValue(item.afterValues[field]))),
                ],
              ),
            ),
          if (item.deepLink != null)
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: () => context.push(item.deepLink!),
                icon: const Icon(Icons.open_in_new),
                label: const Text('Otwórz'),
              ),
            ),
        ],
      ),
    );
  }
}

String _displayValue(Object? value) {
  if (value == null) return '—';
  if (value is Map) {
    if (value['masked'] != null) return value['masked'].toString();
    if (value['length'] != null) return '${value['length']} znaków';
    return 'Zmieniono dane';
  }
  if (value is List) return '${value.length} elementów';
  if (value is bool) return value ? 'Tak' : 'Nie';
  return value.toString();
}

String _action(String value) =>
    <String, String>{
      'created': 'Utworzono',
      'updated': 'Zmieniono',
      'deleted': 'Usunięto',
      'restored': 'Przywrócono',
      'status_changed': 'Zmieniono status',
      'accepted': 'Zaakceptowano',
      'rejected': 'Odrzucono',
      'merged': 'Połączono',
      'linked': 'Powiązano',
      'unlinked': 'Odłączono',
      'moved': 'Przeniesiono',
      'deactivated': 'Dezaktywowano',
    }[value] ??
    value;
String _date(DateTime value) =>
    '${value.day.toString().padLeft(2, '0')}.${value.month.toString().padLeft(2, '0')}.${value.year}';
String _dateTime(DateTime value) {
  final DateTime local = value.toLocal();
  return '${_date(local)}, ${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
}
