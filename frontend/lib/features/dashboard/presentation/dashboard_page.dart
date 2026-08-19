import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/widgets/app_shell.dart';
import '../../system_status/application/system_status_provider.dart';
import '../../system_status/domain/backend_status.dart';

class DashboardPage extends ConsumerWidget {
  const DashboardPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ThemeData theme = Theme.of(context);
    final AsyncValue<BackendStatus> backendStatus = ref.watch(
      backendStatusProvider,
    );

    return Scaffold(
      appBar: AppBar(
        leading: AppShell.mobileNavigationLeading(context),
        title: const Text('Dashboard'),
        actions: <Widget>[
          IconButton(
            tooltip: 'Odśwież status backendu',
            onPressed: () {
              ref.invalidate(backendStatusProvider);
            },
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            tooltip: 'Wyszukiwanie',
            onPressed: () => context.push('/search'),
            icon: const Icon(Icons.search),
          ),
          IconButton(
            tooltip: 'Powiadomienia',
            onPressed: () {},
            icon: const Icon(Icons.notifications_outlined),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(backendStatusProvider);
          await ref.read(backendStatusProvider.future);
        },
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              const _DashboardGlobalSearchBar(),
              const SizedBox(height: 28),
              Text(
                'Dzień dobry',
                style: theme.textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Tutaj pojawią się najważniejsze informacje i zadania.',
                style: theme.textTheme.bodyLarge?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 28),
              _BackendStatusCard(
                status: backendStatus,
                onRefresh: () {
                  ref.invalidate(backendStatusProvider);
                },
              ),
              const SizedBox(height: 24),
              LayoutBuilder(
                builder: (BuildContext context, BoxConstraints constraints) {
                  final int columns = constraints.maxWidth >= 1100
                      ? 4
                      : constraints.maxWidth >= 650
                      ? 2
                      : 1;

                  return GridView.count(
                    crossAxisCount: columns,
                    crossAxisSpacing: 16,
                    mainAxisSpacing: 16,
                    childAspectRatio: 2.2,
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    children: <Widget>[
                      const _SummaryCard(
                        title: 'Aktywne sprawy',
                        value: '0',
                        icon: Icons.work_outline,
                      ),
                      const _SummaryCard(
                        title: 'Nowe dokumenty',
                        value: '0',
                        icon: Icons.description_outlined,
                      ),
                      const _SummaryCard(
                        title: 'Zadania',
                        value: '0',
                        icon: Icons.task_alt_outlined,
                      ),
                      _SummaryCard(
                        title: 'Maile',
                        value: 'Otwórz',
                        icon: Icons.mail_outline,
                        onTap: () => context.push('/mail'),
                      ),
                    ],
                  );
                },
              ),
              const SizedBox(height: 24),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: SizedBox(
                    width: double.infinity,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          'Ostatnia aktywność',
                          style: theme.textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 20),
                        const Center(
                          child: Padding(
                            padding: EdgeInsets.symmetric(vertical: 40),
                            child: Text('Brak aktywności do wyświetlenia'),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DashboardGlobalSearchBar extends StatefulWidget {
  const _DashboardGlobalSearchBar();

  @override
  State<_DashboardGlobalSearchBar> createState() =>
      _DashboardGlobalSearchBarState();
}

class _DashboardGlobalSearchBarState extends State<_DashboardGlobalSearchBar> {
  final TextEditingController _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _openSearch([String? value]) {
    FocusManager.instance.primaryFocus?.unfocus();
    final String query = (value ?? _controller.text).trim();
    final Uri target = Uri(
      path: '/search',
      queryParameters: query.isEmpty ? null : <String, String>{'q': query},
    );
    context.go(target.toString());
  }

  @override
  Widget build(BuildContext context) {
    final bool compact = MediaQuery.sizeOf(context).width < 600;
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 920),
      child: SearchBar(
        key: const Key('dashboard-global-search-bar'),
        controller: _controller,
        leading: const Icon(Icons.search),
        hintText: compact
            ? 'Szukaj w NEXT Stabil'
            : 'Szukaj klientów, dokumentów, e-maili, realizacji...',
        textInputAction: TextInputAction.search,
        onTap: () {
          if (_controller.text.trim().isEmpty) {
            _openSearch();
          }
        },
        onSubmitted: _openSearch,
      ),
    );
  }
}

class _BackendStatusCard extends StatelessWidget {
  const _BackendStatusCard({required this.status, required this.onRefresh});

  final AsyncValue<BackendStatus> status;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: status.when(
          loading: () {
            return const Row(
              children: <Widget>[
                SizedBox(
                  width: 28,
                  height: 28,
                  child: CircularProgressIndicator(strokeWidth: 3),
                ),
                SizedBox(width: 16),
                Expanded(child: Text('Sprawdzanie połączenia z backendem...')),
              ],
            );
          },
          error: (Object error, StackTrace stackTrace) {
            final String message = _friendlyErrorMessage(error);

            return Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Icon(Icons.cloud_off, color: theme.colorScheme.error, size: 32),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        'Backend: OFFLINE',
                        style: theme.textTheme.titleMedium?.copyWith(
                          color: theme.colorScheme.error,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(message),
                    ],
                  ),
                ),
                IconButton(
                  tooltip: 'Spróbuj ponownie',
                  onPressed: onRefresh,
                  icon: const Icon(Icons.refresh),
                ),
              ],
            );
          },
          data: (BackendStatus backend) {
            final Color statusColor = backend.isOnline
                ? const Color(0xFF18864B)
                : theme.colorScheme.error;

            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Row(
                  children: <Widget>[
                    Container(
                      width: 12,
                      height: 12,
                      decoration: BoxDecoration(
                        color: statusColor,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        backend.isOnline
                            ? 'Backend: ONLINE'
                            : 'Backend: NIEPRAWIDŁOWY STATUS',
                        style: theme.textTheme.titleMedium?.copyWith(
                          color: statusColor,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    IconButton(
                      tooltip: 'Odśwież',
                      onPressed: onRefresh,
                      icon: const Icon(Icons.refresh),
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                Wrap(
                  spacing: 28,
                  runSpacing: 16,
                  children: <Widget>[
                    _StatusValue(
                      label: 'Aplikacja',
                      value: backend.application,
                    ),
                    _StatusValue(label: 'Wersja', value: backend.version),
                    _StatusValue(
                      label: 'Środowisko',
                      value: backend.environment,
                    ),
                    _StatusValue(
                      label: 'Tryb debug',
                      value: backend.debug ? 'Tak' : 'Nie',
                    ),
                    _StatusValue(
                      label: 'Czas odpowiedzi',
                      value: '${backend.latencyMilliseconds} ms',
                    ),
                    _StatusValue(label: 'Adres API', value: backend.baseUrl),
                  ],
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  String _friendlyErrorMessage(Object error) {
    if (error is DioException) {
      switch (error.type) {
        case DioExceptionType.connectionTimeout:
          return 'Przekroczono czas oczekiwania na połączenie.';
        case DioExceptionType.receiveTimeout:
          return 'Backend nie odpowiedział w wymaganym czasie.';
        case DioExceptionType.connectionError:
          return 'Nie można połączyć się z usługą FastAPI.';
        case DioExceptionType.badResponse:
          return 'Backend zwrócił błąd HTTP '
              '${error.response?.statusCode ?? 'bez kodu'}.';
        case DioExceptionType.cancel:
          return 'Żądanie zostało anulowane.';
        case DioExceptionType.sendTimeout:
          return 'Przekroczono czas wysyłania żądania.';
        case DioExceptionType.badCertificate:
          return 'Certyfikat serwera nie został zaakceptowany.';
        case DioExceptionType.transformTimeout:
          return 'Przekroczono czas przetwarzania odpowiedzi serwera.';
        case DioExceptionType.unknown:
          return error.message ?? 'Wystąpił nieznany błąd połączenia.';
      }
    }

    return error.toString();
  }
}

class _StatusValue extends StatelessWidget {
  const _StatusValue({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return ConstrainedBox(
      constraints: const BoxConstraints(minWidth: 120, maxWidth: 280),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            label,
            style: theme.textTheme.labelMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            value,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: theme.textTheme.bodyLarge?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({
    required this.title,
    required this.value,
    required this.icon,
    this.onTap,
  });

  final String title;
  final String value;
  final IconData icon;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: <Widget>[
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: theme.colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(icon, color: theme.colorScheme.onPrimaryContainer),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      value,
                      style: theme.textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
