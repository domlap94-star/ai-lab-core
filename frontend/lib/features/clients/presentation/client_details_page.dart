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
import '../domain/client.dart';
import '../domain/industry.dart';
import 'client_workspace_panels.dart';
import 'client_edit_dialog.dart';
import 'client_contact_actions.dart';
import 'contact_person_dialog.dart';
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
              onEditSection: (section) =>
                  _editClientSection(context, ref, client, section),
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
    await _openClientEditor(context, ref, client, null);
  }

  Future<void> _editClientSection(
    BuildContext context,
    WidgetRef ref,
    Client client,
    ClientEditSection section,
  ) async {
    await _openClientEditor(context, ref, client, section);
  }

  Future<void> _openClientEditor(
    BuildContext context,
    WidgetRef ref,
    Client client,
    ClientEditSection? section,
  ) async {
    List<Industry> industries = const <Industry>[];
    if (section == ClientEditSection.basic || section == null) {
      try {
        industries = await ref.read(industriesProvider.future);
      } catch (_) {
        industries = client.industry == null
            ? const <Industry>[]
            : <Industry>[client.industry!];
      }
    }
    if (!context.mounted) return;
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => ClientEditDialog(
        client: client,
        section: section,
        industries: industries,
      ),
    );
    if (data == null || !context.mounted) return;
    await _update(
      context,
      ref,
      client.id,
      data,
      section == null ? 'Dane klienta zapisane.' : 'Sekcja klienta zapisana.',
    );
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
    required this.onEditSection,
    required this.onEditNotes,
    required this.onDelete,
    this.emailSourceId,
  });

  final Client client;
  final VoidCallback onEdit;
  final ValueChanged<ClientEditSection> onEditSection;
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
  ValueChanged<ClientEditSection> get onEditSection => widget.onEditSection;
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
                    key: const Key('client-full-edit'),
                    onPressed: onEdit,
                    icon: const Icon(Icons.edit_outlined),
                    label: const Text('Edytuj klienta'),
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
                      TextButton.icon(
                        key: const Key('client-section-edit-name'),
                        onPressed: () => onEditSection(ClientEditSection.name),
                        icon: const Icon(Icons.edit_outlined),
                        label: const Text('Edytuj'),
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
                editKey: const Key('client-section-edit-basic'),
                onEdit: () => onEditSection(ClientEditSection.basic),
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
                editKey: const Key('client-section-edit-registration'),
                onEdit: () => onEditSection(ClientEditSection.registration),
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
                editKey: const Key('client-section-edit-contact'),
                onEdit: () => onEditSection(ClientEditSection.contact),
                children: <Widget>[
                  Row(
                    children: <Widget>[
                      Expanded(
                        child: Text(
                          'Osoby kontaktowe',
                          style: theme.textTheme.titleMedium,
                        ),
                      ),
                      TextButton.icon(
                        key: const Key('contact-person-add'),
                        onPressed: () => _editContactPerson(context),
                        icon: const Icon(Icons.person_add_alt_1_outlined),
                        label: const Text('Dodaj osobę'),
                      ),
                    ],
                  ),
                  if (client.contactPersons.isEmpty)
                    const Padding(
                      padding: EdgeInsets.only(top: 8, bottom: 16),
                      child: Text('Brak osób kontaktowych'),
                    )
                  else
                    ...client.contactPersons.map(
                      (person) => _ContactPersonCard(
                        person: person,
                        onEdit: () => _editContactPerson(context, person),
                        onArchive: () => _archiveContactPerson(context, person),
                      ),
                    ),
                  const SizedBox(height: 12),
                  Text(
                    'Kontakty ogólne firmy',
                    style: theme.textTheme.titleMedium,
                  ),
                  const SizedBox(height: 8),
                  if (client.genericEmails.isEmpty &&
                      client.genericPhones.isEmpty)
                    const Padding(
                      padding: EdgeInsets.only(bottom: 12),
                      child: Text('Brak kontaktów ogólnych'),
                    ),
                  ...client.genericEmails.map(
                    (item) => _DetailRow(
                      label:
                          '${item.isPrimary ? 'E-mail (główny)' : 'E-mail'} • ${_originLabel(item.origin)}',
                      value: item.value,
                    ),
                  ),
                  ...client.genericPhones.map(
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
                editKey: const Key('client-section-edit-address'),
                onEdit: () => onEditSection(ClientEditSection.address),
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
                editKey: const Key('client-section-edit-system'),
                onEdit: () => onEditSection(ClientEditSection.system),
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
    setState(() => _callPending = true);
    try {
      await launchCanonicalClientCall(
        context: context,
        ref: ref,
        clientId: client.id,
        phoneNumber: phoneNumber,
        contactId: contactId,
        launcher: ref.read(phoneUriLauncherProvider),
      );
    } finally {
      if (mounted) setState(() => _callPending = false);
    }
  }

  Future<void> _editContactPerson(
    BuildContext context, [
    ContactPerson? person,
  ]) async {
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => ContactPersonDialog(client: client, person: person),
    );
    if (data == null || !mounted) return;
    final session = ref.read(authControllerProvider).value?.session;
    if (session == null) return;
    try {
      final repository = ref.read(clientsRepositoryProvider);
      if (person == null) {
        await repository.createContactPerson(
          session: session,
          clientId: client.id,
          data: data,
        );
      } else {
        await repository.updateContactPerson(
          session: session,
          clientId: client.id,
          personId: person.id,
          data: data,
        );
      }
      ref.invalidate(clientDetailsProvider(client.id));
      ref.invalidate(clientsControllerProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              person == null
                  ? 'Osoba kontaktowa dodana.'
                  : 'Osoba kontaktowa zapisana.',
            ),
          ),
        );
      }
    } catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(_contactPersonError(error))));
      }
    }
  }

  Future<void> _archiveContactPerson(
    BuildContext context,
    ContactPerson person,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Usunąć osobę kontaktową?'),
        content: const Text(
          'Osoba zostanie zarchiwizowana. Jej e-maile i telefony pozostaną przy kliencie jako kontakty ogólne.',
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Anuluj'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Usuń osobę'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final session = ref.read(authControllerProvider).value?.session;
    if (session == null) return;
    try {
      await ref
          .read(clientsRepositoryProvider)
          .archiveContactPerson(
            session: session,
            clientId: client.id,
            personId: person.id,
          );
      ref.invalidate(clientDetailsProvider(client.id));
      ref.invalidate(clientsControllerProvider);
    } catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(_contactPersonError(error))));
      }
    }
  }

  String _contactPersonError(Object error) {
    if (error is DioException) {
      final detail = error.response?.data is Map
          ? (error.response!.data as Map)['detail']?.toString()
          : null;
      return detail ?? 'Nie udało się zapisać osoby kontaktowej.';
    }
    return 'Nie udało się zapisać osoby kontaktowej.';
  }

  Future<void> _openGoogleMaps(BuildContext context, String address) async {
    await openCanonicalClientMaps(context, address);
  }

  String _originLabel(String origin) => switch (origin) {
    'gmail' => 'Gmail',
    'sheets' => 'Google Sheets',
    'migration' => 'dane zastane',
    'manual' => 'ręcznie',
    _ => 'inne',
  };
}

