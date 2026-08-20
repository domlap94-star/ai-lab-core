import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/formatters/polish_date_time.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/domain/auth_session.dart';
import '../../documents/application/documents_providers.dart';
import '../../documents/domain/document.dart';
import '../../documents/presentation/document_media_preview.dart';
import '../../documents/presentation/document_presentation.dart';
import '../../mail/data/global_mail_api.dart';
import '../../mail/domain/global_mail.dart';
import '../../mail/presentation/mail_reconciliation_dialog.dart';
import '../application/client_emails_provider.dart';
import '../domain/client_email.dart';
import '../domain/client_email_page.dart';

class ClientEmailsPanel extends ConsumerStatefulWidget {
  const ClientEmailsPanel({
    required this.clientId,
    this.focusedSourceId,
    super.key,
  });

  final int clientId;
  final int? focusedSourceId;

  @override
  ConsumerState<ClientEmailsPanel> createState() => _ClientEmailsPanelState();
}

class _ClientEmailsPanelState extends ConsumerState<ClientEmailsPanel> {
  static const int _pageSize = 10;

  bool _expanded = false;
  bool _hasLoaded = false;
  int _skip = 0;
  final Set<int> _expandedMessageIds = <int>{};
  final Set<int> _openingDocumentIds = <int>{};
  bool _reconciling = false;

  @override
  void initState() {
    super.initState();
    _applyFocus();
  }

  void _applyFocus() {
    final int? focused = widget.focusedSourceId;
    if (focused == null) return;
    _expanded = true;
    _hasLoaded = true;
    _skip = 0;
    _expandedMessageIds.add(focused);
  }

  ClientEmailsPageRequest get _request => ClientEmailsPageRequest(
    clientId: widget.clientId,
    skip: _skip,
    limit: _pageSize,
    sourceId: widget.focusedSourceId,
  );

