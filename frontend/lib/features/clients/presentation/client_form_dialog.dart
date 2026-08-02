import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../application/clients_controller.dart';
import '../application/clients_providers.dart';
import '../data/client_create_request.dart';
import '../domain/client.dart';
import '../domain/industry.dart';

class ClientFormDialog extends ConsumerStatefulWidget {
  const ClientFormDialog({super.key});

  @override
  ConsumerState<ClientFormDialog> createState() => _ClientFormDialogState();
}

class _ClientFormDialogState extends ConsumerState<ClientFormDialog> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();

  final TextEditingController _nameController = TextEditingController();
  final TextEditingController _legalNameController = TextEditingController();
  final TextEditingController _taxIdController = TextEditingController();
  final TextEditingController _registrationNumberController =
      TextEditingController();
  final TextEditingController _websiteController = TextEditingController();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _phoneController = TextEditingController();
  final TextEditingController _streetController = TextEditingController();
  final TextEditingController _buildingNumberController =
      TextEditingController();
  final TextEditingController _unitNumberController = TextEditingController();
  final TextEditingController _postalCodeController = TextEditingController();
  final TextEditingController _cityController = TextEditingController();
  final TextEditingController _countryCodeController = TextEditingController(
    text: 'PL',
  );
  final TextEditingController _notesController = TextEditingController();

  ClientType _clientType = ClientType.company;
  int? _industryId;
  bool _isSubmitting = false;

  @override
  void dispose() {
    _nameController.dispose();
    _legalNameController.dispose();
    _taxIdController.dispose();
    _registrationNumberController.dispose();
    _websiteController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _streetController.dispose();
    _buildingNumberController.dispose();
    _unitNumberController.dispose();
    _postalCodeController.dispose();
    _cityController.dispose();
    _countryCodeController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();

    final FormState? form = _formKey.currentState;

    if (form == null || !form.validate()) {
      return;
    }

    setState(() {
      _isSubmitting = true;
    });

    try {
      final ClientCreateRequest request = ClientCreateRequest(
        clientType: _clientType,
        name: _nameController.text,
        legalName: _legalNameController.text,
        taxId: _taxIdController.text,
        registrationNumber: _registrationNumberController.text,
        industryId: _industryId,
        website: _websiteController.text,
        primaryEmail: _emailController.text,
        primaryPhone: _phoneController.text,
        street: _streetController.text,
        buildingNumber: _buildingNumberController.text,
        unitNumber: _unitNumberController.text,
        postalCode: _postalCodeController.text,
        city: _cityController.text,
        countryCode: _countryCodeController.text,
        notes: _notesController.text,
      );

      final Client createdClient = await ref
          .read(clientsControllerProvider.notifier)
          .createClient(request);

      if (!mounted) {
        return;
      }

      Navigator.of(context).pop<Client>(createdClient);
    } catch (error) {
      if (!mounted) {
        return;
      }

      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          SnackBar(
            content: Text(_friendlyErrorMessage(error)),
            backgroundColor: Theme.of(context).colorScheme.error,
          ),
        );
    } finally {
      if (mounted) {
        setState(() {
          _isSubmitting = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final AsyncValue<List<Industry>> industriesValue = ref.watch(
      industriesProvider,
    );

    return Dialog(
      insetPadding: const EdgeInsets.all(24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 900, maxHeight: 820),
        child: Column(
          children: <Widget>[
            Padding(
              padding: const EdgeInsets.fromLTRB(28, 24, 20, 20),
              child: Row(
                children: <Widget>[
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      color: theme.colorScheme.primaryContainer,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      Icons.person_add_alt_1,
                      color: theme.colorScheme.onPrimaryContainer,
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Text(
                      'Dodaj klienta',
                      style: theme.textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  IconButton(
                    tooltip: 'Zamknij',
                    onPressed: _isSubmitting
                        ? null
                        : () {
                            Navigator.of(context).pop();
                          },
                    icon: const Icon(Icons.close),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            Expanded(
              child: Form(
                key: _formKey,
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(28),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      _SectionTitle(
                        title: 'Dane podstawowe',
                        icon: Icons.badge_outlined,
                      ),
                      const SizedBox(height: 16),
                      _ResponsiveFields(
                        children: <Widget>[
                          DropdownButtonFormField<ClientType>(
                            initialValue: _clientType,
                            decoration: const InputDecoration(
                              labelText: 'Typ klienta',
                              prefixIcon: Icon(Icons.category_outlined),
                              border: OutlineInputBorder(),
                            ),
                            items: ClientType.values
                                .map(
                                  (ClientType type) =>
                                      DropdownMenuItem<ClientType>(
                                        value: type,
                                        child: Text(type.displayName),
                                      ),
                                )
                                .toList(),
                            onChanged: _isSubmitting
                                ? null
                                : (ClientType? value) {
                                    if (value == null) {
                                      return;
                                    }

                                    setState(() {
                                      _clientType = value;
                                    });
                                  },
                          ),
                          TextFormField(
                            controller: _nameController,
                            enabled: !_isSubmitting,
                            autofocus: true,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Nazwa klienta',
                              prefixIcon: Icon(Icons.person_outline),
                              border: OutlineInputBorder(),
                            ),
                            validator: (String? value) {
                              if (value == null || value.trim().isEmpty) {
                                return 'Wprowadź nazwę klienta.';
                              }

                              if (value.trim().length > 255) {
                                return 'Nazwa może mieć maksymalnie 255 znaków.';
                              }

                              return null;
                            },
                          ),
                          TextFormField(
                            controller: _legalNameController,
                            enabled: !_isSubmitting,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Pełna nazwa prawna',
                              prefixIcon: Icon(Icons.business_outlined),
                              border: OutlineInputBorder(),
                            ),
                          ),
                          _IndustryField(
                            industriesValue: industriesValue,
                            selectedIndustryId: _industryId,
                            enabled: !_isSubmitting,
                            onChanged: (int? value) {
                              setState(() {
                                _industryId = value;
                              });
                            },
                            onRetry: () {
                              ref.invalidate(industriesProvider);
                            },
                          ),
                        ],
                      ),
                      const SizedBox(height: 30),
                      _SectionTitle(
                        title: 'Dane rejestrowe',
                        icon: Icons.assignment_outlined,
                      ),
                      const SizedBox(height: 16),
                      _ResponsiveFields(
                        children: <Widget>[
                          TextFormField(
                            controller: _taxIdController,
                            enabled: !_isSubmitting,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'NIP lub identyfikator podatkowy',
                              prefixIcon: Icon(Icons.numbers),
                              border: OutlineInputBorder(),
                            ),
                          ),
                          TextFormField(
                            controller: _registrationNumberController,
                            enabled: !_isSubmitting,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Numer rejestracyjny',
                              hintText: 'REGON, KRS lub inny numer',
                              prefixIcon: Icon(Icons.app_registration),
                              border: OutlineInputBorder(),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 30),
                      _SectionTitle(
                        title: 'Kontakt',
                        icon: Icons.contact_phone_outlined,
                      ),
                      const SizedBox(height: 16),
                      _ResponsiveFields(
                        children: <Widget>[
                          TextFormField(
                            controller: _emailController,
                            enabled: !_isSubmitting,
                            keyboardType: TextInputType.emailAddress,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'E-mail',
                              prefixIcon: Icon(Icons.email_outlined),
                              border: OutlineInputBorder(),
                            ),
                            validator: _validateEmail,
                          ),
                          TextFormField(
                            controller: _phoneController,
                            enabled: !_isSubmitting,
                            keyboardType: TextInputType.phone,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Telefon',
                              prefixIcon: Icon(Icons.phone_outlined),
                              border: OutlineInputBorder(),
                            ),
                          ),
                          TextFormField(
                            controller: _websiteController,
                            enabled: !_isSubmitting,
                            keyboardType: TextInputType.url,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Strona internetowa',
                              hintText: 'https://example.com',
                              prefixIcon: Icon(Icons.language),
                              border: OutlineInputBorder(),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 30),
                      _SectionTitle(
                        title: 'Adres',
                        icon: Icons.location_on_outlined,
                      ),
                      const SizedBox(height: 16),
                      _ResponsiveFields(
                        children: <Widget>[
                          TextFormField(
                            controller: _streetController,
                            enabled: !_isSubmitting,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Ulica',
                              prefixIcon: Icon(Icons.signpost_outlined),
                              border: OutlineInputBorder(),
                            ),
                          ),
                          TextFormField(
                            controller: _buildingNumberController,
                            enabled: !_isSubmitting,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Numer budynku',
                              prefixIcon: Icon(Icons.home_outlined),
                              border: OutlineInputBorder(),
                            ),
                          ),
                          TextFormField(
                            controller: _unitNumberController,
                            enabled: !_isSubmitting,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Numer lokalu',
                              prefixIcon: Icon(Icons.door_front_door_outlined),
                              border: OutlineInputBorder(),
                            ),
                          ),
                          TextFormField(
                            controller: _postalCodeController,
                            enabled: !_isSubmitting,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Kod pocztowy',
                              prefixIcon: Icon(
                                Icons.local_post_office_outlined,
                              ),
                              border: OutlineInputBorder(),
                            ),
                          ),
                          TextFormField(
                            controller: _cityController,
                            enabled: !_isSubmitting,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Miejscowość',
                              prefixIcon: Icon(Icons.location_city_outlined),
                              border: OutlineInputBorder(),
                            ),
                          ),
                          TextFormField(
                            controller: _countryCodeController,
                            enabled: !_isSubmitting,
                            textCapitalization: TextCapitalization.characters,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Kod kraju',
                              hintText: 'PL',
                              prefixIcon: Icon(Icons.flag_outlined),
                              border: OutlineInputBorder(),
                            ),
                            validator: (String? value) {
                              final String normalized =
                                  value?.trim().toUpperCase() ?? '';

                              if (normalized.length != 2) {
                                return 'Kod kraju musi mieć dokładnie 2 znaki.';
                              }

                              return null;
                            },
                          ),
                        ],
                      ),
                      const SizedBox(height: 30),
                      _SectionTitle(
                        title: 'Notatki',
                        icon: Icons.notes_outlined,
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _notesController,
                        enabled: !_isSubmitting,
                        minLines: 4,
                        maxLines: 8,
                        decoration: const InputDecoration(
                          labelText: 'Dodatkowe informacje',
                          alignLabelWithHint: true,
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.all(20),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: <Widget>[
                  TextButton(
                    onPressed: _isSubmitting
                        ? null
                        : () {
                            Navigator.of(context).pop();
                          },
                    child: const Text('Anuluj'),
                  ),
                  const SizedBox(width: 12),
                  FilledButton.icon(
                    onPressed: _isSubmitting ? null : _submit,
                    icon: _isSubmitting
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.save_outlined),
                    label: Text(
                      _isSubmitting ? 'Zapisywanie...' : 'Dodaj klienta',
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  String? _validateEmail(String? value) {
    final String email = value?.trim() ?? '';

    if (email.isEmpty) {
      return null;
    }

    final RegExp emailPattern = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

    if (!emailPattern.hasMatch(email)) {
      return 'Wprowadź poprawny adres e-mail.';
    }

    return null;
  }

  String _friendlyErrorMessage(Object error) {
    if (error is ClientsAuthenticationException) {
      return error.message;
    }

    if (error is DioException) {
      final int? statusCode = error.response?.statusCode;

      if (statusCode == 401) {
        return 'Sesja użytkownika wygasła. Zaloguj się ponownie.';
      }

      if (statusCode == 409) {
        return 'Aktywny klient z tym numerem NIP już istnieje.';
      }

      if (statusCode == 422) {
        return _validationErrorMessage(error.response?.data);
      }

      if (statusCode != null && statusCode >= 500) {
        return 'Serwer nie może teraz utworzyć klienta.';
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
          return 'Tworzenie klienta zostało anulowane.';
        case DioExceptionType.sendTimeout:
          return 'Przekroczono czas wysyłania danych.';
        case DioExceptionType.badCertificate:
          return 'Certyfikat serwera nie został zaakceptowany.';
        case DioExceptionType.transformTimeout:
          return 'Przekroczono czas przetwarzania odpowiedzi.';
        case DioExceptionType.unknown:
          return error.message ?? 'Wystąpił nieznany błąd.';
      }
    }

    if (error is FormatException) {
      return error.message;
    }

    return 'Nie udało się utworzyć klienta.';
  }

  String _validationErrorMessage(dynamic data) {
    if (data is Map) {
      final dynamic detail = data['detail'];

      if (detail is String && detail.trim().isNotEmpty) {
        return detail;
      }

      if (detail is List && detail.isNotEmpty) {
        final dynamic firstError = detail.first;

        if (firstError is Map) {
          final String? message = firstError['msg']?.toString();

          if (message != null && message.trim().isNotEmpty) {
            return message;
          }
        }
      }
    }

    return 'Dane klienta nie przeszły walidacji.';
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.title, required this.icon});

  final String title;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return Row(
      children: <Widget>[
        Icon(icon, size: 22, color: theme.colorScheme.primary),
        const SizedBox(width: 10),
        Text(
          title,
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}

class _ResponsiveFields extends StatelessWidget {
  const _ResponsiveFields({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final bool useTwoColumns = constraints.maxWidth >= 680;

        if (!useTwoColumns) {
          return Column(
            children: children
                .map(
                  (Widget child) => Padding(
                    padding: const EdgeInsets.only(bottom: 16),
                    child: child,
                  ),
                )
                .toList(),
          );
        }

        return Wrap(
          spacing: 16,
          runSpacing: 16,
          children: children
              .map(
                (Widget child) => SizedBox(
                  width: (constraints.maxWidth - 16) / 2,
                  child: child,
                ),
              )
              .toList(),
        );
      },
    );
  }
}

class _IndustryField extends StatelessWidget {
  const _IndustryField({
    required this.industriesValue,
    required this.selectedIndustryId,
    required this.enabled,
    required this.onChanged,
    required this.onRetry,
  });

  final AsyncValue<List<Industry>> industriesValue;
  final int? selectedIndustryId;
  final bool enabled;
  final ValueChanged<int?> onChanged;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return industriesValue.when(
      loading: () {
        return const InputDecorator(
          decoration: InputDecoration(
            labelText: 'Branża',
            prefixIcon: Icon(Icons.business_center_outlined),
            border: OutlineInputBorder(),
          ),
          child: Row(
            children: <Widget>[
              SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
              SizedBox(width: 12),
              Text('Pobieranie branż...'),
            ],
          ),
        );
      },
      error: (Object error, StackTrace stackTrace) {
        return InputDecorator(
          decoration: const InputDecoration(
            labelText: 'Branża',
            prefixIcon: Icon(Icons.error_outline),
            border: OutlineInputBorder(),
          ),
          child: Row(
            children: <Widget>[
              const Expanded(child: Text('Nie udało się pobrać branż.')),
              IconButton(
                tooltip: 'Spróbuj ponownie',
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
        );
      },
      data: (List<Industry> industries) {
        final List<Industry> activeIndustries =
            industries
                .where((Industry industry) => industry.isActive)
                .toList(growable: false)
              ..sort(
                (Industry first, Industry second) =>
                    first.name.compareTo(second.name),
              );

        return DropdownButtonFormField<int>(
          initialValue: selectedIndustryId,
          isExpanded: true,
          decoration: const InputDecoration(
            labelText: 'Branża',
            prefixIcon: Icon(Icons.business_center_outlined),
            border: OutlineInputBorder(),
          ),
          items: activeIndustries
              .map(
                (Industry industry) => DropdownMenuItem<int>(
                  value: industry.id,
                  child: Text(industry.name, overflow: TextOverflow.ellipsis),
                ),
              )
              .toList(),
          onChanged: enabled ? onChanged : null,
        );
      },
    );
  }
}
