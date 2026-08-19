String formatPolishDate(DateTime value) {
  final DateTime local = value.toLocal();
  String twoDigits(int number) => number.toString().padLeft(2, '0');
  return '${twoDigits(local.day)}.${twoDigits(local.month)}.${local.year}';
}

String formatPolishDateTime(DateTime value) {
  final DateTime local = value.toLocal();
  String twoDigits(int number) => number.toString().padLeft(2, '0');
  return '${formatPolishDate(local)}, '
      '${twoDigits(local.hour)}:${twoDigits(local.minute)}';
}
