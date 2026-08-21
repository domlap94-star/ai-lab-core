import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/widgets/app_shell.dart';
import '../../../core/formatters/polish_date_time.dart';
import '../application/clients_providers.dart';
import '../application/clients_controller.dart';
import '../application/client_workflow_status.dart';
import '../../auth/application/auth_controller.dart';
import '../../timeline/application/timeline_providers.dart';
import '../../timeline/domain/timeline.dart';
import '../domain/client.dart';
import 'client_workspace_panels.dart';
import 'client_edit_dialog.dart';
import '../../tasks/presentation/client_work_items_panel.dart';
import 'client_realizations_panel.dart';

final phoneUriLauncherProvider = Provider<Future<bool> Function(Uri)>((
  Ref ref,
) {
  return (Uri uri) => launchUrl(uri);
});

class ClientDetailsPage extends ConsumerWidget {
  const ClientDetailsPage({
    required this.clientId,
    this.emailSourceId,
    super.key,
  });

  final int clientId;
  final int? emailSourceId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<Client> clientValue = ref.watch(
      clientDetailsProvider(clientId),
    );

    final bool centrallyHandled = AppShell.centrallyHandlesBack(context);
    return PopScope<Object?>(
      canPop: centrallyHandled || context.canPop(),
      onPopInvokedWithResult: (bool didPop, Object? result) {
        if (!didPop && !centrallyHandled) {
          context.go('/clients');
        }
      },
      child: Scaffold(
        appBar: AppBar(
          leading: IconButton(
            tooltip: 'Wróć do klientów',
            onPressed: () => _goBack(context),
            icon: const Icon(Icons.arrow_back),
          ),
          title: const Text('Szczegóły klienta'),
          actions: <Widget>[
            IconButton(
              tooltip: 'Odśwież dane klienta',
              onPressed: clientValue.isLoading
                  ? null
                  : () {
                      ref.invalidate(clientDetailsProvider(clientId));
                    },
              icon: const Icon(Icons.refresh),
            ),
            const SizedBox(width: 8),
          ],
        ),
        body: clientValue.when(
          loading: () => const _LoadingView(),
          error: (Object error, StackTrace stackTrace) {
            return _ErrorView(
              message: _friendlyErrorMessage(error),
              onRetry: () {
                ref.invalidate(clientDetailsProvider(clientId));
              },
            );
          },
          data: (Client client) {
            return _ClientDetails(
              client: client,
              emailSourceId: emailSourceId,
              onEdit: () => _editClient(context, ref, client),
              onEditNotes: () => _editNotes(context, ref, client),
              onDelete: () => _deleteClient(context, ref, client),
            );
          },
        ),
      ),
    );
  }

  Future<void> _editClient(
    BuildContext context,
    WidgetRef ref,
    Client client,
  ) async {
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => ClientEditDialog(client: client),
    );
    if (data == null || !context.mounted) return;
    await _update(context, ref, client.id, data, 'Dane klienta zapisane.');
  }

  Future<void> _editNotes(
    BuildContext context,
    WidgetRef ref,
    Client client,
  ) async {
    final controller = TextEditingController(text: client.notes);
    final value = await showDialog<String?>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Edytuj notatki'),
        content: TextField(
          controller: controller,
          minLines: 6,
          maxLines: 14,
          decoration: const InputDecoration(border: OutlineInputBorder()),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Anuluj'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, controller.text),
            child: const Text('Zapisz'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (value == null || !context.mounted) return;
    await _update(context, ref, client.id, <String, dynamic>{
      'notes': value.trim().isEmpty ? null : value,
    }, 'Notatki zapisane.');
  }

  Future<void> _update(
    BuildContext context,
    WidgetRef ref,
    int id,
    Map<String, dynamic> data,
    String message,
  ) async {
    try {
      final session = ref.read(authControllerProvider).value?.session;
      if (session == null) {
        throw const ClientsAuthenticationException(
          'Brak aktywnej sesji użytkownika.',
        );
      }
      await ref
          .read(clientsRepositoryProvider)
          .updateClient(session: session, clientId: id, data: data);
      ref.invalidate(clientDetailsProvider(id));
      ref.invalidate(clientsControllerProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(message)));
      }
    } catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(_friendlyErrorMessage(error))));
      }
    }
  }

  Future<void> _deleteClient(
    BuildContext context,
    WidgetRef ref,
    Client client,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Przenieść klienta do kosza?'),
        content: const Text(
          'Element będzie można przywrócić przez 7 dni.\n'
          'Po tym czasie zostanie automatycznie usunięty na stałe.',
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Anuluj'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Przenieś do kosza'),
          ),
        ],
      ),
    );
    if (confirmed != true || !context.mounted) return;
    final session = ref.read(authControllerProvider).value?.session;
    if (session == null) return;
    await ref
        .read(clientsRepositoryProvider)
        .deleteClient(session: session, clientId: client.id);
    ref.invalidate(clientsControllerProvider);
    if (context.mounted) context.go('/clients');
  }

  void _goBack(BuildContext context) {
    if (context.canPop()) {
      context.pop();
    } else {
      context.go('/clients');
    }
  }

  String _friendlyErrorMessage(Object error) {
    if (error is ClientsAuthenticationException) {
      return error.message;
    }

    if (error is DioException) {
      final int? statusCode = error.response?.statusCode;

      if (statusCode == 401) {
        return 'Sesja użytkownika wygasła lub jest nieprawidłowa.';
      }

      if (statusCode == 403) {
        return 'Nie masz uprawnień do wyświetlenia tego klienta.';
      }

      if (statusCode == 404) {
        return 'Klient nie istnieje lub został usunięty.';
      }

      switch (error.type) {
        case DioExceptionType.connectionTimeout:
          return 'Przekroczono czas oczekiwania na połączenie.';
        case DioExceptionType.receiveTimeout:
          return 'Backend nie odpowiedział w wymaganym czasie.';
        case DioExceptionType.connectionError:
          return 'Nie można połączyć się z serwerem NEXT Stabil.';
        case DioExceptionType.badResponse:
          return 'Serwer zwrócił błąd HTTP '
              '${error.response?.statusCode ?? 'bez kodu'}.';
        case DioExceptionType.cancel:
          return 'Pobieranie klienta zostało anulowane.';
        case DioExceptionType.sendTimeout:
          return 'Przekroczono czas wysyłania żądania.';
        case DioExceptionType.badCertificate:
          return 'Certyfikat serwera nie został zaakceptowany.';
        case DioExceptionType.transformTimeout:
          return 'Przekroczono czas przetwarzania odpowiedzi.';
        case DioExceptionType.unknown:
          return error.message ??
              'Wystąpił nieznany błąd podczas pobierania klienta.';
      }
    }

    if (error is FormatException) {
      return error.message;
    }

    return 'Nie udało się pobrać danych klienta.';
  }
}

