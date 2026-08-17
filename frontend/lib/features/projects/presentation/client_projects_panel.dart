import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../application/projects_providers.dart';
import '../domain/project.dart';
import 'project_form_dialog.dart';

class ClientProjectsPanel extends ConsumerStatefulWidget {
  const ClientProjectsPanel({required this.clientId, super.key});
  final int clientId;
  @override
  ConsumerState<ClientProjectsPanel> createState() =>
      _ClientProjectsPanelState();
}

class _ClientProjectsPanelState extends ConsumerState<ClientProjectsPanel> {
  bool _expanded = false;
  ProjectQuery get query => ProjectQuery(clientId: widget.clientId, limit: 20);
  Future<void> _create() async {
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => ProjectFormDialog(clientId: widget.clientId),
    );
    if (data != null && mounted) {
      await ref
          .read(projectsApiProvider)
          .create(requireProjectWidgetSession(ref), data);
      ref.invalidate(projectsPageProvider(query));
    }
  }

  @override
  Widget build(BuildContext context) {
    final value = _expanded ? ref.watch(projectsPageProvider(query)) : null;
    return Card(
      child: Column(
        children: <Widget>[
          ListTile(
            key: const Key('client-projects-toggle'),
            title: const Text('Realizacje'),
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
                  label: const Text('Dodaj realizację'),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: value!.when(
                loading: () => const CircularProgressIndicator(),
                error: (error, _) => Text('$error'),
                data: (page) => page.items.isEmpty
                    ? const Text('Brak realizacji klienta.')
                    : Column(
                        children: page.items
                            .map(
                              (project) => ListTile(
                                title: Text(project.name),
                                subtitle: Text(
                                  '${project.status.label} • ${project.location}',
                                ),
                                onTap: () =>
                                    context.push('/projects/${project.id}'),
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
