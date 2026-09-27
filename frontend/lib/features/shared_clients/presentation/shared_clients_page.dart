import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../auth/application/auth_controller.dart';
import '../application/client_access_providers.dart';

class SharedClientsPage extends ConsumerStatefulWidget {
  const SharedClientsPage({super.key});

  @override
  ConsumerState<SharedClientsPage> createState() => _SharedClientsPageState();
}

class _SharedClientsPageState extends ConsumerState<SharedClientsPage> {
  int? _clientId;
  int? _externalUserId;
  bool _busy = false;

  Future<void> _change({required bool grant}) async {
    final clientId = _clientId;
    final userId = _externalUserId;
    final session = ref.read(authControllerProvider).value?.session;
    if (clientId == null || userId == null || session == null) return;
    if (!grant) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Cofnąć dostęp?'),
          content: const Text(
            'Użytkownik natychmiast utraci dostęp do klienta i jego zasobów.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Anuluj'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Cofnij dostęp'),
            ),
          ],
        ),
      );
      if (confirmed != true || !mounted) return;
    }
    setState(() => _busy = true);
    try {
      if (grant) {
        await ref
            .read(clientAccessRepositoryProvider)
            .grant(
              session: session,
              clientId: clientId,
              externalUserId: userId,
            );
      } else {
        await ref
            .read(clientAccessRepositoryProvider)
            .revoke(
              session: session,
              clientId: clientId,
              externalUserId: userId,
            );
      }
      ref.invalidate(clientGrantHistoryProvider);
      ref.invalidate(clientAccessManagerOptionsProvider);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final role = ref.watch(authControllerProvider).value?.user?.role ?? '';
    final external = role.trim().toLowerCase() == 'external';
    final data = ref.watch(
      external ? sharedClientsProvider : clientGrantHistoryProvider,
    );
    final options = external
        ? null
        : ref.watch(clientAccessManagerOptionsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Udostępnieni klienci')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (!external) ...[
            Text(
              'Nadaj lub cofnij dostęp użytkownika Zewnętrznego',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            options!.when(
              loading: () => const LinearProgressIndicator(),
              error: (_, _) =>
                  const Text('Nie udało się odczytać klientów i użytkowników.'),
              data: (value) => Column(
                children: [
                  DropdownButtonFormField<int>(
                    key: ValueKey('client-$_clientId'),
                    initialValue: _clientId,
                    decoration: const InputDecoration(labelText: 'Klient'),
                    items: value['clients']!
                        .map(
                          (row) => DropdownMenuItem<int>(
                            value: row['id'] as int,
                            child: Text(row['name'].toString()),
                          ),
                        )
                        .toList(growable: false),
                    onChanged: _busy
                        ? null
                        : (value) => setState(() => _clientId = value),
                  ),
                  DropdownButtonFormField<int>(
                    key: ValueKey('external-user-$_externalUserId'),
                    initialValue: _externalUserId,
                    decoration: const InputDecoration(
                      labelText: 'Użytkownik Zewnętrzny',
                    ),
                    items: value['external_users']!
                        .map(
                          (row) => DropdownMenuItem<int>(
                            value: row['id'] as int,
                            child: Text(row['username'].toString()),
                          ),
                        )
                        .toList(growable: false),
                    onChanged: _busy
                        ? null
                        : (value) => setState(() => _externalUserId = value),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [
                FilledButton(
                  onPressed: _busy ? null : () => _change(grant: true),
                  child: const Text('Udostępnij'),
                ),
                OutlinedButton(
                  onPressed: _busy ? null : () => _change(grant: false),
                  child: const Text('Cofnij'),
                ),
              ],
            ),
            const Divider(height: 32),
          ],
          data.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (_, _) => const Text('Nie udało się odczytać udostępnień.'),
            data: (rows) => rows.isEmpty
                ? const Text('Brak udostępnionych klientów.')
                : Column(
                    children: rows
                        .map((row) {
                          final clientId = row['client_id'] ?? row['id'];
                          final name = row['name']?.toString();
                          final optionRows = options?.value;
                          final clientOption = optionRows?['clients']?.where(
                            (item) => item['id'] == clientId,
                          );
                          final externalOption = optionRows?['external_users']
                              ?.where(
                                (item) => item['id'] == row['external_user_id'],
                              );
                          final resolvedClient =
                              clientOption != null && clientOption.isNotEmpty
                              ? clientOption.first['name'].toString()
                              : null;
                          final resolvedExternal =
                              externalOption != null &&
                                  externalOption.isNotEmpty
                              ? externalOption.first['username'].toString()
                              : null;
                          return ListTile(
                            key: ValueKey('shared-client-$clientId'),
                            leading: const Icon(Icons.business_outlined),
                            title: Text(
                              name ?? resolvedClient ?? 'Klient #$clientId',
                            ),
                            subtitle: external
                                ? null
                                : Text(
                                    '${resolvedExternal ?? 'Zewnętrzny #${row['external_user_id']}'} · ${row['active'] == true ? 'aktywny' : 'cofnięty'}',
                                  ),
                            onTap: external
                                ? () => context.go('/clients/$clientId')
                                : null,
                          );
                        })
                        .toList(growable: false),
                  ),
          ),
        ],
      ),
    );
  }
}
