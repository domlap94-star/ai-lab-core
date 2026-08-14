import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'client_form_dialog.dart';

import '../application/client_list_filter.dart';
import '../application/client_list_view_memory.dart';
import '../application/client_workflow_status.dart';
import 'client_workflow_widgets.dart';
import '../application/clients_controller.dart';
import '../application/clients_providers.dart';
import '../domain/client.dart';
import '../domain/client_page.dart';
import '../domain/industry.dart';

class ClientsPage extends ConsumerStatefulWidget {
  const ClientsPage({super.key});

  @override
  ConsumerState<ClientsPage> createState() => _ClientsPageState();
}

class _ClientsPageState extends ConsumerState<ClientsPage> {
  final TextEditingController _searchController = TextEditingController();
  final TextEditingController _locationController = TextEditingController();
  final FocusNode _searchFocusNode = FocusNode();

  ClientSortOrder _sortOrder = ClientSortOrder.newestFirst;
  ClientWorkflowState? _statusFilter;
  bool _filtersExpanded = false;
  ClientType? _clientTypeFilter;
  int? _industryIdFilter;

  ClientListViewMemory get _viewMemory => ClientListViewMemory.instance;

  @override
  void initState() {
    super.initState();

    _searchController.text = _viewMemory.searchQuery;
    _locationController.text = _viewMemory.locationQuery;
    _sortOrder = _viewMemory.sortOrder;
    _statusFilter = _viewMemory.workflowStatusFilter;
    _filtersExpanded = _viewMemory.filtersExpanded;
    _clientTypeFilter = _viewMemory.clientTypeFilter;
    _industryIdFilter = _viewMemory.industryIdFilter;
  }

  @override
  void dispose() {
    _searchController.dispose();
    _locationController.dispose();
    _searchFocusNode.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    _searchFocusNode.unfocus();

    _viewMemory.searchQuery = _searchController.text;

    await ref
        .read(clientsControllerProvider.notifier)
        .search(_searchController.text);
  }

  Future<void> _clearSearch() async {
    _searchController.clear();
    _searchFocusNode.unfocus();
    _viewMemory.clearSearch();

    await ref.read(clientsControllerProvider.notifier).clearSearch();
  }

