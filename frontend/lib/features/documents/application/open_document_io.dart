import 'dart:io';

import 'package:open_filex/open_filex.dart';

import '../data/document_content.dart';

Future<void> openDocumentContent(
  DocumentContent content,
  int documentId,
) async {
  final Directory directory = await Directory.systemTemp.createTemp(
    'ai_lab_document_$documentId',
  );
  final String safeName = _safeFileName(content.fileName, documentId);
  final File file = File('${directory.path}${Platform.pathSeparator}$safeName');
  await file.writeAsBytes(content.bytes, flush: true);

  final OpenResult result = await OpenFilex.open(
    file.path,
    type: content.contentType,
  );
  if (result.type != ResultType.done) {
    throw StateError('Nie udało się otworzyć dokumentu: ${result.message}');
  }
}

String _safeFileName(String value, int documentId) {
  final String cleaned = value
      .replaceAll(RegExp(r'[<>:"/\\|?*\x00-\x1F]'), '_')
      .trim();
  if (cleaned.isEmpty || cleaned == '.' || cleaned == '..') {
    return 'document-$documentId';
  }
  return cleaned;
}
