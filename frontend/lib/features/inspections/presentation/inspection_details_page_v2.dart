import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/network/friendly_api_error.dart';
import '../../../core/widgets/app_shell.dart';
import '../../../core/widgets/read_error_view.dart';
import '../../documents/application/documents_providers.dart';
import '../../documents/presentation/document_intake_dialog.dart';
import '../application/inspection_field_services.dart';
import '../application/inspections_providers.dart';
import '../domain/inspection.dart';
import 'inspection_form_dialog.dart';

enum _NotesSaveState { idle, saving, saved, failed }

class InspectionDetailsPage extends ConsumerStatefulWidget {
  const InspectionDetailsPage({
    required this.inspectionId,
    this.returnPath,
    super.key,
  });

  final int inspectionId;
  final String? returnPath;

  @override
  ConsumerState<InspectionDetailsPage> createState() =>
      _InspectionDetailsPageState();
}

class _InspectionDetailsPageState extends ConsumerState<InspectionDetailsPage> {
  final TextEditingController _notes = TextEditingController();
  Timer? _notesDebounce;
  Future<void>? _saveLoop;
  bool _notesInitialized = false;
  bool _notesDirty = false;
  bool _leaving = false;
  bool _sharingLocation = false;
  bool _listening = false;
  _NotesSaveState _notesSaveState = _NotesSaveState.idle;
  String? _notesError;
  late final InspectionSpeechService _speechService;

  bool get _hasPendingSave =>
      _notesDirty || _notesDebounce?.isActive == true || _saveLoop != null;

  @override
  void initState() {
    super.initState();
    _speechService = ref.read(inspectionSpeechServiceProvider);
  }

  @override
  void dispose() {
    _notesDebounce?.cancel();
    if (_listening) unawaited(_speechService.cancel());
    _notes.dispose();
    super.dispose();
  }

  void _initializeNotes(Inspection item) {
    if (_notesInitialized) return;
    _notesInitialized = true;
    _notes.text = item.notes ?? '';
  }

  void _onNotesChanged(String _) {
    _notesDirty = true;
    _notesError = null;
    _notesSaveState = _NotesSaveState.idle;
    _notesDebounce?.cancel();
    _notesDebounce = Timer(const Duration(milliseconds: 800), _ensureSave);
    setState(() {});
  }

  Future<void> _ensureSave() {
    _notesDebounce?.cancel();
    _notesDebounce = null;
    return _saveLoop ??= _drainNotesSaves().whenComplete(() {
      _saveLoop = null;
    });
  }

  Future<void> _drainNotesSaves() async {
    while (_notesDirty) {
      _notesDirty = false;
      final String text = _notes.text.trim();
      if (mounted) setState(() => _notesSaveState = _NotesSaveState.saving);
      try {
        await ref.read(inspectionsApiProvider).update(
          requireInspectionWidgetSession(ref),
          widget.inspectionId,
          <String, dynamic>{'notes': text.isEmpty ? null : text},
        );
        if (mounted && !_notesDirty && _notes.text.trim() == text) {
          setState(() => _notesSaveState = _NotesSaveState.saved);
          ref.invalidate(inspectionDetailsProvider(widget.inspectionId));
        }
      } catch (error) {
        _notesDirty = true;
        if (mounted) {
          setState(() {
            _notesSaveState = _NotesSaveState.failed;
            _notesError = friendlyApiError(error);
          });
        }
        break;
      }
    }
  }

  void _goBack() {
    if (widget.returnPath != null) {
      context.go(widget.returnPath!);
    } else if (context.canPop()) {
      context.pop();
    } else {
      context.go('/inspections');
    }
  }

