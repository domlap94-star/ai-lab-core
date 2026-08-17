import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../application/timeline_providers.dart';
import '../domain/timeline.dart';

class TimelinePanel extends ConsumerStatefulWidget {
  const TimelinePanel({
    required this.scope,
    required this.id,
    required this.title,
    super.key,
  });
  final TimelineScope scope;
  final int id;
  final String title;
  @override
  ConsumerState<TimelinePanel> createState() => _TimelinePanelState();
}

class _TimelinePanelState extends ConsumerState<TimelinePanel> {
  bool _expanded = false;
  int _limit = 20;
  String? _eventType;
  TimelineRequest get _request => TimelineRequest(
    scope: widget.scope,
    id: widget.id,
    limit: _limit,
    eventType: _eventType,
  );

  @override
  Widget build(BuildContext context) {
    final value = _expanded ? ref.watch(timelinePageProvider(_request)) : null;
    return Card(
      key: Key('timeline-${widget.scope.name}-${widget.id}'),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          InkWell(
            key: const Key('timeline-toggle'),
            onTap: () => setState(() => _expanded = !_expanded),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
              child: Row(
                children: <Widget>[
                  Icon(
                    Icons.timeline,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      widget.title,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
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
              child: DropdownButtonFormField<String?>(
                key: const Key('timeline-filter'),
                initialValue: _eventType,
                decoration: const InputDecoration(labelText: 'Typ zdarzenia'),
                items: const <DropdownMenuItem<String?>>[
                  DropdownMenuItem(value: null, child: Text('Wszystkie')),
                  DropdownMenuItem(
                    value: 'document_added',
                    child: Text('Dokumenty'),
                  ),
                  DropdownMenuItem(
                    value: 'photo_captured',
                    child: Text('Zdjęcia'),
                  ),
                  DropdownMenuItem(
                    value: 'email_received',
                    child: Text('E-maile odebrane'),
                  ),
                  DropdownMenuItem(
                    value: 'email_sent',
                    child: Text('E-maile wysłane'),
                  ),
                  DropdownMenuItem(
                    value: 'inspection_created',
                    child: Text('Wizje lokalne'),
                  ),
                ],
                onChanged: (value) => setState(() {
                  _eventType = value;
                  _limit = 20;
                }),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: value!.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (error, _) => Column(
                  children: <Widget>[
                    Text('Nie udało się pobrać osi czasu: $error'),
                    TextButton(
                      onPressed: () =>
                          ref.invalidate(timelinePageProvider(_request)),
                      child: const Text('Spróbuj ponownie'),
                    ),
                  ],
                ),
                data: _buildPage,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildPage(TimelinePage page) {
    if (page.items.isEmpty) {
      return const Padding(
        key: Key('timeline-empty'),
        padding: EdgeInsets.symmetric(vertical: 20),
        child: Text(
          'Brak zdarzeń do wyświetlenia.',
          textAlign: TextAlign.center,
        ),
      );
    }
    return Column(
      children: <Widget>[
        ...page.items.map(_eventTile),
        if (page.hasMore)
          TextButton.icon(
            key: const Key('timeline-load-more'),
            onPressed: () => setState(() => _limit += 20),
            icon: const Icon(Icons.expand_more),
            label: const Text('Pokaż więcej'),
          ),
      ],
    );
  }

  Widget _eventTile(TimelineEvent event) => ListTile(
    key: ValueKey<String>('timeline-event-${event.stableKey}'),
    contentPadding: const EdgeInsets.symmetric(vertical: 4),
    leading: CircleAvatar(child: Icon(_icon(event.eventType), size: 20)),
    title: Text(event.title, maxLines: 2, overflow: TextOverflow.ellipsis),
    subtitle: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        if (event.summary?.isNotEmpty == true)
          Text(event.summary!, maxLines: 3, overflow: TextOverflow.ellipsis),
        Text(_formatDate(event.occurredAt)),
      ],
    ),
    trailing: _canOpen(event)
        ? IconButton(
            tooltip: 'Otwórz źródło',
            onPressed: () => _open(event),
            icon: const Icon(Icons.open_in_new),
          )
        : null,
  );

  bool _canOpen(TimelineEvent event) =>
      event.documentId != null ||
      event.inspectionId != null ||
      event.projectId != null ||
      event.clientId != null;
  void _open(TimelineEvent event) {
    if (event.documentId != null) {
      context.push('/documents?document_id=${event.documentId}');
    } else if (event.inspectionId != null) {
      context.push('/inspections/${event.inspectionId}');
    } else if (event.projectId != null) {
      context.push('/projects/${event.projectId}');
    } else if (event.clientId != null) {
      context.push('/clients/${event.clientId}');
    }
  }

  IconData _icon(String type) {
    if (type.startsWith('email_')) return Icons.email_outlined;
    if (type.startsWith('inspection_')) return Icons.fact_check_outlined;
    if (type.startsWith('document_client_')) return Icons.link_outlined;
    return switch (type) {
      'client_created' => Icons.person_add_alt,
      'project_created' => Icons.work_outline,
      'photo_captured' => Icons.photo_camera_outlined,
      _ => Icons.description_outlined,
    };
  }

  String _formatDate(DateTime value) {
    final local = value.toLocal();
    String two(int number) => number.toString().padLeft(2, '0');
    return '${two(local.day)}.${two(local.month)}.${local.year} ${two(local.hour)}:${two(local.minute)}';
  }
}
