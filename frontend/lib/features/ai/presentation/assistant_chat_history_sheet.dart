import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/formatters/polish_date_time.dart';
import '../../auth/application/auth_controller.dart';
import '../application/assistant_conversation_controller.dart';
import '../domain/assistant_conversation.dart';

class AssistantChatHistorySheet extends ConsumerStatefulWidget {
  const AssistantChatHistorySheet({
    required this.onOpen,
    required this.onNewChat,
    required this.onRenamed,
    required this.onDeleted,
    super.key,
  });

  final Future<void> Function(AssistantConversationDetail conversation) onOpen;
  final Future<void> Function(AssistantConversationDetail conversation)
  onNewChat;
  final Future<void> Function(AssistantConversationDetail conversation)
  onRenamed;
  final Future<void> Function(
    AssistantConversationSummary conversation,
    AssistantConversationDeleteResult result,
  )
  onDeleted;

  @override
  ConsumerState<AssistantChatHistorySheet> createState() =>
      _AssistantChatHistorySheetState();
}

class _AssistantChatHistorySheetState
    extends ConsumerState<AssistantChatHistorySheet> {
  List<AssistantConversationSummary>? _items;
  String? _error;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  @override
  Widget build(BuildContext context) => SafeArea(
    child: SizedBox(
      height: MediaQuery.sizeOf(context).height * 0.82,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 8, 8),
            child: Row(
              children: <Widget>[
                Expanded(
                  child: Text(
                    'Historia rozmów',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                IconButton(
                  tooltip: 'Zamknij',
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: FilledButton.icon(
              key: const Key('assistant-history-new-chat'),
              onPressed: _newChat,
              icon: const Icon(Icons.add_comment_outlined),
              label: const Text('Nowa rozmowa'),
            ),
          ),
          const SizedBox(height: 8),
          Expanded(child: _body()),
        ],
      ),
    ),
  );

  Widget _body() {
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Text(_error!, key: const Key('assistant-history-error')),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              key: const Key('assistant-history-retry'),
              onPressed: _load,
              icon: const Icon(Icons.refresh),
              label: const Text('Spróbuj ponownie'),
            ),
          ],
        ),
      );
    }
    if (_items == null) {
      return const Center(
        child: CircularProgressIndicator(key: Key('assistant-history-loading')),
      );
    }
    if (_items!.isEmpty) {
      return const Center(
        child: Text(
          'Nie masz jeszcze zapisanych rozmów.',
          key: Key('assistant-history-empty'),
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(8, 0, 8, 24),
        itemCount: _items!.length,
        separatorBuilder: (_, _) => const Divider(height: 1),
        itemBuilder: (context, index) {
          final item = _items![index];
          return ListTile(
            key: ValueKey<String>('assistant-history-chat-${item.id}'),
            onTap: () => _open(item),
            leading: Icon(
              item.active ? Icons.pending_outlined : Icons.chat_bubble_outline,
            ),
            title: Text(
              item.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            subtitle: Text(
              <String>[
                if (item.lastMessagePreview?.isNotEmpty == true)
                  item.lastMessagePreview!,
                formatPolishDateTime(item.lastActivityAt),
                if (item.active) 'Analiza trwa',
              ].join('\n'),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
            trailing: PopupMenuButton<String>(
              key: ValueKey<String>('assistant-history-actions-${item.id}'),
              onSelected: (value) {
                if (value == 'rename') unawaited(_rename(item));
                if (value == 'delete') unawaited(_delete(item));
              },
              itemBuilder: (_) => const <PopupMenuEntry<String>>[
                PopupMenuItem(value: 'rename', child: Text('Zmień nazwę')),
                PopupMenuItem(value: 'delete', child: Text('Usuń')),
              ],
            ),
          );
        },
      ),
    );
  }

  Future<void> _load() async {
    if (mounted) setState(() => _error = null);
    try {
      final session = (await ref.read(authControllerProvider.future)).session;
      if (session == null) throw StateError('Brak aktywnej sesji.');
      final items = await ref
          .read(assistantConversationRepositoryProvider)
          .listChats(session: session);
      if (mounted) setState(() => _items = items);
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Nie udało się pobrać historii rozmów.');
      }
    }
  }

  Future<void> _newChat() async {
    final session = (await ref.read(authControllerProvider.future)).session;
    if (session == null) return;
    final created = await ref
        .read(assistantConversationRepositoryProvider)
        .createChat(session: session);
    await widget.onNewChat(created);
    if (mounted) Navigator.of(context).pop();
  }

  Future<void> _open(AssistantConversationSummary item) async {
    final session = (await ref.read(authControllerProvider.future)).session;
    if (session == null) return;
    final detail = await ref
        .read(assistantConversationRepositoryProvider)
        .getChat(session: session, conversationId: item.id);
    await widget.onOpen(detail);
    if (mounted) Navigator.of(context).pop();
  }

  Future<void> _rename(AssistantConversationSummary item) async {
    var editedTitle = item.title;
    final title = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Zmień nazwę rozmowy'),
        content: TextFormField(
          key: const Key('assistant-history-rename-input'),
          initialValue: item.title,
          autofocus: true,
          maxLength: 120,
          onChanged: (value) => editedTitle = value,
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Anuluj'),
          ),
          FilledButton(
            key: const Key('assistant-history-rename-save'),
            onPressed: () => Navigator.of(context).pop(editedTitle.trim()),
            child: const Text('Zapisz'),
          ),
        ],
      ),
    );
    if (title == null || title.isEmpty) return;
    final session = (await ref.read(authControllerProvider.future)).session;
    if (session == null) return;
    final renamed = await ref
        .read(assistantConversationRepositoryProvider)
        .renameChat(session: session, conversationId: item.id, title: title);
    await widget.onRenamed(renamed);
    await _load();
  }

  Future<void> _delete(AssistantConversationSummary item) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Usunąć tę rozmowę?'),
        content: Text(
          item.active
              ? 'Usunięcie rozmowy nie anuluje trwającej analizy. '
                    'Analiza będzie kontynuowana w tle i można ją osobno anulować.'
              : 'Rozmowa zniknie z historii.',
          key: const Key('assistant-history-delete-warning'),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Anuluj'),
          ),
          FilledButton(
            key: const Key('assistant-history-delete-confirm'),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Usuń'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    final session = (await ref.read(authControllerProvider.future)).session;
    if (session == null) return;
    final result = await ref
        .read(assistantConversationRepositoryProvider)
        .deleteChat(session: session, conversationId: item.id);
    await widget.onDeleted(item, result);
    await _load();
  }
}
