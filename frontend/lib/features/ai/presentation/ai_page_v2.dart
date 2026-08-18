import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/network/friendly_api_error.dart';
import '../../../core/widgets/app_shell.dart';
import '../../auth/application/auth_controller.dart';
import '../../clients/presentation/searchable_client_picker.dart';
import '../../inspections/application/inspections_providers.dart';
import '../../inspections/domain/inspection.dart';
import '../application/business_assistant_providers.dart';
import '../application/agent_assistant_providers.dart';
import '../application/technical_assistant_providers.dart';
import '../domain/agent_assistant.dart';
import '../domain/business_assistant.dart';
import '../domain/technical_assistant.dart';

enum AiMode { business, technical, agent }

class AiPage extends ConsumerStatefulWidget {
  const AiPage({
    this.initialMode = AiMode.business,
    this.initialClientId,
    this.initialInspectionId,
    super.key,
  });
  final AiMode initialMode;
  final int? initialClientId;
  final int? initialInspectionId;
  @override
  ConsumerState<AiPage> createState() => _AiPageState();
}

class _AiPageState extends ConsumerState<AiPage> {
  final _controller = TextEditingController();
  final _conversation = <Map<String, String>>[];
  BusinessAssistantAnswer? _businessAnswer;
  TechnicalAssistantAnswer? _technicalAnswer;
  AgentAssistantAnswer? _agentAnswer;
  String? _error;
  CancelToken? _cancelToken;
  late AiMode _mode;
  int? _clientId;
  String? _clientName;
  int? _inspectionId;
  List<Inspection> _inspections = const [];
  bool _loading = false;
  bool _loadingInspections = false;

  @override
  void initState() {
    super.initState();
    _mode = widget.initialMode;
    _clientId = widget.initialClientId;
    _inspectionId = widget.initialInspectionId;
    if (_clientId != null) {
      _clientName = 'Klient #$_clientId';
      WidgetsBinding.instance.addPostFrameCallback((_) => _loadInspections());
    }
  }

