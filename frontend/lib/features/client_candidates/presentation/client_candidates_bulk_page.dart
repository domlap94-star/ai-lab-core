import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../auth/application/auth_controller.dart';
import '../application/client_candidates_providers.dart';
import '../domain/client_candidate.dart';

class ClientCandidatesBulkPage extends ConsumerStatefulWidget {
  const ClientCandidatesBulkPage({super.key});
  @override
  ConsumerState<ClientCandidatesBulkPage> createState() => _State();
}

class _State extends ConsumerState<ClientCandidatesBulkPage> {
  bool selecting = false;
  bool submitting = false;
  final Set<int> selected = <int>{};

  void toggle(int id) => setState(
    () => selected.contains(id) ? selected.remove(id) : selected.add(id),
  );

  Future<void> acceptSelected() async {
    final session = ref.read(authControllerProvider).value?.session;
    if (session == null || selected.isEmpty) return;
    setState(() => submitting = true);
    try {
      final result = await ref
          .read(clientCandidatesRepositoryProvider)
          .bulkAccept(
            session: session,
            candidateIds: selected.toList()..sort(),
          );
      final rows = (result['results'] as List<dynamic>? ?? const [])
          .whereType<Map>();
      int count(String status) =>
          rows.where((row) => row['result'] == status).length;
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Dodano: ${count('promoted')} · Duplikaty: ${count('duplicate')} · '
            'Konflikty: ${count('conflict')} · Błędy: ${count('failed') + count('not_found')}',
          ),
        ),
      );
      setState(() {
        selecting = false;
        selected.clear();
      });
      ref.invalidate(clientCandidatesProvider);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Nie udało się wykonać operacji zbiorczej.'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final value = ref.watch(clientCandidatesProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Kandydaci na klientów'),
        actions: <Widget>[
          TextButton.icon(
            key: const Key('candidate-multi-select'),
            onPressed: submitting
                ? null
                : () => setState(() {
                    selecting = !selecting;
                    selected.clear();
                  }),
            icon: Icon(selecting ? Icons.close : Icons.checklist),
            label: Text(selecting ? 'Anuluj wybór' : 'Wybierz kilka'),
          ),
          IconButton(
            onPressed: value.isLoading
                ? null
                : () => ref.invalidate(clientCandidatesProvider),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: value.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, _) => Center(
          child: FilledButton(
            onPressed: () => ref.invalidate(clientCandidatesProvider),
            child: const Text('Spróbuj ponownie'),
          ),
        ),
        data: (List<ClientCandidate> candidates) => Column(
          children: <Widget>[
            if (selecting)
              Padding(
                padding: const EdgeInsets.all(12),
                child: Wrap(
                  spacing: 12,
                  runSpacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: <Widget>[
                    Text(
                      'Wybrano: ${selected.length}',
                      key: const Key('candidate-selected-count'),
                    ),
                    FilledButton.icon(
                      key: const Key('candidate-bulk-accept'),
                      onPressed: selected.isEmpty || submitting
                          ? null
                          : acceptSelected,
                      icon: const Icon(Icons.person_add_alt_1),
                      label: const Text('Dodaj wybrane'),
                    ),
                  ],
                ),
              ),
            Expanded(
              child: candidates.isEmpty
                  ? const Center(child: Text('Brak oczekujących kandydatów.'))
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: candidates.length,
                      itemBuilder: (context, index) {
                        final candidate = candidates[index];
                        return Card(
                          child: ListTile(
                            leading: selecting
                                ? Checkbox(
                                    value: selected.contains(candidate.id),
                                    onChanged: (_) => toggle(candidate.id),
                                  )
                                : CircleAvatar(
                                    child: Text(
                                      candidate.displayName
                                          .substring(0, 1)
                                          .toUpperCase(),
                                    ),
                                  ),
                            title: Text(candidate.displayName),
                            subtitle: Text(
                              <String?>[
                                candidate.primaryEmail,
                                candidate.primaryPhone,
                                candidate.city,
                              ].whereType<String>().join(' · '),
                            ),
                            trailing: selecting
                                ? null
                                : const Icon(Icons.chevron_right),
                            onTap: () => selecting
                                ? toggle(candidate.id)
                                : context.push(
                                    '/client-candidates/${candidate.id}',
                                  ),
                          ),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
