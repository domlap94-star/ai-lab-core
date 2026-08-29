import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/formatters/polish_date_time.dart';
import '../../../core/network/friendly_api_error.dart';
import '../../../core/widgets/app_shell.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/domain/auth_session.dart';
import '../../documents/application/documents_providers.dart';
import '../../documents/domain/document.dart';
import '../../documents/presentation/document_media_preview.dart';
import '../../documents/presentation/document_presentation.dart';
import '../data/global_mail_api.dart';
import '../domain/global_mail.dart';
import 'ignored_mail_source_controls.dart';
import 'mail_reconciliation_dialog.dart';

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
  bool _reconciling = false;
  bool _hasMore = false;
  String? _error;
  String? _direction;
  String? _readState;
  bool? _linked;
  bool? _attachments;
  bool? _ignored;
  DateTimeRange? _dates;
  GlobalMailItem? _selected;

  GlobalMailApi get _api => ref.read(globalMailApiProvider);
  AuthSession? get _session => ref.read(authControllerProvider).value?.session;
  bool get _isAdmin =>
      ref.read(authControllerProvider).value?.user?.role == 'Administrator';

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
        ignored: _ignored,
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
        ignored: _ignored,
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
          actions: <Widget>[
            if (_isAdmin)
              IconButton(
                key: const Key('manage-ignored-mail-sources'),
                tooltip: 'Ignorowani nadawcy',
                onPressed: _manageIgnoredRules,
                icon: const Icon(Icons.block_outlined),
              ),
            IconButton(
              key: const Key('mail-reconcile'),
              tooltip: 'Odśwież skrzynkę',
              onPressed: _reconciling ? null : _reconcile,
              icon: _reconciling
                  ? const SizedBox.square(
                      dimension: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.sync),
            ),
            IconButton(
              key: const Key('mail-compose'),
              tooltip: 'Nowa wiadomość',
              onPressed: () => _compose('compose'),
              icon: const Icon(Icons.edit_outlined),
            ),
          ],
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

  Future<void> _reconcile() async {
    if (_reconciling) return;
    final AuthSession? session = _session;
    if (session == null) return;
    setState(() => _reconciling = true);
    try {
      final MailReconciliationDryRun dryRun = await _api.reconciliationDryRun(
        session,
      );
      MailReconciliationResult result = MailReconciliationResult.current(
        dryRun,
      );
      if (dryRun.missingCount > 0) {
        if (!mounted ||
            !await confirmMailReconciliation(
              context,
              dryRun,
              openedFromClient: false,
            )) {
          return;
        }
        result = await _api.reconciliationApply(session, dryRun);
      }
      await _reload();
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(result.userSummary)));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            friendlyApiError(
              error,
              fallback: 'Nie udało się odświeżyć skrzynki.',
            ),
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => _reconciling = false);
    }
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
            _menu(
              'Ignorowane',
              _ignored?.toString(),
              const <String, String>{
                'true': 'Tylko ignorowane',
                'false': 'Bez ignorowanych',
              },
              (v) {
                _ignored = v == null ? null : v == 'true';
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
              if (_isAdmin &&
                  item.direction == 'received' &&
                  canonicalIgnoredMailAddress(item.sender) != null)
                PopupMenuButton<String>(
                  key: ValueKey<String>('mail-ignore-menu-${item.sourceId}'),
                  tooltip: 'Opcje nadawcy',
                  onSelected: (_) => item.ignored
                      ? _manageIgnoredRules()
                      : _ignoreSender(item.sender!),
                  itemBuilder: (_) => <PopupMenuEntry<String>>[
                    PopupMenuItem<String>(
                      value: 'ignore',
                      child: Text(
                        item.ignored
                            ? 'Zarządzaj ignorowaniem'
                            : 'Ignoruj nadawcę',
                      ),
                    ),
                  ],
                ),
            ],
          ),
          onTap: () => _open(item),
        );
      },
    );
  }

  Future<void> _ignoreSender(String sender) async {
    final session = _session;
    if (session == null) return;
    final bool changed = await showIgnoreMailSenderDialog(
      context: context,
      api: _api,
      session: session,
      sender: sender,
    );
    if (changed && mounted) await _reload();
  }

  Future<void> _manageIgnoredRules() async {
    final AuthSession? session = _session;
    if (session == null) return;
    await showIgnoredMailSourcesDialog(
      context: context,
      api: _api,
      session: session,
    );
    if (mounted) await _reload();
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
            OutlinedButton.icon(
              key: const Key('mail-unified-assistant'),
              onPressed: item.clientId == null
                  ? null
                  : () => context.push(
                      '/ai?client_id=${item.clientId}&mail_source_id=${item.sourceId}&question=${Uri.encodeQueryComponent('Podsumuj tę wiadomość i wskaż najważniejsze działania.')}',
                    ),
              icon: const Icon(Icons.auto_awesome_outlined),
              label: const Text('Zapytaj AI'),
            ),
            FilledButton.tonalIcon(
              key: const Key('mail-reply'),
              onPressed: () => _compose('reply', source: item),
              icon: const Icon(Icons.reply),
              label: const Text('Odpowiedz'),
            ),
            OutlinedButton.icon(
              key: const Key('mail-forward'),
              onPressed: () => _compose('forward', source: item),
              icon: const Icon(Icons.forward),
              label: const Text('Przekaż dalej'),
            ),
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
            if (item.ignored)
              const Chip(
                avatar: Icon(Icons.block, size: 18),
                label: Text('Ignorowany nadawca'),
              ),
            if (_isAdmin &&
                item.direction == 'received' &&
                canonicalIgnoredMailAddress(item.sender) != null)
              ActionChip(
                key: const Key('ignore-mail-sender'),
                avatar: Icon(
                  item.ignored ? Icons.rule_outlined : Icons.block_outlined,
                  size: 18,
                ),
                label: Text(
                  item.ignored ? 'Zarządzaj ignorowaniem' : 'Ignoruj nadawcę',
                ),
                onPressed: () => item.ignored
                    ? _manageIgnoredRules()
                    : _ignoreSender(item.sender!),
              ),
          ],
        ),
        const Divider(height: 32),
        SelectableText(item.bodyText ?? 'Brak treści tekstowej.'),
        if (item.attachments.isNotEmpty) ...<Widget>[
          const Divider(height: 32),
          Text('Załączniki', style: Theme.of(context).textTheme.titleMedium),
          ...item.attachments.map(_attachmentTile),
        ],
      ],
    );
  }

  Widget _attachmentTile(GlobalMailAttachment attachment) {
    final String filename =
        attachment.filename ?? 'Dokument #${attachment.documentId}';
    final String contentType = attachment.mimeType ?? '';
    final bool image = isInternalPreviewImage(contentType, filename);
    return Card(
      child: InkWell(
        onTap: image
            ? () => _openAttachment(attachment)
            : () => context.push(
                '/documents?document_id=${attachment.documentId}',
              ),
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Row(
            children: <Widget>[
              if (image)
                DocumentImageThumbnail(
                  documentId: attachment.documentId,
                  contentType: contentType,
                  fileName: filename,
                  onOpen: () => _openAttachment(attachment),
                )
              else
                const SizedBox(
                  width: documentThumbnailWidth,
                  child: Icon(Icons.description_outlined),
                ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      filename,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${attachment.mimeType ?? 'typ nieznany'} · '
                      '${attachment.processingStatus}',
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _openAttachment(GlobalMailAttachment attachment) async {
    final AuthSession? session = _session;
    if (session == null) return;
    try {
      final RepositoryDocument document = await ref
          .read(documentsRepositoryProvider)
          .fetchDocument(session: session, documentId: attachment.documentId);
      if (!mounted) return;
      await openDocumentMedia(context, ref, document);
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Nie udało się otworzyć załącznika: ${friendlyDocumentError(error)}',
          ),
        ),
      );
    }
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

  String _operationId() {
    final Random random = Random.secure();
    String hex(int count) => List<String>.generate(
      count,
      (_) => random.nextInt(16).toRadixString(16),
    ).join();
    return '${hex(8)}-${hex(4)}-4${hex(3)}-${(8 + random.nextInt(4)).toRadixString(16)}${hex(3)}-${hex(12)}';
  }

  Future<void> _compose(String action, {GlobalMailItem? source}) async {
    final TextEditingController to = TextEditingController(
      text: action == 'reply' ? (source?.sender ?? '') : '',
    );
    final TextEditingController cc = TextEditingController();
    final TextEditingController bcc = TextEditingController();
    final TextEditingController subject = TextEditingController(
      text: action == 'reply'
          ? 'Re: ${source?.subject ?? ''}'
          : action == 'forward'
          ? 'Fwd: ${source?.subject ?? ''}'
          : '',
    );
    final TextEditingController body = TextEditingController();
    bool includeAttachments = false;
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => StatefulBuilder(
        builder: (BuildContext context, StateSetter setModalState) => AlertDialog(
          title: Text(
            action == 'compose'
                ? 'Nowa wiadomość'
                : action == 'reply'
                ? 'Odpowiedz'
                : 'Przekaż dalej',
          ),
          content: SizedBox(
            width: 620,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  if (action != 'reply')
                    TextField(
                      key: const Key('mail-to'),
                      controller: to,
                      decoration: const InputDecoration(labelText: 'Do'),
                    ),
                  if (action != 'reply')
                    TextField(
                      controller: cc,
                      decoration: const InputDecoration(labelText: 'DW'),
                    ),
                  if (action != 'reply')
                    TextField(
                      controller: bcc,
                      decoration: const InputDecoration(labelText: 'UDW'),
                    ),
                  if (action != 'reply')
                    TextField(
                      key: const Key('mail-subject'),
                      controller: subject,
                      decoration: const InputDecoration(labelText: 'Temat'),
                    ),
                  TextField(
                    key: const Key('mail-body'),
                    controller: body,
                    minLines: 6,
                    maxLines: 14,
                    decoration: const InputDecoration(labelText: 'Treść'),
                  ),
                  if (source?.attachments.isNotEmpty == true)
                    CheckboxListTile(
                      value: includeAttachments,
                      onChanged: (bool? value) => setModalState(
                        () => includeAttachments = value == true,
                      ),
                      title: const Text('Dołącz widoczne załączniki'),
                    ),
                ],
              ),
            ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Anuluj'),
            ),
            FilledButton(
              key: const Key('mail-review-send'),
              onPressed: () async {
                if (to.text.trim().isEmpty ||
                    body.text.trim().isEmpty ||
                    (action != 'reply' && subject.text.trim().isEmpty)) {
                  return;
                }
                final bool? send = await showDialog<bool>(
                  context: context,
                  builder: (BuildContext context) => AlertDialog(
                    title: const Text('Wyślij wiadomość?'),
                    content: Text(
                      'Do: ${to.text.trim()}\nTemat: ${subject.text.trim()}\nZałączniki: ${includeAttachments ? source?.attachments.length ?? 0 : 0}',
                    ),
                    actions: <Widget>[
                      TextButton(
                        onPressed: () => Navigator.pop(context, false),
                        child: const Text('Wróć'),
                      ),
                      FilledButton(
                        key: const Key('mail-confirm-send'),
                        onPressed: () => Navigator.pop(context, true),
                        child: const Text('Wyślij'),
                      ),
                    ],
                  ),
                );
                if (send == true && context.mounted) {
                  Navigator.pop(context, true);
                }
              },
              child: const Text('Dalej'),
            ),
          ],
        ),
      ),
    );
    if (confirmed != true || !mounted) return;
    final AuthSession? session = _session;
    if (session == null) return;
    final String operationId = _operationId();
    try {
      final MailSendResult result = await _api.send(
        session,
        operationId: operationId,
        to: to.text
            .split(',')
            .map((String value) => value.trim())
            .where((String value) => value.isNotEmpty)
            .toList(),
        cc: cc.text
            .split(',')
            .map((String value) => value.trim())
            .where((String value) => value.isNotEmpty)
            .toList(),
        bcc: bcc.text
            .split(',')
            .map((String value) => value.trim())
            .where((String value) => value.isNotEmpty)
            .toList(),
        subject: subject.text.trim(),
        body: body.text.trim(),
        attachmentDocumentIds: includeAttachments
            ? source?.attachments
                      .map((GlobalMailAttachment item) => item.documentId)
                      .toList() ??
                  const <int>[]
            : const <int>[],
        clientId: source?.clientId,
        sourceId: source?.sourceId,
        action: action,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            result.status == 'canonical_synced'
                ? 'Wiadomość wysłana.'
                : 'Stan wysyłki: ${result.status}',
          ),
        ),
      );
      if (result.status == 'canonical_synced') {
        await _reload();
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              friendlyApiError(
                error,
                fallback: 'Nie udało się wysłać wiadomości.',
              ),
            ),
          ),
        );
      }
    } finally {
      to.dispose();
      cc.dispose();
      bcc.dispose();
      subject.dispose();
      body.dispose();
    }
  }
}
