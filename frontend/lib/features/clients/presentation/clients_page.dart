import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'client_form_dialog.dart';

import '../application/clients_controller.dart';
import '../application/clients_providers.dart';
import '../domain/client.dart';

class ClientsPage extends ConsumerStatefulWidget {
  const ClientsPage({super.key});

  @override
  ConsumerState<ClientsPage> createState() => _ClientsPageState();
}

class _ClientsPageState extends ConsumerState<ClientsPage> {
  final TextEditingController _searchController = TextEditingController();
  final FocusNode _searchFocusNode = FocusNode();

  @override
  void dispose() {
    _searchController.dispose();
    _searchFocusNode.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    _searchFocusNode.unfocus();

    await ref
        .read(clientsControllerProvider.notifier)
        .search(_searchController.text);
  }

  Future<void> _clearSearch() async {
    _searchController.clear();
    _searchFocusNode.unfocus();

    await ref.read(clientsControllerProvider.notifier).clearSearch();
  }

  Future<void> _refresh() async {
    await ref.read(clientsControllerProvider.notifier).refresh();
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final AsyncValue<List<Client>> clientsValue = ref.watch(
      clientsControllerProvider,
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Klienci'),
        actions: <Widget>[
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
              data: (List<Client> clients) {
                if (clients.isEmpty) {
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
                      Row(
                        children: <Widget>[
                          Text(
                            'Liczba klientów: ${clients.length}',
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      ...clients.map<Widget>(
                        (Client client) => Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: _ClientCard(
                            client: client,
                            onTap: () {
                              context.go('/clients/${client.id}');
                            },
                          ),
                        ),
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
  const _ClientCard({required this.client, required this.onTap});

  final Client client;
  final VoidCallback onTap;

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
              CircleAvatar(
                radius: 24,
                backgroundColor: theme.colorScheme.primaryContainer,
                foregroundColor: theme.colorScheme.onPrimaryContainer,
                child: Icon(_clientTypeIcon(client.clientType)),
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

  IconData _clientTypeIcon(ClientType type) {
    return switch (type) {
      ClientType.company => Icons.business_outlined,
      ClientType.person => Icons.person_outline,
      ClientType.institution => Icons.account_balance_outlined,
      ClientType.other => Icons.category_outlined,
    };
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
