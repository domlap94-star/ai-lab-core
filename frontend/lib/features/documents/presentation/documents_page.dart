import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/widgets/app_shell.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/domain/auth_session.dart';
import '../../clients/application/clients_providers.dart';
import '../../clients/application/clients_repository.dart';
import '../../clients/domain/client.dart';
import '../application/documents_controller.dart';
import '../application/documents_providers.dart';
import '../application/documents_repository.dart';
import '../domain/document.dart';
import '../domain/document_client_match.dart';
import '../domain/document_filters.dart';
import '../domain/document_page.dart';
import 'document_presentation.dart';
import 'document_intake_dialog.dart';
import 'document_media_preview.dart';
import 'document_trash_action.dart';

class DocumentsPage extends ConsumerStatefulWidget {
  const DocumentsPage({super.key});

  @override
  ConsumerState<DocumentsPage> createState() => _DocumentsPageState();
}

class _DocumentsPageState extends ConsumerState<DocumentsPage> {
  final TextEditingController _searchController = TextEditingController();
  Timer? _searchDebounce;
  final Set<int> _openingIds = <int>{};
  final Map<int, double?> _openProgress = <int, double?>{};

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final AsyncValue<DocumentPage> documents = ref.watch(
      documentsControllerProvider,
    );
    final DocumentsController controller = ref.read(
      documentsControllerProvider.notifier,
    );

