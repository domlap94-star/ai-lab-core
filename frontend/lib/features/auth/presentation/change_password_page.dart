import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../application/account_providers.dart';
import '../application/auth_controller.dart';
import '../application/auth_state.dart';

class ChangePasswordPage extends ConsumerStatefulWidget {
  const ChangePasswordPage({super.key, this.forced = false});

  final bool forced;

  @override
  ConsumerState<ChangePasswordPage> createState() {
    return _ChangePasswordPageState();
  }
}

class _ChangePasswordPageState extends ConsumerState<ChangePasswordPage> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();

  final TextEditingController _currentPasswordController =
      TextEditingController();

  final TextEditingController _newPasswordController = TextEditingController();

  final TextEditingController _confirmPasswordController =
      TextEditingController();

  bool _isSubmitting = false;
  bool _obscureCurrent = true;
  bool _obscureNew = true;
  bool _obscureConfirm = true;

  @override
  void dispose() {
    _currentPasswordController.dispose();
    _newPasswordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
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
          .changePassword(
            session: session,
            currentPassword: _currentPasswordController.text,
            newPassword: _newPasswordController.text,
          );

      if (!mounted) {
        return;
      }

      _currentPasswordController.clear();
      _newPasswordController.clear();
      _confirmPasswordController.clear();

      await ref.read(authControllerProvider.notifier).refreshCurrentUser();

      if (!mounted) {
        return;
      }

      _showMessage('Hasło zostało zmienione.');
    } on DioException catch (error) {
      if (!mounted) {
        return;
      }

      _showMessage(_friendlyError(error), isError: true);
    } catch (_) {
      if (!mounted) {
        return;
      }

      _showMessage('Nie udało się zmienić hasła.', isError: true);
    } finally {
      if (mounted) {
        setState(() {
          _isSubmitting = false;
        });
      }
    }
  }

  String _friendlyError(DioException error) {
    final int? statusCode = error.response?.statusCode;

    if (statusCode == 404) {
      return 'Frontend jest gotowy. Endpoint zmiany hasła '
          'zostanie uruchomiony po zakończeniu batcha klientów.';
    }

    if (statusCode == 401) {
      return 'Obecne hasło jest nieprawidłowe albo sesja wygasła.';
    }

    if (statusCode == 400) {
      final dynamic data = error.response?.data;

      if (data is Map) {
        final dynamic detail = data['detail'];

        if (detail != null) {
          return detail.toString();
        }
      }

      return 'Backend odrzucił zmianę hasła.';
    }

    return 'Nie udało się połączyć z usługą zmiany hasła.';
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
    return Scaffold(
      appBar: widget.forced ? null : AppBar(title: const Text('Zmień hasło')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: <Widget>[
                      const Icon(Icons.security_outlined, size: 52),
                      const SizedBox(height: 16),
                      Text(
                        'Bezpieczeństwo konta',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        widget.forced
                            ? 'Administrator wymaga zmiany hasła przed '
                                  'uzyskaniem dostępu do systemu.'
                            : 'Po zmianie hasła system potwierdzi '
                                  'operację po stronie backendu.',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                      const SizedBox(height: 24),
                      TextFormField(
                        controller: _currentPasswordController,
                        enabled: !_isSubmitting,
                        obscureText: _obscureCurrent,
                        autofillHints: const <String>[AutofillHints.password],
                        decoration: InputDecoration(
                          labelText: 'Obecne hasło',
                          prefixIcon: const Icon(Icons.lock_outline),
                          border: const OutlineInputBorder(),
                          suffixIcon: IconButton(
                            tooltip: _obscureCurrent
                                ? 'Pokaż hasło'
                                : 'Ukryj hasło',
                            onPressed: _isSubmitting
                                ? null
                                : () {
                                    setState(() {
                                      _obscureCurrent = !_obscureCurrent;
                                    });
                                  },
                            icon: Icon(
                              _obscureCurrent
                                  ? Icons.visibility_outlined
                                  : Icons.visibility_off_outlined,
                            ),
                          ),
                        ),
                        validator: (String? value) {
                          if (value == null || value.isEmpty) {
                            return 'Wprowadź obecne hasło.';
                          }

                          return null;
                        },
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _newPasswordController,
                        enabled: !_isSubmitting,
                        obscureText: _obscureNew,
                        autofillHints: const <String>[
                          AutofillHints.newPassword,
                        ],
                        decoration: InputDecoration(
                          labelText: 'Nowe hasło',
                          prefixIcon: const Icon(Icons.password),
                          border: const OutlineInputBorder(),
                          suffixIcon: IconButton(
                            tooltip: _obscureNew
                                ? 'Pokaż hasło'
                                : 'Ukryj hasło',
                            onPressed: _isSubmitting
                                ? null
                                : () {
                                    setState(() {
                                      _obscureNew = !_obscureNew;
                                    });
                                  },
                            icon: Icon(
                              _obscureNew
                                  ? Icons.visibility_outlined
                                  : Icons.visibility_off_outlined,
                            ),
                          ),
                        ),
                        validator: (String? value) {
                          if (value == null || value.length < 10) {
                            return 'Nowe hasło musi mieć '
                                'co najmniej 10 znaków.';
                          }

                          if (value == _currentPasswordController.text) {
                            return 'Nowe hasło musi różnić się '
                                'od obecnego.';
                          }

                          return null;
                        },
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _confirmPasswordController,
                        enabled: !_isSubmitting,
                        obscureText: _obscureConfirm,
                        autofillHints: const <String>[
                          AutofillHints.newPassword,
                        ],
                        textInputAction: TextInputAction.done,
                        onFieldSubmitted: (_) {
                          if (!_isSubmitting) {
                            _submit();
                          }
                        },
                        decoration: InputDecoration(
                          labelText: 'Powtórz nowe hasło',
                          prefixIcon: const Icon(Icons.password),
                          border: const OutlineInputBorder(),
                          suffixIcon: IconButton(
                            tooltip: _obscureConfirm
                                ? 'Pokaż hasło'
                                : 'Ukryj hasło',
                            onPressed: _isSubmitting
                                ? null
                                : () {
                                    setState(() {
                                      _obscureConfirm = !_obscureConfirm;
                                    });
                                  },
                            icon: Icon(
                              _obscureConfirm
                                  ? Icons.visibility_outlined
                                  : Icons.visibility_off_outlined,
                            ),
                          ),
                        ),
                        validator: (String? value) {
                          if (value != _newPasswordController.text) {
                            return 'Hasła nie są identyczne.';
                          }

                          return null;
                        },
                      ),
                      const SizedBox(height: 24),
                      FilledButton.icon(
                        onPressed: _isSubmitting ? null : _submit,
                        icon: _isSubmitting
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              )
                            : const Icon(Icons.password),
                        label: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          child: Text(
                            _isSubmitting ? 'Zapisywanie...' : 'Zmień hasło',
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
