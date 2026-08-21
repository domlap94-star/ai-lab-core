import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../auth/application/auth_controller.dart';
import '../../timeline/application/timeline_providers.dart';
import '../../timeline/domain/timeline.dart';
import '../application/clients_providers.dart';

String _operationId() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  final hex = bytes
      .map((value) => value.toRadixString(16).padLeft(2, '0'))
      .join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}

Future<void> launchCanonicalClientCall({
  required BuildContext context,
  required WidgetRef ref,
  required int clientId,
  required String phoneNumber,
  required Future<bool> Function(Uri) launcher,
  int? contactId,
}) async {
  final normalized = phoneNumber.trim().replaceAll(RegExp(r'[^\d+]'), '');
  if (normalized.isEmpty) return;
  var logFailed = false;
  try {
    final session = (await ref.read(authControllerProvider.future)).session;
    if (session == null || !session.isAuthenticated) {
      logFailed = true;
    } else {
      await ref
          .read(clientsRepositoryProvider)
          .recordCallInitiated(
            session: session,
            clientId: clientId,
            operationId: _operationId(),
            contactId: contactId,
          );
      ref.invalidate(
        timelinePageProvider(
          TimelineRequest(scope: TimelineScope.client, id: clientId),
        ),
      );
    }
  } catch (_) {
    logFailed = true;
  }
  if (logFailed && context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text(
          'Nie udało się zapisać rozpoczęcia połączenia. Telefon zostanie otwarty.',
        ),
      ),
    );
  }
  var opened = false;
  try {
    opened = await launcher(Uri(scheme: 'tel', path: normalized));
  } catch (_) {
    opened = false;
  }
  if (!opened && context.mounted) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        const SnackBar(
          content: Text('Nie udało się otworzyć aplikacji telefonu.'),
        ),
      );
  }
}

Future<void> openCanonicalClientMaps(
  BuildContext context,
  String address,
) async {
  var destination = address.trim();
  if (destination.isEmpty) return;
  destination = destination.replaceAll(
    RegExp(r',\s*PL$', caseSensitive: false),
    ', Polska',
  );
  final uri = Uri.https('www.google.com', '/maps/dir/', <String, String>{
    'api': '1',
    'destination': destination,
    'travelmode': 'driving',
  });
  final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
  if (!opened && context.mounted) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        const SnackBar(content: Text('Nie udało się otworzyć Google Maps.')),
      );
  }
}
