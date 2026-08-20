import 'package:flutter/material.dart';

import '../domain/global_mail.dart';

Future<bool> confirmMailReconciliation(
  BuildContext context,
  MailReconciliationDryRun dryRun, {
  required bool openedFromClient,
}) async {
  if (dryRun.missingCount == 0) return false;
  return await showDialog<bool>(
        context: context,
        builder: (BuildContext dialogContext) => AlertDialog(
          title: const Text('Dodać brakujące wiadomości?'),
          content: Text(
            '${openedFromClient ? 'Odświeżenie obejmuje całą skrzynkę, a dopasowanie do klienta wykona istniejący Matching V2. ' : ''}'
            'Sprawdzono ${dryRun.messagesExamined} wiadomości. '
            'Brakuje ${dryRun.missingCount}. '
            'Oczekiwane nowe kandydatury: ${dryRun.expectedCandidates}, '
            'dokumenty: ${dryRun.expectedDocuments}.',
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('Anuluj'),
            ),
            FilledButton(
              key: const Key('mail-reconcile-confirm'),
              onPressed: () => Navigator.of(dialogContext).pop(true),
              child: const Text('Dodaj brakujące'),
            ),
          ],
        ),
      ) ??
      false;
}
