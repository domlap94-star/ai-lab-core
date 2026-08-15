import 'package:dio/dio.dart';

String documentSourceLabel(String value) => switch (value.toLowerCase()) {
  'gmail' => 'Gmail',
  'upload' => 'Przesłany plik',
  'archive' => 'Archiwum',
  _ => polishDocumentCode(value),
};

String documentProcessingLabel(String value) => switch (value.toLowerCase()) {
  'pending' => 'Oczekuje',
  'stored' => 'Zapisany',
  'extracting' => 'Ekstrakcja',
  'processed' => 'Przetworzony',
  'failed' => 'Błąd',
  _ => polishDocumentCode(value),
};

String documentMatchLabel(String value) => switch (value.toLowerCase()) {
  'unmatched' => 'Niedopasowany',
  'suggested' => 'Sugerowany',
  'matched' => 'Dopasowany',
  'confirmed' => 'Potwierdzony',
  'rejected' => 'Odrzucony',
  _ => polishDocumentCode(value),
};

String documentContentTypeLabel(String value) => switch (value.toLowerCase()) {
  'application/pdf' => 'PDF',
  'image/jpeg' => 'JPEG',
  'image/png' => 'PNG',
  'message/rfc822' => 'Wiadomość e-mail',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document' =>
    'DOCX',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' => 'XLSX',
  _ => value.isEmpty ? 'Nieznany' : value,
};

String polishDocumentCode(String value) {
  final String spaced = value.replaceAll('_', ' ').trim();
  if (spaced.isEmpty) return 'Brak';
  return '${spaced[0].toUpperCase()}${spaced.substring(1).toLowerCase()}';
}

String formatDocumentDate(DateTime value) {
  final DateTime local = value.toLocal();
  String two(int number) => number.toString().padLeft(2, '0');
  return '${two(local.day)}.${two(local.month)}.${local.year} '
      '${two(local.hour)}:${two(local.minute)}';
}

String formatDocumentBytes(int bytes) {
  if (bytes >= 1024 * 1024) {
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
  if (bytes >= 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
  return '$bytes B';
}

String friendlyDocumentError(Object error) {
  if (error is DioException) {
    return switch (error.response?.statusCode) {
      401 => 'Sesja użytkownika wygasła lub jest nieprawidłowa.',
      404 => 'Dokument nie istnieje lub plik nie jest już dostępny.',
      409 => 'Dokument jest chwilowo niedostępny do otwarcia.',
      _ => 'Nie udało się pobrać dokumentów. Spróbuj ponownie.',
    };
  }
  final String text = error.toString();
  return text.length > 240 ? '${text.substring(0, 240)}…' : text;
}
