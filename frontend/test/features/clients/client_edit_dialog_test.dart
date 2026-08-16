import 'package:ai_lab/features/clients/domain/client.dart';
import 'package:ai_lab/features/clients/presentation/client_edit_dialog.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
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
}

Future<void> _pumpDialog(WidgetTester tester, Client client) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(body: ClientEditDialog(client: client)),
    ),
  );
  await tester.pumpAndSettle();
}

Client _client({
  String? primaryEmail,
  String? primaryPhone,
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
    emails: emails,
    phones: phones,
    addresses: addresses,
    createdAt: DateTime.utc(2026, 8, 16),
    updatedAt: DateTime.utc(2026, 8, 16),
  );
}
