import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../domain/app_version_info.dart';

final appVersionProvider = FutureProvider<AppVersionInfo>((Ref ref) async {
  final PackageInfo packageInfo = await PackageInfo.fromPlatform();

  return AppVersionInfo(
    version: packageInfo.version,
    buildNumber: packageInfo.buildNumber,
  );
});