  Future<void> _refresh() async {
    await ref.read(clientsControllerProvider.notifier).refresh();
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final AsyncValue<ClientPage> clientsValue = ref.watch(
      clientsControllerProvider,
    );
    final AsyncValue<List<Industry>> industriesValue = ref.watch(
      industriesProvider,
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Klienci'),
        actions: <Widget>[
          OutlinedButton.icon(
            onPressed: () {
              context.go('/client-candidates');
            },
            icon: const Icon(Icons.manage_accounts_outlined),
            label: const Text('Kandydaci'),
          ),

          const SizedBox(width: 12),

          FilledButton.icon(
            onPressed: () async {
              final Client? created = await showDialog<Client>(
                context: context,
                barrierDismissible: false,
                builder: (_) => const ClientFormDialog(),
              );

              if (!context.mounted || created == null) {
                return;
              }

              ScaffoldMessenger.of(context)
                ..hideCurrentSnackBar()
                ..showSnackBar(
                  SnackBar(
                    content: Text('Dodano klienta: ${created.displayName}'),
                  ),
                );
            },
            icon: const Icon(Icons.add),
            label: const Text('Dodaj klienta'),
          ),

          const SizedBox(width: 12),

          IconButton(
            tooltip: 'Odśwież listę klientów',
            onPressed: clientsValue.isLoading ? null : _refresh,
            icon: const Icon(Icons.refresh),
          ),

          const SizedBox(width: 8),
        ],
      ),
      body: Column(
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 16, 24, 12),
            child: _SearchBar(
              controller: _searchController,
              focusNode: _searchFocusNode,
              isLoading: clientsValue.isLoading,
              onSearch: _search,
              onClear: _clearSearch,
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 0, 24, 12),
            child: _ServerFilters(
              industries: industriesValue.value ?? const <Industry>[],
              clientType: _clientTypeFilter,
              industryId: _industryIdFilter,
              isLoading: clientsValue.isLoading,
              onClientTypeChanged: (ClientType? value) async {
                _viewMemory.clientTypeFilter = value;
                setState(() => _clientTypeFilter = value);
                await ref
                    .read(clientsControllerProvider.notifier)
                    .setFilters(
                      clientType: value,
                      industryId: _industryIdFilter,
                    );
              },
              onIndustryChanged: (int? value) async {
                _viewMemory.industryIdFilter = value;
                setState(() => _industryIdFilter = value);
                await ref
                    .read(clientsControllerProvider.notifier)
                    .setFilters(
                      clientType: _clientTypeFilter,
                      industryId: value,
                    );
              },
              onReset: () async {
                _viewMemory.clientTypeFilter = null;
                _viewMemory.industryIdFilter = null;
                setState(() {
                  _clientTypeFilter = null;
                  _industryIdFilter = null;
                });
                await ref.read(clientsControllerProvider.notifier).setFilters();
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 0, 24, 12),
            child: _ClientFilterPanel(
              expanded: _filtersExpanded,
              locationController: _locationController,
              sortOrder: _sortOrder,
              workflowStatusFilter: _statusFilter,
              onExpandedChanged: (bool value) {
                _viewMemory.filtersExpanded = value;

                setState(() {
                  _filtersExpanded = value;
                });
              },
              onLocationChanged: () {
                _viewMemory.locationQuery = _locationController.text;
                setState(() {});
              },
              onClearLocation: () {
                _locationController.clear();
                _viewMemory.clearLocation();
                setState(() {});
              },
              onSortChanged: (ClientSortOrder value) {
                _viewMemory.sortOrder = value;

                setState(() {
                  _sortOrder = value;
                });
              },
              onWorkflowStatusChanged: (ClientWorkflowState? value) {
                _viewMemory.workflowStatusFilter = value;

                setState(() {
                  _statusFilter = value;
                });
              },
              onReset: () {
                _locationController.clear();
                _viewMemory.clearLocation();
                _viewMemory.workflowStatusFilter = null;
                _viewMemory.sortOrder = ClientSortOrder.newestFirst;

                setState(() {
                  _statusFilter = null;
                  _sortOrder = ClientSortOrder.newestFirst;
                });
              },
            ),
          ),
          Expanded(
            child: clientsValue.when(
              loading: () {
                return const _ClientsLoadingView();
              },
              error: (Object error, StackTrace stackTrace) {
                return _ClientsErrorView(
                  message: _friendlyErrorMessage(error),
                  onRetry: _refresh,
                );
              },
              data: (ClientPage page) {
                final List<Client> clients = page.items;
                final List<Client> visibleClients = filterAndSortClients(
                  clients,
                  locationQuery: _locationController.text,
                  sortOrder: _sortOrder,
                  workflowStatusFilter: _statusFilter,
                );
                if (visibleClients.isEmpty) {
                  final bool hasSearchQuery = ref
                      .read(clientsControllerProvider.notifier)
                      .searchQuery
                      .isNotEmpty;

                  return _EmptyClientsView(
                    hasSearchQuery: hasSearchQuery,
                    onClearSearch: _clearSearch,
                    onRefresh: _refresh,
                  );
                }

                return RefreshIndicator(
                  onRefresh: _refresh,
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(24, 8, 24, 32),
                    children: <Widget>[
                      _ClientStatusSummary(
                        clients: clients,
                        selectedStatus: _statusFilter,
                        onSelected: (ClientWorkflowState? value) {
                          _viewMemory.workflowStatusFilter = value;

                          setState(() {
                            _statusFilter = value;
                          });
                        },
                      ),
                      const SizedBox(height: 10),
                      Row(
                        children: <Widget>[
                          Text(
                            'Wyniki: ${page.total} · '
                            'strona ${page.pageNumber} z ${page.pageCount} · '
                            '${clients.length} na tej stronie',
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      ...visibleClients.map<Widget>(
                        (Client client) => Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: _ClientCard(
                            client: client,
                            onTap: () {
                              context.go('/clients/${client.id}');
                            },
                            onStatusChanged: () {
                              setState(() {});
                            },
                          ),
                        ),
                      ),
                      const SizedBox(height: 8),
                      ClientPaginationControls(
                        page: page,
                        onPrevious: ref
                            .read(clientsControllerProvider.notifier)
                            .previousPage,
                        onNext: ref
                            .read(clientsControllerProvider.notifier)
                            .nextPage,
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  String _friendlyErrorMessage(Object error) {
    if (error is ClientsAuthenticationException) {
      return error.message;
    }

    if (error is DioException) {
      if (error.response?.statusCode == 401) {
        return 'Sesja użytkownika wygasła lub jest nieprawidłowa.';
      }

      if (error.response?.statusCode == 403) {
        return 'Nie masz uprawnień do wyświetlenia klientów.';
      }

      switch (error.type) {
        case DioExceptionType.connectionTimeout:
          return 'Przekroczono czas oczekiwania na połączenie.';
        case DioExceptionType.receiveTimeout:
          return 'Backend nie odpowiedział w wymaganym czasie.';
        case DioExceptionType.connectionError:
          return 'Nie można połączyć się z serwerem AI LAB.';
        case DioExceptionType.badResponse:
          return 'Serwer zwrócił błąd HTTP '
              '${error.response?.statusCode ?? 'bez kodu'}.';
        case DioExceptionType.cancel:
          return 'Pobieranie klientów zostało anulowane.';
        case DioExceptionType.sendTimeout:
          return 'Przekroczono czas wysyłania żądania.';
        case DioExceptionType.badCertificate:
          return 'Certyfikat serwera nie został zaakceptowany.';
        case DioExceptionType.transformTimeout:
          return 'Przekroczono czas przetwarzania odpowiedzi.';
        case DioExceptionType.unknown:
          return error.message ??
              'Wystąpił nieznany błąd podczas pobierania klientów.';
      }
    }

    if (error is FormatException) {
      return error.message;
    }

    return 'Nie udało się pobrać listy klientów.';
  }
}

class _ServerFilters extends StatelessWidget {
  const _ServerFilters({
    required this.industries,
    required this.clientType,
    required this.industryId,
    required this.isLoading,
    required this.onClientTypeChanged,
    required this.onIndustryChanged,
    required this.onReset,
  });

  final List<Industry> industries;
  final ClientType? clientType;
  final int? industryId;
  final bool isLoading;
  final ValueChanged<ClientType?> onClientTypeChanged;
  final ValueChanged<int?> onIndustryChanged;
  final VoidCallback onReset;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 12,
      runSpacing: 12,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: <Widget>[
        SizedBox(
          width: 220,
          child: DropdownButtonFormField<ClientType?>(
            initialValue: clientType,
            decoration: const InputDecoration(
              labelText: 'Typ klienta',
              border: OutlineInputBorder(),
            ),
            items: <DropdownMenuItem<ClientType?>>[
              const DropdownMenuItem<ClientType?>(
                value: null,
                child: Text('Wszystkie typy'),
              ),
              ...ClientType.values.map(
                (ClientType type) => DropdownMenuItem<ClientType?>(
                  value: type,
                  child: Text(type.displayName),
                ),
              ),
            ],
            onChanged: isLoading ? null : onClientTypeChanged,
          ),
        ),
        SizedBox(
          width: 280,
          child: DropdownButtonFormField<int?>(
            initialValue: industryId,
            decoration: const InputDecoration(
              labelText: 'Branża',
              border: OutlineInputBorder(),
            ),
            items: <DropdownMenuItem<int?>>[
              const DropdownMenuItem<int?>(
                value: null,
                child: Text('Wszystkie branże'),
              ),
              ...industries.map(
                (Industry industry) => DropdownMenuItem<int?>(
                  value: industry.id,
                  child: Text(industry.name),
                ),
              ),
            ],
            onChanged: isLoading ? null : onIndustryChanged,
          ),
        ),
        TextButton.icon(
          onPressed: isLoading || (clientType == null && industryId == null)
              ? null
              : onReset,
          icon: const Icon(Icons.filter_alt_off_outlined),
          label: const Text('Wyczyść filtry bazy'),
        ),
      ],
    );
  }
}

class ClientPaginationControls extends StatelessWidget {
  const ClientPaginationControls({
    required this.page,
    required this.onPrevious,
    required this.onNext,
    super.key,
  });

  final ClientPage page;
  final Future<void> Function() onPrevious;
  final Future<void> Function() onNext;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: <Widget>[
        OutlinedButton.icon(
          onPressed: page.hasPreviousPage ? onPrevious : null,
          icon: const Icon(Icons.chevron_left),
          label: const Text('Poprzednia'),
        ),
        const SizedBox(width: 16),
        Text('${page.pageNumber} / ${page.pageCount}'),
        const SizedBox(width: 16),
        FilledButton.icon(
          onPressed: page.hasNextPage ? onNext : null,
          icon: const Icon(Icons.chevron_right),
          label: const Text('Następna'),
        ),
      ],
    );
  }
}

class _SearchBar extends StatelessWidget {
  const _SearchBar({
    required this.controller,
    required this.focusNode,
    required this.isLoading,
    required this.onSearch,
    required this.onClear,
  });

  final TextEditingController controller;
  final FocusNode focusNode;
  final bool isLoading;
  final Future<void> Function() onSearch;
  final Future<void> Function() onClear;

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 760),
      child: TextField(
        controller: controller,
        focusNode: focusNode,
        enabled: !isLoading,
        textInputAction: TextInputAction.search,
        onSubmitted: (_) {
          onSearch();
        },
        decoration: InputDecoration(
          labelText: 'Szukaj klientów',
          hintText: 'Nazwa, NIP, e-mail, telefon lub miejscowość',
          prefixIcon: const Icon(Icons.search),
          suffixIcon: Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              IconButton(
                tooltip: 'Wyczyść wyszukiwanie',
                onPressed: isLoading ? null : onClear,
                icon: const Icon(Icons.clear),
              ),
              IconButton(
                tooltip: 'Szukaj',
                onPressed: isLoading ? null : onSearch,
                icon: const Icon(Icons.arrow_forward),
              ),
            ],
          ),
          border: const OutlineInputBorder(),
        ),
      ),
    );
  }
}

