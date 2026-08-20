import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/application/auth_controller.dart';
import '../application/documents_providers.dart';
import '../data/document_content.dart';
import '../domain/document.dart';

const double documentThumbnailWidth = 100;
const double documentThumbnailHeight = 76;

bool isInternalPreviewImage(String contentType, String? filename) {
  final String mime = contentType.split(';').first.trim().toLowerCase();
  if (const <String>{'image/jpeg', 'image/png', 'image/webp'}.contains(mime)) {
    return true;
  }
  if (mime.isNotEmpty && mime != 'application/octet-stream') return false;
  final String name = (filename ?? '').toLowerCase();
  return const <String>{'.jpg', '.jpeg', '.png', '.webp'}.any(name.endsWith);
}

class DocumentImageThumbnail extends ConsumerWidget {
  const DocumentImageThumbnail({
    required this.documentId,
    required this.contentType,
    required this.fileName,
    required this.onOpen,
    this.width = documentThumbnailWidth,
    super.key,
  });

  final int documentId;
  final String contentType;
  final String fileName;
  final VoidCallback onOpen;
  final double width;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!isInternalPreviewImage(contentType, fileName)) {
      return const Icon(Icons.description_outlined);
    }
    final AsyncValue<Uint8List> thumbnail = ref.watch(
      documentThumbnailProvider(documentId),
    );
    return Semantics(
      button: true,
      label: 'Otwórz obraz $fileName',
      child: Tooltip(
        message: 'Otwórz obraz $fileName',
        child: Material(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(8),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            key: ValueKey<String>('document-thumbnail-$documentId'),
            onTap: onOpen,
            child: SizedBox(
              width: width,
              height: documentThumbnailHeight,
              child: thumbnail.when(
                loading: () => const Center(
                  child: SizedBox.square(
                    dimension: 22,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ),
                error: (_, _) =>
                    const Center(child: Icon(Icons.broken_image_outlined)),
                data: (Uint8List bytes) => Image.memory(
                  bytes,
                  fit: BoxFit.contain,
                  cacheWidth: 200,
                  gaplessPlayback: true,
                  errorBuilder: (_, _, _) =>
                      const Center(child: Icon(Icons.broken_image_outlined)),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

Future<void> openDocumentMedia(
  BuildContext context,
  WidgetRef ref,
  RepositoryDocument document, {
  void Function(int received, int total)? onProgress,
}) async {
  final session = requireDocumentSessionFromAuth(
    ref.read(authControllerProvider),
  );
  if (isInternalPreviewImage(document.contentType, document.displayName)) {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        fullscreenDialog: true,
        builder: (_) => InternalImageViewer(
          document: document,
          load: () => ref
              .read(documentsRepositoryProvider)
              .fetchContent(
                session: session,
                document: document,
                onProgress: onProgress,
              ),
        ),
      ),
    );
    return;
  }
  await ref
      .read(documentOpenServiceProvider)
      .open(session: session, document: document, onProgress: onProgress);
}

class InternalImageViewer extends StatefulWidget {
  const InternalImageViewer({
    required this.document,
    required this.load,
    super.key,
  });

  final RepositoryDocument document;
  final Future<DocumentContent> Function() load;

  @override
  State<InternalImageViewer> createState() => _InternalImageViewerState();
}

class _InternalImageViewerState extends State<InternalImageViewer> {
  late Future<DocumentContent> _content;

  @override
  void initState() {
    super.initState();
    _content = widget.load();
  }

  void _retry() => setState(() => _content = widget.load());

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: const Key('internal-image-viewer'),
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: Text(widget.document.displayName),
        leading: IconButton(
          tooltip: 'Zamknij podgląd',
          onPressed: () => Navigator.of(context).pop(),
          icon: const Icon(Icons.close),
        ),
      ),
      body: FutureBuilder<DocumentContent>(
        future: _content,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError || snapshot.data == null) {
            return Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  const Icon(
                    Icons.broken_image_outlined,
                    color: Colors.white,
                    size: 48,
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'Nie udało się wczytać obrazu.',
                    style: TextStyle(color: Colors.white),
                  ),
                  TextButton.icon(
                    onPressed: _retry,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Spróbuj ponownie'),
                  ),
                ],
              ),
            );
          }
          return InteractiveViewer(
            key: const Key('internal-image-interactive-viewer'),
            minScale: 0.5,
            maxScale: 8,
            boundaryMargin: const EdgeInsets.all(80),
            child: Center(
              child: Image.memory(
                snapshot.data!.bytes,
                fit: BoxFit.contain,
                errorBuilder: (_, _, _) => const Icon(
                  Icons.broken_image_outlined,
                  color: Colors.white,
                  size: 48,
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
