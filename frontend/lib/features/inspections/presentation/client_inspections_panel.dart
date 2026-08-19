import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/formatters/polish_date_time.dart';
import '../../../core/widgets/app_shell.dart';
import '../../../core/widgets/read_error_view.dart';
import '../application/inspections_providers.dart';
import '../domain/inspection.dart';
import 'inspection_form_dialog.dart';

class ClientInspectionsPanel extends ConsumerStatefulWidget {
  const ClientInspectionsPanel({
    required this.clientId,
    required this.clientName,
    super.key,
  });
  final int clientId;
  final String clientName;

  @override
  ConsumerState<ClientInspectionsPanel> createState() =>
      _ClientInspectionsPanelState();
}

class _ClientInspectionsPanelState
    extends ConsumerState<ClientInspectionsPanel> {
  bool _expanded = false;
  InspectionQuery get _query =>
      InspectionQuery(clientId: widget.clientId, limit: 20);

  Future<void> _create() async {
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => InspectionFormDialog(
        clientId: widget.clientId,
        clientName: widget.clientName,
      ),
    );
    if (data == null || !mounted) return;
    await ref
        .read(inspectionsApiProvider)
        .create(requireInspectionWidgetSession(ref), data);
    ref.invalidate(inspectionsPageProvider(_query));
  }

  @override
  Widget build(BuildContext context) {
    final value = _expanded ? ref.watch(inspectionsPageProvider(_query)) : null;
    return Card(
      child: Column(
        children: <Widget>[
          ListTile(
            key: const Key('client-inspections-toggle'),
            leading: const Icon(Icons.fact_check_outlined),
            title: const Text('Wizje lokalne'),
            subtitle: value?.value == null
                ? null
                : Text('${value!.value!.total} wizji'),
            trailing: Icon(_expanded ? Icons.expand_less : Icons.expand_more),
            onTap: () => setState(() => _expanded = !_expanded),
          ),
          if (_expanded) ...<Widget>[
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.all(12),
              child: Align(
                alignment: Alignment.centerRight,
                child: FilledButton.icon(
                  key: const Key('client-inspection-create'),
                  onPressed: _create,
                  icon: const Icon(Icons.add),
                  label: const Text('Dodaj wizję lokalną'),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: value!.when(
                loading: () => const CircularProgressIndicator(),
                error: (error, _) => ReadErrorView(
                  error: error,
                  onRetry: () =>
                      ref.invalidate(inspectionsPageProvider(_query)),
                ),
                data: (page) => page.items.isEmpty
                    ? const Text('Brak wizji lokalnych.')
                    : Column(
                        children: page.items
                            .map(
                              (inspection) => ListTile(
                                title: const Text('Wizja lokalna'),
                                subtitle: Text(inspection.status.label),
                                trailing: Text(
                                  inspection.scheduledAt == null
                                      ? 'bez terminu'
                                      : formatPolishDate(
                                          inspection.scheduledAt!,
                                        ),
                                ),
                                onTap: () => context.push(
                                  AppShell.inspectionPathWithReturn(
                                    inspectionId: inspection.id,
                                    returnPath: '/clients/${widget.clientId}',
                                  ),
                                ),
                              ),
                            )
                            .toList(growable: false),
                      ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