    return Scaffold(
      appBar: AppBar(
        leading: AppShell.mobileNavigationLeading(context),
        title: const Text('Repozytorium dokumentów'),
        actions: <Widget>[
          AppShell.globalSearchAction(context),
          IconButton(
            key: const Key('global-document-upload'),
            tooltip: 'Dodaj dokumenty',
            onPressed: _showUpload,
            icon: const Icon(Icons.upload_file),
          ),
          IconButton(
            tooltip: 'Odśwież',
            onPressed: controller.refresh,
            icon: const Icon(Icons.refresh),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: <Widget>[
            _buildToolbar(context, controller, documents.value),
            Expanded(
              child: documents.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (Object error, StackTrace _) => _ErrorState(
                  message: friendlyDocumentError(error),
                  onRetry: controller.refresh,
                ),
                data: (DocumentPage page) => _buildResults(page, controller),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _showUpload() async {
    final session = ref.read(authControllerProvider).value?.session;
    if (session == null || !mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => DocumentIntakeDialog(
        repository: ref.read(documentsRepositoryProvider),
        session: session,
        onCompleted: () =>
            ref.read(documentsControllerProvider.notifier).refresh(),
      ),
    );
  }

  Widget _buildToolbar(
    BuildContext context,
    DocumentsController controller,
    DocumentPage? page,
  ) {
    final DocumentFilters filters = controller.filters;
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerLowest,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Expanded(
                  child: TextField(
                    key: const Key('document-search'),
                    controller: _searchController,
                    decoration: InputDecoration(
                      labelText: 'Szukaj dokumentów',
                      hintText: 'Nazwa pliku, klient, kandydat lub typ treści',
                      prefixIcon: const Icon(Icons.search),
                      suffixIcon: _searchController.text.isEmpty
                          ? null
                          : IconButton(
                              tooltip: 'Wyczyść wyszukiwanie',
                              onPressed: () {
                                _searchDebounce?.cancel();
                                _searchController.clear();
                                setState(() {});
                                controller.search('');
                              },
                              icon: const Icon(Icons.close),
                            ),
                      border: const OutlineInputBorder(),
                    ),
                    onChanged: (String value) {
                      setState(() {});
                      _searchDebounce?.cancel();
                      _searchDebounce = Timer(
                        const Duration(milliseconds: 400),
                        () => controller.search(value),
                      );
                    },
                  ),
                ),
                const SizedBox(width: 16),
                Text(
                  page == null ? 'Ładowanie…' : '${page.total} dokumentów',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ],
            ),
            const SizedBox(height: 12),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: <Widget>[
                  _FilterDropdown<DocumentLinkState>(
                    label: 'Powiązanie',
                    value: filters.linkState,
                    values: DocumentLinkState.values,
                    labelFor: (DocumentLinkState value) => value.label,
                    onChanged: (DocumentLinkState? value) {
                      if (value != null) {
                        controller.setFilters(
                          filters.copyWith(linkState: value),
                        );
                      }
                    },
                  ),
                  _FilterDropdown<String?>(
                    label: 'Źródło',
                    value: filters.sourceType,
                    values: const <String?>[null, 'gmail', 'upload', 'archive'],
                    labelFor: (String? value) => value == null
                        ? 'Wszystkie'
                        : documentSourceLabel(value),
                    onChanged: (String? value) => controller.setFilters(
                      filters.copyWith(
                        sourceType: value,
                        clearSourceType: value == null,
                      ),
                    ),
                  ),
                  _FilterDropdown<String?>(
                    label: 'Dopasowanie',
                    value: filters.matchStatus,
                    values: const <String?>[
                      null,
                      'unmatched',
                      'suggested',
                      'matched',
                      'confirmed',
                      'rejected',
                    ],
                    labelFor: (String? value) =>
                        value == null ? 'Wszystkie' : documentMatchLabel(value),
                    onChanged: (String? value) => controller.setFilters(
                      filters.copyWith(
                        matchStatus: value,
                        clearMatchStatus: value == null,
                      ),
                    ),
                  ),
                  _FilterDropdown<String?>(
                    label: 'Przetwarzanie',
                    value: filters.processingStatus,
                    values: const <String?>[
                      null,
                      'pending',
                      'stored',
                      'extracting',
                      'processed',
                      'failed',
                    ],
                    labelFor: (String? value) => value == null
                        ? 'Wszystkie'
                        : documentProcessingLabel(value),
                    onChanged: (String? value) => controller.setFilters(
                      filters.copyWith(
                        processingStatus: value,
                        clearProcessingStatus: value == null,
                      ),
                    ),
                  ),
                  _FilterDropdown<String?>(
                    label: 'Typ treści',
                    value: filters.contentType,
                    values: const <String?>[
                      null,
                      'application/pdf',
                      'image/jpeg',
                      'image/png',
                      'message/rfc822',
                      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    ],
                    labelFor: (String? value) => value == null
                        ? 'Wszystkie'
                        : documentContentTypeLabel(value),
                    onChanged: (String? value) => controller.setFilters(
                      filters.copyWith(
                        contentType: value,
                        clearContentType: value == null,
                      ),
                    ),
                  ),
                  if (filters.clientId != null)
                    Padding(
                      padding: const EdgeInsets.only(right: 10),
                      child: InputChip(
                        label: Text('Klient: ${filters.clientName}'),
                        onDeleted: () => controller.setFilters(
                          filters.copyWith(clearClient: true),
                        ),
                      ),
                    ),
                  if (filters.isActive)
                    TextButton.icon(
                      onPressed: controller.clearFilters,
                      icon: const Icon(Icons.filter_alt_off),
                      label: const Text('Wyczyść filtry'),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResults(DocumentPage page, DocumentsController controller) {
    if (page.items.isEmpty) return const _EmptyState();

    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final Widget content = constraints.maxWidth >= 960
            ? _DocumentTable(
                documents: page.items,
                openingIds: _openingIds,
                progress: _openProgress,
                onDetails: _showDetails,
                onOpen: _openDocument,
                onClient: controller.filterByClient,
              )
            : _DocumentCards(
                documents: page.items,
                openingIds: _openingIds,
                progress: _openProgress,
                onDetails: _showDetails,
                onOpen: _openDocument,
                onClient: controller.filterByClient,
              );

        return Column(
          children: <Widget>[
            Expanded(child: content),
            _PaginationBar(
              page: page,
              onPrevious: controller.previousPage,
              onNext: controller.nextPage,
            ),
          ],
        );
      },
    );
  }

  Future<void> _openDocument(RepositoryDocument document) async {
    setState(() {
      _openingIds.add(document.id);
      _openProgress[document.id] = null;
    });
    try {
      await openDocumentMedia(
        context,
        ref,
        document,
        onProgress: (int received, int total) {
          if (!mounted) return;
          setState(() {
            _openProgress[document.id] = total > 0 ? received / total : null;
          });
        },
      );
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Nie udało się otworzyć pliku: ${friendlyDocumentError(error)}',
            ),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _openingIds.remove(document.id);
          _openProgress.remove(document.id);
        });
      }
    }
  }

  void _showDetails(RepositoryDocument document) {
    showDialog<void>(
      context: context,
      builder: (BuildContext context) => _DocumentDetailsDialog(
        documentId: document.id,
        onOpen: _openDocument,
      ),
    );
  }
}

class _FilterDropdown<T> extends StatelessWidget {
  const _FilterDropdown({
    required this.label,
    required this.value,
    required this.values,
    required this.labelFor,
    required this.onChanged,
  });

  final String label;
  final T value;
  final List<T> values;
  final String Function(T value) labelFor;
  final ValueChanged<T?> onChanged;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 10),
      child: DropdownMenu<T>(
        width: 190,
        label: Text(label),
        initialSelection: value,
        dropdownMenuEntries: values
            .map(
              (T item) =>
                  DropdownMenuEntry<T>(value: item, label: labelFor(item)),
            )
            .toList(growable: false),
        onSelected: onChanged,
      ),
    );
  }
}

