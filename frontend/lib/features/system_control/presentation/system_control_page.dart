import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/application/auth_controller.dart';
import '../../auth/application/auth_providers.dart';
import '../../auth/application/auth_state.dart';
import '../data/supervisor_api.dart';

class SystemControlPage extends ConsumerStatefulWidget {
  const SystemControlPage({super.key});

  @override
  ConsumerState<SystemControlPage> createState() {
    return _SystemControlPageState();
  }
}

class _SystemControlPageState extends ConsumerState<SystemControlPage> {
  late final SupervisorApi _api;

  SupervisorStatus? _status;
  bool _loading = false;
  String? _message;

  bool _isAdmin(String role) {
    final String normalized = role.trim().toLowerCase();
    return normalized == 'administrator' || normalized == 'admin';
  }

  @override
  void initState() {
    super.initState();

    _api = SupervisorApi(ref.read(authTokenStorageProvider));

    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
  }

  Future<void> _refresh() async {
    setState(() {
      _loading = true;
      _message = null;
    });

    try {
      final SupervisorStatus status = await _api.getStatus();

      if (!mounted) {
        return;
      }

      setState(() {
        _status = status;
      });
    } on DioException {
      if (!mounted) {
        return;
      }

      setState(() {
        _status = null;
        _message =
            'Supervisor nie jest jeszcze uruchomiony lub nie można '
            'się z nim połączyć.';
      });
    } catch (_) {
      if (!mounted) {
        return;
      }

      setState(() {
        _status = null;
        _message = 'Nie udało się odczytać stanu systemu.';
      });
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  Future<void> _execute(
    String title,
    Future<void> Function() action, {
    required bool destructive,
  }) async {
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext dialogContext) {
        return AlertDialog(
          title: Text(title),
          content: Text(
            destructive
                ? 'Ta operacja może chwilowo odłączyć aplikację. Kontynuować?'
                : 'Potwierdź wykonanie operacji.',
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop(false);
              },
              child: const Text('Anuluj'),
            ),
            FilledButton(
              onPressed: () {
                Navigator.of(dialogContext).pop(true);
              },
              child: const Text('Potwierdź'),
            ),
          ],
        );
      },
    );

    if (confirmed != true) {
      return;
    }

    setState(() {
      _loading = true;
      _message = null;
    });

    try {
      await action();

      if (!mounted) {
        return;
      }

      setState(() {
        _message = 'Polecenie zostało przyjęte.';
      });

      await Future<void>.delayed(const Duration(seconds: 2));

      await _refresh();
    } on DioException {
      if (!mounted) {
        return;
      }

      setState(() {
        _message = 'Nie udało się wysłać polecenia do supervisora.';
      });
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final AsyncValue<AuthState> authValue = ref.watch(authControllerProvider);

    final String role = authValue.value?.user?.role ?? '';

    if (!_isAdmin(role)) {
      return Scaffold(
        appBar: AppBar(title: const Text('System')),
        body: const Center(
          child: Padding(
            padding: EdgeInsets.all(24),
            child: Text(
              'Ta sekcja jest dostępna wyłącznie dla administratora.',
              textAlign: TextAlign.center,
            ),
          ),
        ),
      );
    }

    final SupervisorStatus? current = _status;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Sterowanie systemem'),
        actions: <Widget>[
          IconButton(
            tooltip: 'Odśwież',
            onPressed: _loading ? null : _refresh,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: <Widget>[
          Card(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: <Widget>[
                  Text(
                    'Stan AI-Lab',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 16),
                  if (_loading) const LinearProgressIndicator(),
                  if (_message != null) ...<Widget>[
                    const SizedBox(height: 12),
                    Text(_message!),
                  ],
                  const SizedBox(height: 16),
                  _StatusRow(
                    label: 'Supervisor',
                    online: current?.supervisorOnline == true,
                  ),
                  _StatusRow(
                    label: 'AI-Lab',
                    online: current?.systemRunning == true,
                  ),
                  ...?current?.services.entries.map(
                    (MapEntry<String, bool> entry) =>
                        _StatusRow(label: entry.key, online: entry.value),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Wrap(
                spacing: 12,
                runSpacing: 12,
                children: <Widget>[
                  FilledButton.icon(
                    onPressed: _loading
                        ? null
                        : () {
                            _execute(
                              'Uruchom system',
                              _api.startSystem,
                              destructive: false,
                            );
                          },
                    icon: const Icon(Icons.play_arrow),
                    label: const Text('Uruchom system'),
                  ),
                  FilledButton.tonalIcon(
                    onPressed: _loading
                        ? null
                        : () {
                            _execute(
                              'Restartuj system',
                              _api.restartSystem,
                              destructive: true,
                            );
                          },
                    icon: const Icon(Icons.restart_alt),
                    label: const Text('Restartuj system'),
                  ),
                  OutlinedButton.icon(
                    onPressed: _loading
                        ? null
                        : () {
                            _execute(
                              'Zatrzymaj system',
                              _api.stopSystem,
                              destructive: true,
                            );
                          },
                    icon: const Icon(Icons.stop_circle_outlined),
                    label: const Text('Zatrzymaj system'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _StatusRow extends StatelessWidget {
  const _StatusRow({required this.label, required this.online});

  final String label;
  final bool online;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(online ? Icons.check_circle : Icons.cancel),
      title: Text(label),
      trailing: Text(online ? 'online' : 'offline'),
    );
  }
}
