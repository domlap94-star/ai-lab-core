// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use

import 'dart:html' as html;

import '../data/document_content.dart';

Future<void> openDocumentContent(
  DocumentContent content,
  int documentId,
) async {
  final html.Blob blob = html.Blob(<Object>[
    content.bytes,
  ], content.contentType);
  final String url = html.Url.createObjectUrlFromBlob(blob);
  final html.AnchorElement anchor = html.AnchorElement(href: url)
    ..download = content.fileName;
  try {
    html.document.body?.append(anchor);
    anchor.click();
    await Future<void>.delayed(Duration.zero);
  } finally {
    anchor.remove();
    html.Url.revokeObjectUrl(url);
  }
}
