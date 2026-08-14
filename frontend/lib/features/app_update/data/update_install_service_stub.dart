import 'package:dio/dio.dart';

import '../domain/app_update.dart';

class UpdateInstallDelegate {
  UpdateInstallDelegate(Dio dio);

  Future<String> downloadAndVerify(
    UpdateCheckResult result, {
    void Function(int received, int total)? onProgress,
    void Function()? onVerifying,
  }) {
    throw UnsupportedError(
      'Native update installation is not supported on this platform.',
    );
  }

  Future<void> launchInstaller(String filePath) {
    throw UnsupportedError(
      'Native update installation is not supported on this platform.',
    );
  }
}