  @override
  void dispose() {
    _cancelToken?.cancel();
    _controller.dispose();
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
                SegmentedButton<AiMode>(
                  key: const Key('ai-mode-selector'),
                  segments: const <ButtonSegment<AiMode>>[
                    ButtonSegment(
                      value: AiMode.business,
                      icon: Icon(Icons.business_center_outlined),
                      label: Text('Biznesowy'),
                    ),
                    ButtonSegment(
                      value: AiMode.technical,
                      icon: Icon(Icons.engineering_outlined),
                      label: Text('Techniczny'),
                    ),
                    ButtonSegment(
                      value: AiMode.agent,
                      icon: Icon(Icons.manage_search_outlined),
                      label: Text('Agent'),
                    ),
                  ],
                  selected: <AiMode>{_mode},
                  onSelectionChanged: _loading
                      ? null
                      : (value) => _changeMode(value.first),
                ),
                const SizedBox(height: 16),
                Text(switch (_mode) {
                  AiMode.business =>
                    'Globalny asystent biznesowy tylko do odczytu',
                  AiMode.technical => 'Asystent techniczny oparty na dowodach',
                  AiMode.agent => 'Audytowany Agent zadaniowy tylko do odczytu',
                }, style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                Text(switch (_mode) {
                  AiMode.business =>
                    'Pyta o klientów, kandydatów, dokumenty, e-maile i wizje. Nie zmienia danych ani nie wykonuje działań.',
                  AiMode.technical =>
                    'Analizuje tekst dokumentów, notatki i dane wizji. Oddziela fakty od hipotez.',
                  AiMode.agent =>
                    'Dobiera wyłącznie dozwolone narzędzia odczytowe, łączy wyniki i pokazuje źródła oraz ślad użytych narzędzi.',
                }),
                if (_mode != AiMode.business) ...<Widget>[
                  const SizedBox(height: 16),
                  SearchableClientPicker(
                    key: ValueKey<String>('technical-client-${_clientId ?? 0}'),
                    initialClientId: _clientId,
                    initialClientName: _clientName,
                    enabled: !_loading,
                    onChanged: _selectClient,
                  ),
                  if (_clientId != null) ...<Widget>[
                    const SizedBox(height: 12),
                    DropdownButtonFormField<int?>(
                      key: const Key('technical-inspection-picker'),
                      initialValue: _inspectionId,
                      isExpanded: true,
                      decoration: InputDecoration(
                        labelText: 'Wizja lokalna (opcjonalnie)',
                        suffixIcon: _loadingInspections
                            ? const Padding(
                                padding: EdgeInsets.all(12),
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              )
                            : null,
                      ),
                      items: <DropdownMenuItem<int?>>[
                        const DropdownMenuItem<int?>(
                          child: Text('Bez konkretnej wizji'),
                        ),
                        if (_inspectionId != null &&
                            !_inspections.any(
                              (item) => item.id == _inspectionId,
                            ))
                          DropdownMenuItem<int?>(
                            value: _inspectionId,
                            child: Text('Wizja #$_inspectionId'),
                          ),
                        ..._inspections.map(
                          (item) => DropdownMenuItem<int?>(
                            value: item.id,
                            child: Text(
                              '${item.status.label} · ${item.title}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ),
                      ],
                      onChanged: _loading ? null : _selectInspection,
                    ),
                  ],
                ],
                const SizedBox(height: 16),
                TextField(
                  key: Key('${_mode.name}-ai-question'),
                  controller: _controller,
                  enabled: !_loading,
                  minLines: 1,
                  maxLines: 4,
                  maxLength: 1000,
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _ask(),
                  decoration: InputDecoration(
                    hintText: switch (_mode) {
                      AiMode.business =>
                        'Zapytaj o firmę, klientów, dokumenty, wizje...',
                      AiMode.technical =>
                        'Zapytaj o problem techniczny, dokumentację lub wizję lokalną…',
                      AiMode.agent =>
                        'Zadaj pytanie lub poproś o zebranie informacji z systemu…',
                    },
                    prefixIcon: Icon(switch (_mode) {
                      AiMode.business => Icons.auto_awesome_outlined,
                      AiMode.technical => Icons.engineering_outlined,
                      AiMode.agent => Icons.manage_search_outlined,
                    }),
                    border: const OutlineInputBorder(),
                  ),
                ),
                _examples(),
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
                              child: CircularProgressIndicator(strokeWidth: 3),
                            ),
                            if (_mode == AiMode.agent)
                              const Text(
                                'Agent sprawdza dane…',
                                key: Key('agent-ai-activity'),
                              ),
                            OutlinedButton(
                              key: const Key('business-ai-cancel'),
                              onPressed: _cancel,
                              child: const Text('Anuluj'),
                            ),
                          ],
                        )
                      : FilledButton.icon(
                          key: Key('${_mode.name}-ai-send'),
                          onPressed: _ask,
                          icon: const Icon(Icons.send_outlined),
                          label: const Text('Wyślij'),
                        ),
                ),
                if (_error != null) _errorView(),
                if (_businessAnswer != null) _businessResult(_businessAnswer!),
                if (_technicalAnswer != null)
                  _technicalResult(_technicalAnswer!),
                if (_agentAnswer != null) _agentResult(_agentAnswer!),
              ],
            ),
          ),
        ),
      ),
    ),
  );

  Widget _examples() {
    final examples = switch (_mode) {
      AiMode.business => <String>[
        'Co wydarzyło się w CRM w ostatnich 7 dniach?',
        'Ilu klientów ma status Oględziny?',
        'Którzy klienci nie mieli kontaktu od 30 dni?',
        'Jakie wizje lokalne są zaplanowane?',
      ],
      AiMode.technical => <String>[
        'Podsumuj technicznie ten przypadek',
        'Co sprawdzić podczas wizji lokalnej?',
        'Jakich danych brakuje?',
        'Co mówi dokumentacja o gruncie?',
      ],
      AiMode.agent => <String>[
        'Pokaż klientów wymagających uwagi',
        'Znajdź najnowsze dokumenty klienta',
        'Podsumuj ostatnią aktywność tego klienta',
        'Zbierz informacje o tej wizji lokalnej',
      ],
    };
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: examples
          .map(
            (question) => ActionChip(
              key: ValueKey<String>('${_mode.name}-ai-example-$question'),
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
    );
  }

  Widget _errorView() => Padding(
    padding: const EdgeInsets.only(top: 16),
    child: Material(
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
  );

  Widget _businessResult(BusinessAssistantAnswer answer) => _resultShell(
    answer: answer.answer,
    answerKey: const Key('business-ai-answer'),
    sections: const [],
    sources: answer.sources
        .map(
          (x) => _SourceView(
            type: x.sourceType,
            id: x.sourceId,
            title: x.title,
            snippet: x.snippet,
            route: x.route,
          ),
        )
        .toList(),
    limitations: answer.limitations,
  );

  Widget _technicalResult(TechnicalAssistantAnswer answer) => _resultShell(
    answer: answer.answer,
    answerKey: const Key('technical-ai-answer'),
    sections: <Widget>[
      if (answer.facts.isNotEmpty) _listSection('Fakty', answer.facts),
      if (answer.inferences.isNotEmpty)
        _listSection('Wnioski / hipotezy', answer.inferences),
      if (answer.missingInformation.isNotEmpty)
        _listSection('Brakujące dane', answer.missingInformation),
    ],
    sources: answer.sources
        .map(
          (x) => _SourceView(
            type: x.sourceType,
            id: x.sourceId,
            title: x.title,
            snippet: x.snippet,
            route: x.route,
          ),
        )
        .toList(),
    limitations: answer.limitations,
  );

  Widget _agentResult(AgentAssistantAnswer answer) => _resultShell(
    answer: answer.answer,
    answerKey: const Key('agent-ai-answer'),
    sections: <Widget>[
      if (answer.toolTrace.isNotEmpty)
        _listSection(
          'Użyte narzędzia',
          answer.toolTrace
              .map((x) => '${x.name} — ${x.outcome.toUpperCase()}')
              .toList(),
        ),
    ],
    sources: answer.sources
        .map(
          (x) => _SourceView(
            type: x.sourceType,
            id: x.sourceId,
            title: x.title,
            snippet: x.snippet,
            route: x.route,
          ),
        )
        .toList(),
    limitations: answer.limitations,
  );

  Widget _resultShell({
    required String answer,
    required Key answerKey,
    required List<Widget> sections,
    required List<_SourceView> sources,
    required List<String> limitations,
  }) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: <Widget>[
      const SizedBox(height: 20),
      Text('Odpowiedź', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 8),
      SelectableText(answer, key: answerKey),
      ...sections,
      if (sources.isNotEmpty) ...<Widget>[
        const SizedBox(height: 18),
        Text('Źródła', style: Theme.of(context).textTheme.titleSmall),
        ...sources.map(_sourceTile),
      ],
      ...limitations.map(
        (item) => Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Text(item, style: Theme.of(context).textTheme.bodySmall),
        ),
      ),
    ],
  );

  Widget _listSection(String title, List<String> items) => Padding(
    padding: const EdgeInsets.only(top: 16),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(title, style: Theme.of(context).textTheme.titleSmall),
        ...items.map((item) => Text('• $item')),
      ],
    ),
  );

  Widget _sourceTile(_SourceView source) => ListTile(
    key: ValueKey<String>('business-ai-source-${source.type}-${source.id}'),
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

  void _changeMode(AiMode mode) {
    _cancel();
    setState(() {
      _mode = mode;
      _conversation.clear();
      _businessAnswer = null;
      _technicalAnswer = null;
      _agentAnswer = null;
      _error = null;
    });
  }

  void _selectClient(ClientPickerSelection? selection) {
    setState(() {
      _clientId = selection?.id;
      _clientName = selection?.name;
      _inspectionId = null;
      _inspections = const [];
      _conversation.clear();
      _technicalAnswer = null;
      _agentAnswer = null;
    });
    if (selection != null) _loadInspections();
  }

  void _selectInspection(int? value) => setState(() {
    _inspectionId = value;
    _conversation.clear();
    _technicalAnswer = null;
  });

  Future<void> _loadInspections() async {
    final id = _clientId;
    if (id == null || !mounted) return;
    setState(() => _loadingInspections = true);
    try {
      final session = (await ref.read(authControllerProvider.future)).session;
      if (session == null) return;
      final page = await ref
          .read(inspectionsApiProvider)
          .list(session, clientId: id, limit: 50);
      if (!mounted || id != _clientId) return;
      setState(() {
        _inspections = page.items;
        if (_inspectionId != null &&
            !_inspections.any((item) => item.id == _inspectionId)) {
          _inspectionId = null;
        }
      });
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Nie udało się wczytać wizji klienta.');
      }
    } finally {
      if (mounted && id == _clientId) {
        setState(() => _loadingInspections = false);
      }
    }
  }

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
      final history = List<Map<String, String>>.unmodifiable(
        _conversation.length <= 8
            ? _conversation
            : _conversation.sublist(_conversation.length - 8),
      );
      if (_mode == AiMode.business) {
        final result = await ref
            .read(businessAssistantGatewayProvider)
            .ask(
              session: session,
              question: question,
              conversation: history,
              cancelToken: cancelToken,
            );
        if (!mounted || !identical(cancelToken, _cancelToken)) return;
        setState(() {
          _businessAnswer = result;
          _technicalAnswer = null;
          _agentAnswer = null;
          _remember(question, result.answer);
        });
      } else if (_mode == AiMode.technical) {
        final result = await ref
            .read(technicalAssistantGatewayProvider)
            .ask(
              session: session,
              question: question,
              clientId: _clientId,
              inspectionId: _inspectionId,
              conversation: history,
              cancelToken: cancelToken,
            );
        if (!mounted || !identical(cancelToken, _cancelToken)) return;
        setState(() {
          _technicalAnswer = result;
          _businessAnswer = null;
          _agentAnswer = null;
          _remember(question, result.answer);
        });
      } else {
        final result = await ref
            .read(agentAssistantGatewayProvider)
            .ask(
              session: session,
              question: question,
              clientId: _clientId,
              inspectionId: _inspectionId,
              conversation: history,
              cancelToken: cancelToken,
            );
        if (!mounted || !identical(cancelToken, _cancelToken)) return;
        setState(() {
          _agentAnswer = result;
          _businessAnswer = null;
          _technicalAnswer = null;
          _remember(question, result.answer);
        });
      }
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

  void _remember(String question, String answer) {
    _conversation
      ..add(<String, String>{'role': 'user', 'content': question})
      ..add(<String, String>{'role': 'assistant', 'content': answer});
  }

  void _cancel() {
    _cancelToken?.cancel('Anulowano przez użytkownika');
    _cancelToken = null;
    if (mounted) setState(() => _loading = false);
  }
}

class _SourceView {
  const _SourceView({
    required this.type,
    required this.id,
    required this.title,
    required this.snippet,
    required this.route,
  });
  final String type;
  final int? id;
  final String title;
  final String snippet;
  final String? route;
}
