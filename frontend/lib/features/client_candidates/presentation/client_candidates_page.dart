import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../application/client_candidates_providers.dart';
import '../domain/client_candidate.dart';

class ClientCandidatesPage extends ConsumerWidget {
  const ClientCandidatesPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<List<ClientCandidate>> value = ref.watch(
      clientCandidatesProvider,
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Kandydaci na klientów'),
        actions: <Widget>[
          IconButton(
            tooltip: 'Odśwież',
            onPressed: value.isLoading
                ? null
                : () {
                    ref.invalidate(clientCandidatesProvider);
                  },
            icon: const Icon(Icons.refresh),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: value.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (Object error, StackTrace stackTrace) => _ErrorView(
          message: _message(error),
          onRetry: () {
            ref.invalidate(clientCandidatesProvider);
          },
        ),
        data: (List<ClientCandidate> candidates) {
          if (candidates.isEmpty) {
            return const Center(child: Text('Brak oczekujących kandydatów.'));
          }

          return RefreshIndicator(
            onRefresh: () async {
              ref.invalidate(clientCandidatesProvider);
              await ref.read(clientCandidatesProvider.future);
            },
            child: ListView.builder(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
              itemCount: candidates.length + 1,
              itemBuilder: (BuildContext context, int index) {
                if (index == 0) {
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 16),
                    child: Text(
                      'Pierwsze ${candidates.length} oczekujących kandydatów',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  );
                }

                final ClientCandidate candidate = candidates[index - 1];

                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Card(
                    child: InkWell(
                      borderRadius: BorderRadius.circular(12),
                      onTap: () {
                        context.push('/client-candidates/${candidate.id}');
                      },
                      child: Padding(
                        padding: const EdgeInsets.all(18),
                        child: Row(
                          children: <Widget>[
                            CircleAvatar(
                              child: Text(
                                candidate.displayName
                                    .substring(0, 1)
                                    .toUpperCase(),
                              ),
                            ),
                            const SizedBox(width: 16),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: <Widget>[
                                  Text(
                                    candidate.displayName,
                                    style: Theme.of(context)
                                        .textTheme
                                        .titleMedium
                                        ?.copyWith(fontWeight: FontWeight.w700),
                                  ),
                                  if (candidate.primaryEmail != null)
                                    Text(candidate.primaryEmail!),
                                  if (candidate.primaryPhone != null)
                                    Text(candidate.primaryPhone!),
                                  if (candidate.city != null)
                                    Text(candidate.city!),
                                  const SizedBox(height: 8),
                                  Wrap(
                                    spacing: 8,
                                    runSpacing: 8,
                                    children: <Widget>[
                                      Chip(
                                        label: Text(
                                          'Pewność: '
                                          '${(candidate.confidence * 100).round()}%',
                                        ),
                                      ),
                                      Chip(
                                        label: Text(
                                          _typeLabel(candidate.clientType),
                                        ),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                            const Icon(Icons.chevron_right),
                          ],
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }

  static String _typeLabel(String value) {
    switch (value) {
      case 'company':
        return 'Firma';
      case 'person':
        return 'Osoba';
      case 'institution':
        return 'Instytucja';
      default:
        return 'Inny';
    }
  }

  static String _message(Object error) {
    if (error is ClientCandidatesAuthenticationException) {
      return error.message;
    }

    if (error is DioException) {
      return 'Błąd HTTP: ${error.response?.statusCode ?? '-'}';
    }

    return error.toString();
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            const Icon(Icons.error_outline, size: 56),
            const SizedBox(height: 16),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: onRetry,
              child: const Text('Spróbuj ponownie'),
            ),
          ],
        ),
      ),
    );
  }
}
