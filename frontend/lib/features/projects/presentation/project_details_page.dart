import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../documents/application/documents_providers.dart';
import '../../documents/presentation/document_intake_dialog.dart';
import '../application/projects_providers.dart';
import '../domain/project.dart';
import 'project_form_dialog.dart';

class ProjectDetailsPage extends ConsumerWidget {
  const ProjectDetailsPage({required this.projectId, super.key});
  final int projectId;
  Future<void> _edit(
    BuildContext context,
    WidgetRef ref,
    Project project,
  ) async {
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => ProjectFormDialog(project: project),
    );
    if (data != null && context.mounted) {
      await ref
          .read(projectsApiProvider)
          .update(requireProjectWidgetSession(ref), project.id, data);
      ref.invalidate(projectDetailsProvider(project.id));
    }
  }

  Future<void> _delete(
    BuildContext context,
    WidgetRef ref,
    Project project,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Usunąć realizację?'),
        content: const Text(
          'Realizacja zniknie z aktywnej listy. Dokumenty pozostaną zachowane.',
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Anuluj'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Usuń'),
          ),
        ],
      ),
    );
    if (confirmed == true && context.mounted) {
      await ref
          .read(projectsApiProvider)
          .delete(requireProjectWidgetSession(ref), project.id);
      ref.invalidate(projectsPageProvider);
      if (context.mounted) context.go('/projects');
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final value = ref.watch(projectDetailsProvider(projectId));
    return PopScope<Object?>(
      canPop: context.canPop(),
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) context.go('/projects');
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Realizacja'),
          leading: IconButton(
            onPressed: () =>
                context.canPop() ? context.pop() : context.go('/projects'),
            icon: const Icon(Icons.arrow_back),
          ),
        ),
        body: value.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => Center(child: Text('$error')),
          data: (project) => ListView(
            padding: const EdgeInsets.all(16),
            children: <Widget>[
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: <Widget>[
                  FilledButton.icon(
                    onPressed: () => _edit(context, ref, project),
                    icon: const Icon(Icons.edit),
                    label: const Text('Edytuj'),
                  ),
                  OutlinedButton.icon(
                    onPressed: () => _delete(context, ref, project),
                    icon: const Icon(Icons.delete_outline),
                    label: const Text('Usuń realizację'),
                  ),
                ],
              ),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        project.name,
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      Text('Klient: ${project.clientName}'),
                      Text('Status: ${project.status.label}'),
                      Text(
                        'Daty: ${project.startDate?.toIso8601String().split('T').first ?? '—'} – '
                        '${project.endDate?.toIso8601String().split('T').first ?? '—'}',
                      ),
                      Text(
                        'Lokalizacja: ${project.location.isEmpty ? 'brak' : project.location}',
                      ),
                      Text(project.description ?? 'Brak opisu'),
                    ],
                  ),
                ),
              ),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      const Text('Dokumenty i zdjęcia'),
                      const Text('Pliki przypisane do tej realizacji'),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: <Widget>[
                          TextButton(
                            onPressed: () => context.push(
                              '/documents?project_id=${project.id}',
                            ),
                            child: const Text('Pokaż'),
                          ),
                          FilledButton.icon(
                            key: const Key('project-document-upload'),
                            onPressed: () => showDialog<void>(
                              context: context,
                              builder: (_) => DocumentIntakeDialog(
                                repository: ref.read(
                                  documentsRepositoryProvider,
                                ),
                                session: requireProjectWidgetSession(ref),
                                clientId: project.clientId,
                                projectId: project.id,
                              ),
                            ),
                            icon: const Icon(Icons.upload_file),
                            label: const Text('Dodaj'),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const Card(
                child: ListTile(
                  title: Text('Inspekcje'),
                  subtitle: Text('Moduł zostanie dodany w CHUNK 10B.'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
