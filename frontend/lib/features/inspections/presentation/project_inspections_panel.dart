import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/widgets/read_error_view.dart';
import '../../projects/domain/project.dart';
import '../application/inspections_providers.dart';
import '../domain/inspection.dart';
import 'inspection_form_dialog.dart';

class ProjectInspectionsPanel extends ConsumerStatefulWidget {
  const ProjectInspectionsPanel({required this.project, super.key});
  final Project project;
  @override
  ConsumerState<ProjectInspectionsPanel> createState() =>
      _ProjectInspectionsPanelState();
}

class _ProjectInspectionsPanelState
    extends ConsumerState<ProjectInspectionsPanel> {
  bool _expanded = false;
  InspectionQuery get query =>
      InspectionQuery(projectId: widget.project.id, limit: 20);
  Future<void> _create() async {
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => InspectionFormDialog(project: widget.project),
    );
    if (data != null && mounted) {
      await ref
          .read(inspectionsApiProvider)
          .create(requireInspectionWidgetSession(ref), data);
      ref.invalidate(inspectionsPageProvider(query));
    }
  }

  @override
  Widget build(BuildContext context) {
    final value = _expanded ? ref.watch(inspectionsPageProvider(query)) : null;
    return Card(
      child: Column(
        children: <Widget>[
          ListTile(
            key: const Key('project-inspections-toggle'),
            title: const Text('Wizje lokalne'),
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
                  onPressed: _create,
                  icon: const Icon(Icons.add),
                  label: const Text('Dodaj wizję'),
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
                      ref.invalidate(inspectionsPageProvider(query)),
                ),
                data: (page) => page.items.isEmpty
                    ? const Text('Brak wizji lokalnych.')
                    : Column(
                        children: page.items
                            .map(
                              (inspection) => ListTile(
                                title: Text(inspection.title),
                                subtitle: Text(
                                  '${inspection.status.label} • ${inspection.scheduledAt?.toLocal().toString() ?? 'bez terminu'}',
                                ),
                                onTap: () => context.push(
                                  '/inspections/${inspection.id}',
                                ),
                              ),
                            )
                            .toList(),
                      ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
