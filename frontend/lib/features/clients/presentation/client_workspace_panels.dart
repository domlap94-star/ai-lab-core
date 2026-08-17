import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../auth/application/auth_controller.dart';
import '../../auth/domain/auth_session.dart';
import '../../documents/application/client_documents_provider.dart';
import '../../documents/application/documents_providers.dart';
import '../../documents/domain/document.dart';
import '../../documents/domain/document_page.dart';
import '../../documents/presentation/document_intake_dialog.dart';
import '../../documents/presentation/document_presentation.dart';
import '../../projects/presentation/client_projects_panel.dart';
import 'client_emails_panel.dart';

class ClientWorkspacePanels extends StatelessWidget {
  const ClientWorkspacePanels({
    required this.clientId,
    required this.clientName,
    super.key,
  });

  final int clientId;
  final String clientName;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: <Widget>[
        ClientProjectsPanel(clientId: clientId),
        const SizedBox(height: 20),
        ClientDocumentsPanel(clientId: clientId, clientName: clientName),
        const SizedBox(height: 20),
        ClientEmailsPanel(clientId: clientId),
      ],
    );
  }
}

class ClientDocumentsPanel extends ConsumerStatefulWidget {
  const ClientDocumentsPanel({
    required this.clientId,
    required this.clientName,
    super.key,
  });

  final int clientId;
  final String clientName;

  @override
  ConsumerState<ClientDocumentsPanel> createState() =>
      _ClientDocumentsPanelState();
}

class _ClientDocumentsPanelState extends ConsumerState<ClientDocumentsPanel> {
  static const int _pageSize = 10;

  bool _expanded = false;
  bool _hasLoaded = false;
  int _skip = 0;
  final Set<int> _openingIds = <int>{};
  final Map<int, double?> _openingProgress = <int, double?>{};

  ClientDocumentsPageRequest get _request => ClientDocumentsPageRequest(
    clientId: widget.clientId,
    skip: _skip,
    limit: _pageSize,
  );

