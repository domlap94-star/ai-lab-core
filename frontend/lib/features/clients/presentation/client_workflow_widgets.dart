import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/application/auth_controller.dart';
import '../application/client_workflow_status.dart';
import '../application/clients_providers.dart';
import '../domain/client.dart';

class ClientWorkflowAvatar extends ConsumerWidget {
  const ClientWorkflowAvatar({
    super.key,
    required this.client,
    required this.onStatusChanged,
  });

  final Client client;
  final VoidCallback onStatusChanged;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ThemeData theme = Theme.of(context);
    final ClientWorkflowStatus status = ClientWorkflowMemory.instance.statusFor(
      client,
    );

    return PopupMenuButton<ClientWorkflowState>(
      tooltip: 'Status klienta',
      onSelected: (ClientWorkflowState value) async {
        DateTime? date;

        if (value.requiresDate) {
          final DateTime now = DateTime.now();

          date = await showDatePicker(
            context: context,
            initialDate: status.date ?? now,
            firstDate: DateTime(2020),
            lastDate: DateTime(2100),
            helpText: value == ClientWorkflowState.inspection
                ? 'Wybierz datę oględzin'
                : 'Wybierz datę kontaktu',
            cancelText: 'Anuluj',
            confirmText: 'Zapisz',
          );

          if (date == null) {
            return;
          }
        }

        final session = ref.read(authControllerProvider).value?.session;
        if (session == null) return;
        await ref
            .read(clientsRepositoryProvider)
            .bulkWorkflowStatus(
              session: session,
              clientIds: <int>[client.id],
              status: value.apiValue,
              effectiveDate: date?.toIso8601String().split('T').first,
            );
        ClientWorkflowMemory.instance.setStatus(
          client.id,
          ClientWorkflowStatus(state: value, date: date),
        );
        ref.invalidate(clientWorkflowStatusesProvider);
        onStatusChanged();
      },
      itemBuilder: (BuildContext context) {
        return ClientWorkflowState.values
            .map(
              (ClientWorkflowState value) => PopupMenuItem<ClientWorkflowState>(
                value: value,
                child: Row(
                  children: <Widget>[
                    Container(
                      width: 14,
                      height: 14,
                      decoration: BoxDecoration(
                        color: value.color(theme),
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: theme.colorScheme.outlineVariant,
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(child: Text(value.label)),
                  ],
                ),
              ),
            )
            .toList();
      },
      child: _WorkflowCircle(status: status),
    );
  }
}

class _WorkflowCircle extends StatelessWidget {
  const _WorkflowCircle({required this.status});

  final ClientWorkflowStatus status;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final Color fill = status.state.color(theme);
    final Color foreground = status.state.foregroundColor(theme);

    return Tooltip(
      message: status.displayLabel,
      child: Container(
        width: 52,
        height: 52,
        decoration: BoxDecoration(
          color: fill,
          shape: BoxShape.circle,
          border: Border.all(color: theme.colorScheme.outlineVariant),
        ),
        child: Center(
          child: status.state.requiresDate && status.date != null
              ? Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: <Widget>[
                    Text(
                      status.state.shortLabel,
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: foreground,
                        fontWeight: FontWeight.w800,
                        height: 1,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      ClientWorkflowStatus.formatBadgeDate(status.date!),
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: foreground,
                        fontSize: 9,
                        fontWeight: FontWeight.w700,
                        height: 1,
                      ),
                    ),
                  ],
                )
              : Text(
                  status.state.shortLabel,
                  style: theme.textTheme.labelMedium?.copyWith(
                    color: foreground,
                    fontWeight: FontWeight.w800,
                  ),
                ),
        ),
      ),
    );
  }
}

class ClientWorkflowStatusFilterField extends StatelessWidget {
  const ClientWorkflowStatusFilterField({
    super.key,
    required this.value,
    required this.onChanged,
  });

  final ClientWorkflowState? value;
  final ValueChanged<ClientWorkflowState?> onChanged;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return DropdownButtonFormField<ClientWorkflowState?>(
      initialValue: value,
      isExpanded: true,
      decoration: const InputDecoration(
        labelText: 'Status',
        prefixIcon: Icon(Icons.flag_outlined),
        border: OutlineInputBorder(),
      ),
      items: <DropdownMenuItem<ClientWorkflowState?>>[
        const DropdownMenuItem<ClientWorkflowState?>(
          value: null,
          child: Text('Wszystkie statusy'),
        ),
        ...ClientWorkflowState.values.map(
          (ClientWorkflowState workflowState) =>
              DropdownMenuItem<ClientWorkflowState?>(
                value: workflowState,
                child: Row(
                  children: <Widget>[
                    Container(
                      width: 14,
                      height: 14,
                      decoration: BoxDecoration(
                        color: workflowState.color(theme),
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: theme.colorScheme.outlineVariant,
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(child: Text(workflowState.label)),
                  ],
                ),
              ),
        ),
      ],
      onChanged: onChanged,
    );
  }
}