  Future<void> _leave() async {
    if (_leaving) return;
    _leaving = true;
    if (_hasPendingSave) await _ensureSave();
    if (!mounted) return;
    if (_notesSaveState == _NotesSaveState.failed) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Nie udało się zapisać ostatniej zmiany notatki.'),
        ),
      );
    }
    _goBack();
  }

  Future<void> _edit(Inspection item) async {
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => InspectionFormDialog(inspection: item),
    );
    if (data != null && mounted) {
      await ref
          .read(inspectionsApiProvider)
          .update(requireInspectionWidgetSession(ref), item.id, data);
      ref.invalidate(inspectionDetailsProvider(item.id));
    }
  }

  Future<void> _complete(Inspection item) async {
    await ref.read(inspectionsApiProvider).update(
      requireInspectionWidgetSession(ref),
      item.id,
      <String, dynamic>{'status': 'completed'},
    );
    ref.invalidate(inspectionDetailsProvider(item.id));
  }

  Future<void> _shareLocation() async {
    setState(() => _sharingLocation = true);
    final service = ref.read(inspectionLocationServiceProvider);
    final result = await service.currentLocation();
    if (!mounted) return;
    if (result.status == FieldLocationStatus.success) {
      try {
        await ref.read(inspectionsApiProvider).update(
          requireInspectionWidgetSession(ref),
          widget.inspectionId,
          <String, dynamic>{
            'latitude': result.latitude,
            'longitude': result.longitude,
            'location_accuracy_m': result.accuracy,
          },
        );
        ref.invalidate(inspectionDetailsProvider(widget.inspectionId));
        if (mounted) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(const SnackBar(content: Text('Lokalizacja zapisana')));
        }
      } catch (error) {
        if (mounted) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(SnackBar(content: Text(friendlyApiError(error))));
        }
      }
    } else {
      await _showLocationProblem(result.status);
    }
    if (mounted) setState(() => _sharingLocation = false);
  }

  Future<void> _showLocationProblem(FieldLocationStatus status) async {
    final bool settings = status == FieldLocationStatus.deniedForever;
    final bool services = status == FieldLocationStatus.serviceDisabled;
    final String message = switch (status) {
      FieldLocationStatus.denied =>
        'Nie udzielono dostępu do lokalizacji. Wizja nadal działa bez GPS.',
      FieldLocationStatus.deniedForever =>
        'Dostęp do lokalizacji jest wyłączony na stałe. Włącz go w ustawieniach aplikacji.',
      FieldLocationStatus.serviceDisabled =>
        'Usługi lokalizacji są wyłączone. Włącz GPS i spróbuj ponownie.',
      _ => 'Nie udało się pobrać lokalizacji. Spróbuj ponownie.',
    };
    final bool? open = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Lokalizacja niedostępna'),
        content: Text(message),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Zamknij'),
          ),
          if (settings || services)
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: Text(settings ? 'Ustawienia aplikacji' : 'Włącz GPS'),
            ),
        ],
      ),
    );
    if (open == true) {
      if (settings) {
        await ref.read(inspectionLocationServiceProvider).openAppSettings();
      } else {
        await ref
            .read(inspectionLocationServiceProvider)
            .openLocationSettings();
      }
    }
  }

  Future<void> _toggleSpeech() async {
    final speech = ref.read(inspectionSpeechServiceProvider);
    if (_listening) {
      await speech.stop();
      if (mounted) setState(() => _listening = false);
      return;
    }
    final status = await speech.start(
      onFinalResult: (String text) {
        if (!mounted) return;
        final String existing = _notes.text.trimRight();
        final String combined = existing.isEmpty ? text : '$existing\n$text';
        _notes.value = TextEditingValue(
          text: combined,
          selection: TextSelection.collapsed(offset: combined.length),
        );
        _onNotesChanged(combined);
      },
      onStopped: () {
        if (mounted && _listening) setState(() => _listening = false);
      },
    );
    if (!mounted) return;
    if (status == SpeechStartStatus.listening) {
      setState(() => _listening = true);
      return;
    }
    final bool permanent = status == SpeechStartStatus.deniedForever;
    final String message = switch (status) {
      SpeechStartStatus.denied =>
        'Nie udzielono dostępu do mikrofonu. Nadal możesz wpisać notatkę ręcznie.',
      SpeechStartStatus.deniedForever =>
        'Dostęp do mikrofonu jest wyłączony na stałe. Włącz go w ustawieniach aplikacji.',
      SpeechStartStatus.unavailable =>
        'Rozpoznawanie mowy nie jest dostępne na tym urządzeniu.',
      _ => 'Nie udało się uruchomić rozpoznawania mowy.',
    };
    final bool? open = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Mikrofon niedostępny'),
        content: Text(message),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Zamknij'),
          ),
          if (permanent)
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Ustawienia aplikacji'),
            ),
        ],
      ),
    );
    if (open == true) await speech.openAppSettings();
  }

  Future<void> _cancelSpeech() async {
    await ref.read(inspectionSpeechServiceProvider).cancel();
    if (mounted) setState(() => _listening = false);
  }

  Future<void> _delete(Inspection item) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Usunąć wizję lokalną?'),
        content: const Text(
          'Wizja zniknie z aktywnej listy. Dokumenty i zdjęcia pozostaną zachowane.',
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Anuluj'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Usuń'),
          ),
        ],
      ),
    );
    if (confirmed == true && mounted) {
      await ref
          .read(inspectionsApiProvider)
          .delete(requireInspectionWidgetSession(ref), item.id);
      ref.invalidate(inspectionsPageProvider);
      if (mounted) context.go('/inspections');
    }
  }

  Widget _notesStatus() => switch (_notesSaveState) {
    _NotesSaveState.saving => const Row(
      key: Key('inspection-notes-saving'),
      children: <Widget>[
        SizedBox(
          width: 14,
          height: 14,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
        SizedBox(width: 8),
        Text('Zapisywanie…'),
      ],
    ),
    _NotesSaveState.saved => const Text(
      'Zapisano',
      key: Key('inspection-notes-saved'),
    ),
    _NotesSaveState.failed => Wrap(
      crossAxisAlignment: WrapCrossAlignment.center,
      children: <Widget>[
        Text(_notesError ?? 'Nie udało się zapisać.'),
        TextButton(
          onPressed: _ensureSave,
          child: const Text('Spróbuj ponownie'),
        ),
      ],
    ),
    _ => const SizedBox.shrink(),
  };

  @override
  Widget build(BuildContext context) {
    final value = ref.watch(inspectionDetailsProvider(widget.inspectionId));
    final bool centrallyHandled = AppShell.centrallyHandlesBack(context);
    return PopScope<Object?>(
      canPop: !_hasPendingSave && (centrallyHandled || context.canPop()),
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop && (_hasPendingSave || !centrallyHandled)) {
          unawaited(_leave());
        }
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Wizja lokalna'),
          leading: IconButton(
            onPressed: _leave,
            icon: const Icon(Icons.arrow_back),
          ),
        ),
        body: value.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => ReadErrorView(
            error: error,
            onRetry: () =>
                ref.invalidate(inspectionDetailsProvider(widget.inspectionId)),
          ),
          data: (item) {
            _initializeNotes(item);
            final speech = ref.watch(inspectionSpeechServiceProvider);
            return ListView(
              padding: const EdgeInsets.all(16),
              children: <Widget>[
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: <Widget>[
                    FilledButton.icon(
                      onPressed: () => _edit(item),
                      icon: const Icon(Icons.edit),
                      label: const Text('Edytuj'),
                    ),
                    if (item.status != InspectionStatus.completed)
                      OutlinedButton.icon(
                        onPressed: () => _complete(item),
                        icon: const Icon(Icons.check),
                        label: const Text('Zakończ'),
                      ),
                    OutlinedButton.icon(
                      onPressed: () => _delete(item),
                      icon: const Icon(Icons.delete_outline),
                      label: const Text('Usuń wizję'),
                    ),
                  ],
                ),
                _inspectionCard(context, item),
                _notesCard(context, speech),
                _documentsCard(context, item),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _inspectionCard(BuildContext context, Inspection item) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Wizja lokalna',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          Text('Klient: ${item.clientName}'),
          Text('Status: ${item.status.label}'),
          Text('Termin: ${item.scheduledAt?.toLocal().toString() ?? 'brak'}'),
          const SizedBox(height: 8),
          Text(
            item.latitude == null
                ? 'Lokalizacja: brak'
                : 'Lokalizacja zapisana',
          ),
          if (item.locationAccuracyM != null)
            Text('Dokładność: ${item.locationAccuracyM!.round()} m'),
          const SizedBox(height: 8),
          FilledButton.tonalIcon(
            key: const Key('inspection-share-location'),
            onPressed: _sharingLocation ? null : _shareLocation,
            icon: _sharingLocation
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.my_location),
            label: Text(
              _sharingLocation
                  ? 'Pobieranie lokalizacji…'
                  : 'Udostępnij lokalizację',
            ),
          ),
        ],
      ),
    ),
  );

  Widget _notesCard(BuildContext context, InspectionSpeechService speech) =>
      Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Expanded(
                    child: Text(
                      'Notatki',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                  if (speech.isSupportedPlatform)
                    IconButton(
                      key: const Key('inspection-notes-microphone'),
                      tooltip: _listening ? 'Zatrzymaj' : 'Dyktuj notatkę',
                      onPressed: _toggleSpeech,
                      icon: Icon(_listening ? Icons.stop : Icons.mic_none),
                    ),
                ],
              ),
              if (_listening)
                Row(
                  children: <Widget>[
                    const Expanded(child: Text('Słucham…')),
                    TextButton(
                      onPressed: _cancelSpeech,
                      child: const Text('Anuluj'),
                    ),
                  ],
                ),
              TextField(
                key: const Key('inspection-inline-notes'),
                controller: _notes,
                minLines: 4,
                maxLines: 10,
                onChanged: _onNotesChanged,
                decoration: const InputDecoration(
                  hintText: 'Dodaj notatki z wizji lokalnej',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 8),
              _notesStatus(),
            ],
          ),
        ),
      );

  Widget _documentsCard(BuildContext context, Inspection item) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Text('Dokumenty i zdjęcia'),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              TextButton(
                onPressed: () =>
                    context.push('/documents?inspection_id=${item.id}'),
                child: const Text('Pokaż'),
              ),
              FilledButton.icon(
                key: const Key('inspection-document-upload'),
                onPressed: () => showDialog<void>(
                  context: context,
                  builder: (_) => DocumentIntakeDialog(
                    repository: ref.read(documentsRepositoryProvider),
                    session: requireInspectionWidgetSession(ref),
                    clientId: item.clientId,
                    inspectionId: item.id,
                    locationService: ref.read(
                      inspectionLocationServiceProvider,
                    ),
                  ),
                ),
                icon: const Icon(Icons.upload_file),
                label: const Text('Dodaj dokument lub zdjęcie'),
              ),
            ],
          ),
        ],
      ),
    ),
  );
}