class _ContactPersonCard extends StatelessWidget {
  const _ContactPersonCard({
    required this.person,
    required this.onEdit,
    required this.onArchive,
  });

  final ContactPerson person;
  final VoidCallback onEdit;
  final VoidCallback onArchive;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      key: Key('contact-person-${person.id}'),
      margin: const EdgeInsets.only(top: 10),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Wrap(
              spacing: 8,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: <Widget>[
                Text(
                  person.displayName,
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (person.isPreferred) const Chip(label: Text('Preferowany')),
                if (person.isDecisionMaker) const Chip(label: Text('Decydent')),
              ],
            ),
            if (person.role?.trim().isNotEmpty == true) ...<Widget>[
              const SizedBox(height: 4),
              Text(person.role!, style: theme.textTheme.bodyMedium),
            ],
            if (person.emails.isNotEmpty) ...<Widget>[
              const SizedBox(height: 10),
              ...person.emails.map((point) => Text('E-mail: ${point.value}')),
            ],
            if (person.phones.isNotEmpty) ...<Widget>[
              const SizedBox(height: 6),
              ...person.phones.map((point) => Text('Telefon: ${point.value}')),
            ],
            if (person.notes?.trim().isNotEmpty == true) ...<Widget>[
              const SizedBox(height: 10),
              Text('Notatka: ${person.notes}'),
            ],
            const SizedBox(height: 8),
            Wrap(
              alignment: WrapAlignment.end,
              spacing: 8,
              children: <Widget>[
                TextButton.icon(
                  onPressed: onEdit,
                  icon: const Icon(Icons.edit_outlined),
                  label: const Text('Edytuj'),
                ),
                TextButton.icon(
                  onPressed: onArchive,
                  icon: const Icon(Icons.delete_outline),
                  label: const Text('Usuń'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
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
    this.onEdit,
    this.editKey,
  });

  final String title;
  final IconData icon;
  final List<Widget> children;
  final VoidCallback? onEdit;
  final Key? editKey;

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
                if (onEdit != null)
                  TextButton.icon(
                    key: editKey,
                    onPressed: onEdit,
                    icon: const Icon(Icons.edit_outlined),
                    label: const Text('Edytuj'),
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