class _DocumentTable extends StatelessWidget {
  const _DocumentTable({
    required this.documents,
    required this.openingIds,
    required this.progress,
    required this.onDetails,
    required this.onOpen,
    required this.onClient,
  });

  final List<RepositoryDocument> documents;
  final Set<int> openingIds;
  final Map<int, double?> progress;
  final ValueChanged<RepositoryDocument> onDetails;
  final ValueChanged<RepositoryDocument> onOpen;
  final void Function(int id, String name) onClient;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: SizedBox(
        width: double.infinity,
        child: DataTable(
          dataRowMinHeight: 96,
          dataRowMaxHeight: 112,
          showCheckboxColumn: false,
          columns: const <DataColumn>[
            DataColumn(label: Text('Nazwa')),
            DataColumn(label: Text('Typ')),
            DataColumn(label: Text('Źródło')),
            DataColumn(label: Text('Powiązanie')),
            DataColumn(label: Text('Status')),
            DataColumn(label: Text('Data')),
            DataColumn(label: Text('Akcje')),
          ],
          rows: documents
              .map((RepositoryDocument document) {
                return DataRow(
                  onSelectChanged: (_) => onDetails(document),
                  cells: <DataCell>[
                    DataCell(
                      ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 390),
                        child: Row(
                          children: <Widget>[
                            if (isInternalPreviewImage(
                              document.contentType,
                              document.displayName,
                            )) ...<Widget>[
                              DocumentImageThumbnail(
                                documentId: document.id,
                                contentType: document.contentType,
                                fileName: document.displayName,
                                onOpen: () => onOpen(document),
                              ),
                              const SizedBox(width: 10),
                            ],
                            Expanded(
                              child: InkWell(
                                onTap:
                                    isInternalPreviewImage(
                                      document.contentType,
                                      document.displayName,
                                    )
                                    ? () => onOpen(document)
                                    : null,
                                child: Text(
                                  document.displayName,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    DataCell(
                      Text(documentContentTypeLabel(document.contentType)),
                    ),
                    DataCell(Text(documentSourceLabel(document.sourceType))),
                    DataCell(
                      _LinkedEntity(document: document, onClient: onClient),
                    ),
                    DataCell(_StatusChip(value: document.processingStatus)),
                    DataCell(
                      Text(
                        formatDocumentDate(
                          document.capturedAt ?? document.createdAt,
                        ),
                      ),
                    ),
                    DataCell(
                      _OpenButton(
                        document: document,
                        opening: openingIds.contains(document.id),
                        progress: progress[document.id],
                        onPressed: onOpen,
                      ),
                    ),
                  ],
                );
              })
              .toList(growable: false),
        ),
      ),
    );
  }
}

class _DocumentCards extends StatelessWidget {
  const _DocumentCards({
    required this.documents,
    required this.openingIds,
    required this.progress,
    required this.onDetails,
    required this.onOpen,
    required this.onClient,
  });

  final List<RepositoryDocument> documents;
  final Set<int> openingIds;
  final Map<int, double?> progress;
  final ValueChanged<RepositoryDocument> onDetails;
  final ValueChanged<RepositoryDocument> onOpen;
  final void Function(int id, String name) onClient;

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.all(12),
      itemCount: documents.length,
      separatorBuilder: (_, _) => const SizedBox(height: 8),
      itemBuilder: (BuildContext context, int index) {
        final RepositoryDocument document = documents[index];
        return Card(
          child: InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: () => onDetails(document),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      if (isInternalPreviewImage(
                        document.contentType,
                        document.displayName,
                      ))
                        DocumentImageThumbnail(
                          documentId: document.id,
                          contentType: document.contentType,
                          fileName: document.displayName,
                          onOpen: () => onOpen(document),
                        )
                      else
                        const Icon(Icons.description_outlined),
                      const SizedBox(width: 10),
                      Expanded(
                        child: InkWell(
                          onTap:
                              isInternalPreviewImage(
                                document.contentType,
                                document.displayName,
                              )
                              ? () => onOpen(document)
                              : null,
                          child: Text(
                            document.displayName,
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: _StatusChip(value: document.processingStatus),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '${documentContentTypeLabel(document.contentType)} • '
                    '${documentSourceLabel(document.sourceType)} • '
                    '${formatDocumentBytes(document.fileSize)}',
                  ),
                  const SizedBox(height: 6),
                  _LinkedEntity(document: document, onClient: onClient),
                  const SizedBox(height: 8),
                  Row(
                    children: <Widget>[
                      Expanded(
                        child: Text(
                          formatDocumentDate(
                            document.capturedAt ?? document.createdAt,
                          ),
                        ),
                      ),
                      _OpenButton(
                        document: document,
                        opening: openingIds.contains(document.id),
                        progress: progress[document.id],
                        onPressed: onOpen,
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class _LinkedEntity extends StatelessWidget {
  const _LinkedEntity({required this.document, required this.onClient});
  final RepositoryDocument document;
  final void Function(int id, String name) onClient;

  @override
  Widget build(BuildContext context) {
    if (document.clientId != null && document.clientName != null) {
      return TextButton(
        onPressed: () => onClient(document.clientId!, document.clientName!),
        child: Text(document.clientName!),
      );
    }
    if (document.candidateName != null) {
      return Text('Kandydat: ${document.candidateName}');
    }
    return const Text('Niepowiązany');
  }
}

class _OpenButton extends StatelessWidget {
  const _OpenButton({
    required this.document,
    required this.opening,
    required this.progress,
    required this.onPressed,
  });
  final RepositoryDocument document;
  final bool opening;
  final double? progress;
  final ValueChanged<RepositoryDocument> onPressed;

  @override
  Widget build(BuildContext context) {
    if (opening) {
      return SizedBox(
        width: 32,
        height: 32,
        child: CircularProgressIndicator(value: progress, strokeWidth: 3),
      );
    }
    return IconButton(
      tooltip: 'Otwórz plik',
      onPressed: () => onPressed(document),
      icon: const Icon(Icons.open_in_new),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.value});
  final String value;

  @override
  Widget build(BuildContext context) {
    final bool failed = value.toLowerCase() == 'failed';
    return Chip(
      visualDensity: VisualDensity.compact,
      avatar: Icon(
        failed ? Icons.error_outline : Icons.check_circle_outline,
        size: 16,
      ),
      label: Text(documentProcessingLabel(value)),
    );
  }
}

class _PaginationBar extends StatelessWidget {
  const _PaginationBar({
    required this.page,
    required this.onPrevious,
    required this.onNext,
  });
  final DocumentPage page;
  final VoidCallback onPrevious;
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) {
    return Material(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: <Widget>[
            Text('Strona ${page.currentPage} z ${page.pageCount}'),
            const SizedBox(width: 12),
            IconButton(
              tooltip: 'Poprzednia strona',
              onPressed: page.hasPreviousPage ? onPrevious : null,
              icon: const Icon(Icons.chevron_left),
            ),
            IconButton(
              tooltip: 'Następna strona',
              onPressed: page.hasNextPage ? onNext : null,
              icon: const Icon(Icons.chevron_right),
            ),
          ],
        ),
      ),
    );
  }
}

class _DocumentDetailsDialog extends ConsumerWidget {
  const _DocumentDetailsDialog({
    required this.documentId,
    required this.onOpen,
  });
  final int documentId;
  final ValueChanged<RepositoryDocument> onOpen;

  Future<void> _trash(
    BuildContext context,
    WidgetRef ref,
    RepositoryDocument document,
  ) async {
    if (await confirmAndTrashDocument(context, ref, document) &&
        context.mounted) {
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<RepositoryDocument> details = ref.watch(
      documentDetailsProvider(documentId),
    );
    final role = ref.watch(authControllerProvider).value?.user?.role ?? '';
    final isAdmin =
        role.trim().toLowerCase() == 'administrator' ||
        role.trim().toLowerCase() == 'admin';
    return AlertDialog(
      title: const Text('Szczegóły dokumentu'),
      content: SizedBox(
        width: 560,
        child: details.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (Object error, StackTrace _) =>
              Text(friendlyDocumentError(error)),
          data: (RepositoryDocument document) => SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                if (isInternalPreviewImage(
                  document.contentType,
                  document.displayName,
                )) ...<Widget>[
                  DocumentImageThumbnail(
                    documentId: document.id,
                    contentType: document.contentType,
                    fileName: document.displayName,
                    onOpen: () => onOpen(document),
                  ),
                  const SizedBox(height: 12),
                ],
                Text(
                  document.displayName,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const Divider(height: 24),
                _DetailRow('ID', '${document.id}'),
                _DetailRow('Typ treści', document.contentType),
                _DetailRow('Rozmiar', formatDocumentBytes(document.fileSize)),
                _DetailRow('Źródło', documentSourceLabel(document.sourceType)),
                _DetailRow('Powiązanie', document.linkedEntityName),
                _DetailRow(
                  'Przetwarzanie',
                  documentProcessingLabel(document.processingStatus),
                ),
                _DetailRow(
                  'Analiza wizualna',
                  documentVisionLabel(document.visionStatus),
                ),
                _DetailRow(
                  'Metadane',
                  polishDocumentCode(document.metadataStatus),
                ),
                _DetailRow(
                  'Dopasowanie',
                  documentMatchLabel(document.matchStatus),
                ),
                if (document.matchConfidence != null)
                  _DetailRow(
                    'Pewność dopasowania',
                    '${(document.matchConfidence! * 100).toStringAsFixed(1)}%',
                  ),
                _DetailRow('Utworzono', formatDocumentDate(document.createdAt)),
                if (document.capturedAt != null)
                  _DetailRow(
                    'Pozyskano',
                    formatDocumentDate(document.capturedAt!),
                  ),
                if (document.archiveMemberPath != null)
                  _DetailRow('Ścieżka w archiwum', document.archiveMemberPath!),
                const Divider(height: 28),
                DocumentClientMatchPanel(document: document),
              ],
            ),
          ),
        ),
      ),
      actions: <Widget>[
        if (details.value != null)
          TextButton.icon(
            key: const Key('document-unified-assistant'),
            onPressed: () {
              Navigator.of(context).pop();
              context.push(
                '/ai?document_id=${details.value!.id}&question=${Uri.encodeQueryComponent('Co mówi ten dokument?')}',
              );
            },
            icon: const Icon(Icons.auto_awesome_outlined),
            label: const Text('Zapytaj AI'),
          ),
        if (isAdmin && details.value != null)
          TextButton.icon(
            key: const Key('trash-document-action'),
            onPressed: () => _trash(context, ref, details.value!),
            icon: const Icon(Icons.delete_outline),
            label: const Text('Przenieś do kosza'),
          ),
        if (details.value case final RepositoryDocument document
            when documentSupportsVision(
              document.contentType,
              document.originalFilename,
            ))
          TextButton.icon(
            onPressed: () async {
              try {
                await ref
                    .read(documentsRepositoryProvider)
                    .analyzeVision(
                      session: requireDocumentSessionFromAuth(
                        ref.read(authControllerProvider),
                      ),
                      documentId: document.id,
                    );
                ref.invalidate(documentDetailsProvider(document.id));
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Analiza wizualna została zlecona.'),
                    ),
                  );
                }
              } catch (error) {
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(friendlyDocumentError(error))),
                  );
                }
              }
            },
            icon: const Icon(Icons.auto_awesome),
            label: Text(
              document.visionStatus == 'complete' ||
                      document.visionStatus == 'partial'
                  ? 'Analizuj ponownie'
                  : 'Analizuj wizualnie',
            ),
          ),
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Zamknij'),
        ),
        if (details.value != null)
          FilledButton.icon(
            onPressed: () {
              Navigator.of(context).pop();
              onOpen(details.value!);
            },
            icon: const Icon(Icons.open_in_new),
            label: const Text('Otwórz plik'),
          ),
      ],
    );
  }
}

