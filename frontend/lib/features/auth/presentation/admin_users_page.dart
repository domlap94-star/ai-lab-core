import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../application/account_providers.dart';
import '../application/auth_controller.dart';
import '../application/auth_state.dart';
import '../data/account_api.dart';

class AdminUsersPage extends ConsumerStatefulWidget {
  const AdminUsersPage({super.key});

  @override
  ConsumerState<AdminUsersPage> createState() {
    return _AdminUsersPageState();
  }
}

class _AdminUsersPageState extends ConsumerState<AdminUsersPage> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();

  final TextEditingController _usernameController = TextEditingController();

  final TextEditingController _emailController = TextEditingController();

  final TextEditingController _passwordController = TextEditingController();

  String _role = 'User';
  bool _obscurePassword = true;
  bool _isSubmitting = false;
  bool _isLoadingUsers = false;
  List<ManagedUser> _users = const <ManagedUser>[];
  String? _usersMessage;

  @override
  void initState() {
    super.initState();

    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadUsers();
    });
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  bool _isAdminRole(String role) {
    final String normalized = role.trim().toLowerCase();

    return normalized == 'administrator' || normalized == 'admin';
  }

  Future<void> _loadUsers() async {
    final AuthState? state = ref.read(authControllerProvider).value;

    final session = state?.session;

    if (session == null || !session.isAuthenticated) {
      return;
    }

    setState(() {
      _isLoadingUsers = true;
      _usersMessage = null;
    });

    try {
      final List<ManagedUser> users = await ref
          .read(accountApiProvider)
          .fetchUsers(session: session);

      if (!mounted) {
        return;
      }

      setState(() {
        _users = users;
      });
    } on DioException catch (error) {
      if (!mounted) {
        return;
      }

      setState(() {
        if (error.response?.statusCode == 404) {
          _usersMessage =
              'Backend zarządzania użytkownikami '
              'zostanie uruchomiony w Phase 2.';
        } else {
          _usersMessage = 'Nie udało się pobrać użytkowników.';
        }
      });
    } catch (_) {
      if (!mounted) {
        return;
      }

      setState(() {
        _usersMessage = 'Nie udało się pobrać użytkowników.';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoadingUsers = false;
        });
      }
    }
  }

  Future<void> _createUser() async {
    FocusScope.of(context).unfocus();

    if (_formKey.currentState?.validate() != true) {
      return;
    }

    final AuthState? state = ref.read(authControllerProvider).value;

    final session = state?.session;

    if (session == null || !session.isAuthenticated) {
      _showMessage('Sesja wygasła. Zaloguj się ponownie.', isError: true);
      return;
    }

    setState(() {
      _isSubmitting = true;
    });

    try {
      await ref
          .read(accountApiProvider)
          .createUser(
            session: session,
            username: _usernameController.text,
            email: _emailController.text,
            role: _role,
            temporaryPassword: _passwordController.text,
          );

      if (!mounted) {
        return;
      }

      _usernameController.clear();
      _emailController.clear();
      _passwordController.clear();

      setState(() {
        _role = 'User';
      });

      _showMessage('Użytkownik został utworzony.');

      await _loadUsers();
    } on DioException catch (error) {
      if (!mounted) {
        return;
      }

      final int? statusCode = error.response?.statusCode;

      String message = 'Nie udało się utworzyć użytkownika.';

      if (statusCode == 404) {
        message =
            'Panel jest gotowy. Endpoint zostanie '
            'uruchomiony w Phase 2.';
      } else if (statusCode == 403) {
        message = 'Brak uprawnień administratora.';
      } else if (statusCode == 409) {
        message =
            'Użytkownik o tej nazwie lub adresie '
            'e-mail już istnieje.';
      }

      _showMessage(message, isError: true);
    } finally {
      if (mounted) {
        setState(() {
          _isSubmitting = false;
        });
      }
    }
  }

  Future<void> _resetPassword(ManagedUser user) async {
    final TextEditingController controller = TextEditingController();

    bool obscure = true;

    final String? temporaryPassword = await showDialog<String>(
      context: context,
      builder: (BuildContext dialogContext) {
        return StatefulBuilder(
          builder: (BuildContext context, StateSetter setDialogState) {
            return AlertDialog(
              title: Text('Reset hasła: ${user.username}'),
              content: TextField(
                controller: controller,
                obscureText: obscure,
                autofocus: true,
                decoration: InputDecoration(
                  labelText: 'Nowe hasło tymczasowe',
                  helperText: 'Minimum 10 znaków.',
                  suffixIcon: IconButton(
                    onPressed: () {
                      setDialogState(() {
                        obscure = !obscure;
                      });
                    },
                    icon: Icon(
                      obscure
                          ? Icons.visibility_outlined
                          : Icons.visibility_off_outlined,
                    ),
                  ),
                ),
              ),
              actions: <Widget>[
                TextButton(
                  onPressed: () {
                    Navigator.of(dialogContext).pop();
                  },
                  child: const Text('Anuluj'),
                ),
                FilledButton(
                  onPressed: () {
                    final String value = controller.text;

                    if (value.length < 10) {
                      return;
                    }

                    Navigator.of(dialogContext).pop(value);
                  },
                  child: const Text('Ustaw hasło tymczasowe'),
                ),
              ],
            );
          },
        );
      },
    );

    controller.dispose();

    if (temporaryPassword == null) {
      return;
    }

    final AuthState? state = ref.read(authControllerProvider).value;

    final session = state?.session;

    if (session == null || !session.isAuthenticated) {
      _showMessage('Sesja wygasła.', isError: true);
      return;
    }

    try {
      await ref
          .read(accountApiProvider)
          .resetUserPassword(
            session: session,
            userId: user.id,
            temporaryPassword: temporaryPassword,
          );

      if (!mounted) {
        return;
      }

      _showMessage('Hasło tymczasowe zostało ustawione.');

      await _loadUsers();
    } on DioException catch (error) {
      if (!mounted) {
        return;
      }

      final String message = error.response?.statusCode == 404
          ? 'Endpoint resetu zostanie '
                'uruchomiony w Phase 2.'
          : 'Nie udało się zresetować hasła.';

      _showMessage(message, isError: true);
    }
  }

  void _showMessage(String message, {bool isError = false}) {
    final ThemeData theme = Theme.of(context);

    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
          backgroundColor: isError ? theme.colorScheme.error : null,
        ),
      );
  }

  @override
  Widget build(BuildContext context) {
    final AuthState? state = ref.watch(authControllerProvider).value;

    final String role = state?.user?.role ?? '';

    if (!_isAdminRole(role)) {
      return Scaffold(
        appBar: AppBar(title: const Text('Użytkownicy')),
        body: const Center(
          child: Padding(
            padding: EdgeInsets.all(24),
            child: Text(
              'Ta sekcja jest dostępna wyłącznie '
              'dla administratora.',
              textAlign: TextAlign.center,
            ),
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Zarządzanie użytkownikami'),
        actions: <Widget>[
          IconButton(
            tooltip: 'Odśwież',
            onPressed: _isLoadingUsers ? null : _loadUsers,
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
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    Text(
                      'Dodaj użytkownika',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 20),
                    TextFormField(
                      controller: _usernameController,
                      enabled: !_isSubmitting,
                      decoration: const InputDecoration(
                        labelText: 'Nazwa użytkownika',
                        border: OutlineInputBorder(),
                      ),
                      validator: (String? value) {
                        if (value == null || value.trim().length < 3) {
                          return 'Minimum 3 znaki.';
                        }

                        return null;
                      },
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _emailController,
                      enabled: !_isSubmitting,
                      keyboardType: TextInputType.emailAddress,
                      decoration: const InputDecoration(
                        labelText: 'E-mail',
                        border: OutlineInputBorder(),
                      ),
                      validator: (String? value) {
                        final String text = value?.trim() ?? '';

                        if (!text.contains('@') || !text.contains('.')) {
                          return 'Wprowadź poprawny e-mail.';
                        }

                        return null;
                      },
                    ),
                    const SizedBox(height: 16),
                    DropdownButtonFormField<String>(
                      initialValue: _role,
                      decoration: const InputDecoration(
                        labelText: 'Rola',
                        border: OutlineInputBorder(),
                      ),
                      items: const <DropdownMenuItem<String>>[
                        DropdownMenuItem<String>(
                          value: 'User',
                          child: Text('Użytkownik'),
                        ),
                        DropdownMenuItem<String>(
                          value: 'Administrator',
                          child: Text('Administrator'),
                        ),
                      ],
                      onChanged: _isSubmitting
                          ? null
                          : (String? value) {
                              if (value == null) {
                                return;
                              }

                              setState(() {
                                _role = value;
                              });
                            },
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _passwordController,
                      enabled: !_isSubmitting,
                      obscureText: _obscurePassword,
                      decoration: InputDecoration(
                        labelText: 'Hasło tymczasowe',
                        border: const OutlineInputBorder(),
                        suffixIcon: IconButton(
                          onPressed: _isSubmitting
                              ? null
                              : () {
                                  setState(() {
                                    _obscurePassword = !_obscurePassword;
                                  });
                                },
                          icon: Icon(
                            _obscurePassword
                                ? Icons.visibility_outlined
                                : Icons.visibility_off_outlined,
                          ),
                        ),
                      ),
                      validator: (String? value) {
                        if (value == null || value.length < 10) {
                          return 'Minimum 10 znaków.';
                        }

                        return null;
                      },
                    ),
                    const SizedBox(height: 20),
                    FilledButton.icon(
                      onPressed: _isSubmitting ? null : _createUser,
                      icon: const Icon(Icons.person_add_alt_1),
                      label: Text(
                        _isSubmitting ? 'Tworzenie...' : 'Dodaj użytkownika',
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(height: 20),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: <Widget>[
                  Text(
                    'Użytkownicy',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 12),
                  if (_isLoadingUsers) const LinearProgressIndicator(),
                  if (_usersMessage != null)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      child: Text(_usersMessage!),
                    ),
                  if (!_isLoadingUsers &&
                      _usersMessage == null &&
                      _users.isEmpty)
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: 12),
                      child: Text('Brak użytkowników.'),
                    ),
                  ..._users.map(
                    (ManagedUser user) => _UserTile(
                      user: user,
                      onResetPassword: () {
                        _resetPassword(user);
                      },
                    ),
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

class _UserTile extends StatelessWidget {
  const _UserTile({required this.user, required this.onResetPassword});

  final ManagedUser user;
  final VoidCallback onResetPassword;

  @override
  Widget build(BuildContext context) {
    final List<String> flags = <String>[];

    if (user.mustChangePassword) {
      flags.add('wymagana zmiana hasła');
    }

    if (user.passwordResetRequested) {
      flags.add('prośba o reset hasła');
    }

    if (!user.isActive) {
      flags.add('nieaktywny');
    }

    return ListTile(
      leading: CircleAvatar(
        child: Text(
          user.username.isEmpty ? '?' : user.username[0].toUpperCase(),
        ),
      ),
      title: Text(user.username),
      subtitle: Text(
        <String>[
          user.email,
          user.role,
          if (flags.isNotEmpty) flags.join(' • '),
        ].join('\n'),
      ),
      isThreeLine: flags.isNotEmpty,
      trailing: IconButton(
        tooltip: 'Ustaw hasło tymczasowe',
        onPressed: onResetPassword,
        icon: const Icon(Icons.lock_reset),
      ),
    );
  }
}