class _ClientFilterPanel extends StatelessWidget {
  const _ClientFilterPanel({
    required this.expanded,
    required this.locationController,
    required this.sortOrder,
    required this.workflowStatusFilter,
    required this.onExpandedChanged,
    required this.onLocationChanged,
    required this.onClearLocation,
    required this.onSortChanged,
    required this.onWorkflowStatusChanged,
    required this.onReset,
  });

  final bool expanded;
  final TextEditingController locationController;
  final ClientSortOrder sortOrder;
  final ClientWorkflowState? workflowStatusFilter;
  final ValueChanged<bool> onExpandedChanged;
  final VoidCallback onLocationChanged;
  final VoidCallback onClearLocation;
  final ValueChanged<ClientSortOrder> onSortChanged;
  final ValueChanged<ClientWorkflowState?> onWorkflowStatusChanged;
  final VoidCallback onReset;

  int get activeFilterCount {
    int count = 0;

    if (locationController.text.trim().isNotEmpty) {
      count++;
    }

    if (workflowStatusFilter != null) {
      count++;
    }

    if (sortOrder != ClientSortOrder.newestFirst) {
      count++;
    }

    return count;
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final int activeCount = activeFilterCount;

    return Card(
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: <Widget>[
          InkWell(
            onTap: () {
              onExpandedChanged(!expanded);
            },
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Row(
                children: <Widget>[
                  const Icon(Icons.tune),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Filtry i sortowanie',
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  if (activeCount > 0) ...<Widget>[
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 9,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.primaryContainer,
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        '$activeCount aktywne',
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: theme.colorScheme.onPrimaryContainer,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                  ],
                  AnimatedRotation(
                    turns: expanded ? 0.5 : 0,
                    duration: const Duration(milliseconds: 180),
                    child: const Icon(Icons.keyboard_arrow_down),
                  ),
                ],
              ),
            ),
          ),
          AnimatedCrossFade(
            duration: const Duration(milliseconds: 180),
            crossFadeState: expanded
                ? CrossFadeState.showSecond
                : CrossFadeState.showFirst,
            firstChild: const SizedBox.shrink(),
            secondChild: Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              child: LayoutBuilder(
                builder: (BuildContext context, BoxConstraints constraints) {
                  final bool compact = constraints.maxWidth < 900;

                  final Widget locationField = TextField(
                    controller: locationController,
                    onChanged: (_) {
                      onLocationChanged();
                    },
                    decoration: InputDecoration(
                      labelText: 'Lokalizacja',
                      hintText: 'Miasto, ulica, kod lub fragment adresu',
                      prefixIcon: const Icon(Icons.location_on_outlined),
                      suffixIcon: locationController.text.isEmpty
                          ? null
                          : IconButton(
                              tooltip: 'Wyczyść filtr lokalizacji',
                              onPressed: onClearLocation,
                              icon: const Icon(Icons.clear),
                            ),
                      border: const OutlineInputBorder(),
                    ),
                  );

                  final Widget sortField =
                      DropdownButtonFormField<ClientSortOrder>(
                        initialValue: sortOrder,
                        isExpanded: true,
                        decoration: const InputDecoration(
                          labelText: 'Sortowanie',
                          prefixIcon: Icon(Icons.sort),
                          border: OutlineInputBorder(),
                        ),
                        items: ClientSortOrder.values
                            .map(
                              (ClientSortOrder value) =>
                                  DropdownMenuItem<ClientSortOrder>(
                                    value: value,
                                    child: Text(value.label),
                                  ),
                            )
                            .toList(),
                        onChanged: (ClientSortOrder? value) {
                          if (value != null) {
                            onSortChanged(value);
                          }
                        },
                      );

                  final Widget statusField = ClientWorkflowStatusFilterField(
                    value: workflowStatusFilter,
                    onChanged: onWorkflowStatusChanged,
                  );

                  final Widget resetButton = OutlinedButton.icon(
                    onPressed: activeCount == 0 ? null : onReset,
                    icon: const Icon(Icons.restart_alt),
                    label: const Text('Wyczyść filtry'),
                  );

                  if (compact) {
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: <Widget>[
                        locationField,
                        const SizedBox(height: 12),
                        sortField,
                        const SizedBox(height: 12),
                        statusField,
                        const SizedBox(height: 12),
                        Align(
                          alignment: Alignment.centerRight,
                          child: resetButton,
                        ),
                      ],
                    );
                  }

                  return Column(
                    children: <Widget>[
                      Row(
                        children: <Widget>[
                          Expanded(flex: 2, child: locationField),
                          const SizedBox(width: 12),
                          Expanded(child: sortField),
                          const SizedBox(width: 12),
                          Expanded(child: statusField),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Align(
                        alignment: Alignment.centerRight,
                        child: resetButton,
                      ),
                    ],
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ClientStatusSummary extends StatelessWidget {
  const _ClientStatusSummary({
    required this.clients,
    required this.selectedStatus,
    required this.onSelected,
  });

  final List<Client> clients;
  final ClientWorkflowState? selectedStatus;
  final ValueChanged<ClientWorkflowState?> onSelected;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final ClientWorkflowMemory workflowMemory = ClientWorkflowMemory.instance;

    final Map<ClientWorkflowState, int> counts = <ClientWorkflowState, int>{
      for (final ClientWorkflowState status in ClientWorkflowState.values)
        status: 0,
    };

    for (final Client client in clients) {
      final ClientWorkflowState status = workflowMemory.statusFor(client).state;

      counts[status] = (counts[status] ?? 0) + 1;
    }

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: <Widget>[
          _ClientStatusChip(
            label: 'Ta strona',
            count: clients.length,
            selected: selectedStatus == null,
            onTap: () {
              onSelected(null);
            },
          ),
          const SizedBox(width: 8),
          ...ClientWorkflowState.values.expand((
            ClientWorkflowState status,
          ) sync* {
            yield _ClientStatusChip(
              label: status.label,
              count: counts[status] ?? 0,
              color: status.color(theme),
              selected: selectedStatus == status,
              onTap: () {
                onSelected(selectedStatus == status ? null : status);
              },
            );

            yield const SizedBox(width: 8);
          }),
        ],
      ),
    );
  }
}

class _ClientStatusChip extends StatelessWidget {
  const _ClientStatusChip({
    required this.label,
    required this.count,
    required this.selected,
    required this.onTap,
    this.color,
  });

  final String label;
  final int count;
  final bool selected;
  final VoidCallback onTap;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return ActionChip(
      onPressed: onTap,
      avatar: color == null
          ? null
          : Container(
              width: 11,
              height: 11,
              decoration: BoxDecoration(
                color: color,
                shape: BoxShape.circle,
                border: Border.all(color: theme.colorScheme.outlineVariant),
              ),
            ),
      label: Text('$label ($count)'),
      side: selected
          ? BorderSide(color: theme.colorScheme.primary, width: 1.5)
          : null,
      backgroundColor: selected ? theme.colorScheme.primaryContainer : null,
    );
  }
}

class _ClientsLoadingView extends StatelessWidget {
  const _ClientsLoadingView();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          CircularProgressIndicator(),
          SizedBox(height: 16),
          Text('Pobieranie klientów...'),
        ],
      ),
    );
  }
}

