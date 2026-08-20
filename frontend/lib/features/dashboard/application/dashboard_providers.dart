import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/application/auth_controller.dart';
import '../../documents/application/documents_providers.dart';
import '../../documents/domain/document.dart';
import '../../documents/domain/document_filters.dart';
import '../../mail/data/global_mail_api.dart';
import '../../mail/domain/global_mail.dart';

const int dashboardPreviewLimit = 6;

final dashboardRecentMailProvider = FutureProvider<List<GlobalMailItem>>((
  Ref ref,
) async {
  final session = ref.watch(authControllerProvider).value?.session;
  if (session == null) throw StateError('Brak aktywnej sesji użytkownika.');
  final page = await ref
      .watch(globalMailApiProvider)
      .list(session: session, skip: 0, limit: dashboardPreviewLimit);
  return page.items;
});

final dashboardRecentDocumentsProvider =
    FutureProvider<List<RepositoryDocument>>((Ref ref) async {
      final session = ref.watch(authControllerProvider).value?.session;
      if (session == null) throw StateError('Brak aktywnej sesji użytkownika.');
      final page = await ref
          .watch(documentsRepositoryProvider)
          .fetchDocuments(
            session: session,
            filters: const DocumentFilters(),
            skip: 0,
            limit: dashboardPreviewLimit,
          );
      return page.items;
    });
