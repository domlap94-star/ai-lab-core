import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app_version/application/app_version_provider.dart';
import '../../app_version/domain/app_version_info.dart';
import '../application/auth_controller.dart';
import '../application/auth_state.dart';
import 'reset_password_page.dart';

class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key});

  @override
  ConsumerState<LoginPage> createState() {
    return _LoginPageState();
  }
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();

  final TextEditingController _usernameController = TextEditingController();

  final TextEditingController _passwordController = TextEditingController();

  bool _obscurePassword = true;

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();

    final FormState? form = _formKey.currentState;

    if (form == null || !form.validate()) {
      return;
    }

    await ref
        .read(authControllerProvider.notifier)
        .login(
          username: _usernameController.text,
          password: _passwordController.text,
        );
  }

  void _openResetPassword() {
    Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (_) => const ResetPasswordPage()));
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    final AsyncValue<AuthState> authState = ref.watch(authControllerProvider);

    final AsyncValue<AppVersionInfo> appVersion = ref.watch(appVersionProvider);

    final bool isLoading = authState.isLoading;
    final String? sessionNotice = authState.value?.notice;

    ref.listen<AsyncValue<AuthState>>(authControllerProvider, (
      AsyncValue<AuthState>? previous,
      AsyncValue<AuthState> next,
    ) {
      if (next.hasError && previous?.error != next.error) {
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(
            SnackBar(
              content: Text(_friendlyErrorMessage(next.error!)),
              backgroundColor: theme.colorScheme.error,
            ),
          );
      }
    });

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(32),
                  child: Form(
                    key: _formKey,
                    child: AutofillGroup(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: <Widget>[
                          SizedBox(
                            height: 96,
                            child: Image.asset(
                              'logo.png',
                              fit: BoxFit.contain,
                              semanticLabel: 'NEXT Stabil',
                            ),
                          ),
                          const SizedBox(height: 16),
                          Text(
                            'Zaloguj się, aby przejść do systemu.',
                            textAlign: TextAlign.center,
                            style: theme.textTheme.bodyLarge?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                          if (sessionNotice?.isNotEmpty == true) ...<Widget>[
                            const SizedBox(height: 16),
                            Semantics(
                              liveRegion: true,
                              child: Container(
                                key: const Key('session-expired-message'),
                                padding: const EdgeInsets.all(12),
                                decoration: BoxDecoration(
                                  color: theme.colorScheme.errorContainer,
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Text(
                                  sessionNotice!,
                                  textAlign: TextAlign.center,
                                  style: TextStyle(
                                    color: theme.colorScheme.onErrorContainer,
                                  ),
                                ),
                              ),
                            ),
                          ],
                          const SizedBox(height: 32),
                          TextFormField(
                            controller: _usernameController,
                            enabled: !isLoading,
                            autofocus: true,
                            autofillHints: const <String>[
                              AutofillHints.username,
                            ],
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Nazwa użytkownika',
                              hintText: 'Wpisz nazwę użytkownika',
                              prefixIcon: Icon(Icons.person_outline),
                              border: OutlineInputBorder(),
                            ),
                            validator: (String? value) {
                              if (value == null || value.trim().isEmpty) {
                                return 'Wprowadź nazwę użytkownika.';
                              }

                              return null;
                            },
                          ),
                          const SizedBox(height: 18),
                          TextFormField(
                            controller: _passwordController,
                            enabled: !isLoading,
                            obscureText: _obscurePassword,
                            autofillHints: const <String>[
                              AutofillHints.password,
                            ],
                            textInputAction: TextInputAction.done,
                            onFieldSubmitted: (_) {
                              if (!isLoading) {
                                _submit();
                              }
                            },
                            decoration: InputDecoration(
                              labelText: 'Hasło',
                              hintText: 'Wpisz hasło',
                              prefixIcon: const Icon(Icons.lock_outline),
                              border: const OutlineInputBorder(),
                              suffixIcon: IconButton(
                                tooltip: _obscurePassword
                                    ? 'Pokaż hasło'
                                    : 'Ukryj hasło',
                                onPressed: isLoading
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
                              if (value == null || value.isEmpty) {
                                return 'Wprowadź hasło.';
                              }

                              return null;
                            },
                          ),
                          Align(
                            alignment: Alignment.centerRight,
                            child: TextButton(
                              onPressed: isLoading ? null : _openResetPassword,
                              child: const Text('Nie pamiętasz hasła?'),
                            ),
                          ),
                          const SizedBox(height: 8),
                          FilledButton.icon(
                            onPressed: isLoading ? null : _submit,
                            icon: isLoading
                                ? const SizedBox(
                                    width: 18,
                                    height: 18,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                    ),
                                  )
                                : const Icon(Icons.login),
                            label: Padding(
                              padding: const EdgeInsets.symmetric(vertical: 14),
                              child: Text(
                                isLoading ? 'Logowanie...' : 'Zaloguj się',
                              ),
                            ),
                          ),
                          const SizedBox(height: 16),
                          Text(
                            appVersion.when(
                              data: (AppVersionInfo value) =>
                                  'NEXT Stabil ${value.displayVersion}',
                              loading: () => 'NEXT Stabil',
                              error: (_, _) => 'NEXT Stabil',
                            ),
                            textAlign: TextAlign.center,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
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
        ),
      ),
    );
  }

  String _friendlyErrorMessage(Object error) {
    if (error is AuthException) {
      return error.message;
    }

    if (error is DioException) {
      if (error.response?.statusCode == 401) {
        return 'Nieprawidłowa nazwa użytkownika lub hasło.';
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
          return 'Logowanie zostało anulowane.';
        case DioExceptionType.sendTimeout:
          return 'Przekroczono czas wysyłania żądania.';
        case DioExceptionType.badCertificate:
          return 'Certyfikat serwera nie został zaakceptowany.';
        case DioExceptionType.transformTimeout:
          return 'Przekroczono czas przetwarzania odpowiedzi.';
        case DioExceptionType.unknown:
          return error.message ?? 'Wystąpił nieznany błąd logowania.';
      }
    }

    if (error is FormatException) {
      return error.message;
    }

    return 'Nie udało się zalogować. Spróbuj ponownie.';
  }
}