class _ClientsErrorView extends StatelessWidget {
  const _ClientsErrorView({required this.message, required this.onRetry});

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Icon(
                Icons.cloud_off_outlined,
                size: 64,
                color: theme.colorScheme.error,
              ),
              const SizedBox(height: 20),
              Text(
                'Nie udało się pobrać klientów',
                textAlign: TextAlign.center,
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                message,
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyLarge?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 24),
              FilledButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: const Text('Spróbuj ponownie'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _EmptyClientsView extends StatelessWidget {
  const _EmptyClientsView({
    required this.hasSearchQuery,
    required this.onClearSearch,
    required this.onRefresh,
  });

  final bool hasSearchQuery;
  final Future<void> Function() onClearSearch;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Icon(
                hasSearchQuery ? Icons.search_off : Icons.people_outline,
                size: 72,
                color: theme.colorScheme.onSurfaceVariant,
              ),
              const SizedBox(height: 20),
              Text(
                hasSearchQuery ? 'Nie znaleziono klientów' : 'Brak klientów',
                textAlign: TextAlign.center,
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                hasSearchQuery
                    ? 'Żaden klient nie odpowiada podanym kryteriom.'
                    : 'W bazie nie ma jeszcze żadnych aktywnych klientów.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyLarge?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 24),
              if (hasSearchQuery)
                OutlinedButton.icon(
                  onPressed: onClearSearch,
                  icon: const Icon(Icons.clear),
                  label: const Text('Wyczyść wyszukiwanie'),
                )
              else
                OutlinedButton.icon(
                  onPressed: onRefresh,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Odśwież'),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ClientCard extends StatelessWidget {
  const _ClientCard({
    required this.client,
    required this.onTap,
    required this.onStatusChanged,
  });

  final Client client;
  final VoidCallback onTap;
  final VoidCallback onStatusChanged;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              ClientWorkflowAvatar(
                client: client,
                onStatusChanged: onStatusChanged,
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(
                          child: Text(
                            client.displayName,
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        _ClientTypeBadge(label: client.clientType.displayName),
                      ],
                    ),
                    if (client.legalName?.isNotEmpty == true &&
                        client.legalName != client.name) ...<Widget>[
                      const SizedBox(height: 4),
                      Text(
                        client.legalName!,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 20,
                      runSpacing: 10,
                      children: <Widget>[
                        if (client.taxId?.isNotEmpty == true)
                          _ClientInformation(
                            icon: Icons.badge_outlined,
                            value: 'NIP: ${client.taxId}',
                          ),
                        if (client.primaryEmail?.isNotEmpty == true)
                          _ClientInformation(
                            icon: Icons.email_outlined,
                            value: client.primaryEmail!,
                          ),
                        if (client.primaryPhone?.isNotEmpty == true)
                          _ClientInformation(
                            icon: Icons.phone_outlined,
                            value: client.primaryPhone!,
                          ),
                        if (client.city?.isNotEmpty == true)
                          _ClientInformation(
                            icon: Icons.location_on_outlined,
                            value: client.city!,
                          ),
                        if (client.industry?.name.isNotEmpty == true)
                          _ClientInformation(
                            icon: Icons.business_center_outlined,
                            value: client.industry!.name,
                          ),
                        _ClientInformation(
                          icon: Icons.calendar_today_outlined,
                          value:
                              'Dodano: ${_formatClientDate(client.createdAt)}',
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              const Icon(Icons.chevron_right),
            ],
          ),
        ),
      ),
    );
  }

  String _formatClientDate(DateTime value) {
    final DateTime local = value.toLocal();
    String twoDigits(int number) => number.toString().padLeft(2, '0');

    return '${twoDigits(local.day)}.'
        '${twoDigits(local.month)}.'
        '${local.year}';
  }
}

class _ClientTypeBadge extends StatelessWidget {
  const _ClientTypeBadge({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: theme.colorScheme.secondaryContainer,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: theme.textTheme.labelMedium?.copyWith(
          color: theme.colorScheme.onSecondaryContainer,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _ClientInformation extends StatelessWidget {
  const _ClientInformation({required this.icon, required this.value});

  final IconData icon;
  final String value;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Icon(icon, size: 18, color: theme.colorScheme.onSurfaceVariant),
        const SizedBox(width: 6),
        Flexible(
          child: Text(
            value,
            overflow: TextOverflow.ellipsis,
            style: theme.textTheme.bodyMedium,
          ),
        ),
      ],
    );
  }
}
