import 'package:ai_lab/app/app.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('AI LAB dashboard and navigation are displayed', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(1440, 900);
    tester.view.devicePixelRatio = 1.0;

    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(const ProviderScope(child: App()));

    await tester.pumpAndSettle();

    expect(find.text('AI LAB'), findsOneWidget);
    expect(find.text('Dashboard'), findsWidgets);
    expect(find.text('Aktywne sprawy'), findsOneWidget);
    expect(find.text('Dokumenty'), findsOneWidget);
    expect(find.text('Asystent AI'), findsOneWidget);
  });
}