  @override
  void didUpdateWidget(covariant ClientEmailsPanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.clientId != widget.clientId ||
        oldWidget.focusedSourceId != widget.focusedSourceId) {
      _expanded = false;
      _hasLoaded = false;
      _skip = 0;
      _expandedMessageIds.clear();
      _openingDocumentIds.clear();
      _applyFocus();
    }
  }

  @override
  Widget build(BuildContext context) {
    final AsyncValue<ClientEmailPage>? emails = _hasLoaded
        ? ref.watch(clientEmailsPageProvider(_request))
        : null;
    final ClientEmailPage? page = emails?.value;
    final ThemeData theme = Theme.of(context);

    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          InkWell(
            key: const Key('client-emails-toggle'),
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
                  Icon(Icons.email_outlined, color: theme.colorScheme.primary),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          'Maile',
                          style: theme.textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        if (page != null)
                          Text(
                            '${page.total} wiadomości',
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
              padding: const EdgeInsets.all(16),
              child: emails!.when(
                loading: () => const _EmailPanelLoading(),
                error: (Object error, StackTrace _) => _EmailPanelError(
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

  Widget _buildLoaded(ClientEmailPage page) {
    if (page.items.isEmpty && page.total == 0) {
      return Padding(
        key: Key('client-emails-empty'),
        padding: const EdgeInsets.symmetric(vertical: 20),
        child: Text(
          widget.focusedSourceId == null
              ? 'Brak źródłowych wiadomości Gmail powiązanych z tym klientem.'
              : 'Nie znaleziono wskazanej wiadomości dla tego klienta.',
          textAlign: TextAlign.center,
        ),
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
            key: const Key('client-emails-refresh'),
            tooltip: 'Odśwież skrzynkę i maile klienta',
            onPressed: _reconciling ? null : _reconcile,
            icon: _reconciling
                ? const SizedBox.square(
                    dimension: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.sync),
          ),
        ),
        ...page.items.map(_buildEmailCard),
        const SizedBox(height: 8),
        if (widget.focusedSourceId == null)
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
                    key: const Key('client-emails-previous'),
                    tooltip: 'Poprzednia strona',
                    onPressed: page.hasPreviousPage ? _previousPage : null,
                    icon: const Icon(Icons.chevron_left),
                  ),
                  IconButton(
                    key: const Key('client-emails-next'),
                    tooltip: 'Następna strona',
                    onPressed: page.hasNextPage ? _nextPage : null,
                    icon: const Icon(Icons.chevron_right),
                  ),
                ],
              ),
            ],
          ),
      ],
    );
  }

  Widget _buildEmailCard(ClientEmail email) {
    final bool messageExpanded = _expandedMessageIds.contains(email.id);
    final bool focused = widget.focusedSourceId == email.id;
    final String sender = <String?>[email.fromName, email.fromAddress]
        .whereType<String>()
        .join(' <')
        .replaceFirstMapped(
          RegExp(r' <([^<]+)$'),
          (Match match) => ' <${match.group(1)}>',
        );

    return Card.outlined(
      key: ValueKey<String>('client-email-${email.id}'),
      margin: const EdgeInsets.only(bottom: 10),
      color: focused
          ? Theme.of(context).colorScheme.primaryContainer.withAlpha(90)
          : null,
      child: InkWell(
        key: ValueKey<String>('client-email-toggle-${email.id}'),
        onTap: () {
          setState(() {
            if (messageExpanded) {
              _expandedMessageIds.remove(email.id);
            } else {
              _expandedMessageIds.add(email.id);
            }
          });
        },
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Wrap(
                alignment: WrapAlignment.spaceBetween,
                crossAxisAlignment: WrapCrossAlignment.center,
                spacing: 10,
                runSpacing: 6,
                children: <Widget>[
                  _DirectionBadge(direction: email.direction),
                  Text(_formatDate(email.messageAt)),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                email.displaySubject,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 6),
              Text(
                'Od: ${sender.isEmpty ? 'nieustalony nadawca' : sender}',
                maxLines: messageExpanded ? null : 1,
                overflow: messageExpanded ? null : TextOverflow.ellipsis,
              ),
              Text(
                'Do: ${email.toAddresses.isEmpty ? 'brak danych' : email.toAddresses.join(', ')}',
                maxLines: messageExpanded ? null : 1,
                overflow: messageExpanded ? null : TextOverflow.ellipsis,
              ),
              const SizedBox(height: 8),
              if (!messageExpanded)
                Text(
                  _preview(email.bodyText),
                  key: ValueKey<String>('client-email-preview-${email.id}'),
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                ),
              if (email.attachmentCount > 0) ...<Widget>[
                const SizedBox(height: 8),
                Text(
                  '${email.attachmentCount} ${_attachmentWord(email.attachmentCount)}',
                ),
              ],
              if (messageExpanded) ...<Widget>[
                const Divider(height: 24),
                _DetailLine(label: 'Data', value: _formatDate(email.messageAt)),
                _DetailLine(
                  label: 'DW',
                  value: email.ccAddresses.isEmpty
                      ? 'brak'
                      : email.ccAddresses.join(', '),
                ),
                if (email.threadId != null)
                  _DetailLine(label: 'Wątek Gmail', value: email.threadId!),
                const SizedBox(height: 10),
                SelectionArea(
                  key: ValueKey<String>('client-email-body-${email.id}'),
                  child: Text(email.bodyText ?? 'Brak treści wiadomości.'),
                ),
                if (email.attachments.isNotEmpty) ...<Widget>[
                  const SizedBox(height: 14),
                  const Text(
                    'Załączniki',
                    style: TextStyle(fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 4),
                  Wrap(
                    spacing: 8,
                    runSpacing: 6,
                    children: email.attachments
                        .map((item) => _attachmentButton(item))
                        .toList(growable: false),
                  ),
                ],
                if (email.sourceUrl != null) ...<Widget>[
                  const SizedBox(height: 8),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton.icon(
                      onPressed: () => _openSource(email.sourceUrl!),
                      icon: const Icon(Icons.open_in_new, size: 18),
                      label: const Text('Otwórz źródło'),
                    ),
                  ),
                ],
              ],
              Align(
                alignment: Alignment.centerRight,
                child: Icon(
                  messageExpanded ? Icons.expand_less : Icons.expand_more,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _attachmentButton(ClientEmailAttachment attachment) {
    final bool opening = _openingDocumentIds.contains(attachment.documentId);
    final bool image = isInternalPreviewImage(
      attachment.contentType,
      attachment.displayName,
    );
    return SizedBox(
      width: 240,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          if (image) ...<Widget>[
            DocumentImageThumbnail(
              documentId: attachment.documentId,
              contentType: attachment.contentType,
              fileName: attachment.displayName,
              onOpen: () => _openAttachment(attachment),
            ),
            const SizedBox(height: 4),
          ],
          OutlinedButton.icon(
            key: ValueKey<String>(
              'client-email-attachment-${attachment.documentId}',
            ),
            onPressed: opening ? null : () => _openAttachment(attachment),
            icon: opening
                ? const SizedBox.square(
                    dimension: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Icon(
                    image ? Icons.image_outlined : Icons.attach_file,
                    size: 18,
                  ),
            label: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 190),
              child: Text(
                '${attachment.displayName} (${formatDocumentBytes(attachment.fileSize)})',
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _refresh() {
    ref.invalidate(clientEmailsPageProvider(_request));
  }

  Future<void> _reconcile() async {
    if (_reconciling) return;
    final AuthSession? session = ref
        .read(authControllerProvider)
        .value
        ?.session;
    if (session == null || !session.isAuthenticated) return;
    setState(() => _reconciling = true);
    try {
      final GlobalMailApi api = ref.read(globalMailApiProvider);
      final MailReconciliationDryRun dryRun = await api.reconciliationDryRun(
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
              openedFromClient: true,
            )) {
          return;
        }
        result = await api.reconciliationApply(session, dryRun);
      }
      if (!mounted) return;
      setState(() {
        _skip = 0;
        _expandedMessageIds.clear();
      });
      _refresh();
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(result.userSummary)));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Nie udało się odświeżyć maili: ${friendlyDocumentError(error)}',
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => _reconciling = false);
    }
  }

  void _nextPage() {
    setState(() {
      _skip += _pageSize;
      _expandedMessageIds.clear();
    });
  }

  void _previousPage() {
    setState(() {
      _skip = (_skip - _pageSize).clamp(0, 1 << 31);
      _expandedMessageIds.clear();
    });
  }

  Future<void> _openAttachment(ClientEmailAttachment attachment) async {
    final AuthSession? session = ref
        .read(authControllerProvider)
        .value
        ?.session;
    if (session == null || !session.isAuthenticated) return;
    setState(() => _openingDocumentIds.add(attachment.documentId));
    try {
      final RepositoryDocument document = await ref
          .read(documentsRepositoryProvider)
          .fetchDocument(session: session, documentId: attachment.documentId);
      if (!mounted) return;
      await openDocumentMedia(context, ref, document);
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Nie udało się otworzyć załącznika: ${friendlyDocumentError(error)}',
            ),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _openingDocumentIds.remove(attachment.documentId));
      }
    }
  }

  Future<void> _openSource(String sourceUrl) async {
    final Uri? uri = Uri.tryParse(sourceUrl);
    if (uri == null ||
        !await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Nie udało się otworzyć źródła.')),
        );
      }
    }
  }
}

