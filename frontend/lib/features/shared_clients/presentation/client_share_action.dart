import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/application/auth_controller.dart';
import '../application/client_access_providers.dart';

class ClientShareAction extends ConsumerStatefulWidget {
  const ClientShareAction({
    required this.clientId,
    required this.clientDisplayName,
    super.key,
  });

  final int clientId;
  final String clientDisplayName;

  @override
  ConsumerState<ClientShareAction> createState() => _ClientShareActionState();
}

class _ClientShareActionState extends ConsumerState<ClientShareAction> {
  final MenuController _menuController = MenuController();
  bool _menuRequested = false;

  Future<void> _openMenu() async {
    if (!_menuRequested) setState(() => _menuRequested = true);
    invalidateClientAccess(ref, widget.clientId);
    _menuController.open();
  }

  Future<void> _confirm(ClientShareUser user) async {
    _menuController.close();
    bool submitting = false;

    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (BuildContext dialogContext) {
        return StatefulBuilder(
          builder: (BuildContext dialogContext, StateSetter setDialogState) =>
              AlertDialog(
                title: const Text('Udostępnić klienta?'),
                content: Text(
                  'Udostępnić klienta „${widget.clientDisplayName}” '
                  'użytkownikowi „${user.displayName}”?\n\n'
                  'Użytkownik uzyska dostęp do klienta oraz jego zasobów '
                  'zgodnie z zakresem uprawnień R25.',
                ),
                actions: <Widget>[
                  TextButton(
                    onPressed: submitting
                        ? null
                        : () => Navigator.of(dialogContext).pop(),
                    child: const Text('Anuluj'),
                  ),
                  FilledButton(
                    key: const Key('client-share-confirm'),
                    onPressed: submitting
                        ? null
                        : () async {
                            if (submitting) return;
                            setDialogState(() => submitting = true);
                            await _grant(dialogContext, user);
                          },
                    child: submitting
                        ? const SizedBox.square(
                            dimension: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('Udostępnij'),
                  ),
                ],
              ),
        );
      },
    );
  }

  Future<void> _grant(BuildContext dialogContext, ClientShareUser user) async {
    final session = ref.read(authControllerProvider).value?.session;
    String? errorMessage;
    try {
      if (session == null) {
        errorMessage = 'Nie masz uprawnień do udostępnienia klienta.';
      } else {
        await ref
            .read(clientAccessRepositoryProvider)
            .grant(
              session: session,
              clientId: widget.clientId,
              externalUserId: user.id,
            );
      }
    } on DioException catch (error) {
      final int? statusCode = error.response?.statusCode;
      if (statusCode == 409) {
        errorMessage = 'Ten użytkownik ma już dostęp do klienta.';
      } else if (statusCode == 401 || statusCode == 403) {
        errorMessage = 'Nie masz uprawnień do udostępnienia klienta.';
      } else {
        errorMessage = 'Nie udało się udostępnić klienta. Spróbuj ponownie.';
      }
    } catch (_) {
      errorMessage = 'Nie udało się udostępnić klienta. Spróbuj ponownie.';
    }

    invalidateClientAccess(ref, widget.clientId);
    if (!dialogContext.mounted) return;
    Navigator.of(dialogContext).pop();
    if (!mounted) return;

    final String message =
        errorMessage ??
        'Udostępniono klienta użytkownikowi ${user.displayName}.';
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final String? role = ref.watch(authControllerProvider).value?.user?.role;
    if (!canManageClientAccess(role)) return const SizedBox.shrink();

    final AsyncValue<List<ClientShareUser>> availableUsers = _menuRequested
        ? ref.watch(availableClientShareUsersProvider(widget.clientId))
        : const AsyncValue<List<ClientShareUser>>.loading();

    return MenuAnchor(
      controller: _menuController,
      menuChildren: <Widget>[
        SizedBox(
          width: 320,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 320),
            child: availableUsers.when(
              loading: () => const Padding(
                padding: EdgeInsets.all(16),
                child: Row(
                  children: <Widget>[
                    SizedBox.square(
                      dimension: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                    SizedBox(width: 12),
                    Expanded(child: Text('Ładowanie użytkowników…')),
                  ],
                ),
              ),
              error: (_, _) => const Padding(
                padding: EdgeInsets.all(16),
                child: Text('Nie udało się pobrać użytkowników.'),
              ),
              data: (List<ClientShareUser> users) => users.isEmpty
                  ? const Padding(
                      padding: EdgeInsets.all(16),
                      child: Text(
                        'Brak użytkowników, którym można udostępnić klienta.',
                      ),
                    )
                  : SingleChildScrollView(
                      primary: false,
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: users
                            .map(
                              (ClientShareUser user) => MenuItemButton(
                                key: ValueKey<String>(
                                  'client-share-user-${user.id}',
                                ),
                                onPressed: () => _confirm(user),
                                child: SizedBox(
                                  width: double.infinity,
                                  child: Text(user.displayName),
                                ),
                              ),
                            )
                            .toList(growable: false),
                      ),
                    ),
            ),
          ),
        ),
      ],
      builder:
          (BuildContext context, MenuController controller, Widget? child) =>
              Semantics(
                label: 'Udostępnij klienta',
                button: true,
                child: IconButton(
                  key: ValueKey<String>('client-share-${widget.clientId}'),
                  tooltip: 'Udostępnij klienta',
                  constraints: const BoxConstraints.tightFor(
                    width: 48,
                    height: 48,
                  ),
                  onPressed: _openMenu,
                  icon: const Icon(Icons.share_outlined),
                ),
              ),
    );
  }
}
