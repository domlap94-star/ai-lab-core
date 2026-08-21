import 'dart:async';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/widgets/app_shell.dart';
import '../../auth/application/auth_controller.dart';
import '../application/knowledge_base_providers.dart';
import '../domain/knowledge_base_models.dart';

const Map<String, String> _categories = <String, String>{
  'norms': 'Normy',
  'technical_datasheets': 'Karty techniczne',
  'manuals': 'Instrukcje',
  'producer_materials': 'Materiały producentów',
  'formulas': 'Wzory',
  'reference_calculations': 'Obliczenia referencyjne',
  'other': 'Inne',
};

String _processingLabel(String value) =>
    <String, String>{
      'uploaded': 'Przesłano',
      'queued': 'W kolejce',
      'extracting': 'Ekstrakcja',
      'ocr': 'OCR',
      'processed': 'Wyodrębniono',
      'failed': 'Błąd',
    }[value] ??
    value;

String _analysisLabel(String value) =>
    <String, String>{
      'not_required': 'Analiza niewymagana',
      'local_pending': 'Analiza lokalna oczekuje',
      'local_processing': 'Analiza lokalna',
      'local_accepted': 'Analiza lokalna gotowa',
      'advanced_required': 'Wymagana analiza zaawansowana',
      'advanced_queued': 'Analiza zaawansowana w kolejce',
      'advanced_processing': 'Analiza zaawansowana',
      'awaiting_auth': 'Oczekuje na logowanie',
      'awaiting_ui_fix': 'Oczekuje na poprawkę integracji',
      'advanced_validating': 'Walidacja',
      'advanced_accepted': 'Gotowe',
      'review_required': 'Wymaga przeglądu',
      'failed': 'Błąd',
    }[value] ??
    value;

String _indexingLabel(String value) =>
    <String, String>{
      'not_ready': 'Niezaindeksowany',
      'pending': 'Oczekuje na indeks',
      'indexing': 'Indeksowanie',
      'indexed': 'Zaindeksowany',
      'failed': 'Błąd indeksu',
    }[value] ??
    value;

class AdminKnowledgeBasePage extends ConsumerStatefulWidget {
  const AdminKnowledgeBasePage({super.key});
  @override
  ConsumerState<AdminKnowledgeBasePage> createState() =>
      _AdminKnowledgeBasePageState();
}

