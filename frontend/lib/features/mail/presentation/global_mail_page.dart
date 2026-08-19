import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/formatters/polish_date_time.dart';
import '../../../core/network/friendly_api_error.dart';
import '../../../core/widgets/app_shell.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/domain/auth_session.dart';
import '../data/global_mail_api.dart';
import '../domain/global_mail.dart';

class GlobalMailPage extends ConsumerStatefulWidget {
  const GlobalMailPage({super.key});

  @override
  ConsumerState<GlobalMailPage> createState() => _GlobalMailPageState();
}

class _GlobalMailPageState extends ConsumerState<GlobalMailPage> {
  final TextEditingController _search = TextEditingController();
  final List<GlobalMailItem> _items = <GlobalMailItem>[];
  Timer? _debounce;
  bool _loading = true;
  bool _loadingMore = false;
  bool _hasMore = false;
  String? _error;
  String? _direction;
  String? _readState;
  bool? _linked;
  bool? _attachments;
  DateTimeRange? _dates;
  GlobalMailItem? _selected;

  GlobalMailApi get _api => ref.read(globalMailApiProvider);
  AuthSession? get _session => ref.read(authControllerProvider).value?.session;

  @override
  void initState() {
    super.initState();
    scheduleMicrotask(_reload);
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _search.dispose();
    super.dispose();
  }

