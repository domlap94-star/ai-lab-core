import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/widgets/app_shell.dart';
import '../../../core/network/friendly_api_error.dart';
import '../../auth/application/auth_controller.dart';
import '../application/business_assistant_providers.dart';
import '../domain/business_assistant.dart';

export 'ai_page_v2.dart';

class LegacyAiPage extends ConsumerStatefulWidget {
  const LegacyAiPage({super.key});

  @override
  ConsumerState<LegacyAiPage> createState() => _AiPageState();
}

class _AiPageState extends ConsumerState<LegacyAiPage> {
  final _controller = TextEditingController();
  final _conversation = <Map<String, String>>[];
  BusinessAssistantAnswer? _answer;
  String? _error;
  CancelToken? _cancelToken;
  bool _loading = false;

  @override
  void dispose() {
    _cancelToken?.cancel();
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: AppShell.mobileNavigationLeading(context),
        title: const Text('Asystent AI'),
        actions: <Widget>[AppShell.globalSearchAction(context)],
      ),
      body: SafeArea(
        child: Align(
          alignment: Alignment.topCenter,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 920),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: <Widget>[
                  Text(
                    'Globalny asystent biznesowy tylko do odczytu',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Pyta o klientów, kandydatów, dokumenty, e-maile i wizje. Nie zmienia danych ani nie wykonuje działań.',
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    key: const Key('business-ai-question'),
                    controller: _controller,
                    enabled: !_loading,
                    minLines: 1,
                    maxLines: 4,
                    maxLength: 1000,
                    textInputAction: TextInputAction.send,
                    onSubmitted: (_) => _ask(),
                    decoration: const InputDecoration(
                      hintText:
                          'Zapytaj o firmę, klientów, dokumenty, wizje...',
                      prefixIcon: Icon(Icons.auto_awesome_outlined),
                      border: OutlineInputBorder(),
                    ),
                  ),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children:
                        <String>[
                              'Co wydarzyło się w CRM w ostatnich 7 dniach?',
                              'Ilu klientów ma status Oględziny?',
                              'Którzy klienci nie mieli kontaktu od 30 dni?',
                              'Jakie wizje lokalne są zaplanowane?',
                            ]
                            .map(
                              (question) => ActionChip(
                                key: ValueKey<String>(
                                  'business-ai-example-$question',
                                ),
                                label: Text(
                                  question,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                                onPressed: _loading
                                    ? null
                                    : () {
                                        _controller.text = question;
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
                            spacing: 12,
                            crossAxisAlignment: WrapCrossAlignment.center,
                            children: <Widget>[
                              const SizedBox(
                                width: 22,
                                height: 22,
                                child: CircularProgressIndicator(
                                  strokeWidth: 3,
                                ),
                              ),
                              OutlinedButton(
                                key: const Key('business-ai-cancel'),
                                onPressed: _cancel,
                                child: const Text('Anuluj'),
                              ),
                            ],
                          )
                        : FilledButton.icon(
                            key: const Key('business-ai-send'),
                            onPressed: _ask,
                            icon: const Icon(Icons.send_outlined),
                            label: const Text('Wyślij'),
                          ),
                  ),
                  if (_error != null) ...<Widget>[
                    const SizedBox(height: 16),
                    Material(
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
                            Text(_error!, key: const Key('business-ai-error')),
                            TextButton.icon(
                              key: const Key('business-ai-retry'),
                              onPressed: _ask,
                              icon: const Icon(Icons.refresh),
                              label: const Text('Spróbuj ponownie'),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                  if (_answer != null) ...<Widget>[
                    const SizedBox(height: 20),
                    Text(
                      'Odpowiedź',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    SelectableText(
                      _answer!.answer,
                      key: const Key('business-ai-answer'),
                    ),
                    if (_answer!.sources.isNotEmpty) ...<Widget>[
                      const SizedBox(height: 18),
                      Text(
                        'Źródła',
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                      ..._answer!.sources.map(_sourceTile),
                    ],
                    ..._answer!.limitations.map(
                      (item) => Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(
                          item,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _sourceTile(BusinessAssistantSource source) => ListTile(
    key: ValueKey<String>(
      'business-ai-source-${source.sourceType}-${source.sourceId}',
    ),
    contentPadding: EdgeInsets.zero,
    leading: const Icon(Icons.open_in_new),
    title: Text(source.title, maxLines: 2, overflow: TextOverflow.ellipsis),
    subtitle: Text(
      source.snippet,
      maxLines: 3,
      overflow: TextOverflow.ellipsis,
    ),
    onTap: source.route == null ? null : () => context.push(source.route!),
  );

  Future<void> _ask() async {
    final question = _controller.text.trim();
    if (_loading || question.length < 2) return;
    final session = (await ref.read(authControllerProvider.future)).session;
    if (session == null || !mounted) return;
    _cancelToken?.cancel('superseded');
    final cancelToken = CancelToken();
    _cancelToken = cancelToken;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await ref
          .read(businessAssistantGatewayProvider)
          .ask(
            session: session,
            question: question,
            conversation: List.unmodifiable(
              _conversation.length <= 8
                  ? _conversation
                  : _conversation.sublist(_conversation.length - 8),
            ),
            cancelToken: cancelToken,
          );
      if (!mounted || !identical(cancelToken, _cancelToken)) return;
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
      if (mounted && identical(cancelToken, _cancelToken)) {
        setState(() => _loading = false);
      }
    }
  }

  void _cancel() {
    _cancelToken?.cancel('Anulowano przez użytkownika');
    _cancelToken = null;
    setState(() => _loading = false);
  }
}
