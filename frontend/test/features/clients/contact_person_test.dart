import 'package:ai_lab/features/clients/data/client_response.dart';
import 'package:ai_lab/features/clients/domain/client.dart';
import 'package:ai_lab/features/clients/presentation/contact_person_dialog.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test(
    'ContactPerson response keeps person ownership separate from generic contacts',
    () {
      final response = ClientResponse.fromJson(<String, dynamic>{
        'id': 10,
        'client_type': 'company',
        'name': 'Fixture',
        'country_code': 'PL',
        'emails': <Map<String, dynamic>>[
          <String, dynamic>{
            'id': 1,
            'value': 'office@example.invalid',
            'is_primary': true,
            'origin': 'manual',
          },
          <String, dynamic>{
            'id': 2,
            'value': 'jan@example.invalid',
            'is_primary': false,
            'origin': 'manual',
            'contact_person_id': 7,
          },
        ],
        'phones': const <Map<String, dynamic>>[],
        'addresses': const <Map<String, dynamic>>[],
        'contact_persons': <Map<String, dynamic>>[
          <String, dynamic>{
            'id': 7,
            'client_id': 10,
            'display_name': 'Jan Kowalski',
            'role': 'Inżynier',
            'is_preferred': true,
            'is_decision_maker': true,
            'position': 0,
            'origin': 'manual',
            'created_at': '2026-08-22T10:00:00Z',
            'updated_at': '2026-08-22T10:00:00Z',
            'contact_points': <Map<String, dynamic>>[
              <String, dynamic>{
                'id': 2,
                'value': 'jan@example.invalid',
                'is_primary': false,
                'origin': 'manual',
                'contact_person_id': 7,
              },
            ],
          },
        ],
        'created_at': '2026-08-22T10:00:00Z',
        'updated_at': '2026-08-22T10:00:00Z',
      }).toDomain();
      expect(response.contactPersons.single.displayName, 'Jan Kowalski');
      expect(
        response.contactPersons.single.emails.single.value,
        'jan@example.invalid',
      );
      expect(response.genericEmails.single.value, 'office@example.invalid');
    },
  );

  testWidgets('dialog validates name and returns bounded person payload', (
    tester,
  ) async {
    final client = _client();
    Map<String, dynamic>? result;
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: FilledButton(
              onPressed: () async {
                result = await showDialog<Map<String, dynamic>>(
                  context: context,
                  builder: (_) => ContactPersonDialog(client: client),
                );
              },
              child: const Text('Otwórz'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Otwórz'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('contact-person-save')));
    await tester.pump();
    expect(find.text('Nazwa osoby jest wymagana.'), findsOneWidget);
    await tester.enterText(
      find.byKey(const Key('contact-person-name')),
      '  Jan   Kowalski ',
    );
    await tester.tap(find.byType(CheckboxListTile).first);
    await tester.tap(find.byKey(const Key('contact-person-preferred')));
    await tester.tap(find.byKey(const Key('contact-person-save')));
    await tester.pumpAndSettle();
    expect(result?['display_name'], 'Jan Kowalski');
    expect(result?['is_preferred'], true);
    expect(result?['contact_point_ids'], <int>[1]);
  });

  for (final width in <double>[360, 390, 600, 1200]) {
    testWidgets('ContactPerson dialog has no overflow at ${width.toInt()} px', (
      tester,
    ) async {
      tester.view.physicalSize = Size(width, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(home: ContactPersonDialog(client: _client())),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.text('Dodaj osobę kontaktową'), findsOneWidget);
    });
  }
}

Client _client() => Client(
  id: 10,
  clientType: ClientType.company,
  name: 'Fixture',
  countryCode: 'PL',
  emails: const <ClientContactPoint>[
    ClientContactPoint(id: 1, value: 'office@example.invalid', isPrimary: true),
  ],
  effectiveAddedDate: DateTime.utc(2026, 8, 22),
  createdAt: DateTime.utc(2026, 8, 22),
  updatedAt: DateTime.utc(2026, 8, 22),
);