  Future<void> _reload() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final AuthSession? session = _session;
      if (session == null) throw StateError('Brak aktywnej sesji.');
      final page = await _api.list(
        session: session,
        skip: 0,
        search: _search.text.trim().isEmpty ? null : _search.text.trim(),
        direction: _direction,
        readState: _readState,
        linked: _linked,
        hasAttachments: _attachments,
        dateFrom: _dates?.start,
        dateTo: _dates?.end.add(const Duration(days: 1)),
      );
      if (!mounted) return;
      setState(() {
        _items
          ..clear()
          ..addAll(page.items);
        _hasMore = page.hasMore;
      });
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = friendlyApiError(
            error,
            fallback: 'Nie udało się pobrać maili.',
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadMore() async {
    if (_loadingMore || !_hasMore) return;
    setState(() => _loadingMore = true);
    try {
      final session = _session;
      if (session == null) return;
      final page = await _api.list(
        session: session,
        skip: _items.length,
        search: _search.text.trim().isEmpty ? null : _search.text.trim(),
        direction: _direction,
        readState: _readState,
        linked: _linked,
        hasAttachments: _attachments,
        dateFrom: _dates?.start,
        dateTo: _dates?.end.add(const Duration(days: 1)),
      );
      if (mounted) {
        setState(() {
          _items.addAll(page.items);
          _hasMore = page.hasMore;
        });
      }
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  Future<void> _open(GlobalMailItem item) async {
    final session = _session;
    if (session == null) return;
    setState(() => _selected = item);
    try {
      final detail = await _api.detail(session, item.sourceId);
      if (mounted) setState(() => _selected = detail);
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              friendlyApiError(
                error,
                fallback: 'Nie udało się otworzyć maila.',
              ),
            ),
          ),
        );
      }
    }
  }

  void _searchChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), _reload);
  }

  @override
  Widget build(BuildContext context) {
    final bool desktop = MediaQuery.sizeOf(context).width >= 800;
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (bool didPop, Object? result) {
        if (didPop) return;
        if (_selected != null) {
          setState(() => _selected = null);
        } else {
          context.go('/dashboard');
        }
      },
      child: Scaffold(
        appBar: AppBar(
          leading: desktop || _selected == null
              ? AppShell.mobileNavigationLeading(context)
              : BackButton(onPressed: () => setState(() => _selected = null)),
          title: const Text('Maile'),
        ),
        body: desktop
            ? Row(
                children: <Widget>[
                  SizedBox(width: 430, child: _mailList()),
                  const VerticalDivider(width: 1),
                  Expanded(
                    child: _selected == null
                        ? const Center(child: Text('Wybierz wiadomość'))
                        : _detail(_selected!),
                  ),
                ],
              )
            : (_selected == null ? _mailList() : _detail(_selected!)),
      ),
    );
  }

  Widget _mailList() => Column(
    children: <Widget>[
      Padding(
        padding: const EdgeInsets.all(12),
        child: TextField(
          key: const Key('mail-search'),
          controller: _search,
          onChanged: _searchChanged,
          decoration: const InputDecoration(
            prefixIcon: Icon(Icons.search),
            labelText: 'Szukaj w mailach',
          ),
        ),
      ),
      SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        child: Row(
          children: <Widget>[
            _menu(
              'Kierunek',
              _direction,
              const <String, String>{
                'received': 'Przychodzące',
                'sent': 'Wychodzące',
                'unknown': 'Nieznany',
              },
              (v) {
                _direction = v;
                _reload();
              },
            ),
            _menu(
              'Stan',
              _readState,
              const <String, String>{
                'read': 'Przeczytane',
                'unread': 'Nieprzeczytane',
                'unknown': 'Nieznany',
              },
              (v) {
                _readState = v;
                _reload();
              },
            ),
            _menu(
              'Klient',
              _linked?.toString(),
              const <String, String>{
                'true': 'Przypisane',
                'false': 'Nieprzypisane',
              },
              (v) {
                _linked = v == null ? null : v == 'true';
                _reload();
              },
            ),
            FilterChip(
              label: const Text('Załączniki'),
              selected: _attachments == true,
              onSelected: (v) {
                _attachments = v ? true : null;
                _reload();
              },
            ),
            TextButton.icon(
              onPressed: _pickDates,
              icon: const Icon(Icons.date_range),
              label: Text(
                _dates == null
                    ? 'Daty'
                    : '${formatPolishDate(_dates!.start)}–${formatPolishDate(_dates!.end)}',
              ),
            ),
          ],
        ),
      ),
      const SizedBox(height: 8),
      Expanded(child: _listBody()),
    ],
  );

  Widget _menu(
    String label,
    String? value,
    Map<String, String> values,
    ValueChanged<String?> onChanged,
  ) => Padding(
    padding: const EdgeInsets.only(right: 8),
    child: DropdownButton<String?>(
      value: value,
      hint: Text(label),
      items: <DropdownMenuItem<String?>>[
        DropdownMenuItem<String?>(
          value: null,
          child: Text('$label: wszystkie'),
        ),
        ...values.entries.map(
          (e) => DropdownMenuItem<String?>(value: e.key, child: Text(e.value)),
        ),
      ],
      onChanged: onChanged,
    ),
  );

  Widget _listBody() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Text(_error!),
            const SizedBox(height: 8),
            FilledButton(
              onPressed: _reload,
              child: const Text('Spróbuj ponownie'),
            ),
          ],
        ),
      );
    }
    if (_items.isEmpty) {
      return const Center(
        child: Text('Brak wiadomości dla wybranych filtrów.'),
      );
    }
    return ListView.builder(
      key: const Key('mail-list'),
      itemCount: _items.length + (_hasMore ? 1 : 0),
      itemBuilder: (context, index) {
        if (index == _items.length) {
          return Center(
            child: TextButton(
              onPressed: _loadMore,
              child: Text(_loadingMore ? 'Ładowanie…' : 'Pokaż więcej'),
            ),
          );
        }
        final item = _items[index];
        return ListTile(
          selected: _selected?.sourceId == item.sourceId,
          leading: Icon(
            item.direction == 'sent' ? Icons.north_east : Icons.south_west,
          ),
          title: Text(
            item.subject ?? '(bez tematu)',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          subtitle: Text(
            '${item.sender ?? item.recipients.join(', ')}\n${item.clientName ?? 'Nieprzypisany'} · ${formatPolishDateTime(item.occurredAt)}',
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          trailing: Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              if (item.hasAttachments) const Icon(Icons.attach_file, size: 18),
              Icon(
                item.readState == 'unread'
                    ? Icons.mark_email_unread_outlined
                    : item.readState == 'read'
                    ? Icons.drafts_outlined
                    : Icons.help_outline,
                size: 18,
              ),
            ],
          ),
          onTap: () => _open(item),
        );
      },
    );
  }

  Widget _detail(GlobalMailItem item) {
    return ListView(
      key: const Key('mail-detail'),
      padding: const EdgeInsets.all(20),
      children: <Widget>[
        Text(
          item.subject ?? '(bez tematu)',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 12),
        Text('Od: ${item.sender ?? '—'}'),
        Text('Do: ${item.recipients.join(', ')}'),
        if (item.cc.isNotEmpty) Text('DW: ${item.cc.join(', ')}'),
        Text(formatPolishDateTime(item.occurredAt)),
        Wrap(
          spacing: 8,
          children: <Widget>[
            if (item.clientId != null)
              ActionChip(
                label: Text(item.clientName ?? 'Klient #${item.clientId}'),
                avatar: const Icon(Icons.person, size: 18),
                onPressed: () => context.push('/clients/${item.clientId}'),
              ),
            if (item.threadId != null)
              ActionChip(
                label: const Text('Pokaż wątek'),
                avatar: const Icon(Icons.forum_outlined, size: 18),
                onPressed: () => _showThread(item.threadId!),
              ),
          ],
        ),
        const Divider(height: 32),
        SelectableText(item.bodyText ?? 'Brak treści tekstowej.'),
        if (item.attachments.isNotEmpty) ...<Widget>[
          const Divider(height: 32),
          Text('Załączniki', style: Theme.of(context).textTheme.titleMedium),
          ...item.attachments.map(
            (GlobalMailAttachment attachment) => ListTile(
              leading: const Icon(Icons.description_outlined),
              title: Text(
                attachment.filename ?? 'Dokument #${attachment.documentId}',
              ),
              subtitle: Text(
                '${attachment.mimeType ?? 'typ nieznany'} · '
                '${attachment.processingStatus}',
              ),
              onTap: () => context.push(
                '/documents?document_id=${attachment.documentId}',
              ),
            ),
          ),
        ],
      ],
    );
  }

  Future<void> _showThread(String threadId) async {
    final session = _session;
    if (session == null) return;
    final items = await _api.thread(session, threadId);
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Wątek'),
        content: SizedBox(
          width: 600,
          child: ListView(
            shrinkWrap: true,
            children: items
                .map(
                  (item) => ListTile(
                    title: Text(item.subject ?? '(bez tematu)'),
                    subtitle: Text(formatPolishDateTime(item.occurredAt)),
                    onTap: () {
                      Navigator.pop(context);
                      _open(item);
                    },
                  ),
                )
                .toList(),
          ),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Zamknij'),
          ),
        ],
      ),
    );
  }

  Future<void> _pickDates() async {
    final range = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2000),
      lastDate: DateTime.now(),
      initialDateRange: _dates,
    );
    if (range != null) {
      setState(() => _dates = range);
      await _reload();
    }
  }
}
