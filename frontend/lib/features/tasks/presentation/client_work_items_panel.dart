import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../auth/application/auth_controller.dart';
import '../application/tasks_providers.dart';
import '../domain/work_item.dart';
import 'operational_month_calendar.dart';
import 'work_item_form_dialog.dart';

class ClientWorkItemsPanel extends ConsumerWidget {
  const ClientWorkItemsPanel({required this.clientId, super.key});
  final int clientId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final value = ref.watch(workItemsProvider(clientId));
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Wrap(
              alignment: WrapAlignment.spaceBetween,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Text(
                  'Zadania i realizacje',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                FilledButton.tonalIcon(
                  key: const Key('client-create-realization'),
                  onPressed: () async {
                    final data = await showDialog<Map<String, dynamic>>(
                      context: context,
                      builder: (_) =>
                          WorkItemFormDialog(initialClientId: clientId),
                    );
                    if (data == null || !context.mounted) return;
                    data['item_type'] = WorkItemType.realization.name;
                    final session = ref
                        .read(authControllerProvider)
                        .value
                        ?.session;
                    if (session == null) return;
                    await ref.read(workItemsApiProvider).create(session, data);
                    ref.invalidate(workItemsProvider(clientId));
                  },
                  icon: const Icon(Icons.add),
                  label: const Text('Utwórz realizację'),
                ),
              ],
            ),
            const SizedBox(height: 10),
            value.when(
              data: (items) => items.isEmpty
                  ? const Text(
                      'Brak zadań i realizacji powiązanych z klientem.',
                    )
                  : Column(
                      children: [
                        for (final item in items.take(10))
                          ListTile(
                            leading: Icon(
                              CalendarPresentation.icon(item.type.name),
                            ),
                            title: Text(item.title),
                            subtitle: Text(
                              '${item.type.label} • ${item.status.name} • ${item.priority.name}',
                            ),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: () => context.push('/tasks/${item.id}'),
                          ),
                      ],
                    ),
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => Text('Nie udało się pobrać zadań: $error'),
            ),
          ],
        ),
      ),
    );
  }
}
