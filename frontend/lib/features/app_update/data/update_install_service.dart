import 'package:dio/dio.dart';

import '../domain/app_update.dart';
import 'update_install_service_stub.dart'
    if (dart.library.io) 'update_install_service_io.dart'
    as platform;

class UpdateInstallService {
  UpdateInstallService(Dio dio)
    : _delegate = platform.UpdateInstallDelegate(dio);

  final platform.UpdateInstallDelegate _delegate;

  Future<String> downloadAndVerify(
    UpdateCheckResult result, {
    void Function(int received, int total)? onProgress,
    void Function()? onVerifying,
  }) {
    return _delegate.downloadAndVerify(
      result,
      onProgress: onProgress,
      onVerifying: onVerifying,
    );
  }

  Future<void> launchInstaller(String filePath) {
    return _delegate.launchInstaller(filePath);
  }
}
