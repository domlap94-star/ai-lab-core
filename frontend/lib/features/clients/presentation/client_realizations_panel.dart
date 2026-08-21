import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/formatters/polish_date_time.dart';
import '../../documents/application/documents_providers.dart';
import '../../documents/domain/document.dart';
import '../../documents/domain/document_filters.dart';
import '../../documents/presentation/document_media_preview.dart';
import '../../projects/application/projects_providers.dart';
import '../../projects/domain/project.dart';

final _projectDocumentsProvider = FutureProvider.autoDispose
    .family<List<RepositoryDocument>, int>((ref, projectId) async {
      final page = await ref
          .watch(documentsRepositoryProvider)
          .fetchDocuments(
            session: requireDocumentSession(ref),
            filters: DocumentFilters(projectId: projectId),
            skip: 0,
            limit: 20,
          );
      return page.items;
    });

class ClientRealizationsPanel extends ConsumerWidget {
  const ClientRealizationsPanel({required this.clientId, super.key});
  final int clientId;

  String _dates(Project project) {
    if (project.startDate == null && project.endDate == null) {
      return 'Bez terminu';
    }
    return formatPolishDateRange(project.startDate, project.endDate);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final value = ref.watch(
      projectsPageProvider(ProjectQuery(clientId: clientId, limit: 20)),
    );
    return value.when(
      loading: () => const LinearProgressIndicator(),
      error: (_, _) => const SizedBox.shrink(),
      data: (page) {
        if (page.items.isEmpty) return const SizedBox.shrink();
        return Padding(
          padding: const EdgeInsets.only(top: 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Realizacja', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              for (final project in page.items)
                Card(
                  child: ExpansionTile(
                    title: Text(
                      project.name,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    subtitle: Text(
                      '${_dates(project)} • ${project.status.label}',
                    ),
                    childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                    children: [
                      Wrap(
                        spacing: 8,
                        children: [
                          TextButton.icon(
                            onPressed: () =>
                                context.push('/projects/${project.id}'),
                            icon: const Icon(Icons.open_in_new),
                            label: const Text('Otwórz realizację'),
                          ),
                          if (project.workItemId != null)
                            TextButton.icon(
                              onPressed: () =>
                                  context.push('/tasks/${project.workItemId}'),
                              icon: const Icon(Icons.task_alt),
                              label: const Text('Otwórz zadanie'),
                            ),
                        ],
                      ),
                      _ProjectDocuments(projectId: project.id),
                    ],
                  ),
                ),
            ],
          ),
        );
      },
    );
  }
}

class _ProjectDocuments extends ConsumerWidget {
  const _ProjectDocuments({required this.projectId});
  final int projectId;
  @override
  Widget build(BuildContext context, WidgetRef ref) => ref
      .watch(_projectDocumentsProvider(projectId))
      .when(
        loading: () => const LinearProgressIndicator(),
        error: (_, _) =>
            const Text('Nie udało się pobrać dokumentów realizacji.'),
        data: (documents) => ExpansionTile(
          tilePadding: EdgeInsets.zero,
          title: Text('Dokumenty (${documents.length})'),
          children: [
            for (final document in documents)
              ListTile(
                leading: DocumentImageThumbnail(
                  documentId: document.id,
                  contentType: document.contentType,
                  fileName: document.displayName,
                  onOpen: () => openDocumentMedia(context, ref, document),
                ),
                title: Text(
                  document.displayName,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                onTap: () => openDocumentMedia(context, ref, document),
              ),
          ],
        ),
      );
}
