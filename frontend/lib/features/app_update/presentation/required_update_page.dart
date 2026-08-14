import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../application/update_install_controller.dart';
import '../domain/app_update.dart';

class RequiredUpdatePage extends ConsumerWidget {
  const RequiredUpdatePage({required this.result, super.key});

  final UpdateCheckResult result;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final UpdateInstallState installState = ref.watch(
      updateInstallControllerProvider,
    );

    final bool isWindows = result.platform == AppUpdatePlatform.windows;

    final bool isAndroid = result.platform == AppUpdatePlatform.android;

    final bool installable = isWindows || isAndroid;

    final String statusText = switch (installState.phase) {
      UpdateInstallPhase.idle =>
        'Aby kontynuowa\u0107, zainstaluj aktualn\u0105 wersj\u0119.',
      UpdateInstallPhase.downloading =>
        installState.progress == null
            ? 'Pobieranie aktualizacji...'
            : 'Pobieranie: '
                  '${(installState.progress! * 100).round()}%',
      UpdateInstallPhase.verifying => 'Weryfikacja pliku aktualizacji...',
      UpdateInstallPhase.launching =>
        isWindows
            ? 'Uruchamianie instalatora Windows...'
            : 'Otwieranie instalatora Android...',
      UpdateInstallPhase.failed =>
        'Aktualizacja nie powiod\u0142a si\u0119: '
            '${installState.error ?? 'nieznany b\u0142\u0105d'}',
    };

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(32),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      const Icon(Icons.system_update_alt, size: 64),
                      const SizedBox(height: 24),
                      Text(
                        'Wymagana aktualizacja',
                        style: Theme.of(context).textTheme.headlineSmall
                            ?.copyWith(fontWeight: FontWeight.w700),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'Zainstalowana wersja: '
                        '${result.currentDisplayVersion}\n'
                        'Najnowsza wersja: '
                        '${result.latestDisplayVersion}\n'
                        'Minimalna obs\u0142ugiwana wersja: '
                        '${result.manifest.minimumVersion}',
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 20),
                      Text(statusText, textAlign: TextAlign.center),
                      if (installState.phase ==
                              UpdateInstallPhase.downloading &&
                          installState.progress != null) ...<Widget>[
                        const SizedBox(height: 16),
                        LinearProgressIndicator(value: installState.progress),
                      ],
                      const SizedBox(height: 24),
                      if (installable)
                        SizedBox(
                          width: double.infinity,
                          child: FilledButton.icon(
                            onPressed: installState.isBusy
                                ? null
                                : () {
                                    ref
                                        .read(
                                          updateInstallControllerProvider
                                              .notifier,
                                        )
                                        .install(result);
                                  },
                            icon: const Icon(Icons.download),
                            label: const Text(
                              'Pobierz i zainstaluj aktualizacj\u0119',
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
