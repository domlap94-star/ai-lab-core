import 'package:ai_lab/features/clients/application/client_workflow_status.dart';
import 'package:ai_lab/features/clients/presentation/searchable_client_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('workflow status values share the backend API contract', () {
    expect(ClientWorkflowState.obsolete.apiValue, 'obsolete');
    expect(ClientWorkflowState.inspection.apiValue, 'inspection');
    expect(
      ClientWorkflowState.fromApi('phone_contact').label,
      'Kontakt telefoniczny',
    );
    expect(
      ClientWorkflowState.fromApi('unknown'),
      ClientWorkflowState.untouched,
    );
  });

  testWidgets('searchable client picker shows selection and can clear it', (
    tester,
  ) async {
    ClientPickerSelection? changed;
    await tester.binding.setSurfaceSize(const Size(360, 800));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          home: Scaffold(
            body: SearchableClientPicker(
              initialClientId: 42,
              initialClientName: 'Przykładowy klient',
              onChanged: (value) => changed = value,
            ),
          ),
        ),
      ),
    );

    expect(find.text('Przykładowy klient'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.tap(find.byKey(const Key('client-picker-clear')));
    await tester.pump();
    expect(changed, isNull);
    expect(find.byKey(const Key('searchable-client-picker')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
