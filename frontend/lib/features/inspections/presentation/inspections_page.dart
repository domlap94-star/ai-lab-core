import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/widgets/app_shell.dart';
import '../../../core/widgets/read_error_view.dart';
import '../application/inspections_providers.dart';
import '../domain/inspection.dart';
import 'inspection_form_dialog.dart';

class InspectionsPage extends ConsumerStatefulWidget {
  const InspectionsPage({super.key});
  @override
  ConsumerState<InspectionsPage> createState() => _InspectionsPageState();
}

class _InspectionsPageState extends ConsumerState<InspectionsPage> {
  final _search = TextEditingController();
  final _client = TextEditingController();
  Timer? _debounce;
  String _query = '';
  int? _clientId;
  InspectionStatus? _status;
  int _skip = 0;
  InspectionQuery get query => InspectionQuery(
    search: _query,
    clientId: _clientId,
    status: _status,
    skip: _skip,
  );
  @override
  void dispose() {
    _debounce?.cancel();
    _search.dispose();
    _client.dispose();
    super.dispose();
  }

  Future<void> _create() async {
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => const InspectionFormDialog(),
    );
    if (data != null && mounted) {
      await ref
          .read(inspectionsApiProvider)
          .create(requireInspectionWidgetSession(ref), data);
      ref.invalidate(inspectionsPageProvider);
    }
  }

  @override
  Widget build(BuildContext context) {
    final page = ref.watch(inspectionsPageProvider(query));
    return Scaffold(
      appBar: AppBar(
        leading: AppShell.mobileNavigationLeading(context),
        title: const Text('Wizje lokalne'),
        actions: <Widget>[
          AppShell.globalSearchAction(context),
          IconButton(
            key: const Key('inspection-create'),
            tooltip: 'Dodaj wizję',
            onPressed: _create,
            icon: const Icon(Icons.add),
          ),
        ],
      ),
      body: Column(
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.all(16),
            child: LayoutBuilder(
              builder: (context, constraints) {
                final compact = constraints.maxWidth < 600;
                final wideField = compact ? constraints.maxWidth : 320.0;
                final narrowField = compact ? constraints.maxWidth : 160.0;
                return Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: <Widget>[
                    SizedBox(
                      width: wideField,
                      child: TextField(
                        controller: _search,
                        decoration: const InputDecoration(
                          labelText: 'Szukaj wizji',
                          border: OutlineInputBorder(),
                        ),
                        onChanged: (value) {
                          _debounce?.cancel();
                          _debounce = Timer(
                            const Duration(milliseconds: 350),
                            () => setState(() {
                              _query = value;
                              _skip = 0;
                            }),
                          );
                        },
                      ),
                    ),
                    SizedBox(
                      width: narrowField,
                      child: TextField(
                        controller: _client,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'Klient ID',
                          border: OutlineInputBorder(),
                        ),
                        onChanged: (value) => setState(() {
                          _clientId = int.tryParse(value);
                          _skip = 0;
                        }),
                      ),
                    ),
                    SizedBox(
                      width: compact ? constraints.maxWidth : 190,
                      child: DropdownButtonFormField<InspectionStatus?>(
                        initialValue: _status,
                        decoration: const InputDecoration(
                          labelText: 'Status',
                          border: OutlineInputBorder(),
                        ),
                        items: <DropdownMenuItem<InspectionStatus?>>[
                          const DropdownMenuItem(
                            value: null,
                            child: Text('Wszystkie'),
                          ),
                          ...InspectionStatus.values.map(
                            (value) => DropdownMenuItem(
                              value: value,
                              child: Text(value.label),
                            ),
                          ),
                        ],
                        onChanged: (value) => setState(() {
                          _status = value;
                          _skip = 0;
                        }),
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
          Expanded(
            child: page.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => ReadErrorView(
                error: error,
                onRetry: () => ref.invalidate(inspectionsPageProvider(query)),
              ),
              data: (value) => value.items.isEmpty
                  ? const Center(child: Text('Brak wizji lokalnych.'))
                  : ListView.builder(
                      itemCount: value.items.length,
                      itemBuilder: (context, index) {
                        final item = value.items[index];
                        return Card(
                          margin: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 6,
                          ),
                          child: ListTile(
                            title: const Text('Wizja lokalna'),
                            subtitle: Text(
                              '${item.clientName}\n${item.status.label} • ${item.scheduledAt?.toLocal().toString() ?? 'bez terminu'}',
                            ),
                            isThreeLine: true,
                            onTap: () =>
                                context.push('/inspections/${item.id}'),
                          ),
                        );
                      },
                    ),
            ),
          ),
          page.maybeWhen(
            data: (value) => Padding(
              padding: const EdgeInsets.all(8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: <Widget>[
                  IconButton(
                    onPressed: _skip > 0
                        ? () => setState(
                            () => _skip = (_skip - 50).clamp(0, 1 << 30),
                          )
                        : null,
                    icon: const Icon(Icons.chevron_left),
                  ),
                  Text('${value.total} wizji'),
                  IconButton(
                    onPressed: _skip + value.items.length < value.total
                        ? () => setState(() => _skip += 50)
                        : null,
                    icon: const Icon(Icons.chevron_right),
                  ),
                ],
              ),
            ),
            orElse: () => const SizedBox.shrink(),
          ),
        ],
      ),
    );
  }
}