class _ClientDetails extends ConsumerStatefulWidget {
  const _ClientDetails({
    required this.client,
    required this.onEdit,
    required this.onEditNotes,
    required this.onDelete,
    this.emailSourceId,
  });

  final Client client;
  final VoidCallback onEdit;
  final VoidCallback onEditNotes;
  final VoidCallback onDelete;
  final int? emailSourceId;

  @override
  ConsumerState<_ClientDetails> createState() => _ClientDetailsState();
}

class _ClientDetailsState extends ConsumerState<_ClientDetails> {
  bool _callPending = false;
  Client get client => widget.client;
  VoidCallback get onEdit => widget.onEdit;
  VoidCallback get onEditNotes => widget.onEditNotes;
  VoidCallback get onDelete => widget.onDelete;
  int? get emailSourceId => widget.emailSourceId;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final String role =
        ref.watch(authControllerProvider).value?.user?.role ?? '';
    final bool isAdmin =
        role.trim().toLowerCase() == 'administrator' ||
        role.trim().toLowerCase() == 'admin';

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 20, 24, 40),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1100),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Wrap(
                key: const Key('client-details-actions'),
                spacing: 8,
                runSpacing: 8,
                children: <Widget>[
                  OutlinedButton.icon(
                    onPressed: onEdit,
                    icon: const Icon(Icons.edit_outlined),
                    label: const Text('Edytuj'),
                  ),
                  if (isAdmin)
                    TextButton.icon(
                      onPressed: onDelete,
                      icon: const Icon(Icons.delete_outline),
                      label: const Text('Przenieś do kosza'),
                    ),
                ],
              ),
              const SizedBox(height: 12),
              Card(
                key: const Key('client-header-card'),
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Row(
                    key: const Key('client-header-row'),
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      CircleAvatar(
                        radius: 32,
                        backgroundColor: theme.colorScheme.primaryContainer,
                        foregroundColor: theme.colorScheme.onPrimaryContainer,
                        child: Icon(
                          _clientTypeIcon(client.clientType),
                          size: 32,
                        ),
                      ),
                      const SizedBox(width: 20),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text(
                              client.displayName,
                              style: theme.textTheme.headlineSmall?.copyWith(
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              client.clientType.displayName,
                              style: theme.textTheme.bodyLarge?.copyWith(
                                color: theme.colorScheme.onSurfaceVariant,
                              ),
                            ),
                            if (client.legalName?.trim().isNotEmpty ==
                                true) ...[
                              const SizedBox(height: 6),
                              Text(
                                client.legalName!.trim(),
                                style: theme.textTheme.bodyMedium,
                              ),
                            ],
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),
              _ClientWorkflowStatusCard(client: client),
              const SizedBox(height: 20),
              _DetailsSection(
                title: 'Dane podstawowe',
                icon: Icons.badge_outlined,
                children: <Widget>[
                  _DetailRow(
                    label: 'Typ klienta',
                    value: client.clientType.displayName,
                  ),
                  _DetailRow(label: 'Nazwa', value: client.name),
                  _DetailRow(label: 'Nazwa prawna', value: client.legalName),
                  _DetailRow(label: 'Branża', value: client.industry?.name),
                ],
              ),
              const SizedBox(height: 20),
              _DetailsSection(
                title: 'Dane rejestrowe',
                icon: Icons.assignment_outlined,
                children: <Widget>[
                  _DetailRow(
                    label: 'NIP / identyfikator podatkowy',
                    value: client.taxId,
                  ),
                  _DetailRow(
                    label: 'Numer rejestracyjny',
                    value: client.registrationNumber,
                  ),
                ],
              ),
              const SizedBox(height: 20),
              _DetailsSection(
                title: 'Kontakt',
                icon: Icons.contact_phone_outlined,
                children: <Widget>[
                  ...(client.emails.isNotEmpty
                          ? client.emails
                          : <ClientContactPoint>[
                              if (client.primaryEmail != null)
                                ClientContactPoint(
                                  id: 0,
                                  value: client.primaryEmail!,
                                  isPrimary: true,
                                ),
                            ])
                      .map(
                        (item) => _DetailRow(
                          label:
                              '${item.isPrimary ? 'E-mail (główny)' : 'E-mail'} • ${_originLabel(item.origin)}',
                          value: item.value,
                        ),
                      ),
                  ...(client.phones.isNotEmpty
                          ? client.phones
                          : <ClientContactPoint>[
                              if (client.primaryPhone != null)
                                ClientContactPoint(
                                  id: 0,
                                  value: client.primaryPhone!,
                                  isPrimary: true,
                                ),
                            ])
                      .map(
                        (item) => _DetailRow(
                          label: item.isPrimary
                              ? 'Telefon (główny) • ${_originLabel(item.origin)}'
                              : 'Telefon • ${_originLabel(item.origin)}',
                          value: item.value,
                        ),
                      ),
                  if (_canCall(client.primaryPhone)) ...<Widget>[
                    Padding(
                      padding: const EdgeInsets.only(top: 2, bottom: 18),
                      child: Align(
                        alignment: Alignment.centerLeft,
                        child: FilledButton.icon(
                          key: const Key('client-call-button'),
                          onPressed: _callPending
                              ? null
                              : () {
                                  final points = client.phones.where(
                                    (item) => item.isPrimary && item.id > 0,
                                  );
                                  _callPhone(
                                    context,
                                    client.primaryPhone!,
                                    points.isEmpty ? null : points.first.id,
                                  );
                                },
                          icon: const Icon(Icons.phone_outlined),
                          label: const Text('Zadzwoń'),
                        ),
                      ),
                    ),
                  ],
                  _DetailRow(
                    label: 'Strona internetowa',
                    value: client.website,
                  ),
                ],
              ),
              const SizedBox(height: 20),
              _DetailsSection(
                title: 'Adres',
                icon: Icons.location_on_outlined,
                children: <Widget>[
                  if (client.addresses.isNotEmpty)
                    ...client.addresses.map(
                      (address) => Card(
                        key: Key('client-address-${address.id}'),
                        color: theme.colorScheme.surfaceContainerHighest,
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              Text(
                                address.isPrimary
                                    ? '${address.label} (główny)'
                                    : address.label,
                                style: theme.textTheme.titleSmall,
                              ),
                              const SizedBox(height: 6),
                              SelectableText(address.formatted),
                              const SizedBox(height: 6),
                              Text(
                                'Pochodzenie: ${_originLabel(address.origin)}',
                                style: theme.textTheme.labelSmall,
                              ),
                              const SizedBox(height: 8),
                              FilledButton.icon(
                                onPressed: () =>
                                    _openGoogleMaps(context, address.formatted),
                                icon: const Icon(Icons.directions_outlined),
                                label: const Text('Trasa w Google Maps'),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  if (client.addresses.isEmpty &&
                      client.availableAddress?.trim().isNotEmpty ==
                          true) ...<Widget>[
                    Card(
                      color: theme.colorScheme.surfaceContainerHighest,
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Wrap(
                          spacing: 16,
                          runSpacing: 12,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: <Widget>[
                            Icon(
                              Icons.location_on_outlined,
                              color: theme.colorScheme.primary,
                            ),
                            ConstrainedBox(
                              constraints: const BoxConstraints(maxWidth: 520),
                              child: SelectableText(
                                client.availableAddress!,
                                style: theme.textTheme.bodyLarge,
                              ),
                            ),
                            FilledButton.icon(
                              onPressed: () {
                                _openGoogleMaps(
                                  context,
                                  client.availableAddress!,
                                );
                              },
                              icon: const Icon(Icons.directions_outlined),
                              label: const Text('Trasa w Google Maps'),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),
                  ],
                  if (client.addresses.isEmpty &&
                      !client.hasStructuredAddressData &&
                      client.addressFromNotes?.trim().isNotEmpty == true)
                    _DetailRow(
                      label: 'Dostępny adres ze źródła',
                      value: client.addressFromNotes,
                      multiline: true,
                    ),
                  if (client.addresses.isEmpty) ...<Widget>[
                    _DetailRow(label: 'Ulica', value: client.street),
                    _DetailRow(
                      label: 'Numer budynku',
                      value: client.buildingNumber,
                    ),
                    _DetailRow(label: 'Numer lokalu', value: client.unitNumber),
                    _DetailRow(label: 'Kod pocztowy', value: client.postalCode),
                    _DetailRow(label: 'Miejscowość', value: client.city),
                    _DetailRow(label: 'Kod kraju', value: client.countryCode),
                  ],
                ],
              ),
              const SizedBox(height: 20),
              _DetailsSection(
                title: 'Notatki',
                icon: Icons.notes_outlined,
                children: <Widget>[
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton.icon(
                      onPressed: onEditNotes,
                      icon: const Icon(Icons.edit_note),
                      label: const Text('Edytuj'),
                    ),
                  ),
                  _DetailRow(
                    label: 'Dodatkowe informacje',
                    value: client.displayNotes,
                    multiline: true,
                  ),
                ],
              ),
              const SizedBox(height: 20),
              Align(
                alignment: Alignment.centerLeft,
                child: FilledButton.tonalIcon(
                  key: const Key('client-open-technical-ai'),
                  onPressed: () =>
                      context.push('/ai?mode=technical&client_id=${client.id}'),
                  icon: const Icon(Icons.engineering_outlined),
                  label: const Text('Otwórz w Asystencie technicznym'),
                ),
              ),
              const SizedBox(height: 20),
              ClientWorkItemsPanel(clientId: client.id),
              const SizedBox(height: 20),
              ClientWorkspacePanels(
                clientId: client.id,
                clientName: client.displayName,
                emailSourceId: emailSourceId,
              ),
              const SizedBox(height: 20),
              _DetailsSection(
                title: 'Informacje systemowe',
                icon: Icons.info_outline,
                children: <Widget>[
                  _DetailRow(label: 'ID klienta', value: client.id.toString()),
                  _DetailRow(
                    label: 'Data dodania',
                    value: formatPolishDate(client.effectiveAddedDate),
                  ),
                  _DetailRow(
                    label: 'Ostatnia aktualizacja',
                    value: formatPolishDateTime(client.updatedAt),
                  ),
                ],
              ),
              ClientRealizationsPanel(clientId: client.id),
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

  bool _canCall(String? phoneNumber) {
    if (kIsWeb) {
      return false;
    }

    final bool isMobile =
        defaultTargetPlatform == TargetPlatform.android ||
        defaultTargetPlatform == TargetPlatform.iOS;

    return isMobile && phoneNumber != null && phoneNumber.trim().isNotEmpty;
  }

  Future<void> _callPhone(
    BuildContext context,
    String phoneNumber,
    int? contactId,
  ) async {
    if (_callPending) return;
    final String normalizedPhone = phoneNumber.trim().replaceAll(
      RegExp(r'[^\d+]'),
      '',
    );

    if (normalizedPhone.isEmpty) {
      return;
    }

    setState(() => _callPending = true);
    final operationId = _uuidV4();
    bool logFailed = false;
    try {
      final authState = await ref.read(authControllerProvider.future);
      final session = authState.session;
      if (session == null || !session.isAuthenticated) {
        logFailed = true;
      } else {
        await ref
            .read(clientsRepositoryProvider)
            .recordCallInitiated(
              session: session,
              clientId: client.id,
              operationId: operationId,
              contactId: contactId,
            );
        ref.invalidate(
          timelinePageProvider(
            TimelineRequest(scope: TimelineScope.client, id: client.id),
          ),
        );
      }
    } catch (_) {
      logFailed = true;
    }

    if (logFailed && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Nie udało się zapisać rozpoczęcia połączenia. Telefon zostanie otwarty.',
          ),
        ),
      );
    }

    final Uri uri = Uri(scheme: 'tel', path: normalizedPhone);

    bool opened = false;
    try {
      opened = await ref.read(phoneUriLauncherProvider)(uri);
    } catch (_) {
      opened = false;
    } finally {
      if (mounted) setState(() => _callPending = false);
    }

    if (!opened && context.mounted) {
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          const SnackBar(
            content: Text('Nie udało się otworzyć aplikacji telefonu.'),
          ),
        );
    }
  }

  String _uuidV4() {
    final random = Random.secure();
    final bytes = List<int>.generate(16, (_) => random.nextInt(256));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    final hex = bytes
        .map((value) => value.toRadixString(16).padLeft(2, '0'))
        .join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
  }

  Future<void> _openGoogleMaps(BuildContext context, String address) async {
    String destination = address.trim();

    if (destination.isEmpty) {
      return;
    }

    destination = destination.replaceAll(
      RegExp(r',\s*PL$', caseSensitive: false),
      ', Polska',
    );

    final Uri uri = Uri.https('www.google.com', '/maps/dir/', <String, String>{
      'api': '1',
      'destination': destination,
      'travelmode': 'driving',
    });

    final bool opened = await launchUrl(
      uri,
      mode: LaunchMode.externalApplication,
    );

    if (!opened && context.mounted) {
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          const SnackBar(content: Text('Nie udało się otworzyć Google Maps.')),
        );
    }
  }

  String _originLabel(String origin) => switch (origin) {
    'gmail' => 'Gmail',
    'sheets' => 'Google Sheets',
    'migration' => 'dane zastane',
    'manual' => 'ręcznie',
    _ => 'inne',
  };
}

class _ClientWorkflowStatusCard extends ConsumerWidget {
  const _ClientWorkflowStatusCard({required this.client});

  final Client client;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = ClientWorkflowStatus.fromClient(client);
    return Card(
      key: const Key('client-workflow-status-card'),
      child: ListTile(
        leading: const Icon(Icons.flag_outlined),
        title: const Text('Status / kategoria'),
        subtitle: Text(status.displayLabel),
        trailing: TextButton(
          key: const Key('client-workflow-status-edit'),
          onPressed: () => _edit(context, ref, status),
          child: const Text('Edytuj'),
        ),
      ),
    );
  }

  Future<void> _edit(
    BuildContext context,
    WidgetRef ref,
    ClientWorkflowStatus current,
  ) async {
    final selected = await showDialog<ClientWorkflowState>(
      context: context,
      builder: (dialogContext) => SimpleDialog(
        title: const Text('Ustaw status / kategorię'),
        children: ClientWorkflowState.values
            .map(
              (state) => SimpleDialogOption(
                onPressed: () => Navigator.pop(dialogContext, state),
                child: Text(state.label),
              ),
            )
            .toList(growable: false),
      ),
    );
    if (selected == null || !context.mounted) return;
    DateTime? date;
    if (selected.requiresDate) {
      date = await showDatePicker(
        context: context,
        initialDate: current.date ?? DateTime.now(),
        firstDate: DateTime(2020),
        lastDate: DateTime(2100),
      );
      if (date == null || !context.mounted) return;
    }
    final session = ref.read(authControllerProvider).value?.session;
    if (session == null) return;
    await ref
        .read(clientsRepositoryProvider)
        .bulkWorkflowStatus(
          session: session,
          clientIds: <int>[client.id],
          status: selected.apiValue,
          effectiveDate: date?.toIso8601String().split('T').first,
        );
    ref.invalidate(clientWorkflowStatusesProvider(client.id.toString()));
    ref.invalidate(clientDetailsProvider(client.id));
    ref.invalidate(clientsControllerProvider);
  }
}

