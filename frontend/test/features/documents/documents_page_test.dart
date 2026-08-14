import 'package:ai_lab/features/documents/application/documents_controller.dart';
import 'package:ai_lab/features/documents/domain/document.dart';
import 'package:ai_lab/features/documents/domain/document_page.dart';
import 'package:ai_lab/features/documents/presentation/documents_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('documents page shows server result and debounced search', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(1200, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    _WidgetDocumentsController.searches.clear();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          documentsControllerProvider.overrideWith(
            _WidgetDocumentsController.new,
          ),
        ],
        child: const MaterialApp(home: DocumentsPage()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Repozytorium dokumentów'), findsOneWidget);
    expect(find.text('faktura.pdf'), findsOneWidget);
    expect(find.text('5899 dokumentów'), findsOneWidget);
    expect(find.text('Strona 1 z 118'), findsOneWidget);

    await tester.enterText(find.byKey(const Key('document-search')), 'umowa');
    await tester.pump(const Duration(milliseconds: 399));
    expect(_WidgetDocumentsController.searches, isEmpty);
    await tester.pump(const Duration(milliseconds: 1));
    await tester.pumpAndSettle();
    expect(_WidgetDocumentsController.searches, <String>['umowa']);
  });
}

class _WidgetDocumentsController extends DocumentsController {
  static final List<String> searches = <String>[];

  final RepositoryDocument document = RepositoryDocument(
    id: 42,
    originalFilename: 'faktura.pdf',
    contentType: 'application/pdf',
    fileSize: 2048,
    sourceType: 'gmail',
    clientId: 2152,
    clientName: 'Klient Testowy',
    processingStatus: 'processed',
    metadataStatus: 'complete',
    matchStatus: 'matched',
    archiveDepth: 0,
    createdAt: DateTime.utc(2026, 8, 14),
    updatedAt: DateTime.utc(2026, 8, 14),
  );

  @override
  Future<DocumentPage> build() async {
    return DocumentPage(
      items: <RepositoryDocument>[document],
      total: 5899,
      skip: 0,
      limit: 50,
    );
  }

  @override
  Future<void> search(String query) async {
    searches.add(query);
  }
}
