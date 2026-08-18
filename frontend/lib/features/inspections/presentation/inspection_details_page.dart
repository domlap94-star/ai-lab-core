import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/widgets/app_shell.dart';
import '../../../core/widgets/read_error_view.dart';
import '../../documents/application/documents_providers.dart';
import '../../documents/presentation/document_intake_dialog.dart';
import '../application/inspections_providers.dart';
import '../domain/inspection.dart';
import 'inspection_form_dialog.dart';

class InspectionDetailsPage extends ConsumerWidget {
  const InspectionDetailsPage({
    required this.inspectionId,
    this.returnPath,
    super.key,
  });
  final int inspectionId;
  final String? returnPath;

  void _goBack(BuildContext context) {
    if (returnPath != null) {
      context.go(returnPath!);
    } else if (context.canPop()) {
      context.pop();
    } else {
      context.go('/inspections');
    }
  }

  Future<void> _edit(
    BuildContext context,
    WidgetRef ref,
    Inspection item,
  ) async {
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => InspectionFormDialog(inspection: item),
    );
    if (data != null && context.mounted) {
      await ref
          .read(inspectionsApiProvider)
          .update(requireInspectionWidgetSession(ref), item.id, data);
      ref.invalidate(inspectionDetailsProvider(item.id));
    }
  }

  Future<void> _complete(WidgetRef ref, Inspection item) async {
    await ref.read(inspectionsApiProvider).update(
      requireInspectionWidgetSession(ref),
      item.id,
      <String, dynamic>{'status': 'completed'},
    );
    ref.invalidate(inspectionDetailsProvider(item.id));
  }

  Future<void> _delete(
    BuildContext context,
    WidgetRef ref,
    Inspection item,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Usunąć wizję lokalną?'),
        content: const Text(
          'Wizja zniknie z aktywnej listy. Dokumenty i zdjęcia pozostaną zachowane.',
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
          .read(inspectionsApiProvider)
          .delete(requireInspectionWidgetSession(ref), item.id);
      ref.invalidate(inspectionsPageProvider);
      if (context.mounted) context.go('/inspections');
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final value = ref.watch(inspectionDetailsProvider(inspectionId));
    final bool centrallyHandled = AppShell.centrallyHandlesBack(context);
    return PopScope<Object?>(
      canPop: centrallyHandled || context.canPop(),
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop && !centrallyHandled) {
          _goBack(context);
        }
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Wizja lokalna'),
          leading: IconButton(
            onPressed: () => _goBack(context),
            icon: const Icon(Icons.arrow_back),
          ),
        ),
        body: value.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => ReadErrorView(
            error: error,
            onRetry: () =>
                ref.invalidate(inspectionDetailsProvider(inspectionId)),
          ),
          data: (item) => ListView(
            padding: const EdgeInsets.all(16),
            children: <Widget>[
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: <Widget>[
                  FilledButton.icon(
                    onPressed: () => _edit(context, ref, item),
                    icon: const Icon(Icons.edit),
                    label: const Text('Edytuj'),
                  ),
                  if (item.status != InspectionStatus.completed)
                    OutlinedButton.icon(
                      onPressed: () => _complete(ref, item),
                      icon: const Icon(Icons.check),
                      label: const Text('Zakończ'),
                    ),
                  OutlinedButton.icon(
                    onPressed: () => _delete(context, ref, item),
                    icon: const Icon(Icons.delete_outline),
                    label: const Text('Usuń wizję'),
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
                        'Wizja lokalna',
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      Text('Klient: ${item.clientName}'),
                      Text('Status: ${item.status.label}'),
                      Text(
                        'Termin: ${item.scheduledAt?.toLocal().toString() ?? 'brak'}',
                      ),
                      Text('Lokalizacja: ${item.location}'),
                      Text(item.notes ?? 'Brak notatek'),
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
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: <Widget>[
                          TextButton(
                            onPressed: () => context.push(
                              '/documents?inspection_id=${item.id}',
                            ),
                            child: const Text('Pokaż'),
                          ),
                          FilledButton.icon(
                            key: const Key('inspection-document-upload'),
                            onPressed: () => showDialog<void>(
                              context: context,
                              builder: (_) => DocumentIntakeDialog(
                                repository: ref.read(
                                  documentsRepositoryProvider,
                                ),
                                session: requireInspectionWidgetSession(ref),
                                clientId: item.clientId,
                                inspectionId: item.id,
                              ),
                            ),
                            icon: const Icon(Icons.upload_file),
                            label: const Text('Dodaj dokument lub zdjęcie'),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