class _AdminKnowledgeBasePageState
    extends ConsumerState<AdminKnowledgeBasePage> {
  final _search = TextEditingController();
  String? _category;
  String? _status;
  bool _loading = true;
  String? _error;
  List<KnowledgeBaseItem> _items = const <KnowledgeBaseItem>[];
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_load);
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await ref
          .read(knowledgeBaseApiProvider)
          .list(
            requireKnowledgeBaseSession(ref),
            query: _search.text.trim().isEmpty ? null : _search.text.trim(),
            category: _category,
            status: _status,
          );
      if (mounted) {
        setState(() => _items = result.items);
        _schedulePolling();
      }
    } catch (error) {
      if (mounted) setState(() => _error = '$error');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _schedulePolling() {
    _pollTimer?.cancel();
    const terminalProcessing = <String>{'processed', 'failed'};
    const terminalAnalysis = <String>{
      'not_required',
      'local_accepted',
      'advanced_accepted',
      'review_required',
      'failed',
    };
    final pending = _items.any(
      (item) =>
          !terminalProcessing.contains(item.processingStatus) ||
          !terminalAnalysis.contains(item.analysisStatus),
    );
    if (pending && mounted) {
      _pollTimer = Timer(const Duration(seconds: 2), _load);
    }
  }

  Future<void> _openEditor([KnowledgeBaseItem? item]) async {
    final changed = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => _KnowledgeBaseEditor(
        item: item,
        onSave: (Map<String, dynamic> metadata, _SelectedFile? file) async {
          final api = ref.read(knowledgeBaseApiProvider);
          final session = requireKnowledgeBaseSession(ref);
          if (item == null) {
            if (file == null) {
              throw StateError('Wybierz plik.');
            }
            await api.create(
              session,
              metadata: metadata,
              bytes: file.bytes,
              filename: file.name,
            );
          } else {
            await api.update(session, item.id, metadata);
          }
        },
      ),
    );
    if (changed == true) await _load();
  }

  Future<void> _showDetails(KnowledgeBaseItem item) async {
    final detail = await ref
        .read(knowledgeBaseApiProvider)
        .detail(requireKnowledgeBaseSession(ref), item.id);
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(detail.title),
        content: SizedBox(
          width: 620,
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Text(
                  '${_categories[detail.category]} • ${detail.publisher ?? 'Brak wydawcy'} • ${detail.version ?? 'bez wersji'}',
                ),
                const SizedBox(height: 8),
                Text('Źródło: ${detail.source}'),
                Text('Plik: ${detail.originalFilename}'),
                Text(
                  'Status: ${detail.status == 'current' ? 'Aktualny' : 'Zastąpiony'}',
                ),
                Text(
                  'Przetwarzanie: ${detail.processingStatus} (${detail.processingMethod ?? '—'})',
                ),
                Text('Analiza: ${_analysisLabel(detail.analysisStatus)}'),
                Text('Indeks: ${_indexingLabel(detail.indexingStatus)}'),
                if (detail.analysisReason != null)
                  Text('Powód: ${detail.analysisReason}'),
                const Divider(),
                Text(
                  'Cytowania / strony',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                if (detail.pages.isEmpty)
                  const Text('Brak wyodrębnionych stron.')
                else
                  ...detail.pages.take(20).map((page) {
                    final text = page.text ?? 'Brak tekstu';
                    return ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: CircleAvatar(child: Text('${page.page}')),
                      title: Text('Strona ${page.page} • ${page.method}'),
                      subtitle: Text(
                        text.substring(
                          0,
                          text.length > 260 ? 260 : text.length,
                        ),
                      ),
                    );
                  }),
              ],
            ),
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

  @override
  Widget build(BuildContext context) {
    final role =
        ref.watch(authControllerProvider).value?.user?.role.toLowerCase() ?? '';
    if (role != 'admin' && role != 'administrator') {
      return const Scaffold(body: Center(child: Text('Brak uprawnień.')));
    }
    return Scaffold(
      appBar: AppBar(
        leading: AppShell.mobileNavigationLeading(context),
        title: const Text('Baza wiedzy'),
        actions: <Widget>[AppShell.globalSearchAction(context)],
      ),
      floatingActionButton: FloatingActionButton.extended(
        key: const Key('knowledge-base-add'),
        onPressed: () => _openEditor(),
        icon: const Icon(Icons.add),
        label: const Text('Dodaj materiał'),
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
          children: <Widget>[
            Text(
              'Materiały techniczne i referencyjne',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const Text(
              'Oddzielna przestrzeń od dokumentów klientów. Wyszukiwanie działa po metadanych i wyodrębnionym tekście.',
            ),
            const SizedBox(height: 16),
            LayoutBuilder(
              builder: (context, constraints) {
                final narrow = constraints.maxWidth < 600;
                final fields = <Widget>[
                  TextField(
                    controller: _search,
                    decoration: const InputDecoration(
                      labelText: 'Szukaj',
                      prefixIcon: Icon(Icons.search),
                    ),
                    onSubmitted: (_) => _load(),
                  ),
                  DropdownButtonFormField<String>(
                    isExpanded: true,
                    initialValue: _category,
                    decoration: const InputDecoration(labelText: 'Kategoria'),
                    items: <DropdownMenuItem<String>>[
                      const DropdownMenuItem(
                        value: null,
                        child: Text('Wszystkie'),
                      ),
                      ..._categories.entries.map(
                        (entry) => DropdownMenuItem(
                          value: entry.key,
                          child: Text(entry.value),
                        ),
                      ),
                    ],
                    onChanged: (value) {
                      _category = value;
                      _load();
                    },
                  ),
                  DropdownButtonFormField<String>(
                    isExpanded: true,
                    initialValue: _status,
                    decoration: const InputDecoration(labelText: 'Status'),
                    items: const <DropdownMenuItem<String>>[
                      DropdownMenuItem(value: null, child: Text('Wszystkie')),
                      DropdownMenuItem(
                        value: 'current',
                        child: Text('Aktualne'),
                      ),
                      DropdownMenuItem(
                        value: 'superseded',
                        child: Text('Zastąpione'),
                      ),
                    ],
                    onChanged: (value) {
                      _status = value;
                      _load();
                    },
                  ),
                ];
                return narrow
                    ? Column(
                        children: fields
                            .map(
                              (w) => Padding(
                                padding: const EdgeInsets.only(bottom: 10),
                                child: w,
                              ),
                            )
                            .toList(),
                      )
                    : Row(
                        children: fields
                            .map(
                              (w) => Expanded(
                                child: Padding(
                                  padding: const EdgeInsets.only(right: 10),
                                  child: w,
                                ),
                              ),
                            )
                            .toList(),
                      );
              },
            ),
            const SizedBox(height: 12),
            if (_loading) const LinearProgressIndicator(),
            if (_error != null)
              Text(
                'Błąd: $_error',
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            if (!_loading && _items.isEmpty)
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: Text('Brak materiałów w Bazie wiedzy.'),
                ),
              ),
            ..._items.map(
              (item) => Card(
                child: ListTile(
                  isThreeLine: true,
                  title: Text(item.title),
                  subtitle: Text(
                    '${_categories[item.category] ?? item.category} • ${item.publisher ?? 'Brak wydawcy'} • ${item.version ?? 'bez wersji'}\n${item.status == 'current' ? 'Aktualny' : 'Zastąpiony'} • ${_processingLabel(item.processingStatus)} • ${_analysisLabel(item.analysisStatus)} • ${item.tags.join(', ')}',
                  ),
                  trailing: PopupMenuButton<String>(
                    onSelected: (value) async {
                      if (value == 'details') await _showDetails(item);
                      if (value == 'edit') await _openEditor(item);
                      if (value == 'retry') {
                        await ref
                            .read(knowledgeBaseApiProvider)
                            .retry(requireKnowledgeBaseSession(ref), item.id);
                        await _load();
                      }
                      if (value == 'archive') {
                        if (!context.mounted) return;
                        final confirmed = await showDialog<bool>(
                          context: context,
                          builder: (dialogContext) => AlertDialog(
                            title: const Text('Archiwizować materiał?'),
                            content: const Text(
                              'Materiał zniknie z aktywnej Bazy wiedzy. Plik nie zostanie usunięty fizycznie.',
                            ),
                            actions: <Widget>[
                              TextButton(
                                onPressed: () =>
                                    Navigator.pop(dialogContext, false),
                                child: const Text('Anuluj'),
                              ),
                              FilledButton(
                                onPressed: () =>
                                    Navigator.pop(dialogContext, true),
                                child: const Text('Archiwizuj'),
                              ),
                            ],
                          ),
                        );
                        if (confirmed == true) {
                          await ref
                              .read(knowledgeBaseApiProvider)
                              .archive(
                                requireKnowledgeBaseSession(ref),
                                item.id,
                              );
                          await _load();
                        }
                      }
                    },
                    itemBuilder: (_) => const <PopupMenuEntry<String>>[
                      PopupMenuItem(
                        value: 'details',
                        child: Text('Szczegóły i cytowania'),
                      ),
                      PopupMenuItem(
                        value: 'edit',
                        child: Text('Edytuj metadane'),
                      ),
                      PopupMenuItem(
                        value: 'retry',
                        child: Text('Ponów przetwarzanie'),
                      ),
                      PopupMenuItem(
                        value: 'archive',
                        child: Text('Archiwizuj'),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _KnowledgeBaseEditor extends StatefulWidget {
  const _KnowledgeBaseEditor({required this.item, required this.onSave});
  final KnowledgeBaseItem? item;
  final Future<void> Function(Map<String, dynamic>, _SelectedFile?) onSave;
  @override
  State<_KnowledgeBaseEditor> createState() => _KnowledgeBaseEditorState();
}

class _KnowledgeBaseEditorState extends State<_KnowledgeBaseEditor> {
  final _key = GlobalKey<FormState>();
  late final TextEditingController _title,
      _source,
      _publisher,
      _version,
      _date,
      _tags,
      _supersedes;
  late String _category, _status;
  _SelectedFile? _file;
  bool _busy = false;
  String? _error;
  @override
  void initState() {
    super.initState();
    final i = widget.item;
    _title = TextEditingController(text: i?.title);
    _source = TextEditingController(text: i?.source);
    _publisher = TextEditingController(text: i?.publisher);
    _version = TextEditingController(text: i?.version);
    _date = TextEditingController(text: i?.effectiveDate);
    _tags = TextEditingController(text: i?.tags.join(', '));
    _supersedes = TextEditingController(text: i?.supersedesId?.toString());
    _category = i?.category ?? 'norms';
    _status = i?.status ?? 'current';
  }

  @override
  void dispose() {
    for (final c in <TextEditingController>[
      _title,
      _source,
      _publisher,
      _version,
      _date,
      _tags,
      _supersedes,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (!_key.currentState!.validate() ||
        (widget.item == null && _file == null)) {
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.onSave(<String, dynamic>{
        'title': _title.text.trim(),
        'source': _source.text.trim(),
        'publisher': _publisher.text.trim().isEmpty
            ? null
            : _publisher.text.trim(),
        'version': _version.text.trim().isEmpty ? null : _version.text.trim(),
        'effective_date': _date.text.trim().isEmpty ? null : _date.text.trim(),
        'category': _category,
        'tags': _tags.text
            .split(',')
            .map((v) => v.trim())
            .where((v) => v.isNotEmpty)
            .toList(),
        'status': _status,
        'supersedes_id': int.tryParse(_supersedes.text.trim()),
      }, _file);
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(widget.item == null ? 'Dodaj materiał' : 'Edytuj metadane'),
    content: SizedBox(
      width: 560,
      child: Form(
        key: _key,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              TextFormField(
                controller: _title,
                decoration: const InputDecoration(labelText: 'Tytuł'),
                validator: (v) =>
                    v == null || v.trim().isEmpty ? 'Pole wymagane' : null,
              ),
              TextFormField(
                controller: _source,
                decoration: const InputDecoration(labelText: 'Źródło'),
                validator: (v) =>
                    v == null || v.trim().isEmpty ? 'Pole wymagane' : null,
              ),
              TextFormField(
                controller: _publisher,
                decoration: const InputDecoration(labelText: 'Wydawca'),
              ),
              TextFormField(
                controller: _version,
                decoration: const InputDecoration(labelText: 'Wersja'),
              ),
              TextFormField(
                controller: _date,
                decoration: const InputDecoration(
                  labelText: 'Data obowiązywania (RRRR-MM-DD)',
                ),
              ),
              DropdownButtonFormField<String>(
                isExpanded: true,
                initialValue: _category,
                decoration: const InputDecoration(labelText: 'Kategoria'),
                items: _categories.entries
                    .map(
                      (e) =>
                          DropdownMenuItem(value: e.key, child: Text(e.value)),
                    )
                    .toList(),
                onChanged: (v) => setState(() => _category = v!),
              ),
              DropdownButtonFormField<String>(
                isExpanded: true,
                initialValue: _status,
                decoration: const InputDecoration(labelText: 'Status'),
                items: const [
                  DropdownMenuItem(value: 'current', child: Text('Aktualny')),
                  DropdownMenuItem(
                    value: 'superseded',
                    child: Text('Zastąpiony'),
                  ),
                ],
                onChanged: (v) => setState(() => _status = v!),
              ),
              TextFormField(
                controller: _tags,
                decoration: const InputDecoration(
                  labelText: 'Tagi (oddzielone przecinkami)',
                ),
              ),
              TextFormField(
                controller: _supersedes,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Zastępuje materiał ID (opcjonalnie)',
                ),
                validator: (value) =>
                    value != null &&
                        value.trim().isNotEmpty &&
                        int.tryParse(value.trim()) == null
                    ? 'Podaj poprawny numer ID.'
                    : null,
              ),
              if (widget.item == null)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(_file?.name ?? 'Nie wybrano pliku'),
                  trailing: OutlinedButton.icon(
                    onPressed: _busy
                        ? null
                        : () async {
                            final files = await FilePicker.pickFiles();
                            if (files.isNotEmpty) {
                              final selected = files.single;
                              final bytes = await selected.readAsBytes();
                              setState(
                                () =>
                                    _file = _SelectedFile(selected.name, bytes),
                              );
                            }
                          },
                    icon: const Icon(Icons.attach_file),
                    label: const Text('Wybierz plik'),
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
    ),
    actions: <Widget>[
      TextButton(
        onPressed: _busy ? null : () => Navigator.pop(context, false),
        child: const Text('Anuluj'),
      ),
      FilledButton(
        onPressed: _busy ? null : _save,
        child: Text(_busy ? 'Zapisywanie...' : 'Zapisz'),
      ),
    ],
  );
}

class _SelectedFile {
  const _SelectedFile(this.name, this.bytes);

  final String name;
  final Uint8List bytes;
}