  @override
  Widget build(BuildContext context) {
    final AsyncValue<DocumentPage>? documents = _hasLoaded
        ? ref.watch(clientDocumentsPageProvider(_request))
        : null;
    final DocumentPage? page = documents?.value;
    final ThemeData theme = Theme.of(context);

    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          InkWell(
            key: const Key('client-documents-toggle'),
            onTap: () {
              setState(() {
                _expanded = !_expanded;
                _hasLoaded = true;
              });
            },
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
              child: Row(
                children: <Widget>[
                  Icon(
                    Icons.folder_copy_outlined,
                    color: theme.colorScheme.primary,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          'Dokumenty',
                          style: theme.textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        if (page != null)
                          Text(
                            '${page.total} dokumentów',
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                      ],
                    ),
                  ),
                  Icon(_expanded ? Icons.expand_less : Icons.expand_more),
                ],
              ),
            ),
          ),
          if (_expanded) ...<Widget>[
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
              child: Align(
                alignment: Alignment.centerRight,
                child: FilledButton.icon(
                  key: const Key('client-document-upload'),
                  onPressed: _upload,
                  icon: const Icon(Icons.upload_file),
                  label: const Text('Dodaj dokumenty'),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: documents!.when(
                loading: () => const _PanelLoading(),
                error: (Object error, StackTrace _) => _PanelError(
                  message: friendlyDocumentError(error),
                  onRetry: _refresh,
                ),
                data: _buildLoaded,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _upload() async {
    final session = ref.read(authControllerProvider).value?.session;
    if (session == null || !mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => DocumentIntakeDialog(
        repository: ref.read(documentsRepositoryProvider),
        session: session,
        clientId: widget.clientId,
        onCompleted: () {
          _hasLoaded = true;
          _refresh();
        },
      ),
    );
  }

  Widget _buildLoaded(DocumentPage page) {
    if (page.items.isEmpty && page.total == 0) {
      return Column(
        children: <Widget>[
          const Padding(
            key: Key('client-documents-empty'),
            padding: EdgeInsets.symmetric(vertical: 20),
            child: Text('Brak dokumentów przypisanych do tego klienta.'),
          ),
          _FullRepositoryButton(
            clientId: widget.clientId,
            clientName: widget.clientName,
          ),
        ],
      );
    }

    final int rangeStart = page.skip + 1;
    final int rangeEnd = page.skip + page.items.length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Align(
          alignment: Alignment.centerRight,
          child: IconButton(
            key: const Key('client-documents-refresh'),
            tooltip: 'Odśwież dokumenty',
            onPressed: _refresh,
            icon: const Icon(Icons.refresh),
          ),
        ),
        ...page.items.map(_buildDocumentRow),
        const SizedBox(height: 8),
        Wrap(
          alignment: WrapAlignment.spaceBetween,
          crossAxisAlignment: WrapCrossAlignment.center,
          spacing: 12,
          runSpacing: 8,
          children: <Widget>[
            Text('$rangeStart–$rangeEnd z ${page.total}'),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                IconButton(
                  key: const Key('client-documents-previous'),
                  tooltip: 'Poprzednia strona',
                  onPressed: page.hasPreviousPage ? _previousPage : null,
                  icon: const Icon(Icons.chevron_left),
                ),
                IconButton(
                  key: const Key('client-documents-next'),
                  tooltip: 'Następna strona',
                  onPressed: page.hasNextPage ? _nextPage : null,
                  icon: const Icon(Icons.chevron_right),
                ),
              ],
            ),
          ],
        ),
        const SizedBox(height: 8),
        _FullRepositoryButton(
          clientId: widget.clientId,
          clientName: widget.clientName,
        ),
      ],
    );
  }

  Widget _buildDocumentRow(RepositoryDocument document) {
    final bool opening = _openingIds.contains(document.id);
    return Container(
      key: ValueKey<String>('client-document-${document.id}'),
      padding: const EdgeInsets.symmetric(vertical: 10),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: Color(0x1F000000))),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Icon(_fileIcon(document.contentType), size: 22),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  document.displayName,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 5),
                Text(
                  '${documentContentTypeLabel(document.contentType)} • '
                  '${formatDocumentBytes(document.fileSize)} • '
                  '${formatDocumentDate(document.capturedAt ?? document.createdAt)}',
                ),
                const SizedBox(height: 5),
                Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  children: <Widget>[
                    _CompactStatus(documentSourceLabel(document.sourceType)),
                    _CompactStatus(
                      documentProcessingLabel(document.processingStatus),
                    ),
                    _CompactStatus(documentMatchLabel(document.matchStatus)),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          if (opening)
            SizedBox(
              width: 32,
              height: 32,
              child: CircularProgressIndicator(
                value: _openingProgress[document.id],
                strokeWidth: 3,
              ),
            )
          else
            TextButton.icon(
              key: ValueKey<String>('client-document-open-${document.id}'),
              onPressed: () => _openDocument(document),
              icon: const Icon(Icons.open_in_new, size: 18),
              label: const Text('Otwórz'),
            ),
        ],
      ),
    );
  }

  void _refresh() {
    ref.invalidate(clientDocumentsPageProvider(_request));
  }

  void _nextPage() {
    setState(() => _skip += _pageSize);
  }

  void _previousPage() {
    setState(() => _skip = (_skip - _pageSize).clamp(0, 1 << 31));
  }

  Future<void> _openDocument(RepositoryDocument document) async {
    final AuthSession session = requireDocumentSessionFromAuth(
      ref.read(authControllerProvider),
    );
    setState(() {
      _openingIds.add(document.id);
      _openingProgress[document.id] = null;
    });
    try {
      await ref
          .read(documentOpenServiceProvider)
          .open(
            session: session,
            document: document,
            onProgress: (int received, int total) {
              if (!mounted) return;
              setState(() {
                _openingProgress[document.id] = total > 0
                    ? received / total
                    : null;
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
          _openingProgress.remove(document.id);
        });
      }
    }
  }

  IconData _fileIcon(String contentType) {
    if (contentType == 'application/pdf') return Icons.picture_as_pdf_outlined;
    if (contentType.startsWith('image/')) return Icons.image_outlined;
    if (contentType == 'message/rfc822') return Icons.email_outlined;
    return Icons.description_outlined;
  }
}

class _CompactStatus extends StatelessWidget {
  const _CompactStatus(this.label);
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(label, style: Theme.of(context).textTheme.labelSmall),
    );
  }
}

class _FullRepositoryButton extends StatelessWidget {
  const _FullRepositoryButton({
    required this.clientId,
    required this.clientName,
  });

  final int clientId;
  final String clientName;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: TextButton.icon(
        key: const Key('client-documents-all'),
        onPressed: () {
          context.go(
            Uri(
              path: '/documents',
              queryParameters: <String, String>{
                'client_id': '$clientId',
                'client_name': clientName,
              },
            ).toString(),
          );
        },
        icon: const Icon(Icons.folder_open_outlined),
        label: const Text('Pokaż wszystkie dokumenty klienta'),
      ),
    );
  }
}

class _PanelLoading extends StatelessWidget {
  const _PanelLoading();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 24),
      child: Center(child: CircularProgressIndicator()),
    );
  }
}

class _PanelError extends StatelessWidget {
  const _PanelError({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Column(
      key: const Key('client-documents-error'),
      children: <Widget>[
        Text(message, textAlign: TextAlign.center),
        const SizedBox(height: 8),
        TextButton.icon(
          onPressed: onRetry,
          icon: const Icon(Icons.refresh),
          label: const Text('Spróbuj ponownie'),
        ),
      ],
    );
  }
}
