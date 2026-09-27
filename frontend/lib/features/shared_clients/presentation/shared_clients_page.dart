import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/network/api_client.dart';
import '../../auth/application/auth_controller.dart';

final sharedClientsProvider = FutureProvider<List<Map<String, dynamic>>>((
  ref,
) async {
  final auth = ref.watch(authControllerProvider).value;
  final session = auth?.session;
  if (session == null) return const [];
  final response = await ref
      .watch(dioProvider)
      .get<List<dynamic>>(
        '/api/v1/client-access/shared-clients',
        options: Options(
          headers: {
            'Authorization': '${session.tokenType} ${session.accessToken}',
          },
        ),
      );
  return (response.data ?? const []).whereType<Map<String, dynamic>>().toList(
    growable: false,
  );
});

final clientGrantHistoryProvider = FutureProvider<List<Map<String, dynamic>>>((
  ref,
) async {
  final auth = ref.watch(authControllerProvider).value;
  final session = auth?.session;
  if (session == null) return const [];
  final response = await ref
      .watch(dioProvider)
      .get<Map<String, dynamic>>(
        '/api/v1/client-access/grants',
        options: Options(
          headers: {
            'Authorization': '${session.tokenType} ${session.accessToken}',
          },
        ),
      );
  return (response.data?['items'] as List<dynamic>? ?? const [])
      .whereType<Map<String, dynamic>>()
      .toList(growable: false);
});

class SharedClientsPage extends ConsumerStatefulWidget {
  const SharedClientsPage({super.key});

  @override
  ConsumerState<SharedClientsPage> createState() => _SharedClientsPageState();
}

class _SharedClientsPageState extends ConsumerState<SharedClientsPage> {
  final _clientId = TextEditingController();
  final _externalUserId = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _clientId.dispose();
    _externalUserId.dispose();
    super.dispose();
  }

  Future<void> _change({required bool grant}) async {
    final clientId = int.tryParse(_clientId.text.trim());
    final userId = int.tryParse(_externalUserId.text.trim());
    final session = ref.read(authControllerProvider).value?.session;
    if (clientId == null || userId == null || session == null) return;
    setState(() => _busy = true);
    try {
      final dio = ref.read(dioProvider);
      final options = Options(
        headers: {
          'Authorization': '${session.tokenType} ${session.accessToken}',
        },
      );
      if (grant) {
        await dio.post(
          '/api/v1/client-access/grants',
          data: {'client_id': clientId, 'external_user_id': userId},
          options: options,
        );
      } else {
        await dio.delete(
          '/api/v1/client-access/grants',
          queryParameters: {'client_id': clientId, 'external_user_id': userId},
          options: options,
        );
      }
      ref.invalidate(clientGrantHistoryProvider);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final role = ref.watch(authControllerProvider).value?.user?.role ?? '';
    final external = role == 'External';
    final data = ref.watch(
      external ? sharedClientsProvider : clientGrantHistoryProvider,
    );
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
            TextField(
              controller: _clientId,
              decoration: const InputDecoration(labelText: 'ID klienta'),
            ),
            TextField(
              controller: _externalUserId,
              decoration: const InputDecoration(
                labelText: 'ID użytkownika External',
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
            error: (error, _) =>
                Text('Nie udało się odczytać udostępnień: $error'),
            data: (rows) => rows.isEmpty
                ? const Text('Brak udostępnionych klientów.')
                : Column(
                    children: rows
                        .map((row) {
                          final clientId = row['client_id'] ?? row['id'];
                          final name = row['name']?.toString();
                          return ListTile(
                            key: ValueKey('shared-client-$clientId'),
                            leading: const Icon(Icons.business_outlined),
                            title: Text(name ?? 'Klient #$clientId'),
                            subtitle: external
                                ? null
                                : Text(
                                    'External #${row['external_user_id']} · ${row['active'] == true ? 'aktywny' : 'cofnięty'}',
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
