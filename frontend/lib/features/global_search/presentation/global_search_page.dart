import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/network/friendly_api_error.dart';
import '../../../core/formatters/polish_date_time.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/domain/auth_session.dart';
import '../application/global_search_providers.dart';
import '../domain/global_search.dart';

class GlobalSearchPage extends ConsumerStatefulWidget {
  const GlobalSearchPage({this.initialQuery = '', super.key});

  final String initialQuery;

  @override
  ConsumerState<GlobalSearchPage> createState() => _GlobalSearchPageState();
}

class _GlobalSearchPageState extends ConsumerState<GlobalSearchPage> {
  static const Duration _debounce = Duration(milliseconds: 320);
  static const int _pageSize = 25;

  late final TextEditingController _controller;
  Timer? _timer;
  CancelToken? _cancelToken;
  GlobalSearchType? _type;
  AsyncValue<GlobalSearchPageData>? _state;
  List<GlobalSearchResult> _items = const [];
  bool _loadingMore = false;
  int _requestNumber = 0;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.initialQuery.trim());
    if (_controller.text.length >= 2) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _search(reset: true);
      });
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _cancelToken?.cancel('search disposed');
    _controller.dispose();
    super.dispose();
  }

  void _scheduleSearch() {
    _timer?.cancel();
    _cancelToken?.cancel('superseded search');
    final String query = _controller.text.trim();
    if (query.length < 2) {
      setState(() {
        _state = null;
        _items = const [];
      });
      return;
    }
    _timer = Timer(_debounce, () => _search(reset: true));
  }

  Future<void> _search({required bool reset}) async {
    final String query = _controller.text.trim();
    if (query.length < 2) return;
    final AuthSession? session = (await ref.read(
      authControllerProvider.future,
    )).session;
    if (session == null) return;
    final int requestNumber = ++_requestNumber;
    _cancelToken?.cancel('superseded search');
    final CancelToken cancelToken = CancelToken();
    _cancelToken = cancelToken;
    setState(() {
      if (reset) {
        _state = const AsyncLoading<GlobalSearchPageData>();
        _items = const [];
      } else {
        _loadingMore = true;
      }
    });
    try {
      final page = await ref
          .read(globalSearchGatewayProvider)
          .search(
            session: session,
            query: query,
            type: _type,
            skip: reset ? 0 : _items.length,
            limit: _pageSize,
            cancelToken: cancelToken,
          );
      if (!mounted || requestNumber != _requestNumber) return;
      setState(() {
        _items = reset
            ? page.items
            : <GlobalSearchResult>[..._items, ...page.items];
        _state = AsyncData<GlobalSearchPageData>(
          GlobalSearchPageData(
            items: _items,
            skip: 0,
            limit: page.limit,
            hasMore: page.hasMore,
            semanticStatus: page.semanticStatus,
          ),
        );
        _loadingMore = false;
      });
    } on DioException catch (error, stackTrace) {
      if (CancelToken.isCancel(error)) return;
      _setError(requestNumber, error, stackTrace);
    } catch (error, stackTrace) {
      _setError(requestNumber, error, stackTrace);
    }
  }

  void _setError(int requestNumber, Object error, StackTrace stackTrace) {
    if (!mounted || requestNumber != _requestNumber) return;
    setState(() {
      _state = AsyncError<GlobalSearchPageData>(error, stackTrace);
      _loadingMore = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Global Search')),
      body: SafeArea(
        child: Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 920),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: <Widget>[
                  TextField(
                    key: const Key('global-search-field'),
                    controller: _controller,
                    autofocus: true,
                    textInputAction: TextInputAction.search,
                    onChanged: (_) {
                      setState(() {});
                      _scheduleSearch();
                    },
                    onSubmitted: (_) => _search(reset: true),
                    decoration: InputDecoration(
                      labelText: 'Szukaj w NEXT Stabil',
                      hintText: 'Klient, telefon, dokument, e-mail…',
                      prefixIcon: const Icon(Icons.search),
                      suffixIcon: _controller.text.isEmpty
                          ? null
                          : IconButton(
                              key: const Key('global-search-clear'),
                              tooltip: 'Wyczyść',
                              onPressed: () {
                                _controller.clear();
                                _scheduleSearch();
                              },
                              icon: const Icon(Icons.clear),
                            ),
                      border: const OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: <Widget>[
                        ChoiceChip(
                          key: const Key('global-search-filter-all'),
                          label: const Text('Wszystko'),
                          selected: _type == null,
                          onSelected: (_) => _selectType(null),
                        ),
                        const SizedBox(width: 8),
                        for (final type in GlobalSearchType.values) ...<Widget>[
                          ChoiceChip(
                            key: Key('global-search-filter-${type.name}'),
                            label: Text(_filterLabel(type)),
                            selected: _type == type,
                            onSelected: (_) => _selectType(type),
                          ),
                          const SizedBox(width: 8),
                        ],
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  Expanded(child: _body()),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  void _selectType(GlobalSearchType? value) {
    if (_type == value) return;
    setState(() => _type = value);
    _scheduleSearch();
  }

  Widget _body() {
    if (_controller.text.trim().length < 2) {
      return const _SearchMessage(
        icon: Icons.manage_search,
        message: 'Wpisz co najmniej 2 znaki.',
      );
    }
    final state = _state;
    if (state == null || state.isLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.hasError) {
      return _SearchError(
        message: friendlyApiError(
          state.error!,
          fallback: 'Nie udało się wyszukać danych.',
        ),
        onRetry: () => _search(reset: true),
      );
    }
    final page = state.value!;
    if (_items.isEmpty) {
      return const _SearchMessage(
        icon: Icons.search_off,
        message: 'Brak wyników.',
      );
    }
    return Column(
      children: <Widget>[
        if (page.semanticStatus == 'unavailable')
          const MaterialBanner(
            content: Text(
              'Wyniki semantyczne są chwilowo niedostępne. Pokazano dopasowania tekstowe.',
            ),
            actions: <Widget>[SizedBox.shrink()],
          ),
        Expanded(
          child: ListView.separated(
            key: const Key('global-search-results'),
            keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
            itemCount: _items.length + (page.hasMore ? 1 : 0),
            separatorBuilder: (_, _) => const Divider(height: 1),
            itemBuilder: (BuildContext context, int index) {
              if (index == _items.length) {
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Center(
                    child: _loadingMore
                        ? const CircularProgressIndicator()
                        : TextButton.icon(
                            key: const Key('global-search-load-more'),
                            onPressed: () => _search(reset: false),
                            icon: const Icon(Icons.expand_more),
                            label: const Text('Pokaż więcej'),
                          ),
                  ),
                );
              }
              return _SearchResultTile(
                result: _items[index],
                onTap: () {
                  final Uri target = Uri.parse(_items[index].route);
                  context.go(
                    target
                        .replace(
                          queryParameters: <String, String>{
                            ...target.queryParameters,
                            'return_to': '/search',
                          },
                        )
                        .toString(),
                  );
                },
              );
            },
          ),
        ),
      ],
    );
  }

  static String _filterLabel(GlobalSearchType type) => switch (type) {
    GlobalSearchType.client => 'Klienci',
    GlobalSearchType.project => 'Realizacje',
    GlobalSearchType.inspection => 'Wizje',
    GlobalSearchType.document => 'Dokumenty',
    GlobalSearchType.email => 'E-maile',
    GlobalSearchType.candidate => 'Kandydaci',
  };
}

class _SearchResultTile extends StatelessWidget {
  const _SearchResultTile({required this.result, required this.onTap});
  final GlobalSearchResult result;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      key: ValueKey<String>('global-search-${result.type.name}-${result.id}'),
      contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      leading: CircleAvatar(child: Icon(_icon(result.type), size: 20)),
      title: Wrap(
        spacing: 8,
        runSpacing: 4,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: <Widget>[
          Chip(
            visualDensity: VisualDensity.compact,
            label: Text(result.type.label),
          ),
          if (result.type == GlobalSearchType.client &&
              result.clientWorkflowStatusLabel?.isNotEmpty == true)
            Chip(
              visualDensity: VisualDensity.compact,
              label: Text(result.clientWorkflowStatusLabel!),
            ),
          Text(result.title, maxLines: 2, overflow: TextOverflow.ellipsis),
        ],
      ),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          if (result.subtitle?.isNotEmpty == true)
            Text(
              result.subtitle!,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          if (result.snippet?.isNotEmpty == true)
            Text(result.snippet!, maxLines: 3, overflow: TextOverflow.ellipsis),
          if (result.occurredAt != null)
            Text(
              formatPolishDateTime(result.occurredAt!),
              style: Theme.of(context).textTheme.bodySmall,
            ),
          Text(
            'Dopasowanie: ${result.matchReasons.map(_reasonLabel).join(', ')}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
      trailing: const Icon(Icons.chevron_right),
      onTap: onTap,
    );
  }

  static IconData _icon(GlobalSearchType type) => switch (type) {
    GlobalSearchType.client => Icons.person_outline,
    GlobalSearchType.project => Icons.construction_outlined,
    GlobalSearchType.inspection => Icons.location_searching_outlined,
    GlobalSearchType.document => Icons.description_outlined,
    GlobalSearchType.email => Icons.email_outlined,
    GlobalSearchType.candidate => Icons.person_search_outlined,
  };

  static String _reasonLabel(String value) => switch (value) {
    'name' => 'nazwa',
    'email' => 'e-mail',
    'phone' => 'telefon',
    'address' => 'adres',
    'nip' => 'NIP',
    'filename' => 'nazwa pliku',
    'document_text' => 'treść dokumentu',
    'email_subject' => 'temat e-maila',
    'email_body' => 'treść e-maila',
    'project' => 'realizacja',
    'inspection' => 'wizja',
    'semantic' => 'znaczenie treści',
    'notes' => 'notatki',
    'status' => 'status',
    'source' => 'źródło',
    _ => 'tekst',
  };
}

class _SearchMessage extends StatelessWidget {
  const _SearchMessage({required this.icon, required this.message});
  final IconData icon;
  final String message;
  @override
  Widget build(BuildContext context) => Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Icon(icon, size: 48, color: Theme.of(context).colorScheme.outline),
        const SizedBox(height: 12),
        Text(message),
      ],
    ),
  );
}

class _SearchError extends StatelessWidget {
  const _SearchError({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) => Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Text(message, textAlign: TextAlign.center),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          key: const Key('global-search-retry'),
          onPressed: onRetry,
          icon: const Icon(Icons.refresh),
          label: const Text('Spróbuj ponownie'),
        ),
      ],
    ),
  );
}
