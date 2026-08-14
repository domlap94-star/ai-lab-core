import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../data/update_install_service.dart';
import '../domain/app_update.dart';

enum UpdateInstallPhase { idle, downloading, verifying, launching, failed }

class UpdateInstallState {
  const UpdateInstallState({
    this.phase = UpdateInstallPhase.idle,
    this.progress,
    this.error,
  });

  final UpdateInstallPhase phase;
  final double? progress;
  final String? error;

  bool get isBusy {
    return phase == UpdateInstallPhase.downloading ||
        phase == UpdateInstallPhase.verifying ||
        phase == UpdateInstallPhase.launching;
  }

  UpdateInstallState copyWith({
    UpdateInstallPhase? phase,
    double? progress,
    bool clearProgress = false,
    String? error,
    bool clearError = false,
  }) {
    return UpdateInstallState(
      phase: phase ?? this.phase,
      progress: clearProgress ? null : progress ?? this.progress,
      error: clearError ? null : error ?? this.error,
    );
  }
}

final updateInstallServiceProvider = Provider<UpdateInstallService>((Ref ref) {
  return UpdateInstallService(ref.watch(dioProvider));
});

final updateInstallControllerProvider =
    NotifierProvider<UpdateInstallController, UpdateInstallState>(
      UpdateInstallController.new,
    );

class UpdateInstallController extends Notifier<UpdateInstallState> {
  @override
  UpdateInstallState build() {
    return const UpdateInstallState();
  }

  Future<void> install(UpdateCheckResult result) async {
    if (state.isBusy) {
      return;
    }

    final bool installableState =
        result.state == AppUpdateState.available ||
        result.state == AppUpdateState.required;

    final bool nativePlatform =
        result.platform == AppUpdatePlatform.windows ||
        result.platform == AppUpdatePlatform.android;

    if (!installableState || !nativePlatform) {
      return;
    }

    final UpdateInstallService service = ref.read(updateInstallServiceProvider);

    state = const UpdateInstallState(
      phase: UpdateInstallPhase.downloading,
      progress: 0,
    );

    try {
      final String filePath = await service.downloadAndVerify(
        result,
        onProgress: (int received, int total) {
          double? progress;

          if (total > 0) {
            progress = (received / total).clamp(0.0, 1.0).toDouble();
          }

          state = UpdateInstallState(
            phase: UpdateInstallPhase.downloading,
            progress: progress,
          );
        },
        onVerifying: () {
          state = const UpdateInstallState(phase: UpdateInstallPhase.verifying);
        },
      );

      state = const UpdateInstallState(phase: UpdateInstallPhase.launching);

      await service.launchInstaller(filePath);

      state = const UpdateInstallState();
    } catch (error) {
      state = UpdateInstallState(
        phase: UpdateInstallPhase.failed,
        error: error.toString(),
      );
    }
  }

  void reset() {
    state = const UpdateInstallState();
  }
}
