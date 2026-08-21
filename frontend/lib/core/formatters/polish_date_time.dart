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

String formatPolishDateRange(
  DateTime? start,
  DateTime? end, {
  bool includeTime = false,
}) {
  final first = start ?? end;
  final last = end ?? start;
  if (first == null || last == null) return 'Bez terminu';
  final sameDay =
      first.toLocal().year == last.toLocal().year &&
      first.toLocal().month == last.toLocal().month &&
      first.toLocal().day == last.toLocal().day;
  if (sameDay) {
    return includeTime ? formatPolishDateTime(first) : formatPolishDate(first);
  }
  final left = includeTime
      ? formatPolishDateTime(first)
      : formatPolishDate(first);
  final right = includeTime
      ? formatPolishDateTime(last)
      : formatPolishDate(last);
  return '$left – $right';
}
