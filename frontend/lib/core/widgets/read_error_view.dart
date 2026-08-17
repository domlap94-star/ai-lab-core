import 'package:flutter/material.dart';

import '../network/friendly_api_error.dart';

class ReadErrorView extends StatelessWidget {
  const ReadErrorView({
    required this.error,
    required this.onRetry,
    this.fallback = 'Nie udało się wczytać danych.',
    super.key,
  });

  final Object error;
  final VoidCallback onRetry;
  final String fallback;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Text(
              friendlyApiError(error, fallback: fallback),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            TextButton(
              onPressed: onRetry,
              child: const Text('Spróbuj ponownie'),
            ),
          ],
        ),
      ),
    );
  }
}
