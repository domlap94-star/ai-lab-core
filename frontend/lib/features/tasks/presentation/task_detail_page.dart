import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';
import 'package:image_picker/image_picker.dart';
import 'package:go_router/go_router.dart';
import '../../../core/widgets/app_shell.dart';
import '../../auth/application/auth_controller.dart';
import '../../documents/domain/document.dart';
import '../../documents/presentation/document_media_preview.dart';
import '../../inspections/application/inspection_field_services.dart';
import '../application/tasks_providers.dart';
import '../application/calendar_widget_snapshot.dart';
import '../domain/work_item.dart';
import 'work_item_form_dialog.dart';

final workItemDetailProvider = FutureProvider.family<WorkItem, int>((ref, id) {
  final s = ref.watch(authControllerProvider).value?.session;
  if (s == null) throw StateError('Brak sesji');
  return ref.watch(workItemsApiProvider).get(s, id);
});

class TaskDetailPage extends ConsumerWidget {
  const TaskDetailPage({required this.workItemId, super.key});
  final int workItemId;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final value = ref.watch(workItemDetailProvider(workItemId));
    return Scaffold(
      appBar: AppBar(
        leading: AppShell.mobileNavigationLeading(context),
        title: const Text('Szczegóły zadania'),
      ),
      body: value.when(
        data: (item) => ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Text(item.title, style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [
                Chip(label: Text(item.type.label)),
                Chip(label: Text(item.status.name)),
                Chip(label: Text(item.priority.name)),
              ],
            ),
            if (item.description?.isNotEmpty == true)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(item.description!),
              ),
            if (item.clientName != null)
              ListTile(
                leading: const Icon(Icons.business),
                title: Text(item.clientName!),
              ),
            if (item.assigneeDisplay != null)
              ListTile(
                leading: const Icon(Icons.person),
                title: Text(item.assigneeDisplay!),
              ),
            const Divider(),
            const Text(
              'Notatki i dokumenty',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            _NotesPanel(itemId: item.id),
            _DocumentsPanel(itemId: item.id),
            _AttachmentActions(itemId: item.id),
            const Text(
              'Załączniki korzystają z kanonicznego repozytorium Dokumentów i zachowują GPS z jawnego ujęcia, gdy jest dostępny.',
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: () async {
                final data = await showDialog<Map<String, dynamic>>(
                  context: context,
                  builder: (_) => WorkItemFormDialog(item: item),
                );
                if (data == null) return;
                final s = ref.read(authControllerProvider).value?.session;
                if (s == null) return;
                await ref.read(workItemsApiProvider).update(s, item.id, data);
                await CalendarWidgetSnapshot.refreshCurrent(ref);
                ref.invalidate(workItemDetailProvider(item.id));
                ref.invalidate(workItemsProvider);
                ref.invalidate(filteredWorkItemsProvider);
                ref.invalidate(calendarMonthProvider);
              },
              icon: const Icon(Icons.edit),
              label: const Text('Edytuj'),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: () async {
                final confirmed = await showDialog<bool>(
                  context: context,
                  builder: (dialogContext) => AlertDialog(
                    title: const Text('Archiwizować zadanie?'),
                    content: const Text(
                      'Pozycja zniknie z aktywnej listy i kalendarza, ale jej historia zostanie zachowana.',
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(dialogContext, false),
                        child: const Text('Anuluj'),
                      ),
                      FilledButton(
                        onPressed: () => Navigator.pop(dialogContext, true),
                        child: const Text('Archiwizuj'),
                      ),
                    ],
                  ),
                );
                if (confirmed != true || !context.mounted) return;
                final session = ref.read(authControllerProvider).value?.session;
                if (session == null) return;
                await ref
                    .read(workItemsApiProvider)
                    .archive(session, item.id, item.version);
                ref.invalidate(workItemsProvider);
                ref.invalidate(filteredWorkItemsProvider);
                ref.invalidate(calendarMonthProvider);
                await CalendarWidgetSnapshot.refreshCurrent(ref);
                if (context.mounted) context.go('/tasks');
              },
              icon: const Icon(Icons.archive_outlined),
              label: const Text('Archiwizuj'),
            ),
          ],
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) =>
            Center(child: Text('Nie udało się pobrać zadania: $e')),
      ),
    );
  }
}