class DocumentClientMatchPanel extends ConsumerStatefulWidget {
  const DocumentClientMatchPanel({required this.document, super.key});
  final RepositoryDocument document;

  @override
  ConsumerState<DocumentClientMatchPanel> createState() =>
      _DocumentClientMatchPanelState();
}

class _DocumentClientMatchPanelState
    extends ConsumerState<DocumentClientMatchPanel> {
  bool _saving = false;

  @override
  Widget build(BuildContext context) {
    final match = ref.watch(documentClientMatchProvider(widget.document.id));
    return match.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (Object error, StackTrace _) => Text(
        'Nie udało się pobrać dopasowania: ${friendlyDocumentError(error)}',
      ),
      data: (DocumentClientMatch value) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Powiązanie z klientem',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          _DetailRow('Status', _matchStatus(value.status)),
          _DetailRow('Obecny klient', value.currentClientName ?? 'Brak'),
          _DetailRow('Pewność', value.confidence),
          if (value.suggestions.isNotEmpty) ...<Widget>[
            Text('Sugestie', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 6),
            ...value.suggestions.map(
              (suggestion) => Card(
                color: value.conflict
                    ? Theme.of(context).colorScheme.errorContainer
                    : null,
                child: Padding(
                  padding: const EdgeInsets.all(10),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        '${suggestion.clientName} • ${suggestion.confidence}',
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                      ...suggestion.evidence.map(
                        (item) => Text('• ${item.description}'),
                      ),
                      Align(
                        alignment: Alignment.centerRight,
                        child: TextButton(
                          onPressed: _saving
                              ? null
                              : () => _link(
                                  suggestion.clientId,
                                  value,
                                  suggested: true,
                                ),
                          child: Text(
                            value.currentClientId == null
                                ? 'Przypisz'
                                : 'Przenieś tutaj',
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ] else
            const Text('Brak deterministycznej sugestii.'),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              OutlinedButton.icon(
                onPressed: _saving ? null : () => _chooseClient(value),
                icon: const Icon(Icons.person_search),
                label: Text(
                  value.currentClientId == null
                      ? 'Przypisz klienta'
                      : 'Zmień klienta',
                ),
              ),
              if (value.currentClientId != null)
                OutlinedButton.icon(
                  onPressed: _saving ? null : () => _unlink(value),
                  icon: const Icon(Icons.link_off),
                  label: const Text('Odepnij'),
                ),
              if (value.history.isNotEmpty)
                TextButton.icon(
                  onPressed: _saving ? null : _undo,
                  icon: const Icon(Icons.undo),
                  label: const Text('Cofnij ostatnią zmianę'),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _chooseClient(DocumentClientMatch match) async {
    final AuthSession session = requireDocumentSessionFromAuth(
      ref.read(authControllerProvider),
    );
    final Client? client = await showDialog<Client>(
      context: context,
      builder: (BuildContext dialogContext) => _DocumentClientPickerDialog(
        repository: ref.read(clientsRepositoryProvider),
        session: session,
        title: match.currentClientId == null
            ? 'Przypisz klienta'
            : 'Zmień klienta',
      ),
    );
    if (client != null && mounted) {
      await _link(client.id, match, suggested: false);
    }
  }

  Future<void> _link(
    int clientId,
    DocumentClientMatch match, {
    required bool suggested,
  }) async {
    final bool conflict =
        match.conflict ||
        (!suggested &&
            match.suggestions.any((item) => item.clientId != clientId));
    if (!await _confirm(
      conflict
          ? 'Dowody wskazują innego klienta. Czy mimo to zatwierdzić operację?'
          : match.currentClientId == null
          ? 'Przypisać dokument do wybranego klienta?'
          : 'Przenieść dokument do wybranego klienta?',
    )) {
      return;
    }
    await _mutate(
      (repository, session) => repository.linkClient(
        session: session,
        documentId: widget.document.id,
        clientId: clientId,
        move: match.currentClientId != null,
        confirmConflict: conflict,
      ),
    );
  }

  Future<void> _unlink(DocumentClientMatch match) async {
    if (!await _confirm(
      'Odpiąć dokument od ${match.currentClientName}? Plik i jego historia pozostaną zachowane.',
    )) {
      return;
    }
    await _mutate(
      (repository, session) => repository.unlinkClient(
        session: session,
        documentId: widget.document.id,
      ),
    );
  }

  Future<void> _undo() async {
    if (!await _confirm('Cofnąć ostatnią zmianę powiązania dokumentu?')) {
      return;
    }
    await _mutate(
      (repository, session) => repository.undoClientLink(
        session: session,
        documentId: widget.document.id,
      ),
    );
  }

  Future<bool> _confirm(String message) async =>
      await showDialog<bool>(
        context: context,
        builder: (BuildContext dialogContext) => AlertDialog(
          title: const Text('Potwierdzenie'),
          content: Text(message),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Anuluj'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Potwierdź'),
            ),
          ],
        ),
      ) ??
      false;

  Future<void> _mutate(
    Future<void> Function(DocumentsRepository repository, AuthSession session)
    action,
  ) async {
    setState(() => _saving = true);
    try {
      await action(
        ref.read(documentsRepositoryProvider),
        requireDocumentSessionFromAuth(ref.read(authControllerProvider)),
      );
      ref.invalidate(documentClientMatchProvider(widget.document.id));
      ref.invalidate(documentDetailsProvider(widget.document.id));
      await ref.read(documentsControllerProvider.notifier).refresh();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Powiązanie dokumentu zostało zapisane.'),
          ),
        );
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(friendlyDocumentError(error))));
      }
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  static String _matchStatus(String value) => switch (value) {
    'ASSIGNED' => 'Przypisany',
    'CANDIDATE' => 'Kandydat',
    'CONFLICT' => 'Konflikt',
    _ => 'Nieprzypisany',
  };
}

class _DocumentClientPickerDialog extends StatefulWidget {
  const _DocumentClientPickerDialog({
    required this.repository,
    required this.session,
    required this.title,
  });
  final ClientsRepository repository;
  final AuthSession session;
  final String title;

  @override
  State<_DocumentClientPickerDialog> createState() =>
      _DocumentClientPickerDialogState();
}

class _DocumentClientPickerDialogState
    extends State<_DocumentClientPickerDialog> {
  final TextEditingController _search = TextEditingController();
  late Future<List<Client>> _results;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  void _load() {
    _results = widget.repository
        .fetchClients(
          session: widget.session,
          search: _search.text.trim(),
          limit: 20,
        )
        .then((page) => page.items);
  }

  void _searchClients() => setState(_load);

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.title),
      content: SizedBox(
        width: 520,
        height: 430,
        child: Column(
          children: <Widget>[
            TextField(
              key: const Key('document-client-search'),
              controller: _search,
              autofocus: true,
              decoration: InputDecoration(
                labelText: 'Szukaj klienta',
                suffixIcon: IconButton(
                  tooltip: 'Szukaj',
                  onPressed: _searchClients,
                  icon: const Icon(Icons.search),
                ),
              ),
              onSubmitted: (_) => _searchClients(),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: FutureBuilder<List<Client>>(
                future: _results,
                builder:
                    (
                      BuildContext context,
                      AsyncSnapshot<List<Client>> snapshot,
                    ) {
                      if (snapshot.connectionState != ConnectionState.done) {
                        return const Center(child: CircularProgressIndicator());
                      }
                      if (snapshot.hasError) {
                        return Text(friendlyDocumentError(snapshot.error!));
                      }
                      final List<Client> clients =
                          snapshot.data ?? const <Client>[];
                      if (clients.isEmpty) {
                        return const Center(
                          child: Text('Nie znaleziono klientów.'),
                        );
                      }
                      return ListView.builder(
                        itemCount: clients.length,
                        itemBuilder: (BuildContext context, int index) {
                          final Client client = clients[index];
                          return ListTile(
                            title: Text(client.name),
                            subtitle: Text(
                              '${client.clientType.displayName} • ID ${client.id}',
                            ),
                            onTap: () => Navigator.pop(context, client),
                          );
                        },
                      );
                    },
              ),
            ),
          ],
        ),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Anuluj'),
        ),
      ],
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow(this.label, this.value);
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          SizedBox(width: 165, child: Text(label)),
          Expanded(child: SelectableText(value)),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();
  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(Icons.find_in_page_outlined, size: 52),
          SizedBox(height: 12),
          Text('Brak dokumentów dla wybranych kryteriów.'),
        ],
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            const Icon(Icons.cloud_off_outlined, size: 52),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: onRetry,
              child: const Text('Spróbuj ponownie'),
            ),
          ],
        ),
      ),
    );
  }
}
