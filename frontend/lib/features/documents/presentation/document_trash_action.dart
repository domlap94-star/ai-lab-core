import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/application/auth_controller.dart';
import '../../dashboard/application/dashboard_providers.dart';
import '../../projects/application/projects_providers.dart';
import '../../tasks/application/tasks_providers.dart';
import '../application/client_documents_provider.dart';
import '../application/documents_controller.dart';
import '../application/documents_providers.dart';
import '../domain/document.dart';
import 'document_presentation.dart';

bool canTrashDocuments(WidgetRef ref) {
  final String role = ref.watch(authControllerProvider).value?.user?.role ?? '';
  final String normalized = role.trim().toLowerCase();
  return normalized == 'administrator' || normalized == 'admin';
}

Future<bool> confirmAndTrashDocument(
  BuildContext context,
  WidgetRef ref,
  RepositoryDocument document,
) async {
  final bool? confirmed = await showDialog<bool>(
    context: context,
    builder: (BuildContext dialogContext) => AlertDialog(
      title: const Text('Przenieść plik do kosza?'),
      content: const Text(
        'Element będzie można przywrócić przez 7 dni. '
        'Po tym czasie zostanie automatycznie usunięty na stałe.',
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.pop(dialogContext, false),
          child: const Text('Anuluj'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(dialogContext, true),
          child: const Text('Przenieś do kosza'),
        ),
      ],
    ),
  );
  if (confirmed != true || !context.mounted) return false;

  try {
    await ref
        .read(documentsRepositoryProvider)
        .trashDocument(
          session: requireDocumentSessionFromAuth(
            ref.read(authControllerProvider),
          ),
          documentId: document.id,
        );
  } catch (error) {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Nie udało się przenieść pliku do Kosza: '
            '${friendlyDocumentError(error)}',
          ),
        ),
      );
    }
    return false;
  }

  invalidateDocumentProjections(ref, document.id);
  if (context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Dokument przeniesiono do Kosza.')),
    );
  }
  return true;
}

void invalidateDocumentProjections(WidgetRef ref, int documentId) {
  ref.invalidate(documentDetailsProvider(documentId));
  ref.invalidate(documentThumbnailProvider(documentId));
  ref.invalidate(documentsControllerProvider);
  ref.invalidate(clientDocumentsPageProvider);
  ref.invalidate(dashboardRecentDocumentsProvider);
  ref.invalidate(workItemDocumentsProvider);
  ref.invalidate(projectsPageProvider);
  ref.invalidate(projectDetailsProvider);
}