class _AttachmentActions extends ConsumerWidget {
  const _AttachmentActions({required this.itemId, this.noteId});
  final int itemId;
  final int? noteId;

  Future<void> upload(
    BuildContext context,
    WidgetRef ref, {
    required bool camera,
    required bool gallery,
  }) async {
    String? name;
    List<int>? raw;
    String source = 'manual_upload';
    DateTime? captured;
    if (camera || gallery) {
      final file = await ImagePicker().pickImage(
        source: camera ? ImageSource.camera : ImageSource.gallery,
      );
      if (file == null) return;
      name = file.name;
      raw = await file.readAsBytes();
      source = camera ? 'camera_photo' : 'manual_upload';
      captured = camera ? DateTime.now() : null;
    } else {
      final result = await FilePicker.pickFiles();
      final file = result.singleOrNull;
      if (file == null) return;
      name = file.name;
      raw = await file.readAsBytes();
    }
    if (!context.mounted) return;
    FieldLocationResult? location;
    if (camera || gallery) {
      location = await ref.read(fieldLocationServiceProvider).currentLocation();
    }
    final session = ref.read(authControllerProvider).value?.session;
    if (session == null) return;
    await ref
        .read(workItemsApiProvider)
        .uploadDocument(
          session,
          itemId,
          name: name,
          bytes: Uint8List.fromList(raw),
          sourceType: source,
          capturedAt: captured,
          latitude: location?.latitude,
          longitude: location?.longitude,
          accuracy: location?.accuracy,
          noteId: noteId,
        );
    ref.invalidate(workItemDocumentsProvider(itemId));
    if (context.mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Dokument dołączony.')));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) => Wrap(
    spacing: 8,
    runSpacing: 8,
    children: [
      OutlinedButton.icon(
        onPressed: () => upload(context, ref, camera: false, gallery: false),
        icon: const Icon(Icons.attach_file),
        label: const Text('Plik'),
      ),
      OutlinedButton.icon(
        onPressed: () => upload(context, ref, camera: false, gallery: true),
        icon: const Icon(Icons.photo_library_outlined),
        label: const Text('Galeria'),
      ),
      OutlinedButton.icon(
        onPressed: () => upload(context, ref, camera: true, gallery: false),
        icon: const Icon(Icons.camera_alt_outlined),
        label: const Text('Aparat'),
      ),
    ],
  );
}

class _NotesPanel extends ConsumerStatefulWidget {
  const _NotesPanel({required this.itemId});
  final int itemId;
  @override
  ConsumerState<_NotesPanel> createState() => _NotesPanelState();
}

class _NotesPanelState extends ConsumerState<_NotesPanel> {
  bool listening = false;

