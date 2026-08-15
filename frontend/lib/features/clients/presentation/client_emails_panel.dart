import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../auth/application/auth_controller.dart';
import '../../auth/domain/auth_session.dart';
import '../../documents/application/documents_providers.dart';
import '../../documents/domain/document.dart';
import '../../documents/presentation/document_presentation.dart';
import '../application/client_emails_provider.dart';
import '../domain/client_email.dart';
import '../domain/client_email_page.dart';

class ClientEmailsPanel extends ConsumerStatefulWidget {
  const ClientEmailsPanel({required this.clientId, super.key});

  final int clientId;

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

  ClientEmailsPageRequest get _request => ClientEmailsPageRequest(
    clientId: widget.clientId,
    skip: _skip,
    limit: _pageSize,
  );

  @override
  void didUpdateWidget(covariant ClientEmailsPanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.clientId != widget.clientId) {
      _expanded = false;
      _hasLoaded = false;
      _skip = 0;
      _expandedMessageIds.clear();
      _openingDocumentIds.clear();
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
      return const Padding(
        key: Key('client-emails-empty'),
        padding: EdgeInsets.symmetric(vertical: 20),
        child: Text(
          'Brak źródłowych wiadomości Gmail powiązanych z tym klientem.',
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
            tooltip: 'Odśwież maile',
            onPressed: _refresh,
            icon: const Icon(Icons.refresh),
          ),
        ),
        ...page.items.map(_buildEmailCard),
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
    return OutlinedButton.icon(
      key: ValueKey<String>('client-email-attachment-${attachment.documentId}'),
      onPressed: opening ? null : () => _openAttachment(attachment),
      icon: opening
          ? const SizedBox.square(
              dimension: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : const Icon(Icons.attach_file, size: 18),
      label: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 220),
        child: Text(
          '${attachment.displayName} (${formatDocumentBytes(attachment.fileSize)})',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ),
    );
  }

  void _refresh() {
    ref.invalidate(clientEmailsPageProvider(_request));
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
      await ref
          .read(documentOpenServiceProvider)
          .open(session: session, document: document);
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
  final DateTime local = value.toLocal();
  String two(int number) => number.toString().padLeft(2, '0');
  return '${two(local.day)}.${two(local.month)}.${local.year} '
      '${two(local.hour)}:${two(local.minute)}';
}

String _attachmentWord(int count) {
  if (count == 1) return 'załącznik';
  if (count >= 2 && count <= 4) return 'załączniki';
  return 'załączników';
}
