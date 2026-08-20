import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/formatters/polish_date_time.dart';
import '../../../core/widgets/app_shell.dart';
import '../../documents/domain/document.dart';
import '../../documents/presentation/document_media_preview.dart';
import '../../mail/domain/global_mail.dart';
import '../../system_status/application/system_status_provider.dart';
import '../../system_status/domain/backend_status.dart';
import '../../tasks/application/tasks_providers.dart';
import '../../tasks/presentation/dashboard_calendar_card.dart';
import '../application/dashboard_providers.dart';
import '../domain/recent_activity.dart';

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
            key: const Key('dashboard-refresh'),
            tooltip: 'Odśwież Dashboard',
            onPressed: () => _refreshDashboard(ref),
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            tooltip: 'Wyszukiwanie',
            onPressed: () => context.push('/search'),
            icon: const Icon(Icons.search),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => _refreshDashboard(ref),
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: EdgeInsets.symmetric(
            horizontal: MediaQuery.sizeOf(context).width < 600 ? 12 : 24,
            vertical: 20,
          ),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1280),
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
                  const SizedBox(height: 24),
                  const KeyedSubtree(
                    key: Key('dashboard-calendar-section'),
                    child: DashboardCalendarCard(),
                  ),
                  const SizedBox(height: 20),
                  const _DashboardMailSection(
                    key: Key('dashboard-mail-section'),
                  ),
                  const SizedBox(height: 20),
                  const _DashboardDocumentsSection(
                    key: Key('dashboard-documents-section'),
                  ),
                  const SizedBox(height: 20),
                  const _DashboardLastActivitySection(
                    key: Key('dashboard-last-activity-section'),
                  ),
                  const SizedBox(height: 20),
                  KeyedSubtree(
                    key: const Key('dashboard-system-status-section'),
                    child: _BackendStatusCard(
                      status: backendStatus,
                      onRefresh: () => ref.invalidate(backendStatusProvider),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

Future<void> _refreshDashboard(WidgetRef ref) async {
  final DateTime now = DateTime.now();
  final DateTime month = DateTime(now.year, now.month);
  ref.invalidate(calendarMonthProvider);
  ref.invalidate(dashboardRecentMailProvider);
  ref.invalidate(dashboardRecentDocumentsProvider);
  ref.invalidate(dashboardRecentActivityProvider);
  ref.invalidate(backendStatusProvider);

  Future<void> settle(Future<Object?> future) async {
    try {
      await future;
    } catch (_) {
      // A failed section keeps its own error state and does not hide the rest.
    }
  }

  await Future.wait(<Future<void>>[
    settle(ref.read(calendarMonthProvider(month).future)),
    settle(ref.read(dashboardRecentMailProvider.future)),
    settle(ref.read(dashboardRecentDocumentsProvider.future)),
    settle(ref.read(dashboardRecentActivityProvider.future)),
    settle(ref.read(backendStatusProvider.future)),
  ]);
}

class _DashboardMailSection extends ConsumerWidget {
  const _DashboardMailSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<List<GlobalMailItem>> value = ref.watch(
      dashboardRecentMailProvider,
    );
    return _DashboardSection(
      title: 'Maile',
      icon: Icons.mail_outline,
      action: TextButton(
        onPressed: () => context.push('/mail'),
        child: const Text('Zobacz wszystkie'),
      ),
      child: value.when(
        loading: () => const _SectionLoading(label: 'Ładowanie wiadomości…'),
        error: (_, _) => _SectionError(
          message: 'Nie udało się wczytać ostatnich wiadomości.',
          onRetry: () => ref.invalidate(dashboardRecentMailProvider),
        ),
        data: (List<GlobalMailItem> items) {
          if (items.isEmpty) {
            return const _SectionEmpty('Brak ostatnich wiadomości.');
          }
          return Column(
            children: items
                .map(
                  (GlobalMailItem item) => ListTile(
                    key: ValueKey<String>('dashboard-mail-${item.sourceId}'),
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(
                      item.readState == 'unread'
                          ? Icons.mark_email_unread_outlined
                          : Icons.email_outlined,
                    ),
                    title: Text(
                      item.subject?.trim().isNotEmpty == true
                          ? item.subject!
                          : '(bez tematu)',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    subtitle: Text(
                      '${item.sender ?? item.recipients.join(', ')} · '
                      '${formatPolishDateTime(item.occurredAt)}',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    onTap: () => context.push('/mail'),
                  ),
                )
                .toList(growable: false),
          );
        },
      ),
    );
  }
}

class _DashboardDocumentsSection extends ConsumerWidget {
  const _DashboardDocumentsSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<List<RepositoryDocument>> value = ref.watch(
      dashboardRecentDocumentsProvider,
    );
    return _DashboardSection(
      title: 'Dokumenty',
      icon: Icons.description_outlined,
      action: TextButton(
        onPressed: () => context.push('/documents'),
        child: const Text('Zobacz wszystkie'),
      ),
      child: value.when(
        loading: () => const _SectionLoading(label: 'Ładowanie dokumentów…'),
        error: (_, _) => _SectionError(
          message: 'Nie udało się wczytać ostatnich dokumentów.',
          onRetry: () => ref.invalidate(dashboardRecentDocumentsProvider),
        ),
        data: (List<RepositoryDocument> items) {
          if (items.isEmpty) {
            return const _SectionEmpty('Brak dokumentów.');
          }
          return Column(
            children: items
                .map(
                  (RepositoryDocument document) => Padding(
                    key: ValueKey<String>('dashboard-document-${document.id}'),
                    padding: const EdgeInsets.symmetric(vertical: 6),
                    child: Row(
                      children: <Widget>[
                        DocumentImageThumbnail(
                          documentId: document.id,
                          contentType: document.contentType,
                          fileName: document.displayName,
                          onOpen: () =>
                              openDocumentMedia(context, ref, document),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: InkWell(
                            onTap: () {
                              if (isInternalPreviewImage(
                                document.contentType,
                                document.displayName,
                              )) {
                                openDocumentMedia(context, ref, document);
                              } else {
                                context.push(
                                  '/documents?document_id=${document.id}',
                                );
                              }
                            },
                            child: Padding(
                              padding: const EdgeInsets.symmetric(vertical: 8),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: <Widget>[
                                  Text(
                                    document.displayName,
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                    style: Theme.of(context)
                                        .textTheme
                                        .titleSmall
                                        ?.copyWith(fontWeight: FontWeight.w600),
                                  ),
                                  const SizedBox(height: 3),
                                  Text(
                                    '${document.linkedEntityName} · '
                                    '${formatPolishDateTime(document.createdAt)}',
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                        IconButton(
                          tooltip: 'Szczegóły dokumentu',
                          onPressed: () => context.push(
                            '/documents?document_id=${document.id}',
                          ),
                          icon: const Icon(Icons.chevron_right),
                        ),
                      ],
                    ),
                  ),
                )
                .toList(growable: false),
          );
        },
      ),
    );
  }
}

class _DashboardLastActivitySection extends ConsumerWidget {
  const _DashboardLastActivitySection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final value = ref.watch(dashboardRecentActivityProvider);
    return _DashboardSection(
      title: 'Ostatnia aktywność',
      icon: Icons.history,
      child: value.when(
        loading: () => const _SectionLoading(label: 'Ładowanie aktywności…'),
        error: (_, _) => _SectionError(
          message: 'Nie udało się wczytać ostatniej aktywności.',
          onRetry: () => ref.invalidate(dashboardRecentActivityProvider),
        ),
        data: (List<RecentActivityItem> items) {
          if (items.isEmpty) {
            return const _SectionEmpty('Brak ostatniej aktywności.');
          }
          return Column(
            children: items
                .map(
                  (RecentActivityItem item) => Semantics(
                    button: item.deepLink != null,
                    label:
                        '${item.summary}. ${item.actorDisplay}. ${formatPolishDateTime(item.timestamp)}',
                    child: ListTile(
                      key: ValueKey<String>(
                        'dashboard-activity-${item.stableKey}',
                      ),
                      contentPadding: EdgeInsets.zero,
                      leading: CircleAvatar(
                        child: Icon(
                          _activityIcon(item.entityType),
                          semanticLabel: _entityLabel(item.entityType),
                        ),
                      ),
                      title: Text(
                        item.summary,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      subtitle: Text(
                        '${item.actorDisplay} · ${formatPolishDateTime(item.timestamp)}${item.clientName == null ? '' : ' · ${item.clientName}'}',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      trailing: item.deepLink == null
                          ? null
                          : const Icon(Icons.chevron_right),
                      onTap: item.deepLink == null
                          ? null
                          : () => context.push(item.deepLink!),
                    ),
                  ),
                )
                .toList(growable: false),
          );
        },
      ),
    );
  }

  IconData _activityIcon(String type) => switch (type) {
    'client' ||
    'client_contact' ||
    'client_address' ||
    'client_workflow_status' => Icons.business_outlined,
    'client_candidate' || 'candidate_merge' => Icons.person_search_outlined,
    'work_item' ||
    'work_item_note' ||
    'work_item_document' => Icons.task_alt_outlined,
    'absence_request' => Icons.event_busy_outlined,
    'document' => Icons.description_outlined,
    'mail' => Icons.mail_outline,
    'user' => Icons.manage_accounts_outlined,
    'inspection' => Icons.fact_check_outlined,
    'project' => Icons.work_outline,
    _ => Icons.history,
  };

  String _entityLabel(String type) => switch (type) {
    'client' ||
    'client_contact' ||
    'client_address' ||
    'client_workflow_status' => 'Klient',
    'client_candidate' || 'candidate_merge' => 'Kandydat',
    'work_item' || 'work_item_note' || 'work_item_document' => 'Zadanie',
    'absence_request' => 'Absencja',
    'document' => 'Dokument',
    'mail' => 'Wiadomość',
    'user' => 'Użytkownik',
    'inspection' => 'Inspekcja',
    'project' => 'Projekt',
    _ => 'Aktywność',
  };
}

class _DashboardSection extends StatelessWidget {
  const _DashboardSection({
    required this.title,
    required this.icon,
    required this.child,
    this.action,
  });

  final String title;
  final IconData icon;
  final Widget child;
  final Widget? action;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(icon),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(
                    context,
                  ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
                ),
              ),
              ?action,
            ],
          ),
          const SizedBox(height: 10),
          child,
        ],
      ),
    ),
  );
}

class _SectionLoading extends StatelessWidget {
  const _SectionLoading({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 18),
    child: Row(
      children: <Widget>[
        const SizedBox.square(
          dimension: 22,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
        const SizedBox(width: 12),
        Expanded(child: Text(label)),
      ],
    ),
  );
}

class _SectionError extends StatelessWidget {
  const _SectionError({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 8),
    child: Row(
      children: <Widget>[
        Icon(
          Icons.warning_amber_outlined,
          color: Theme.of(context).colorScheme.error,
        ),
        const SizedBox(width: 10),
        Expanded(child: Text(message)),
        TextButton(onPressed: onRetry, child: const Text('Ponów')),
      ],
    ),
  );
}

class _SectionEmpty extends StatelessWidget {
  const _SectionEmpty(this.message);
  final String message;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 12),
    child: Text(message),
  );
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

    return _DashboardSection(
      title: 'Status systemu',
      icon: Icons.monitor_heart_outlined,
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
                      'Backend: NIEDOSTĘPNY',
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
                  _StatusValue(label: 'Aplikacja', value: backend.application),
                  _StatusValue(label: 'Wersja', value: backend.version),
                  _StatusValue(label: 'Środowisko', value: backend.environment),
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

    return 'Nie można potwierdzić stanu backendu.';
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
