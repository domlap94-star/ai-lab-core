class AppVersionInfo {
  const AppVersionInfo({
    required this.version,
    required this.buildNumber,
  });

  final String version;
  final String buildNumber;

  String get displayVersion {
    final String cleanVersion = version.trim();
    final String cleanBuild = buildNumber.trim();

    if (cleanBuild.isEmpty) {
      return cleanVersion;
    }

    return '$cleanVersion+$cleanBuild';
  }
}
