import 'dart:convert';
import 'dart:typed_data';

import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/documents/application/document_open_service.dart';
import 'package:ai_lab/features/documents/application/documents_providers.dart';
import 'package:ai_lab/features/documents/application/documents_repository.dart';
import 'package:ai_lab/features/documents/data/document_content.dart';
import 'package:ai_lab/features/documents/domain/document.dart';
import 'package:ai_lab/features/documents/domain/document_filters.dart';
import 'package:ai_lab/features/documents/domain/document_page.dart';
import 'package:ai_lab/features/documents/presentation/document_media_preview.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

final Uint8List _png = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
);

const AuthSession _session = AuthSession(
  accessToken: 'preview-token',
  tokenType: 'Bearer',
);

final RepositoryDocument _imageDocument = RepositoryDocument(
  id: 7,
  originalFilename: 'photo.webp',
  contentType: 'image/webp',
  fileSize: 4096,
  sourceType: 'camera_photo',
  processingStatus: 'processed',
  metadataStatus: 'complete',
  matchStatus: 'unmatched',
  archiveDepth: 0,
  createdAt: DateTime.utc(2026, 8, 20),
  updatedAt: DateTime.utc(2026, 8, 20),
);

class _AuthController extends AuthController {
  @override
  Future<AuthState> build() async =>
      const AuthState(session: _session, user: null);
}

class _Repository extends DocumentsRepository {
  int contentCalls = 0;

  @override
  Future<DocumentPage> fetchDocuments({
    required AuthSession session,
    required DocumentFilters filters,
    String search = '',
    int skip = 0,
    int limit = 50,
  }) => throw UnimplementedError();

  @override
  Future<RepositoryDocument> fetchDocument({
    required AuthSession session,
    required int documentId,
  }) => throw UnimplementedError();

  @override
  Future<DocumentContent> fetchContent({
    required AuthSession session,
    required RepositoryDocument document,
    void Function(int received, int total)? onProgress,
  }) async {
    contentCalls++;
    return DocumentContent(
      bytes: _png,
      fileName: document.displayName,
      contentType: 'image/png',
    );
  }
}

void main() {
  test('image contract supports JPEG PNG WebP and excludes HEIC/PDF', () {
    expect(isInternalPreviewImage('image/jpeg', 'a.jpg'), isTrue);
    expect(isInternalPreviewImage('image/png', 'a.png'), isTrue);
    expect(isInternalPreviewImage('image/webp', 'a.webp'), isTrue);
    expect(
      isInternalPreviewImage('application/octet-stream', 'a.jpeg'),
      isTrue,
    );
    expect(isInternalPreviewImage('image/heic', 'a.heic'), isFalse);
    expect(isInternalPreviewImage('image/heif', 'a.heif'), isFalse);
    expect(isInternalPreviewImage('application/pdf', 'a.pdf'), isFalse);
  });

  testWidgets('thumbnail is 100 logical pixels and opens from its tap target', (
    WidgetTester tester,
  ) async {
    bool opened = false;
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          documentThumbnailProvider(7).overrideWith((_) async => _png),
        ],
        child: MaterialApp(
          home: Scaffold(
            body: DocumentImageThumbnail(
              documentId: 7,
              contentType: 'image/jpeg',
              fileName: 'photo.jpg',
              onOpen: () => opened = true,
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    final Finder target = find.byKey(
      const ValueKey<String>('document-thumbnail-7'),
    );
    expect(target, findsOneWidget);
    expect(tester.getSize(target).width, documentThumbnailWidth);
    expect(find.byType(Image), findsOneWidget);
    await tester.tap(target);
    expect(opened, isTrue);
  });

  testWidgets('thumbnail failure stays in-app with bounded placeholder', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          documentThumbnailProvider(7).overrideWith(
            (_) => Future<Uint8List>.error(StateError('synthetic')),
          ),
        ],
        child: MaterialApp(
          home: Scaffold(
            body: DocumentImageThumbnail(
              documentId: 7,
              contentType: 'image/png',
              fileName: 'photo.png',
              onOpen: () {},
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byIcon(Icons.broken_image_outlined), findsOneWidget);
  });

  testWidgets(
    'supported image uses internal zoom viewer and never external opener',
    (WidgetTester tester) async {
      final _Repository repository = _Repository();
      int externalCalls = 0;
      final ProviderContainer container = ProviderContainer(
        overrides: [
          authControllerProvider.overrideWith(_AuthController.new),
          documentsRepositoryProvider.overrideWithValue(repository),
          documentOpenServiceProvider.overrideWithValue(
            DocumentOpenService(
              repository,
              opener: (_, _) async => externalCalls++,
            ),
          ),
        ],
      );
      addTearDown(container.dispose);
      await container.read(authControllerProvider.future);
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Consumer(
              builder: (context, ref, _) => Scaffold(
                body: FilledButton(
                  onPressed: () =>
                      openDocumentMedia(context, ref, _imageDocument),
                  child: const Text('Otwórz obraz'),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Otwórz obraz'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('internal-image-viewer')), findsOneWidget);
      expect(
        find.byKey(const Key('internal-image-interactive-viewer')),
        findsOneWidget,
      );
      expect(repository.contentCalls, 1);
      expect(externalCalls, 0);
      await tester.tap(find.byTooltip('Zamknij podgląd'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('internal-image-viewer')), findsNothing);
    },
  );

  for (final double width in <double>[360, 390, 600, 1200]) {
    testWidgets('internal viewer is responsive at ${width.toInt()}', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = Size(width, 800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          home: InternalImageViewer(
            document: _imageDocument,
            load: () async => DocumentContent(
              bytes: _png,
              fileName: 'photo.webp',
              contentType: 'image/png',
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byType(InteractiveViewer), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }
}
