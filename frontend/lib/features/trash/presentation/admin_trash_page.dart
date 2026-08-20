import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/application/auth_controller.dart';
import '../application/trash_providers.dart';
import '../domain/trash_entry.dart';

class AdminTrashPage extends ConsumerWidget {
  const AdminTrashPage({super.key});

  bool _isAdmin(String? role) {
    final value = role?.trim().toLowerCase();
    return value == 'admin' || value == 'administrator';
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final role = ref.watch(authControllerProvider).value?.user?.role;
    if (!_isAdmin(role)) {
      return const Scaffold(
        body: Center(child: Text('Brak uprawnień administratora.')),
      );
    }
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Kosz'),
          bottom: const TabBar(
            tabs: <Tab>[
              Tab(icon: Icon(Icons.description_outlined), text: 'Pliki'),
              Tab(icon: Icon(Icons.business_outlined), text: 'Klienci'),
              Tab(icon: Icon(Icons.people_outline), text: 'Użytkownicy'),
            ],
          ),
        ),
        body: const TabBarView(
          children: <Widget>[
            _TrashTab(entityType: TrashEntityType.document),
            _TrashTab(entityType: TrashEntityType.client),
            _TrashTab(entityType: TrashEntityType.user),
          ],
        ),
      ),
    );
  }
}

class _TrashTab extends ConsumerWidget {
  const _TrashTab({required this.entityType});
  final TrashEntityType entityType;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final page = ref.watch(trashPageProvider(entityType));
    return RefreshIndicator(
      onRefresh: () => ref.refresh(trashPageProvider(entityType).future),
      child: page.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, _) => ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: <Widget>[
            const SizedBox(height: 96),
            const Center(child: Text('Nie udało się pobrać zawartości Kosza.')),
            Center(
              child: TextButton.icon(
                onPressed: () => ref.invalidate(trashPageProvider(entityType)),
                icon: const Icon(Icons.refresh),
                label: const Text('Spróbuj ponownie'),
              ),
            ),
          ],
        ),
        data: (data) {
          if (data.items.isEmpty) {
            return ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              children: const <Widget>[
                SizedBox(height: 96),
                Center(child: Text('Kosz jest pusty.')),
              ],
            );
          }
          return LayoutBuilder(
            builder: (context, constraints) => ListView.separated(
              padding: EdgeInsets.all(constraints.maxWidth < 600 ? 12 : 24),
              itemCount: data.items.length,
              separatorBuilder: (_, _) => const SizedBox(height: 8),
              itemBuilder: (context, index) => _TrashCard(
                entry: data.items[index],
                onRestored: () => ref.invalidate(trashPageProvider(entityType)),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _TrashCard extends ConsumerStatefulWidget {
  const _TrashCard({required this.entry, required this.onRestored});
  final TrashEntry entry;
  final VoidCallback onRestored;

  @override
  ConsumerState<_TrashCard> createState() => _TrashCardState();
}

class _TrashCardState extends ConsumerState<_TrashCard> {
  bool _busy = false;

  String _timeRemaining() {
    final remaining = widget.entry.purgeAfter.difference(DateTime.now());
    if (remaining.isNegative) return 'Oczekuje na bezpieczne usunięcie';
    final days = remaining.inDays;
    final hours = remaining.inHours.remainder(24);
    return days > 0 ? '$days d $hours godz.' : '${remaining.inHours} godz.';
  }

  Future<void> _restore() async {
    setState(() => _busy = true);
    try {
      await ref
          .read(trashApiProvider)
          .restore(
            session: requireTrashSessionFromAuth(
              ref.read(authControllerProvider),
            ),
            entryId: widget.entry.id,
          );
      widget.onRestored();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Element został przywrócony.')),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Nie udało się przywrócić elementu.')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final blocked = widget.entry.state == 'blocked';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Wrap(
          spacing: 16,
          runSpacing: 12,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: <Widget>[
            ConstrainedBox(
              constraints: const BoxConstraints(minWidth: 220, maxWidth: 440),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    widget.entry.safeDisplayLabel,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  Text('Przeniesiono: ${widget.entry.trashedAt}'),
                  Text('Automatyczne usunięcie: ${widget.entry.purgeAfter}'),
                  Text('Pozostało: ${_timeRemaining()}'),
                  Text(
                    'Przeniósł: użytkownik #${widget.entry.trashedByUserId}',
                  ),
                  if (blocked)
                    const Text(
                      'Nie udało się jeszcze usunąć automatycznie. '
                      'System spróbuje ponownie.',
                    ),
                ],
              ),
            ),
            OutlinedButton.icon(
              key: Key('restore-trash-${widget.entry.id}'),
              onPressed: _busy ? null : _restore,
              icon: _busy
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.restore),
              label: const Text('Przywróć'),
            ),
          ],
        ),
      ),
    );
  }
}
