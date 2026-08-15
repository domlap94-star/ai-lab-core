import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../auth/application/auth_controller.dart';
import '../../auth/application/auth_state.dart';
import '../../auth/domain/auth_session.dart';
import '../application/client_candidates_providers.dart';
import '../application/client_candidates_repository.dart';
import '../domain/client_candidate_context.dart';

class ClientCandidateDetailsPage extends ConsumerStatefulWidget {
  const ClientCandidateDetailsPage({required this.candidateId, super.key});

  final int candidateId;

  @override
  ConsumerState<ClientCandidateDetailsPage> createState() =>
      _ClientCandidateDetailsPageState();
}

class _ClientCandidateDetailsPageState
    extends ConsumerState<ClientCandidateDetailsPage> {
  bool _mutating = false;

  @override
  Widget build(BuildContext context) {
    final AsyncValue<ClientCandidateContext> value = ref.watch(
      clientCandidateContextProvider(widget.candidateId),
    );

    return PopScope<Object?>(
      canPop: context.canPop(),
      onPopInvokedWithResult: (bool didPop, Object? result) {
        if (!didPop) {
          context.go('/client-candidates');
        }
      },
      child: Scaffold(
        appBar: AppBar(
          leading: IconButton(
            tooltip: 'Wróć do kandydatów',
            onPressed: () {
              if (context.canPop()) {
                context.pop();
              } else {
                context.go('/client-candidates');
              }
            },
            icon: const Icon(Icons.arrow_back),
          ),
          title: Text('Kandydat #${widget.candidateId}'),
        ),
        body: value.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (Object error, StackTrace stackTrace) => Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Text(error.toString()),
            ),
          ),
          data: (ClientCandidateContext data) {
            final Map<String, dynamic> candidate = data.candidate;

            return ListView(
              padding: const EdgeInsets.fromLTRB(24, 20, 24, 40),
              children: <Widget>[
                _Section(
                  title: 'Dane kandydata',
                  children: <Widget>[
                    _Row('Nazwa', candidate['name']),
                    _Row('Typ', candidate['client_type']),
                    _Row('E-mail', candidate['primary_email']),
                    _Row('Telefon', candidate['primary_phone']),
                    _Row('NIP', candidate['tax_id']),
                    _Row('Miasto', candidate['city']),
                    _Row(
                      'Pewność',
                      '${(((candidate['confidence'] as num?) ?? 0) * 100).round()}%',
                    ),
                    _Row('Status', candidate['status']),
                  ],
                ),
                const SizedBox(height: 18),
                _Section(
                  title: 'Źródła',
                  children: <Widget>[
                    _Row('Google Sheets', data.sheetsCount),
                    _Row('Gmail', data.gmailCount),
                    _Row('Dokumenty', data.documentCount),
                    _Row('Wszystkie źródła', data.sourceCount),
                  ],
                ),
                if (data.sheetsRows.isNotEmpty) ...<Widget>[
                  const SizedBox(height: 18),
                  _Section(
                    title: 'Google Sheets',
                    children: data.sheetsRows
                        .map<Widget>(
                          (Map<String, dynamic> row) =>
                              _PayloadView(value: row['row_data']),
                        )
                        .toList(growable: false),
                  ),
                ],
                if (data.gmailMessages.isNotEmpty) ...<Widget>[
                  const SizedBox(height: 18),
                  _Section(
                    title: 'Gmail',
                    children: data.gmailMessages
                        .map<Widget>(
                          (Map<String, dynamic> message) =>
                              _PayloadView(value: message),
                        )
                        .toList(growable: false),
                  ),
                ],
                if (data.documents.isNotEmpty) ...<Widget>[
                  const SizedBox(height: 18),
                  _Section(
                    title: 'Dokumenty',
                    children: data.documents
                        .map<Widget>(
                          (Map<String, dynamic> document) => ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading: const Icon(Icons.description_outlined),
                            title: Text(
                              document['original_filename']?.toString() ??
                                  document['filename']?.toString() ??
                                  'Dokument',
                            ),
                            subtitle: Text('ID: ${document['id']}'),
                          ),
                        )
                        .toList(growable: false),
                  ),
                ],
                const SizedBox(height: 24),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: <Widget>[
                    FilledButton.icon(
                      onPressed: _mutating ? null : () => _accept(data),
                      icon: const Icon(Icons.person_add_alt_1),
                      label: const Text('Zatwierdź jako klienta'),
                    ),
                    OutlinedButton.icon(
                      onPressed: _mutating ? null : _reject,
                      icon: const Icon(Icons.close),
                      label: const Text('Odrzuć'),
                    ),
                  ],
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Future<AuthSession> _session() async {
    final AsyncValue<AuthState> authValue = ref.read(authControllerProvider);
    final AuthSession? session = authValue.value?.session;

    if (session == null || !session.isAuthenticated) {
      throw StateError('Brak aktywnej sesji.');
    }

    return session;
  }

  Future<void> _accept(ClientCandidateContext data) async {
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext dialogContext) {
        return AlertDialog(
          title: const Text('Zatwierdzić klienta?'),
          content: const Text(
            'Ta operacja utworzy rzeczywisty rekord klienta '
            'i przypisze do niego powiązane dokumenty.',
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Anuluj'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Zatwierdź'),
            ),
          ],
        );
      },
    );

    if (confirmed != true || !mounted) {
      return;
    }

    setState(() => _mutating = true);

    try {
      final AuthSession session = await _session();

      final ClientCandidatesRepository repository = ref.read(
        clientCandidatesRepositoryProvider,
      );

      final CandidateAcceptResult result = await repository.accept(
        session: session,
        candidateId: widget.candidateId,
      );

      ref.invalidate(clientCandidatesProvider);

      if (!mounted) {
        return;
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Utworzono klienta: ${result.clientName}')),
      );

      context.go('/clients/${result.clientId}');
    } on CandidateDuplicateException catch (error) {
      if (!mounted) {
        return;
      }

      await showDialog<void>(
        context: context,
        builder: (BuildContext dialogContext) {
          return AlertDialog(
            title: const Text('Możliwy duplikat'),
            content: Text(
              'Kandydat pasuje do istniejącego klienta '
              '#${error.clientId}.\n\n'
              'Dopasowanie: ${error.matchedBy}.\n\n'
              'Na razie nie wykonano żadnej zmiany.',
            ),
            actions: <Widget>[
              TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('OK'),
              ),
              FilledButton(
                onPressed: () {
                  Navigator.pop(dialogContext);
                  context.go('/clients/${error.clientId}');
                },
                child: const Text('Otwórz klienta'),
              ),
            ],
          );
        },
      );
    } on DioException catch (error) {
      if (mounted) {
        _showError(
          'Nie udało się zatwierdzić kandydata. '
          'HTTP ${error.response?.statusCode ?? '-'}.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _mutating = false);
      }
    }
  }

  Future<void> _reject() async {
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext dialogContext) {
        return AlertDialog(
          title: const Text('Odrzucić kandydata?'),
          content: const Text(
            'Kandydat otrzyma status rejected. '
            'Nie zostanie utworzony klient.',
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Anuluj'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Odrzuć'),
            ),
          ],
        );
      },
    );

    if (confirmed != true || !mounted) {
      return;
    }

    setState(() => _mutating = true);

    try {
      final AuthSession session = await _session();

      await ref
          .read(clientCandidatesRepositoryProvider)
          .reject(session: session, candidateId: widget.candidateId);

      ref.invalidate(clientCandidatesProvider);

      if (!mounted) {
        return;
      }

      context.go('/client-candidates');
    } on DioException catch (error) {
      if (mounted) {
        _showError(
          'Nie udało się odrzucić kandydata. '
          'HTTP ${error.response?.statusCode ?? '-'}.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _mutating = false);
      }
    }
  }

  void _showError(String text) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(text)));
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              title,
              style: Theme.of(
                context,
              ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 16),
            ...children,
          ],
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row(this.label, this.value);

  final String label;
  final Object? value;

  @override
  Widget build(BuildContext context) {
    final String text = value?.toString().trim() ?? '';

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          SizedBox(
            width: 160,
            child: Text(
              label,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
          Expanded(child: SelectableText(text.isEmpty ? '—' : text)),
        ],
      ),
    );
  }
}

class _PayloadView extends StatelessWidget {
  const _PayloadView({required this.value});

  final Object? value;

  @override
  Widget build(BuildContext context) {
    if (value is! Map) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 16),
        child: SelectableText(value?.toString() ?? '—'),
      );
    }

    final Map<dynamic, dynamic> map = value! as Map<dynamic, dynamic>;

    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Column(
        children: map.entries
            .where((MapEntry<dynamic, dynamic> entry) {
              final String text = entry.value?.toString().trim() ?? '';
              return text.isNotEmpty;
            })
            .map<Widget>(
              (MapEntry<dynamic, dynamic> entry) =>
                  _Row(entry.key.toString(), entry.value),
            )
            .toList(growable: false),
      ),
    );
  }
}
