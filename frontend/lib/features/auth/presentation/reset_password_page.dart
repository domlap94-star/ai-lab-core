import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../application/account_providers.dart';

class ResetPasswordPage extends ConsumerStatefulWidget {
  const ResetPasswordPage({super.key});

  @override
  ConsumerState<ResetPasswordPage> createState() {
    return _ResetPasswordPageState();
  }
}

class _ResetPasswordPageState extends ConsumerState<ResetPasswordPage> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();

  final TextEditingController _identifierController = TextEditingController();

  bool _isSubmitting = false;

  @override
  void dispose() {
    _identifierController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();

    if (_formKey.currentState?.validate() != true) {
      return;
    }

    setState(() {
      _isSubmitting = true;
    });

    try {
      await ref
          .read(accountApiProvider)
          .requestPasswordReset(identifier: _identifierController.text);

      if (!mounted) {
        return;
      }

      _showMessage(
        'Jeżeli konto istnieje, żądanie resetu '
        'hasła zostało przyjęte.',
      );
    } on DioException catch (error) {
      if (!mounted) {
        return;
      }

      final String message = error.response?.statusCode == 404
          ? 'Frontend resetu hasła jest gotowy. '
                'Endpoint backendowy zostanie uruchomiony '
                'po zakończeniu batcha klientów.'
          : 'Nie udało się wysłać żądania resetu hasła.';

      _showMessage(message, isError: true);
    } finally {
      if (mounted) {
        setState(() {
          _isSubmitting = false;
        });
      }
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
    return Scaffold(
      appBar: AppBar(title: const Text('Zresetuj hasło')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: <Widget>[
                      SizedBox(
                        height: 84,
                        child: Image.asset(
                          'logo.png',
                          fit: BoxFit.contain,
                          semanticLabel: 'AI-Lab',
                        ),
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'Odzyskiwanie dostępu',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Podaj nazwę użytkownika lub adres '
                        'e-mail. Odpowiedź systemu nie ujawni, '
                        'czy konto istnieje.',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                      const SizedBox(height: 24),
                      TextFormField(
                        controller: _identifierController,
                        enabled: !_isSubmitting,
                        autofocus: true,
                        textInputAction: TextInputAction.done,
                        onFieldSubmitted: (_) {
                          if (!_isSubmitting) {
                            _submit();
                          }
                        },
                        decoration: const InputDecoration(
                          labelText: 'Nazwa użytkownika lub e-mail',
                          prefixIcon: Icon(Icons.person_search_outlined),
                          border: OutlineInputBorder(),
                        ),
                        validator: (String? value) {
                          if (value == null || value.trim().isEmpty) {
                            return 'Wprowadź nazwę użytkownika '
                                'lub adres e-mail.';
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
                            : const Icon(Icons.send_outlined),
                        label: const Padding(
                          padding: EdgeInsets.symmetric(vertical: 12),
                          child: Text('Poproś o reset hasła'),
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
