import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/widgets/app_shell.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/application/auth_state.dart';
import '../../auth/domain/auth_session.dart';
import '../../mail/data/global_mail_api.dart';
import '../../mail/presentation/ignored_mail_source_controls.dart';
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

  bool get _isAdmin =>
      ref.read(authControllerProvider).value?.user?.role == 'Administrator';

  @override
  Widget build(BuildContext context) {
    final AsyncValue<ClientCandidateContext> value = ref.watch(
      clientCandidateContextProvider(widget.candidateId),
    );

    final bool centrallyHandled = AppShell.centrallyHandlesBack(context);
    return PopScope<Object?>(
      canPop: centrallyHandled || context.canPop(),
      onPopInvokedWithResult: (bool didPop, Object? result) {
        if (!didPop && !centrallyHandled) {
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
          actions: <Widget>[
            IconButton(
              key: const Key('candidate-unified-assistant'),
              tooltip: 'Zapytaj Asystenta AI',
              onPressed: () =>
                  context.push('/ai?candidate_id=${widget.candidateId}'),
              icon: const Icon(Icons.auto_awesome_outlined),
            ),
          ],
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
                        .map<Widget>((Map<String, dynamic> message) {
                          final String? sender = _candidateMailSender(
                            message,
                            candidate,
                          );
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 12),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                _PayloadView(value: message),
                                if (_isAdmin && sender != null) ...<Widget>[
                                  const SizedBox(height: 8),
                                  OutlinedButton.icon(
                                    key: ValueKey<String>(
                                      'candidate-ignore-mail-${message['source_id']}',
                                    ),
                                    onPressed: _mutating
                                        ? null
                                        : () => _ignoreMail(sender),
                                    icon: const Icon(Icons.block_outlined),
                                    label: const Text('Ignoruj ten mail'),
                                  ),
                                ],
                              ],
                            ),
                          );
                        })
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

  static String? _candidateMailSender(
    Map<String, dynamic> message,
    Map<String, dynamic> candidate,
  ) {
    final Object? from = message['from'];
    final String? sender = canonicalIgnoredMailAddress(
      from is Map ? from['address']?.toString() : null,
    );
    final String? candidateAddress = canonicalIgnoredMailAddress(
      candidate['primary_email']?.toString(),
    );
    return sender != null && sender == candidateAddress ? sender : null;
  }

  Future<void> _ignoreMail(String sender) async {
    setState(() => _mutating = true);
    try {
      final AuthSession session = await _session();
      if (!mounted) return;
      await showIgnoreMailSenderDialog(
        context: context,
        api: ref.read(globalMailApiProvider),
        session: session,
        sender: sender,
      );
    } finally {
      if (mounted) setState(() => _mutating = false);
    }
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
      await _showDuplicateDialog(error);
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

  Future<void> _showDuplicateDialog(CandidateDuplicateException error) async {
    final List<CandidateDuplicateMatch> matches = error.matches.isEmpty
        ? <CandidateDuplicateMatch>[
            CandidateDuplicateMatch(
              clientId: error.clientId,
              clientName: 'Klient #${error.clientId}',
              workflowStatus: 'untouched',
              workflowStatusLabel: 'Brak modyfikacji',
              confidence: 'certain',
              reasons: <String>[error.matchedBy],
            ),
          ]
        : error.matches;

    await showDialog<void>(
      context: context,
      builder: (BuildContext dialogContext) => AlertDialog(
        title: const Text('Znaleziono istniejącego klienta'),
        content: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: matches
                  .map(
                    (CandidateDuplicateMatch match) => Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text(
                              match.clientName.isEmpty
                                  ? 'Klient #${match.clientId}'
                                  : match.clientName,
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                            const SizedBox(height: 6),
                            Text(
                              '${match.workflowStatusLabel}\n'
                              'Powody: ${match.reasons.map(_reasonLabel).join(', ')}',
                            ),
                            const SizedBox(height: 8),
                            Wrap(
                              spacing: 8,
                              children: <Widget>[
                                TextButton(
                                  onPressed: () {
                                    Navigator.pop(dialogContext);
                                    context.go('/clients/${match.clientId}');
                                  },
                                  child: const Text('Otwórz klienta'),
                                ),
                                FilledButton(
                                  onPressed: () {
                                    Navigator.pop(dialogContext);
                                    _previewMerge(match);
                                  },
                                  child: const Text('Połącz'),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                  )
                  .toList(growable: false),
            ),
          ),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Anuluj'),
          ),
        ],
      ),
    );
  }

  Future<void> _previewMerge(CandidateDuplicateMatch match) async {
    setState(() => _mutating = true);
    try {
      final AuthSession session = await _session();
      final repository = ref.read(clientCandidatesRepositoryProvider);
      final preview = await repository.fetchMergePreview(
        session: session,
        candidateId: widget.candidateId,
        targetClientId: match.clientId,
      );
      if (!mounted) return;

      final Map<String, String> decisions = <String, String>{};
      for (final proposal in preview.fieldProposals) {
        final field = proposal['field']?.toString() ?? '';
        final action =
            proposal['proposed_action']?.toString() ?? 'keep_existing';
        if (field.isNotEmpty && action != 'manual_conflict') {
          decisions[field] = action;
        }
      }

      final bool? reviewed = await showDialog<bool>(
        context: context,
        builder: (BuildContext dialogContext) => StatefulBuilder(
          builder: (BuildContext context, StateSetter setDialogState) {
            return AlertDialog(
              title: const Text('Podgląd połączenia'),
              content: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 720),
                child: SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      Text(
                        '${preview.candidate['name']}  →  ${preview.target['name']}',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 12),
                      ...preview.fieldProposals.map((proposal) {
                        final field = proposal['field']?.toString() ?? '';
                        final required =
                            proposal['required_resolution'] == true;
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 8),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              Text(
                                _fieldLabel(field),
                                style: Theme.of(context).textTheme.titleSmall,
                              ),
                              Text(
                                'Kandydat: ${proposal['candidate_value'] ?? '—'}\n'
                                'Klient: ${proposal['target_value'] ?? '—'}',
                              ),
                              const SizedBox(height: 6),
                              if (required)
                                DropdownButton<String>(
                                  value: decisions[field],
                                  hint: const Text('Wybierz'),
                                  isExpanded: true,
                                  items: const <DropdownMenuItem<String>>[
                                    DropdownMenuItem(
                                      value: 'keep_existing',
                                      child: Text('Zachowaj klienta'),
                                    ),
                                    DropdownMenuItem(
                                      value: 'take_candidate',
                                      child: Text('Użyj kandydata'),
                                    ),
                                  ],
                                  onChanged: (String? value) {
                                    if (value != null) {
                                      setDialogState(
                                        () => decisions[field] = value,
                                      );
                                    }
                                  },
                                )
                              else
                                Text(
                                  _actionLabel(
                                    decisions[field] ?? 'keep_existing',
                                  ),
                                ),
                            ],
                          ),
                        );
                      }),
                      const Divider(),
                      Text(
                        'Dokumenty: ${preview.relationCounts['documents_relinked'] ?? 0}, '
                        'maile: ${preview.relationCounts['emails_relinked'] ?? 0}, '
                        'źródła zachowane: ${preview.relationCounts['sources_preserved'] ?? 0}.',
                      ),
                    ],
                  ),
                ),
              ),
              actions: <Widget>[
                TextButton(
                  onPressed: () => Navigator.pop(dialogContext, false),
                  child: const Text('Anuluj'),
                ),
                FilledButton(
                  onPressed:
                      preview.fieldProposals.any(
                        (proposal) =>
                            proposal['required_resolution'] == true &&
                            !decisions.containsKey(
                              proposal['field']?.toString(),
                            ),
                      )
                      ? null
                      : () => Navigator.pop(dialogContext, true),
                  child: const Text('Dalej'),
                ),
              ],
            );
          },
        ),
      );
      if (reviewed != true || !mounted) return;

      final bool? confirmed = await showDialog<bool>(
        context: context,
        builder: (BuildContext dialogContext) => AlertDialog(
          title: const Text('Potwierdź połączenie'),
          content: Text(
            'Czy na pewno chcesz połączyć tego kandydata z klientem '
            '${preview.target['name']}? Powiązania zostaną przeniesione, '
            'a operacja zostanie zapisana w historii audytu.',
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Anuluj'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Połącz'),
            ),
          ],
        ),
      );
      if (confirmed != true || !mounted) return;

      final result = await repository.merge(
        session: session,
        candidateId: widget.candidateId,
        targetClientId: match.clientId,
        operationId: _operationId(),
        expectedCandidateVersion: preview.expectedCandidateVersion,
        fieldDecisions: decisions,
      );
      ref.invalidate(clientCandidatesProvider);
      ref.invalidate(clientCandidateContextProvider(widget.candidateId));
      if (!mounted) return;
      context.go('/clients/${result.clientId}');
    } on DioException catch (error) {
      if (mounted) {
        _showError(
          'Nie udało się połączyć kandydata. '
          'HTTP ${error.response?.statusCode ?? '-'}.',
        );
      }
    } finally {
      if (mounted) setState(() => _mutating = false);
    }
  }

  static String _reasonLabel(String value) => switch (value) {
    'exact_tax_id' => 'identyczny NIP',
    'exact_email' => 'identyczny e-mail',
    'exact_phone' => 'identyczny telefon',
    'verified_source_identity' => 'zweryfikowane źródło',
    _ => value,
  };

  static String _fieldLabel(String value) => switch (value) {
    'name' => 'Nazwa',
    'legal_name' => 'Nazwa prawna',
    'tax_id' => 'NIP',
    'primary_email' => 'E-mail',
    'primary_phone' => 'Telefon',
    'address' => 'Adres',
    _ => value,
  };

  static String _actionLabel(String value) => switch (value) {
    'take_candidate' => 'Użyj danych kandydata',
    'add' => 'Dodaj',
    _ => 'Zachowaj istniejące',
  };

  static String _operationId() {
    final Random random = Random.secure();
    final List<int> bytes = List<int>.generate(16, (_) => random.nextInt(256));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    final String hex = bytes
        .map((int value) => value.toRadixString(16).padLeft(2, '0'))
        .join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-'
        '${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
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
