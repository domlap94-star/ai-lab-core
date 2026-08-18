import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/widgets/app_shell.dart';
import '../../../core/widgets/read_error_view.dart';
import '../application/projects_providers.dart';
import '../domain/project.dart';
import 'project_form_dialog.dart';

class ProjectsPage extends ConsumerStatefulWidget {
  const ProjectsPage({super.key});
  @override
  ConsumerState<ProjectsPage> createState() => _ProjectsPageState();
}

class _ProjectsPageState extends ConsumerState<ProjectsPage> {
  final _search = TextEditingController();
  final _client = TextEditingController();
  Timer? _debounce;
  int _skip = 0;
  String _query = '';
  int? _clientId;
  ProjectStatus? _status;
  ProjectQuery get query => ProjectQuery(
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
      builder: (_) => const ProjectFormDialog(),
    );
    if (data == null || !mounted) return;
    await ref
        .read(projectsApiProvider)
        .create(requireProjectWidgetSession(ref), data);
    ref.invalidate(projectsPageProvider);
  }

  @override
  Widget build(BuildContext context) {
    final page = ref.watch(projectsPageProvider(query));
    return Scaffold(
      appBar: AppBar(
        leading: AppShell.mobileNavigationLeading(context),
        title: const Text('Realizacje'),
        actions: <Widget>[
          AppShell.globalSearchAction(context),
          IconButton(
            key: const Key('project-create'),
            tooltip: 'Dodaj realizację',
            onPressed: _create,
            icon: const Icon(Icons.add),
          ),
        ],
      ),
      body: Column(
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.all(16),
            child: Wrap(
              spacing: 12,
              runSpacing: 12,
              children: <Widget>[
                SizedBox(
                  width: 360,
                  child: TextField(
                    controller: _search,
                    decoration: const InputDecoration(
                      labelText: 'Szukaj realizacji',
                      prefixIcon: Icon(Icons.search),
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
                  width: 220,
                  child: TextField(
                    controller: _client,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'ID klienta',
                      border: OutlineInputBorder(),
                    ),
                    onChanged: (value) => setState(() {
                      _clientId = int.tryParse(value.trim());
                      _skip = 0;
                    }),
                  ),
                ),
                SizedBox(
                  width: 220,
                  child: DropdownButtonFormField<ProjectStatus?>(
                    initialValue: _status,
                    decoration: const InputDecoration(
                      labelText: 'Status',
                      border: OutlineInputBorder(),
                    ),
                    items: <DropdownMenuItem<ProjectStatus?>>[
                      const DropdownMenuItem(
                        value: null,
                        child: Text('Wszystkie'),
                      ),
                      ...ProjectStatus.values.map(
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
            ),
          ),
          Expanded(
            child: page.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => ReadErrorView(
                error: error,
                onRetry: () => ref.invalidate(projectsPageProvider(query)),
              ),
              data: (value) => value.items.isEmpty
                  ? const Center(child: Text('Brak realizacji.'))
                  : ListView.builder(
                      itemCount: value.items.length,
                      itemBuilder: (context, index) {
                        final project = value.items[index];
                        return Card(
                          margin: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 6,
                          ),
                          child: ListTile(
                            title: Text(project.name),
                            subtitle: Text(
                              '${project.clientName} • ${project.status.label}\n${project.location}',
                            ),
                            isThreeLine: true,
                            trailing: const Icon(Icons.chevron_right),
                            onTap: () =>
                                context.push('/projects/${project.id}'),
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
                  Text('${value.total} realizacji'),
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