  Future<void> addNote() async {
    final controller = TextEditingController();
    final text = await showDialog<String>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Dodaj notatkę'),
          content: TextField(controller: controller, minLines: 4, maxLines: 12),
          actions: [
            IconButton(
              tooltip: listening ? 'Zatrzymaj dyktowanie' : 'Dyktuj po polsku',
              onPressed: () async {
                final speech = ref.read(fieldSpeechServiceProvider);
                if (listening) {
                  await speech.stop();
                  if (mounted) setDialogState(() => listening = false);
                  return;
                }
                final result = await speech.start(
                  onFinalResult: (words) {
                    final prefix = controller.text.trim();
                    controller.text = prefix.isEmpty ? words : '$prefix $words';
                  },
                  onStopped: () {
                    if (mounted) setDialogState(() => listening = false);
                  },
                );
                if (mounted) {
                  setDialogState(
                    () => listening = result == SpeechStartStatus.listening,
                  );
                }
              },
              icon: Icon(listening ? Icons.stop : Icons.mic),
            ),
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Anuluj'),
            ),
            FilledButton(
              onPressed: () =>
                  Navigator.pop(dialogContext, controller.text.trim()),
              child: const Text('Zapisz'),
            ),
          ],
        ),
      ),
    );
    controller.dispose();
    if (text == null || text.isEmpty || !mounted) return;
    final session = ref.read(authControllerProvider).value?.session;
    if (session == null) return;
    await ref
        .read(workItemsApiProvider)
        .createNote(session, widget.itemId, text);
    ref.invalidate(workItemNotesProvider(widget.itemId));
  }

  Future<void> editNote(WorkItemNote note) async {
    final controller = TextEditingController(text: note.text);
    final text = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Edytuj notatkę'),
        content: TextField(controller: controller, minLines: 4, maxLines: 12),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Anuluj'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, controller.text.trim()),
            child: const Text('Zapisz'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (text == null || text.isEmpty || !mounted) return;
    final session = ref.read(authControllerProvider).value?.session;
    if (session == null) return;
    await ref.read(workItemsApiProvider).updateNote(
      session,
      widget.itemId,
      note,
      text,
    );
    ref.invalidate(workItemNotesProvider(widget.itemId));
  }

  Future<void> archiveNote(WorkItemNote note) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Archiwizować notatkę?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Anuluj'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Archiwizuj'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final session = ref.read(authControllerProvider).value?.session;
    if (session == null) return;
    await ref.read(workItemsApiProvider).archiveNote(
      session,
      widget.itemId,
      note,
    );
    ref.invalidate(workItemNotesProvider(widget.itemId));
  }

  @override
  Widget build(BuildContext context) {
    final notes = ref.watch(workItemNotesProvider(widget.itemId));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        notes.when(
          data: (items) => Column(
            children: [
              for (final note in items)
                Card(
                  child: Column(
                    children: [
                      ListTile(
                        leading: const Icon(Icons.note_outlined),
                        title: Text(note.text),
                      ),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: Wrap(
                          children: [
                            IconButton(
                              tooltip: 'Edytuj notatkę',
                              onPressed: () => editNote(note),
                              icon: const Icon(Icons.edit_outlined),
                            ),
                            IconButton(
                              tooltip: 'Archiwizuj notatkę',
                              onPressed: () => archiveNote(note),
                              icon: const Icon(Icons.archive_outlined),
                            ),
                          ],
                        ),
                      ),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: _AttachmentActions(
                          itemId: widget.itemId,
                          noteId: note.id,
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
          loading: () => const LinearProgressIndicator(),
          error: (error, _) => Text('Nie udało się pobrać notatek: $error'),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: addNote,
            icon: const Icon(Icons.add_comment),
            label: const Text('Dodaj notatkę / dyktuj'),
          ),
        ),
      ],
    );
  }
}

class _DocumentsPanel extends ConsumerWidget {
  const _DocumentsPanel({required this.itemId});

  final int itemId;

  RepositoryDocument _document(WorkItemDocument link) => RepositoryDocument(
    id: link.documentId,
    originalFilename: link.filename,
    contentType: link.contentType,
    fileSize: link.fileSize,
    sourceType: link.sourceType,
    processingStatus: 'stored',
    metadataStatus: 'pending',
    matchStatus: 'unmatched',
    capturedAt: link.capturedAt,
    archiveDepth: 0,
    createdAt: link.createdAt,
    updatedAt: link.createdAt,
  );

  Future<void> detach(
    BuildContext context,
    WidgetRef ref,
    WorkItemDocument link,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Odłączyć dokument?'),
        content: const Text(
          'Dokument pozostanie w kanonicznym repozytorium. Usunięte zostanie tylko aktywne powiązanie z zadaniem.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Anuluj'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Odłącz'),
          ),
        ],
      ),
    );
    if (confirmed != true || !context.mounted) return;
    final session = ref.read(authControllerProvider).value?.session;
    if (session == null) return;
    await ref.read(workItemsApiProvider).detachDocument(
      session,
      itemId,
      link.documentId,
    );
    ref.invalidate(workItemDocumentsProvider(itemId));
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final value = ref.watch(workItemDocumentsProvider(itemId));
    return value.when(
      loading: () => const LinearProgressIndicator(),
      error: (error, _) => Text('Nie udało się pobrać dokumentów: $error'),
      data: (links) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final link in links)
            Builder(
              builder: (context) {
                final document = _document(link);
                return Card(
                  child: Padding(
                    padding: const EdgeInsets.all(8),
                    child: Row(
                      children: [
                        DocumentImageThumbnail(
                          documentId: link.documentId,
                          contentType: link.contentType,
                          fileName: link.filename,
                          onOpen: () =>
                              openDocumentMedia(context, ref, document),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: InkWell(
                            onTap: () =>
                                openDocumentMedia(context, ref, document),
                            child: Text(
                              link.filename,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ),
                        IconButton(
                          tooltip: 'Odłącz dokument',
                          onPressed: () => detach(context, ref, link),
                          icon: const Icon(Icons.link_off),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
        ],
      ),
    );
  }
}
