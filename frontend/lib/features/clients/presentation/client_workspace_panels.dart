import 'package:flutter/material.dart';

class ClientWorkspacePanels extends StatelessWidget {
  const ClientWorkspacePanels({required this.clientId, super.key});

  final int clientId;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: <Widget>[
        const _WorkspaceCard(
          title: 'Dokumenty',
          icon: Icons.folder_copy_outlined,
          description:
              'Oferty, umowy, protokoły, załączniki i inne pliki '
              'powiązane z tym klientem będą dostępne w tym miejscu.',
          status:
              'Panel przygotowany. Powiązania dokumentów zostaną '
              'podłączone po zakończeniu parowania klientów.',
        ),
        const SizedBox(height: 20),
        const _WorkspaceCard(
          title: 'Maile',
          icon: Icons.email_outlined,
          description:
              'Historia wiadomości przychodzących i wychodzących '
              'powiązanych z tym klientem będzie dostępna w jednym miejscu.',
          status:
              'Panel przygotowany. Historia Gmail zostanie podłączona '
              'po zakończeniu parowania klientów.',
        ),
      ],
    );
  }
}

class _WorkspaceCard extends StatelessWidget {
  const _WorkspaceCard({
    required this.title,
    required this.icon,
    required this.description,
    required this.status,
  });

  final String title;
  final IconData icon;
  final String description;
  final String status;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(icon, color: theme.colorScheme.primary),
                const SizedBox(width: 10),
                Text(
                  title,
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            Text(description, style: theme.textTheme.bodyLarge),
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Icon(
                    Icons.schedule_outlined,
                    size: 20,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      status,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
