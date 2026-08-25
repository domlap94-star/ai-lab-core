import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/network/friendly_api_error.dart';
import '../../../core/widgets/app_shell.dart';
import '../../auth/application/auth_controller.dart';
import '../../clients/presentation/searchable_client_picker.dart';
import '../application/unified_assistant_providers.dart';
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
                if (result != null && !result!.isPending) answerView(result!),
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
                ? 'Brak źródeł z danych klienta. Odpowiedź oparta na wiedzy ogólnej modelu.'
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
    setState(() {
      loading = true;
      error = null;
      result = null;
      activeRequestId = null;
      progress = 'Zbieram dane';
    });
    try {
      UnifiedAssistantAnswer next;
      DateTime? advancedStartedAt;
      do {
        if (!mounted || token.isCancelled) return;
        setState(
          () => progress = result?.isPending == true
              ? 'Analiza rozszerzona'
              : 'Analizuję dokumentację',
        );
        next = await ref
            .read(unifiedAssistantApiProvider)
            .ask(
              session: session,
              question: question,
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
              attemptId: attemptId,
              cancelToken: token,
            );
        if (!mounted || token.isCancelled) return;
        setState(() {
          result = next;
          activeRequestId = next.requestId;
          progress = next.delayed
              ? 'Analiza trwa dłużej niż zwykle.'
              : next.status == 'advanced_processing'
                  ? 'Analiza rozszerzona'
                  : 'Weryfikuję wynik';
        });
        if (next.isPending) {
          final started = advancedStartedAt ??= DateTime.now();
          if (DateTime.now().difference(started) >=
              const Duration(seconds: 185)) {
            await cancel();
            throw TimeoutException('advanced_analysis_timeout');
          }
          await pollDelay(token);
        }
      } while (next.isPending);
      if (next.status == 'accepted_local' ||
          next.status == 'accepted_advanced') {
        conversation
          ..add(<String, String>{'role': 'user', 'content': question})
          ..add(<String, String>{'role': 'assistant', 'content': next.answer});
      } else {
        setState(
          () => error =
              next.errorMessage ??
              'Wynik wymaga bezpiecznej weryfikacji. Doprecyzuj pytanie.',
        );
      }
    } on DioException catch (exception) {
      if (!mounted || CancelToken.isCancel(exception)) return;
      setState(
        () => error = friendlyApiError(
          exception,
          fallback: 'Nie udało się uzyskać odpowiedzi AI.',
        ),
      );
    } on TimeoutException {
      if (mounted) {
        setState(() => error =
            'Analiza rozszerzona nie zakończyła się w wymaganym czasie. Możesz spróbować ponownie.');
      }
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

  Future<void> cancel() async {
    final requestId = activeRequestId;
    if (requestId != null) {
      final session = (await ref.read(authControllerProvider.future)).session;
      if (session != null) {
        try {
          await ref.read(unifiedAssistantApiProvider).cancel(
            session: session,
            requestId: requestId,
          );
        } catch (_) {
          // The local request is still cancelled; the backend timeout remains fail-closed.
        }
      }
    }
    cancelToken?.cancel('Anulowano przez użytkownika');
    cancelToken = null;
    activeRequestId = null;
    if (mounted) {
      setState(() {
        loading = false;
        progress = '';
      });
    }
  }

  Future<void> pollDelay(CancelToken token) async {
    final completer = Completer<void>();
    late final Timer timer;
    timer = Timer(const Duration(seconds: 3), () {
      if (!completer.isCompleted) completer.complete();
    });
    unawaited(token.whenCancel.then((_) {
      timer.cancel();
      if (!completer.isCompleted) completer.complete();
    }));
    await completer.future;
  }
}