class _DirectionBadge extends StatelessWidget {
  const _DirectionBadge({required this.direction});
  final ClientEmailDirection direction;

  @override
  Widget build(BuildContext context) {
    final (String label, IconData icon) = switch (direction) {
      ClientEmailDirection.sent => ('Wysłana', Icons.north_east),
      ClientEmailDirection.received => ('Odebrana', Icons.south_west),
      ClientEmailDirection.unknown => ('Nieustalona', Icons.help_outline),
    };
    return Chip(
      visualDensity: VisualDensity.compact,
      avatar: Icon(icon, size: 16),
      label: Text(label),
    );
  }
}

class _DetailLine extends StatelessWidget {
  const _DetailLine({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Text('$label: $value'),
    );
  }
}

class _EmailPanelLoading extends StatelessWidget {
  const _EmailPanelLoading();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 24),
      child: Center(child: CircularProgressIndicator()),
    );
  }
}

class _EmailPanelError extends StatelessWidget {
  const _EmailPanelError({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Column(
      key: const Key('client-emails-error'),
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

String clientEmailDirectionLabel(ClientEmailDirection direction) {
  return switch (direction) {
    ClientEmailDirection.sent => 'Wysłana',
    ClientEmailDirection.received => 'Odebrana',
    ClientEmailDirection.unknown => 'Nieustalona',
  };
}

String _preview(String? value) {
  if (value == null || value.trim().isEmpty) return 'Brak treści wiadomości.';
  final String normalized = value.replaceAll(RegExp(r'\s+'), ' ').trim();
  return normalized.length <= 180
      ? normalized
      : '${normalized.substring(0, 180)}…';
}

String _formatDate(DateTime? value) {
  if (value == null) return 'data nieustalona';
  return formatPolishDateTime(value);
}

String _attachmentWord(int count) {
  if (count == 1) return 'załącznik';
  if (count >= 2 && count <= 4) return 'załączniki';
  return 'załączników';
}
