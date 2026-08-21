import 'package:ai_lab/features/clients/domain/client.dart';
import 'package:ai_lab/features/clients/presentation/client_edit_dialog.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('section editors expose only their canonical fields', (
    WidgetTester tester,
  ) async {
    final client = _client(
      primaryEmail: 'jan@example.com',
      primaryPhone: '+48 500 000 001',
      addresses: const <ClientAddress>[
        ClientAddress(
          id: 1,
          label: 'Siedziba',
          street: 'Polna',
          buildingNumber: '1',
          postalCode: '00-001',
          city: 'Warszawa',
          countryCode: 'PL',
          isPrimary: true,
        ),
      ],
    );

    await _pumpDialog(tester, client, section: ClientEditSection.name);
    expect(find.text('Edytuj nazwę klienta'), findsOneWidget);
    expect(find.text('Nazwa / imię i nazwisko'), findsOneWidget);
    expect(find.text('Typ klienta'), findsNothing);
    expect(find.text('NIP / tax ID'), findsNothing);

    await _pumpDialog(tester, client, section: ClientEditSection.basic);
    expect(find.text('Typ klienta'), findsOneWidget);
    expect(find.text('Branża'), findsOneWidget);
    expect(find.text('Nazwa / imię i nazwisko'), findsNothing);
    expect(find.text('Nazwa prawna'), findsNothing);

    await _pumpDialog(tester, client, section: ClientEditSection.registration);
    expect(find.text('Pełna nazwa prawna'), findsNothing);
    expect(find.text('Nazwa prawna'), findsOneWidget);
    expect(find.text('NIP / tax ID'), findsOneWidget);
    expect(find.text('Numer rejestracyjny'), findsOneWidget);
    expect(find.text('Dodaj telefon'), findsNothing);

    await _pumpDialog(tester, client, section: ClientEditSection.contact);
    expect(find.text('Dodaj e-mail'), findsOneWidget);
    expect(find.text('Dodaj telefon'), findsOneWidget);
    expect(find.text('Strona WWW'), findsOneWidget);
    expect(find.byKey(const Key('client-address-editor-0')), findsNothing);

    await _pumpDialog(tester, client, section: ClientEditSection.address);
    expect(find.byKey(const Key('client-address-editor-0')), findsOneWidget);
    expect(find.text('Dodaj e-mail'), findsNothing);
    expect(find.text('Data dodania'), findsNothing);

    await _pumpDialog(tester, client, section: ClientEditSection.system);
    expect(find.byKey(const Key('client-added-date-field')), findsOneWidget);
    expect(find.text('Nazwa / imię i nazwisko'), findsNothing);
    expect(find.text('Dodaj adres'), findsNothing);
  });

  testWidgets(
    'contact section preserves primary lists and address edits fields',
    (WidgetTester tester) async {
      final client = _client(
        primaryEmail: 'jan@example.com',
        primaryPhone: '+48 500 000 001',
        addresses: const <ClientAddress>[
          ClientAddress(
            id: 1,
            label: 'Siedziba',
            street: 'Stara',
            buildingNumber: '1',
            unitNumber: '2',
            postalCode: '00-001',
            city: 'Warszawa',
            countryCode: 'PL',
            isPrimary: true,
          ),
        ],
      );
      Map<String, dynamic>? result;
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => FilledButton(
              onPressed: () async {
                result = await showDialog<Map<String, dynamic>>(
                  context: context,
                  builder: (_) => ClientEditDialog(
                    client: client,
                    section: ClientEditSection.contact,
                  ),
                );
              },
              child: const Text('Kontakt'),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Kontakt'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextFormField, '+48 500 000 001'),
        '+48 600 000 002',
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Zapisz'));
      await tester.pumpAndSettle();
      expect(
        result?.keys,
        unorderedEquals(<String>['website', 'emails', 'phones']),
      );
      expect(
        (result?['phones'] as List<dynamic>).single['value'],
        '+48 600 000 002',
      );
      expect((result?['phones'] as List<dynamic>).single['is_primary'], isTrue);

      result = null;
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => FilledButton(
              onPressed: () async {
                result = await showDialog<Map<String, dynamic>>(
                  context: context,
                  builder: (_) => ClientEditDialog(
                    client: client,
                    section: ClientEditSection.address,
                  ),
                );
              },
              child: const Text('Adres'),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Adres'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Stara'),
        'Nowa',
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Zapisz'));
      await tester.pumpAndSettle();
      expect(result?.keys, unorderedEquals(<String>['addresses']));
      expect((result?['addresses'] as List<dynamic>).single['street'], 'Nowa');
    },
  );

  testWidgets('section save returns only visible fields', (
    WidgetTester tester,
  ) async {
    final client = _client(
      clientAddedAt: DateTime(2020, 5, 6),
      effectiveAddedDate: DateTime(2020, 5, 6),
      addresses: const <ClientAddress>[
        ClientAddress(
          id: 1,
          label: 'Siedziba',
          street: 'Polna',
          buildingNumber: '1',
          postalCode: '00-001',
          city: 'Warszawa',
          countryCode: 'PL',
          isPrimary: true,
        ),
      ],
    );
    final name = await _openAndSaveDialog(
      tester,
      client,
      section: ClientEditSection.name,
    );
    expect(name?.keys, unorderedEquals(<String>['name']));

    final address = await _openAndSaveDialog(
      tester,
      client,
      section: ClientEditSection.address,
    );
    expect(address?.keys, unorderedEquals(<String>['addresses']));
    expect((address?['addresses'] as List<dynamic>).single['street'], 'Polna');

    final system = await _openAndSaveDialog(
      tester,
      client,
      section: ClientEditSection.system,
    );
    expect(system, <String, dynamic>{'client_added_at': '2020-05-06'});
  });

  testWidgets('initializes separate email and phone contact controllers', (
    WidgetTester tester,
  ) async {
    await _pumpDialog(
      tester,
      _client(
        emails: const <ClientContactPoint>[
          ClientContactPoint(id: 1, value: 'jan@example.com', isPrimary: true),
          ClientContactPoint(
            id: 2,
            value: 'anna@example.com',
            isPrimary: false,
          ),
        ],
        phones: const <ClientContactPoint>[
          ClientContactPoint(id: 3, value: '+48 500 000 001', isPrimary: false),
          ClientContactPoint(id: 4, value: '+48 500 000 002', isPrimary: true),
        ],
      ),
    );

    expect(find.text('jan@example.com'), findsOneWidget);
    expect(find.text('anna@example.com'), findsOneWidget);
    expect(find.text('+48 500 000 001'), findsOneWidget);
    expect(find.text('+48 500 000 002'), findsOneWidget);
    expect(find.byType(Radio<int>), findsNWidgets(4));
  });

  testWidgets('falls back to legacy scalar contacts', (
    WidgetTester tester,
  ) async {
    await _pumpDialog(
      tester,
      _client(
        primaryEmail: 'legacy@example.com',
        primaryPhone: '+48 500 000 003',
      ),
    );

    expect(find.text('legacy@example.com'), findsOneWidget);
    expect(find.text('+48 500 000 003'), findsOneWidget);
    expect(find.byType(Radio<int>), findsNWidgets(2));
  });

  testWidgets('accepts null scalars and empty contact lists', (
    WidgetTester tester,
  ) async {
    await _pumpDialog(tester, _client());

    expect(find.byType(Radio<int>), findsNothing);
    expect(find.text('Dodaj e-mail'), findsOneWidget);
    expect(find.text('Dodaj telefon'), findsOneWidget);
  });

  testWidgets('shows multiple addresses and supports add remove and primary', (
    WidgetTester tester,
  ) async {
    await _pumpDialog(
      tester,
      _client(
        addresses: const <ClientAddress>[
          ClientAddress(
            id: 10,
            label: 'Siedziba',
            street: 'Pierwsza',
            city: 'Warszawa',
            countryCode: 'PL',
            isPrimary: true,
          ),
          ClientAddress(
            id: 11,
            label: 'Korespondencja',
            street: 'Druga',
            city: 'Kraków',
            countryCode: 'PL',
            isPrimary: false,
          ),
        ],
      ),
    );

    expect(find.byKey(const Key('client-address-editor-0')), findsOneWidget);
    expect(find.byKey(const Key('client-address-editor-1')), findsOneWidget);
    await tester.ensureVisible(find.byKey(const Key('add-client-address')));
    await tester.tap(find.byKey(const Key('add-client-address')));
    await tester.pump();
    expect(find.byKey(const Key('client-address-editor-2')), findsOneWidget);
  });

  testWidgets('long address editor does not overflow at mobile width', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await _pumpDialog(
      tester,
      _client(
        addresses: const <ClientAddress>[
          ClientAddress(
            id: 12,
            label: 'Bardzo długi opis adresu korespondencyjnego klienta',
            street: 'Aleja Bardzo Długiej Nazwy Ulicy Przemysłowej',
            buildingNumber: '123A',
            unitNumber: '456',
            postalCode: '00-001',
            city: 'Warszawa',
            countryCode: 'PL',
            isPrimary: true,
          ),
        ],
      ),
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('business added date can be cleared and opens a bounded picker', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(360, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await _pumpDialog(
      tester,
      _client(
        clientAddedAt: DateTime(2020, 5, 6),
        effectiveAddedDate: DateTime(2020, 5, 6),
      ),
    );

    expect(find.text('06.05.2020'), findsOneWidget);
    await tester.tap(find.byKey(const Key('client-added-date-clear')));
    await tester.pump();
    expect(
      find.text('Po zapisie: data źródłowa lub techniczna'),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const Key('client-added-date-picker')));
    await tester.pumpAndSettle();
    expect(find.text('Wybierz datę dodania klienta'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('save sends explicit ISO date and clear sends null', (
    WidgetTester tester,
  ) async {
    Map<String, dynamic>? result = await _openAndSaveDialog(
      tester,
      _client(
        clientAddedAt: DateTime(2020, 5, 6),
        effectiveAddedDate: DateTime(2020, 5, 6),
      ),
    );
    expect(result?['client_added_at'], '2020-05-06');

    result = await _openAndSaveDialog(
      tester,
      _client(
        clientAddedAt: DateTime(2020, 5, 6),
        effectiveAddedDate: DateTime(2020, 5, 6),
      ),
      clear: true,
    );
    expect(result?.containsKey('client_added_at'), isTrue);
    expect(result?['client_added_at'], isNull);
  });

  for (final double width in <double>[600, 1200]) {
    testWidgets('added date editor is responsive at ${width.toInt()} px', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = Size(width, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await _pumpDialog(tester, _client());
      expect(find.byKey(const Key('client-added-date-field')), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }
}

Future<void> _pumpDialog(
  WidgetTester tester,
  Client client, {
  ClientEditSection? section,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: ClientEditDialog(client: client, section: section),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<Map<String, dynamic>?> _openAndSaveDialog(
  WidgetTester tester,
  Client client, {
  bool clear = false,
  ClientEditSection? section,
}) async {
  Map<String, dynamic>? result;
  await tester.pumpWidget(
    MaterialApp(
      home: Builder(
        builder: (BuildContext context) => ElevatedButton(
          key: const Key('open-client-edit'),
          onPressed: () async {
            result = await showDialog<Map<String, dynamic>>(
              context: context,
              builder: (_) =>
                  ClientEditDialog(client: client, section: section),
            );
          },
          child: const Text('Open'),
        ),
      ),
    ),
  );
  await tester.tap(find.byKey(const Key('open-client-edit')));
  await tester.pumpAndSettle();
  if (clear) {
    await tester.tap(find.byKey(const Key('client-added-date-clear')));
    await tester.pump();
  }
  await tester.tap(find.widgetWithText(FilledButton, 'Zapisz'));
  await tester.pumpAndSettle();
  return result;
}

Client _client({
  String? primaryEmail,
  String? primaryPhone,
  DateTime? clientAddedAt,
  DateTime? effectiveAddedDate,
  List<ClientContactPoint> emails = const <ClientContactPoint>[],
  List<ClientContactPoint> phones = const <ClientContactPoint>[],
  List<ClientAddress> addresses = const <ClientAddress>[],
}) {
  return Client(
    id: 7,
    clientType: ClientType.person,
    name: 'Jan Kowalski',
    countryCode: 'PL',
    primaryEmail: primaryEmail,
    primaryPhone: primaryPhone,
    clientAddedAt: clientAddedAt,
    emails: emails,
    phones: phones,
    addresses: addresses,
    effectiveAddedDate: effectiveAddedDate ?? DateTime.utc(2026, 8, 16),
    createdAt: DateTime.utc(2026, 8, 16),
    updatedAt: DateTime.utc(2026, 8, 16),
  );
}
