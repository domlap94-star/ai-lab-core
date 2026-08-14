import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../app_version/application/app_version_provider.dart';
import '../../app_version/domain/app_version_info.dart';
import '../domain/app_update.dart';

const String stableManifestPath = '/updates/stable/manifest.json';

class UpdateRepository {
  UpdateRepository(this._dio);

  final Dio _dio;

  Future<UpdateManifest> fetchStableManifest() async {
    final Response<dynamic> response = await _dio.get<dynamic>(
      stableManifestPath,
      options: Options(
        headers: const <String, Object>{'Cache-Control': 'no-cache'},
      ),
    );

    final dynamic data = response.data;

    if (data is! Map) {
      throw const FormatException(
        'Update manifest response must be a JSON object.',
      );
    }

    return UpdateManifest.fromJson(Map<String, dynamic>.from(data));
  }
}

final updateRepositoryProvider = Provider<UpdateRepository>((Ref ref) {
  return UpdateRepository(ref.watch(dioProvider));
});

final updateCheckProvider = FutureProvider<UpdateCheckResult>((Ref ref) async {
  final AppVersionInfo current = await ref.watch(appVersionProvider.future);

  final int? currentBuildNumber = int.tryParse(current.buildNumber.trim());

  if (currentBuildNumber == null) {
    throw FormatException('Invalid local build number: ${current.buildNumber}');
  }

  final UpdateManifest manifest = await ref
      .watch(updateRepositoryProvider)
      .fetchStableManifest();

  return UpdateDecisionEngine.evaluate(
    currentVersion: current.version,
    currentBuildNumber: currentBuildNumber,
    manifest: manifest,
    platform: currentUpdatePlatform(),
  );
});