class _DetailsSection extends StatelessWidget {
  const _DetailsSection({
    required this.title,
    required this.icon,
    required this.children,
  });

  final String title;
  final IconData icon;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(icon, color: theme.colorScheme.primary),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    title,
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            ...children,
          ],
        ),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({
    required this.label,
    required this.value,
    this.multiline = false,
  });

  final String label;
  final String? value;
  final bool multiline;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    final String displayedValue = value?.trim().isNotEmpty == true
        ? value!.trim()
        : 'Brak danych';

    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: LayoutBuilder(
        builder: (BuildContext context, BoxConstraints constraints) {
          if (constraints.maxWidth < 600 || multiline) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  label,
                  style: theme.textTheme.labelMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 4),
                SelectableText(
                  displayedValue,
                  style: theme.textTheme.bodyLarge,
                ),
              ],
            );
          }

          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              SizedBox(
                width: 220,
                child: Text(
                  label,
                  style: theme.textTheme.labelMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
              const SizedBox(width: 20),
              Expanded(
                child: SelectableText(
                  displayedValue,
                  style: theme.textTheme.bodyLarge,
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _LoadingView extends StatelessWidget {
  const _LoadingView();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          CircularProgressIndicator(),
          SizedBox(height: 16),
          Text('Pobieranie danych klienta...'),
        ],
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

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
                Icons.error_outline,
                size: 64,
                color: theme.colorScheme.error,
              ),
              const SizedBox(height: 20),
              Text(
                'Nie udało się pobrać klienta',
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
