import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/network/friendly_api_error.dart';
import '../../auth/application/auth_controller.dart';
import '../application/client_ai_knowledge_providers.dart';
import '../domain/client_ai_knowledge.dart';

class ClientAiKnowledgePanel extends ConsumerStatefulWidget {
  const ClientAiKnowledgePanel({
    required this.clientId,
    required this.clientName,
    super.key,
  });
  final int clientId;
  final String clientName;
  @override
  ConsumerState<ClientAiKnowledgePanel> createState() =>
      _ClientAiKnowledgePanelState();
}

class _ClientAiKnowledgePanelState
    extends ConsumerState<ClientAiKnowledgePanel> {
  static const _examples = <String>[
    'Co ostatnio ustaliliśmy z klientem?',
    'Jakie realizacje ma ten klient?',
    'Czy mamy dokument dotyczący fundamentów?',
  ];
  final _questionController = TextEditingController();
  final _conversation = <Map<String, String>>[];
  ClientAiAnswer? _answer;
  String? _error;
  String? _lastQuestion;
  bool _loading = false;
  CancelToken? _cancelToken;

  @override
  void dispose() {
    _cancelToken?.cancel();
    _questionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      key: const Key('client-ai-knowledge-panel'),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(
                  Icons.auto_awesome_outlined,
                  color: theme.colorScheme.primary,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Zapytaj AI o klienta',
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Odpowiedzi powstają wyłącznie na podstawie danych ${widget.clientName}.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 14),
            TextField(
              key: const Key('client-ai-question'),
              controller: _questionController,
              enabled: !_loading,
              minLines: 1,
              maxLines: 4,
              maxLength: 1000,
              textInputAction: TextInputAction.send,
              decoration: const InputDecoration(
                hintText: 'Co ostatnio ustaliliśmy z klientem?',
                border: OutlineInputBorder(),
              ),
              onSubmitted: (_) => _ask(),
            ),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _examples
                  .map(
                    (question) => ActionChip(
                      label: Text(question, overflow: TextOverflow.ellipsis),
                      onPressed: _loading
                          ? null
                          : () {
                              _questionController.text = question;
                              _ask();
                            },
                    ),
                  )
                  .toList(growable: false),
            ),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerRight,
              child: _loading
                  ? Wrap(
                      crossAxisAlignment: WrapCrossAlignment.center,
                      spacing: 12,
                      children: <Widget>[
                        const SizedBox(
                          width: 22,
                          height: 22,
                          child: CircularProgressIndicator(strokeWidth: 3),
                        ),
                        OutlinedButton(
                          key: const Key('client-ai-cancel'),
                          onPressed: _cancel,
                          child: const Text('Anuluj'),
                        ),
                      ],
                    )
                  : FilledButton.icon(
                      key: const Key('client-ai-send'),
                      onPressed: _ask,
                      icon: const Icon(Icons.send_outlined),
                      label: const Text('Wyślij'),
                    ),
            ),
            if (_error != null) ...<Widget>[
              const SizedBox(height: 16),
              _ErrorCard(message: _error!, onRetry: _retry),
            ],
            if (_answer != null) ...<Widget>[
              const SizedBox(height: 18),
              Text('Odpowiedź', style: theme.textTheme.titleSmall),
              const SizedBox(height: 8),
              SelectableText(
                _answer!.answer,
                key: const Key('client-ai-answer'),
              ),
              if (_answer!.sources.isNotEmpty) ...<Widget>[
                const SizedBox(height: 18),
                Text('Źródła', style: theme.textTheme.titleSmall),
                const SizedBox(height: 6),
                ..._answer!.sources.map(_sourceTile),
              ],
              if (_answer!.limitations.isNotEmpty) ...<Widget>[
                const SizedBox(height: 12),
                ..._answer!.limitations.map(
                  (item) => Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text(
                      item,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }

  Widget _sourceTile(ClientAiSource source) => ListTile(
    key: ValueKey<String>(
      'client-ai-source-${source.sourceType}-${source.sourceId}',
    ),
    contentPadding: EdgeInsets.zero,
    leading: Icon(_sourceIcon(source.sourceType)),
    title: Text(source.title, maxLines: 2, overflow: TextOverflow.ellipsis),
    subtitle: Text(
      source.snippet,
      maxLines: 3,
      overflow: TextOverflow.ellipsis,
    ),
    trailing: const Icon(Icons.open_in_new),
    onTap: source.route == '/clients/${widget.clientId}'
        ? null
        : () => context.push(source.route),
  );

  IconData _sourceIcon(String type) => switch (type) {
    'email' => Icons.email_outlined,
    'document' => Icons.description_outlined,
    'project' => Icons.business_center_outlined,
    'inspection' => Icons.fact_check_outlined,
    'timeline' => Icons.timeline_outlined,
    _ => Icons.person_outline,
  };

  Future<void> _ask() async {
    final question = _questionController.text.trim();
    if (question.length < 2 || _loading) return;
    final session = (await ref.read(authControllerProvider.future)).session;
    if (session == null || !mounted) return;
    _cancelToken?.cancel();
    final cancelToken = CancelToken();
    _cancelToken = cancelToken;
    setState(() {
      _loading = true;
      _error = null;
      _lastQuestion = question;
    });
    try {
      final result = await ref
          .read(clientAiKnowledgeGatewayProvider)
          .ask(
            session: session,
            clientId: widget.clientId,
            question: question,
            conversation: List<Map<String, String>>.unmodifiable(
              _conversation.length <= 8
                  ? _conversation
                  : _conversation.sublist(_conversation.length - 8),
            ),
            cancelToken: cancelToken,
          );
      if (!mounted) return;
      setState(() {
        _answer = result;
        _conversation
          ..add(<String, String>{'role': 'user', 'content': question})
          ..add(<String, String>{
            'role': 'assistant',
            'content': result.answer,
          });
      });
    } on DioException catch (error) {
      if (!mounted || CancelToken.isCancel(error)) return;
      setState(
        () => _error = friendlyApiError(
          error,
          fallback: 'Nie udało się uzyskać odpowiedzi AI.',
        ),
      );
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Nie udało się uzyskać odpowiedzi AI.');
      }
    } finally {
      if (mounted && identical(_cancelToken, cancelToken)) {
        setState(() => _loading = false);
      }
    }
  }

  void _retry() {
    if (_lastQuestion != null) {
      _questionController.text = _lastQuestion!;
      _ask();
    }
  }

  void _cancel() {
    _cancelToken?.cancel('Anulowano przez użytkownika');
    setState(() => _loading = false);
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) => Material(
    color: Theme.of(context).colorScheme.errorContainer,
    borderRadius: BorderRadius.circular(12),
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Wrap(
        alignment: WrapAlignment.spaceBetween,
        crossAxisAlignment: WrapCrossAlignment.center,
        spacing: 12,
        runSpacing: 8,
        children: <Widget>[
          Text(message, key: const Key('client-ai-error')),
          TextButton.icon(
            key: const Key('client-ai-retry'),
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('Spróbuj ponownie'),
          ),
        ],
      ),
    ),
  );
}
