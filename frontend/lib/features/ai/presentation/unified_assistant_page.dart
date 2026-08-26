import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:go_router/go_router.dart';
import '../../../core/network/friendly_api_error.dart';
import '../../../core/widgets/app_shell.dart';
import '../../auth/application/auth_controller.dart';
import '../../clients/presentation/searchable_client_picker.dart';
import '../application/assistant_run_controller.dart';
import '../domain/assistant_run.dart';
import '../domain/unified_assistant.dart';

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
  static const quickActions = <String>[
    'Podsumuj ten przypadek',
    'Co sprawdzić podczas wizji lokalnej?',
    'Jakich danych brakuje?',
    'Co mówi dokumentacja?',
    'Znajdź najnowsze dokumenty',
    'Podsumuj ostatnią aktywność',
  ];
  final controller = TextEditingController();
  final conversation = <Map<String, String>>[];
  CancelToken? cancelToken;
  String? activeRequestId;
  AssistantRunSnapshot? activeRun;
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
    unawaited(_restorePendingRequest());
  }

  @override
  void dispose() {
    cancelToken?.cancel();
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
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
                    conversation.clear();
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
                if (result != null && _hasRenderableAnswer(result!))
                  answerView(result!),
              ],
            ),
          ),
        ),
      ),
    ),
  );

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

  Widget claimCard(UnifiedAssistantClaim claim) {
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
      key: ValueKey<String>('unified-claim-${claim.claimId}'),
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
    final token = CancelToken();
    final attemptId = 'android-${DateTime.now().microsecondsSinceEpoch}';
    cancelToken?.cancel('superseded');
    cancelToken = token;
    if (_hasResetIntent(question)) {
      conversation.clear();
    }
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
            conversation: List.unmodifiable(
              conversation.length <= 8
                  ? conversation
                  : conversation.sublist(conversation.length - 8),
            ),
            clientId: clientId,
            candidateId: widget.initialCandidateId,
            documentId: widget.initialDocumentId,
            mailSourceId: widget.initialMailSourceId,
            inspectionId: widget.initialInspectionId,
          );
      activeRequestId = run.runId;
      await _storage.write(key: _pendingRequestKey, value: run.runId);
      await _storage.write(key: _latestRequestKey, value: run.runId);
      while (!run.isTerminal) {
        if (!mounted || token.isCancelled) return;
        setState(() {
          activeRun = run;
          progress = run.progress.display;
        });
        await pollDelay(token, milliseconds: run.pollAfterMs);
        if (!mounted || token.isCancelled) return;
        run = await ref
            .read(assistantRunRepositoryProvider)
            .get(session: session, runId: run.runId, cancelToken: token);
      }
      if (!mounted || token.isCancelled) return;
      await _storage.delete(key: _pendingRequestKey);
      final answer = run.result;
      setState(() {
        activeRun = run;
        result = answer;
        progress = run.progress.display;
      });
      if (run.status == 'completed' && answer != null) {
        conversation
          ..add(<String, String>{'role': 'user', 'content': question})
          ..add(<String, String>{
            'role': 'assistant',
            'content': answer.answer,
          });
      } else {
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
      if (mounted && identical(token, cancelToken)) {
        setState(() => loading = false);
      }
    }
  }

  String _terminalRunMessage(AssistantRunSnapshot run) {
    if (run.status == 'cancelled') return 'Analiza została anulowana.';
    if (run.status == 'review_required') {
      return 'Wynik wymaga bezpiecznej weryfikacji. Doprecyzuj pytanie.';
    }
    return 'Nie udało się zakończyć analizy. Możesz spróbować ponownie.';
  }

  bool _hasResetIntent(String value) {
    var normalized = value.toLowerCase();
    const replacements = <String, String>{
      'ą': 'a',
      'ć': 'c',
      'ę': 'e',
      'ł': 'l',
      'ń': 'n',
      'ó': 'o',
      'ś': 's',
      'ź': 'z',
      'ż': 'z',
    };
    replacements.forEach((source, target) {
      normalized = normalized.replaceAll(source, target);
    });
    return <String>[
      'ignoruj poprzednie pytanie',
      'ignoruj poprzednie zapytanie',
      'ignoruj poprzedni kontekst',
      'nie bierz pod uwage wczesniejszej rozmowy',
      'zacznij od nowa',
      'nowy temat',
    ].any(normalized.contains);
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
      unawaited(_cancelDurable(requestId));
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
        if (active.isEmpty || !mounted) return;
        requestId = active.first.runId;
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
      await ref
          .read(assistantRunRepositoryProvider)
          .cancel(session: session, runId: requestId);
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
