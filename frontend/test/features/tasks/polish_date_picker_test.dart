import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('WorkItem date picker is Polish and Monday-first', (
    tester,
  ) async {
    DateTime? selected;
    await tester.pumpWidget(
      MaterialApp(
        locale: const Locale('pl', 'PL'),
        supportedLocales: const [Locale('pl', 'PL')],
        localizationsDelegates: const [
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () async {
                selected = await showDatePicker(
                  context: context,
                  locale: const Locale('pl', 'PL'),
                  initialDate: DateTime(2026, 8, 25),
                  firstDate: DateTime(2020),
                  lastDate: DateTime(2100),
                );
              },
              child: const Text('Początek'),
            ),
          ),
        ),
      ),
    );
    final localization = MaterialLocalizations.of(
      tester.element(find.text('Początek')),
    );
    expect(localization.firstDayOfWeekIndex, 1);
    expect(localization.cancelButtonLabel, 'Anuluj');
    await tester.tap(find.text('Początek'));
    await tester.pumpAndSettle();
    expect(find.text('Wybierz datę'), findsOneWidget);
    expect(find.text('Anuluj'), findsOneWidget);
    expect(find.textContaining('sie'), findsWidgets);
    await tester.tap(find.text('25').last);
    await tester.tap(find.text('OK'));
    await tester.pumpAndSettle();
    expect(selected, DateTime(2026, 8, 25));
  });
}
