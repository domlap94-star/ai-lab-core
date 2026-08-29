import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:go_router/go_router.dart';
import '../../../core/network/friendly_api_error.dart';
import '../../../core/widgets/app_shell.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/domain/auth_session.dart';
import '../../clients/presentation/searchable_client_picker.dart';
import '../application/assistant_run_controller.dart';
import '../application/assistant_conversation_controller.dart';
import '../domain/assistant_conversation.dart';
import '../domain/assistant_run.dart';
import '../domain/unified_assistant.dart';
import 'assistant_chat_history_sheet.dart';

class UnifiedAssistantPage extends ConsumerStatefulWidget {
  const UnifiedAssistantPage({
    this.initialClientId,
    this.initialCandidateId,
    this.initialDocumentId,
    this.initialMailSourceId,
    this.initialInspectionId,
    this.initialQuestion,
    super.key,
  });
  final int? initialClientId;
  final int? initialCandidateId;
  final int? initialDocumentId;
  final int? initialMailSourceId;
  final int? initialInspectionId;
  final String? initialQuestion;
  @override
  ConsumerState<UnifiedAssistantPage> createState() =>
      _UnifiedAssistantPageState();
}

class _UnifiedAssistantPageState extends ConsumerState<UnifiedAssistantPage> {
  static const _storage = FlutterSecureStorage();
  static const _pendingRequestKey = 'unified_assistant_pending_run_v2';
  static const _latestRequestKey = 'unified_assistant_latest_run_v2';
  static const _selectedConversationKey =
      'unified_assistant_selected_conversation_v2';
  static const quickActions = <String>[
    'Podsumuj ten przypadek',
    'Co sprawdzić podczas wizji lokalnej?',
    'Jakich danych brakuje?',
    'Co mówi dokumentacja?',
    'Znajdź najnowsze dokumenty',
    'Podsumuj ostatnią aktywność',
  ];
  final controller = TextEditingController();
  CancelToken? cancelToken;
  Timer? hiddenRunTimer;
  String? activeRequestId;
  AssistantRunSnapshot? activeRun;
  AssistantRunSnapshot? hiddenActiveRun;
  AssistantConversationDetail? activeConversation;
  UnifiedAssistantAnswer? result;
  String? error;
  String progress = '';
  bool loading = false;
  int? clientId;
  String? clientName;
  @override
  void initState() {
    super.initState();
    clientId = widget.initialClientId;
    clientName = clientId == null ? null : 'Klient #$clientId';
    controller.text = widget.initialQuestion ?? '';
    unawaited(_restoreAssistantState());
  }

  @override
  void dispose() {
    cancelToken?.cancel();
    hiddenRunTimer?.cancel();
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      leading: AppShell.mobileNavigationLeading(context),
      title: const Text('Asystent AI'),
      actions: <Widget>[
        IconButton(
          key: const Key('assistant-history-menu'),
          tooltip: 'Historia rozmów',
          onPressed: _openHistory,
          icon: const Icon(Icons.more_vert),
        ),
        AppShell.globalSearchAction(context),
      ],
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
                if (hiddenActiveRun != null) _hiddenActiveRunCard(),
                if (activeConversation != null) ...<Widget>[
                  Text(
                    activeConversation!.title,
                    key: const Key('assistant-active-conversation-title'),
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 12),
                  _conversationView(activeConversation!),
                  const SizedBox(height: 12),
                ],
                Text(
                  'Jeden asystent, pełny kontekst',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                const Text(
                  'Zadaj pytanie naturalnie. Asystent dobierze bezpiecznie dane, dokumenty, pocztę, obliczenia i analizę obrazu.',
                ),
                const SizedBox(height: 16),
                SearchableClientPicker(
                  key: ValueKey<String>('unified-client-${clientId ?? 0}'),
                  initialClientId: clientId,
                  initialClientName: clientName,
                  enabled: !loading,
                  onChanged: (selection) => setState(() {
                    clientId = selection?.id;
                    clientName = selection?.name;
                    result = null;
                  }),
                ),
                const SizedBox(height: 12),
                TextField(
                  key: const Key('unified-ai-question'),
                  controller: controller,
                  enabled: !loading,
                  minLines: 2,
                  maxLines: 7,
                  maxLength: 2000,
                  decoration: const InputDecoration(
                    hintText:
                        'Zapytaj o klienta, dokument, mail, wizję lub potrzebne obliczenie…',
                    prefixIcon: Icon(Icons.auto_awesome_outlined),
                    border: OutlineInputBorder(),
                  ),
                ),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: quickActions
                      .map(
                        (question) => ActionChip(
                          key: ValueKey<String>('unified-ai-quick-$question'),
                          label: Text(
                            question,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          onPressed: loading
                              ? null
                              : () {
                                  controller.text = question;
                                  ask();
                                },
                        ),
                      )
                      .toList(growable: false),
                ),
                const SizedBox(height: 12),
                Align(
                  alignment: Alignment.centerRight,
                  child: loading
                      ? Wrap(
                          spacing: 12,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: <Widget>[
                            const SizedBox(
                              width: 22,
                              height: 22,
                              child: CircularProgressIndicator(strokeWidth: 3),
                            ),
                            Text(
                              progress,
                              key: const Key('unified-ai-progress'),
                            ),
                            const Text(
                              'Możesz opuścić ten ekran. Analiza będzie kontynuowana.',
                              key: Key('unified-ai-durable-hint'),
                            ),
                            OutlinedButton(
                              onPressed: () => unawaited(cancel()),
                              child: const Text('Anuluj'),
                            ),
                          ],
                        )
                      : FilledButton.icon(
                          key: const Key('unified-ai-send'),
                          onPressed: ask,
                          icon: const Icon(Icons.send_outlined),
                          label: const Text('Wyślij'),
                        ),
                ),
                if (error != null) errorCard(),
                if (activeConversation == null &&
                    result != null &&
                    _hasRenderableAnswer(result!))
                  answerView(result!),
              ],
            ),
          ),
        ),
      ),
    ),
  );

  Widget _conversationView(AssistantConversationDetail detail) {
    final assistantMessages = detail.messages
        .where((message) => message.role == 'assistant')
        .toList(growable: false);
    final latestAssistantId = assistantMessages.isEmpty
        ? null
        : assistantMessages.last.id;
    return Column(
      key: ValueKey<String>('assistant-conversation-${detail.id}'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: detail.messages
          .map((message) {
            final isUser = message.role == 'user';
            final isLatestAssistant = message.id == latestAssistantId;
            return Align(
              alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
              child: Container(
                constraints: const BoxConstraints(maxWidth: 760),
                margin: const EdgeInsets.only(bottom: 10),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: isUser
                      ? Theme.of(context).colorScheme.primaryContainer
                      : Theme.of(context).colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    SelectableText(
                      message.content,
                      key: isLatestAssistant
                          ? const Key('unified-ai-answer')
                          : ValueKey<String>('assistant-message-${message.id}'),
                    ),
                    if (!isUser && message.runResult != null) ...<Widget>[
                      Material(
                        color: Colors.transparent,
                        child: ExpansionTile(
                          key: isLatestAssistant
                              ? const Key('unified-ai-sources')
                              : ValueKey<String>(
                                  'assistant-message-sources-${message.id}',
                                ),
                          tilePadding: EdgeInsets.zero,
                          title: const Text('Źródła'),
                          subtitle: Text(
                            message.runResult!.sources.isEmpty
                                ? 'Odpowiedź oparta na wiedzy ogólnej.'
                                : '${message.runResult!.sources.length} użytych źródeł',
                          ),
                          children: message.runResult!.sources
                              .map(
                                (source) => ListTile(
                                  key: isLatestAssistant
                                      ? ValueKey<String>(
                                          'unified-source-${source.sourceRef}',
                                        )
                                      : ValueKey<String>(
                                          'assistant-source-${message.id}-${source.sourceRef}',
                                        ),
                                  contentPadding: EdgeInsets.zero,
                                  title: Text(source.title),
                                  subtitle: Text(
                                    '${source.excerpt}\n${source.whyUsed}',
                                  ),
                                  onTap: source.route == null
                                      ? null
                                      : () => context.push(source.route!),
                                ),
                              )
                              .toList(growable: false),
                        ),
                      ),
                      ...message.runResult!.claims
                          .where((claim) => claim.claimClass != 'FACT')
                          .map(
                            (claim) => claimCard(
                              claim,
                              keyPrefix: isLatestAssistant
                                  ? 'unified'
                                  : 'assistant-${message.id}',
                            ),
                          ),
                    ],
                    if (message.runStatus != null &&
                        message.runStatus != 'completed')
                      Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text(
                          _runStatusLabel(message.runStatus!),
                          key: ValueKey<String>(
                            'assistant-message-status-${message.id}',
                          ),
                          style: Theme.of(context).textTheme.labelMedium,
                        ),
                      ),
                  ],
                ),
              ),
            );
          })
          .toList(growable: false),
    );
  }

  Widget _hiddenActiveRunCard() => Card(
    key: const Key('assistant-hidden-active-run'),
    color: Theme.of(context).colorScheme.tertiaryContainer,
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        children: <Widget>[
          const Icon(Icons.pending_outlined),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                const Text('Analiza z usuniętej rozmowy nadal trwa.'),
                Text(hiddenActiveRun!.progress.display),
              ],
            ),
          ),
          TextButton(
            key: const Key('assistant-hidden-active-cancel'),
            onPressed: _cancelHiddenRun,
            child: const Text('Anuluj'),
          ),
        ],
      ),
    ),
  );

  String _runStatusLabel(String status) => switch (status) {
    'review_required' => 'Wymaga bezpiecznej weryfikacji',
    'failed' => 'Analiza nie powiodła się',
    'cancelled' => 'Analiza anulowana',
    'created' || 'queued' || 'running' || 'waiting' => 'Analiza trwa',
    _ => status,
  };

  Widget errorCard() => Padding(
    padding: const EdgeInsets.only(top: 16),
    child: Material(
      color: Theme.of(context).colorScheme.errorContainer,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: <Widget>[
            Expanded(child: Text(error!, key: const Key('unified-ai-error'))),
            TextButton.icon(
              onPressed: ask,
              icon: const Icon(Icons.refresh),
              label: const Text('Spróbuj ponownie'),
            ),
          ],
        ),
      ),
    ),
  );

  Widget answerView(UnifiedAssistantAnswer answer) => Padding(
    padding: const EdgeInsets.only(top: 20),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Text('Odpowiedź', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        SelectableText(answer.answer, key: const Key('unified-ai-answer')),
        ExpansionTile(
          key: const Key('unified-ai-sources'),
          initiallyExpanded: false,
          tilePadding: EdgeInsets.zero,
          title: const Text('Źródła'),
          subtitle: Text(
            answer.sources.isEmpty
                ? 'Odpowiedź oparta na wiedzy ogólnej.'
                : '${answer.sources.length} użytych źródeł',
          ),
          children: answer.sources.map(sourceTile).toList(growable: false),
        ),
        ...answer.claims
            .where((claim) => claim.claimClass != 'FACT')
            .map(claimCard),
      ],
    ),
  );

  bool _hasRenderableAnswer(UnifiedAssistantAnswer answer) =>
      !answer.isPending &&
      (answer.status == 'accepted_local' ||
          answer.status == 'accepted_advanced') &&
      answer.answer.trim().isNotEmpty;

  Widget claimCard(
    UnifiedAssistantClaim claim, {
    String keyPrefix = 'unified',
  }) {
    final label = switch (claim.claimClass) {
      'ESTIMATE' =>
        claim.estimateStatus == 'NOT_ESTIMABLE'
            ? 'Nie można wiarygodnie oszacować'
            : 'Estymacja${claim.confidence == null ? '' : ' — ${_confidenceLabel(claim.confidence!)} pewność'}',
      'HYPOTHESIS' => 'Hipoteza',
      'MISSING' => 'Brakujące dane',
      _ => claim.claimClass,
    };
    return Card(
      key: ValueKey<String>('$keyPrefix-claim-${claim.claimId}'),
      margin: const EdgeInsets.only(top: 12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(label, style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 4),
            Text(claim.text),
            if (claim.assumptions.isNotEmpty)
              Text('Założenia: ${claim.assumptions.join('; ')}'),
            if (claim.missingInputs.isNotEmpty)
              Text('Brakuje: ${claim.missingInputs.join('; ')}'),
            if (claim.confirmOrRefute != null)
              Text('Jak sprawdzić: ${claim.confirmOrRefute}'),
          ],
        ),
      ),
    );
  }

  String _confidenceLabel(String value) => switch (value) {
    'HIGH' => 'wysoka',
    'MEDIUM' => 'średnia',
    'LOW' => 'niska',
    _ => value.toLowerCase(),
  };

  Widget sourceTile(UnifiedAssistantSource source) => ListTile(
    key: ValueKey<String>('unified-source-${source.sourceRef}'),
    contentPadding: EdgeInsets.zero,
    leading: Icon(
      source.externalAnalysis
          ? Icons.verified_user_outlined
          : Icons.source_outlined,
    ),
    title: Text(source.title, maxLines: 2, overflow: TextOverflow.ellipsis),
    subtitle: Text(
      '${source.excerpt}\n${source.whyUsed}',
      maxLines: 5,
      overflow: TextOverflow.ellipsis,
    ),
    trailing: source.supportsClaimIds.isEmpty
        ? null
        : Text(source.supportsClaimIds.join(', ')),
    onTap: source.route == null ? null : () => context.push(source.route!),
  );

  Future<void> ask() async {
    final question = controller.text.trim();
    if (loading || question.length < 2) return;
    final session = (await ref.read(authControllerProvider.future)).session;
    if (session == null || !mounted) return;
    late final AssistantConversationDetail chat;
    try {
      chat = await _ensureConversation(session);
    } catch (_) {
      if (mounted) {
        setState(() => error = 'Nie udało się utworzyć rozmowy.');
      }
      return;
    }
    final token = CancelToken();
    final attemptId = 'android-${DateTime.now().microsecondsSinceEpoch}';
    cancelToken?.cancel('superseded');
    cancelToken = token;
    setState(() {
      loading = true;
      error = null;
      result = null;
      activeRun = null;
      activeRequestId = null;
      progress = 'Tworzę trwałą analizę.';
    });
    try {
      var run = await ref
          .read(assistantRunRepositoryProvider)
          .create(
            session: session,
            question: question,
            attemptId: attemptId,
            conversation: const <Map<String, String>>[],
            conversationId: chat.id,
            clientId: clientId,
            candidateId: widget.initialCandidateId,
            documentId: widget.initialDocumentId,
            mailSourceId: widget.initialMailSourceId,
            inspectionId: widget.initialInspectionId,
          );
      activeRequestId = run.runId;
      await _storage.write(key: _pendingRequestKey, value: run.runId);
      await _storage.write(key: _latestRequestKey, value: run.runId);
      await _reloadConversationIfSelected(chat.id);
      while (!run.isTerminal) {
        if (!mounted ||
            token.isCancelled ||
            activeConversation?.id != chat.id) {
          return;
        }
        setState(() {
          activeRun = run;
          progress = run.progress.display;
        });
        await pollDelay(token, milliseconds: run.pollAfterMs);
        if (!mounted ||
            token.isCancelled ||
            activeConversation?.id != chat.id) {
          return;
        }
        run = await ref
            .read(assistantRunRepositoryProvider)
            .get(session: session, runId: run.runId, cancelToken: token);
      }
      if (!mounted || token.isCancelled || activeConversation?.id != chat.id) {
        return;
      }
      await _storage.delete(key: _pendingRequestKey);
      final answer = run.result;
      setState(() {
        activeRun = run;
        result = answer;
        progress = run.progress.display;
      });
      await _reloadConversationIfSelected(chat.id);
      if (run.status != 'completed' || answer == null) {
        setState(
          () => error = answer?.errorMessage ?? _terminalRunMessage(run),
        );
      }
    } on DioException catch (exception) {
      if (!mounted || CancelToken.isCancel(exception)) return;
      setState(
        () => error = exception.type == DioExceptionType.receiveTimeout
            ? 'Analiza lokalna trwała zbyt długo i została zakończona. Możesz spróbować ponownie.'
            : friendlyApiError(
                exception,
                fallback: 'Nie udało się uzyskać odpowiedzi AI.',
              ),
      );
    } catch (_) {
      if (mounted) {
        setState(() => error = 'Nie udało się uzyskać odpowiedzi AI.');
      }
    } finally {
      if (mounted &&
          identical(token, cancelToken) &&
          activeConversation?.id == chat.id) {
        setState(() => loading = false);
      }
    }
  }

  Future<AssistantConversationDetail> _ensureConversation(
    AuthSession session,
  ) async {
    final current = activeConversation;
    if (current != null) return current;
    final created = await ref
        .read(assistantConversationRepositoryProvider)
        .createChat(session: session);
    if (mounted) {
      setState(() {
        activeConversation = created;
        result = null;
        error = null;
      });
    }
    await _storage.write(
      key: _selectedConversationKey,
      value: created.id.toString(),
    );
    return created;
  }

  Future<void> _openHistory() async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (_) => AssistantChatHistorySheet(
        onOpen: _selectConversation,
        onNewChat: _selectConversation,
        onRenamed: _conversationRenamed,
        onDeleted: _conversationDeleted,
      ),
    );
  }

  Future<void> _selectConversation(
    AssistantConversationDetail conversation,
  ) async {
    cancelToken?.cancel('conversation switched');
    cancelToken = null;
    if (mounted) {
      setState(() {
        activeConversation = conversation;
        activeRequestId = conversation.latestRunId;
        activeRun = null;
        result = null;
        error = null;
        progress = '';
        loading = false;
      });
    }
    await _storage.write(
      key: _selectedConversationKey,
      value: conversation.id.toString(),
    );
    if (conversation.active && conversation.latestRunId != null) {
      unawaited(
        _pollSelectedRun(
          conversation.latestRunId!,
          conversationId: conversation.id,
        ),
      );
    }
  }

  Future<void> _conversationDeleted(
    AssistantConversationSummary conversation,
    AssistantConversationDeleteResult deletion,
  ) async {
    if (activeConversation?.id == conversation.id) {
      cancelToken?.cancel('conversation hidden');
      cancelToken = null;
      await _storage.delete(key: _selectedConversationKey);
      if (mounted) {
        setState(() {
          activeConversation = null;
          activeRequestId = null;
          activeRun = null;
          result = null;
          error = null;
          progress = '';
          loading = false;
        });
      }
    }
    if (deletion.activeRunId != null) {
      await _refreshHiddenActiveRun(preferredRunId: deletion.activeRunId);
    }
  }

  Future<void> _conversationRenamed(
    AssistantConversationDetail conversation,
  ) async {
    if (mounted && activeConversation?.id == conversation.id) {
      setState(() => activeConversation = conversation);
    }
  }

  Future<void> _reloadConversationIfSelected(int conversationId) async {
    if (activeConversation?.id != conversationId) return;
    final session = (await ref.read(authControllerProvider.future)).session;
    if (session == null) return;
    final detail = await ref
        .read(assistantConversationRepositoryProvider)
        .getChat(session: session, conversationId: conversationId);
    if (mounted && activeConversation?.id == conversationId) {
      setState(() => activeConversation = detail);
    }
  }

  Future<void> _restoreAssistantState() async {
    final session = (await ref.read(authControllerProvider.future)).session;
    if (session == null || !mounted) return;
    AssistantConversationDetail? detail;
    final stored = await _storage.read(key: _selectedConversationKey);
    final selectedId = int.tryParse(stored ?? '');
    try {
      if (selectedId != null) {
        detail = await ref
            .read(assistantConversationRepositoryProvider)
            .getChat(session: session, conversationId: selectedId);
      } else {
        final chats = await ref
            .read(assistantConversationRepositoryProvider)
            .listChats(session: session);
        if (chats.isNotEmpty) {
          detail = await ref
              .read(assistantConversationRepositoryProvider)
              .getChat(session: session, conversationId: chats.first.id);
        }
      }
    } catch (_) {
      await _storage.delete(key: _selectedConversationKey);
    }
    if (detail != null && mounted) {
      await _selectConversation(detail);
    } else {
      await _restorePendingRequest();
    }
    await _refreshHiddenActiveRun();
  }

  Future<void> _pollSelectedRun(
    String requestId, {
    required int conversationId,
  }) async {
    final session = (await ref.read(authControllerProvider.future)).session;
    if (session == null || !mounted) return;
    final token = CancelToken();
    cancelToken = token;
    activeRequestId = requestId;
    await _storage.write(key: _pendingRequestKey, value: requestId);
    if (mounted && activeConversation?.id == conversationId) {
      setState(() {
        loading = true;
        progress = 'Przywracam trwającą analizę.';
      });
    }
    try {
      while (mounted &&
          !token.isCancelled &&
          activeConversation?.id == conversationId) {
        final next = await ref
            .read(assistantRunRepositoryProvider)
            .get(session: session, runId: requestId, cancelToken: token);
        if (!mounted ||
            token.isCancelled ||
            activeConversation?.id != conversationId) {
          return;
        }
        setState(() {
          activeRun = next;
          progress = next.progress.display;
          error = next.isTerminal && next.status != 'completed'
              ? next.result?.errorMessage ?? _terminalRunMessage(next)
              : null;
        });
        if (next.isTerminal) {
          await _storage.delete(key: _pendingRequestKey);
          await _reloadConversationIfSelected(conversationId);
          return;
        }
        await pollDelay(token, milliseconds: next.pollAfterMs);
      }
    } on DioException catch (exception) {
      if (mounted && !CancelToken.isCancel(exception)) {
        setState(
          () => error = friendlyApiError(
            exception,
            fallback: 'Nie udało się odczytać stanu analizy.',
          ),
        );
      }
    } finally {
      if (mounted &&
          identical(token, cancelToken) &&
          activeConversation?.id == conversationId) {
        setState(() => loading = false);
      }
    }
  }

  Future<void> _refreshHiddenActiveRun({String? preferredRunId}) async {
    final session = (await ref.read(authControllerProvider.future)).session;
    if (session == null || !mounted) return;
    try {
      final active = await ref
          .read(assistantRunRepositoryProvider)
          .listActive(session: session);
      final hidden = active.where((run) => run.conversationDeleted).toList();
      AssistantRunSnapshot? selected;
      for (final run in hidden) {
        if (run.runId == preferredRunId) {
          selected = run;
          break;
        }
      }
      selected ??= hidden.isEmpty ? null : hidden.first;
      if (mounted) setState(() => hiddenActiveRun = selected);
      hiddenRunTimer?.cancel();
      if (selected != null) {
        final scheduled = selected;
        hiddenRunTimer = Timer(
          Duration(milliseconds: scheduled.pollAfterMs),
          () => unawaited(
            _refreshHiddenActiveRun(preferredRunId: scheduled.runId),
          ),
        );
      }
    } catch (_) {
      // History remains usable when the advisory active-run projection fails.
    }
  }

  Future<void> _cancelHiddenRun() async {
    final run = hiddenActiveRun;
    if (run == null) return;
    final session = (await ref.read(authControllerProvider.future)).session;
    if (session == null) return;
    await ref
        .read(assistantRunRepositoryProvider)
        .cancel(session: session, runId: run.runId);
    hiddenRunTimer?.cancel();
    if (mounted) setState(() => hiddenActiveRun = null);
  }

  String _terminalRunMessage(AssistantRunSnapshot run) {
    if (run.status == 'cancelled') return 'Analiza została anulowana.';
    if (run.status == 'review_required') {
      return 'Wynik wymaga bezpiecznej weryfikacji. Doprecyzuj pytanie.';
    }
    return 'Nie udało się zakończyć analizy. Możesz spróbować ponownie.';
  }

  Future<void> cancel() async {
    final requestId = activeRequestId;
    cancelToken?.cancel('Anulowano przez użytkownika');
    cancelToken = null;
    activeRequestId = null;
    await _storage.delete(key: _pendingRequestKey);
    await _storage.delete(key: _latestRequestKey);
    if (mounted) {
      setState(() {
        loading = false;
        progress = '';
      });
    }
    if (requestId != null) {
      await _cancelDurable(requestId);
    }
  }

  Future<void> _restorePendingRequest() async {
    final session = (await ref.read(authControllerProvider.future)).session;
    if (session == null || !mounted) return;
    var requestId = await _storage.read(key: _pendingRequestKey);
    if (requestId == null || requestId.isEmpty) {
      requestId = await _storage.read(key: _latestRequestKey);
    }
    if (requestId == null || requestId.isEmpty) {
      try {
        final active = await ref
            .read(assistantRunRepositoryProvider)
            .listActive(session: session);
        final visible = active
            .where((run) => !run.conversationDeleted)
            .toList(growable: false);
        if (visible.isEmpty || !mounted) return;
        requestId = visible.first.runId;
        await _storage.write(key: _pendingRequestKey, value: requestId);
        await _storage.write(key: _latestRequestKey, value: requestId);
      } catch (_) {
        return;
      }
    }
    final token = CancelToken();
    cancelToken = token;
    setState(() {
      loading = true;
      activeRequestId = requestId;
      progress = 'Przywracam trwającą analizę.';
    });
    try {
      while (mounted && !token.isCancelled) {
        final next = await ref
            .read(assistantRunRepositoryProvider)
            .get(session: session, runId: requestId, cancelToken: token);
        if (!mounted || token.isCancelled) return;
        if (next.conversationDeleted) {
          await _storage.delete(key: _pendingRequestKey);
          await _storage.delete(key: _latestRequestKey);
          setState(() {
            loading = false;
            activeRequestId = null;
            activeRun = null;
            result = null;
          });
          await _refreshHiddenActiveRun(preferredRunId: next.runId);
          return;
        }
        setState(() {
          activeRun = next;
          result = next.result;
          progress = next.progress.display;
          error = next.isTerminal && next.status != 'completed'
              ? next.result?.errorMessage ?? _terminalRunMessage(next)
              : null;
        });
        if (next.isTerminal) {
          await _storage.delete(key: _pendingRequestKey);
          break;
        }
        await pollDelay(token, milliseconds: next.pollAfterMs);
      }
    } on DioException catch (exception) {
      if (mounted && !CancelToken.isCancel(exception)) {
        if (exception.response?.statusCode == 404) {
          await _storage.delete(key: _pendingRequestKey);
          await _storage.delete(key: _latestRequestKey);
        }
        setState(
          () => error = friendlyApiError(
            exception,
            fallback: 'Nie udało się odczytać stanu analizy.',
          ),
        );
      }
    } finally {
      if (mounted && identical(token, cancelToken)) {
        setState(() => loading = false);
      }
    }
  }

  Future<void> _cancelDurable(String requestId) async {
    final session = (await ref.read(authControllerProvider.future)).session;
    if (session == null) return;
    try {
      final cancelled = await ref
          .read(assistantRunRepositoryProvider)
          .cancel(session: session, runId: requestId);
      final conversationId = cancelled.conversationId;
      if (conversationId != null) {
        await _reloadConversationIfSelected(conversationId);
      }
    } catch (_) {
      // HTTP cancellation already detached the local request and blocks stale binding.
    }
  }

  Future<void> pollDelay(CancelToken token, {int milliseconds = 2500}) async {
    final completer = Completer<void>();
    late final Timer timer;
    timer = Timer(Duration(milliseconds: milliseconds.clamp(500, 30000)), () {
      if (!completer.isCompleted) completer.complete();
    });
    unawaited(
      token.whenCancel.then((_) {
        timer.cancel();
        if (!completer.isCompleted) completer.complete();
      }),
    );
    await completer.future;
  }
}
