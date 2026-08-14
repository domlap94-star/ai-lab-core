import 'package:flutter/foundation.dart';

enum AppUpdatePlatform { web, windows, android, unsupported }

enum AppUpdateState { current, available, required, unsupported }

AppUpdatePlatform currentUpdatePlatform() {
  if (kIsWeb) {
    return AppUpdatePlatform.web;
  }

  switch (defaultTargetPlatform) {
    case TargetPlatform.windows:
      return AppUpdatePlatform.windows;
    case TargetPlatform.android:
      return AppUpdatePlatform.android;
    case TargetPlatform.iOS:
    case TargetPlatform.macOS:
    case TargetPlatform.linux:
    case TargetPlatform.fuchsia:
      return AppUpdatePlatform.unsupported;
  }
}

class UpdatePlatformRelease {
  const UpdatePlatformRelease({
    required this.available,
    required this.url,
    required this.sha256,
  });

  final bool available;
  final String url;
  final String? sha256;

  factory UpdatePlatformRelease.fromJson(Map<String, dynamic> json) {
    final Object? availableValue = json['available'];
    final Object? urlValue = json['url'];
    final Object? shaValue = json['sha256'];

    if (availableValue is! bool) {
      throw const FormatException(
        'Update platform field "available" must be a boolean.',
      );
    }

    if (urlValue is! String || urlValue.trim().isEmpty) {
      throw const FormatException(
        'Update platform field "url" must be a non-empty string.',
      );
    }

    if (shaValue != null && shaValue is! String) {
      throw const FormatException(
        'Update platform field "sha256" must be a string.',
      );
    }

    return UpdatePlatformRelease(
      available: availableValue,
      url: urlValue.trim(),
      sha256: shaValue is String ? shaValue.trim() : null,
    );
  }
}

class UpdateManifest {
  const UpdateManifest({
    required this.channel,
    required this.version,
    required this.buildNumber,
    required this.minimumVersion,
    required this.publishedAt,
    required this.platforms,
  });

  final String channel;
  final String version;
  final int buildNumber;
  final String minimumVersion;
  final DateTime publishedAt;
  final Map<AppUpdatePlatform, UpdatePlatformRelease> platforms;

  factory UpdateManifest.fromJson(Map<String, dynamic> json) {
    final Object? channelValue = json['channel'];
    final Object? versionValue = json['version'];
    final Object? buildValue = json['build_number'];
    final Object? minimumValue = json['minimum_version'];
    final Object? publishedValue = json['published_at'];
    final Object? platformsValue = json['platforms'];

    if (channelValue is! String || channelValue.trim().isEmpty) {
      throw const FormatException('Invalid update channel.');
    }

    if (versionValue is! String || versionValue.trim().isEmpty) {
      throw const FormatException('Invalid update version.');
    }

    if (buildValue is! int || buildValue < 0) {
      throw const FormatException('Invalid update build number.');
    }

    if (minimumValue is! String || minimumValue.trim().isEmpty) {
      throw const FormatException('Invalid minimum version.');
    }

    if (publishedValue is! String) {
      throw const FormatException('Invalid publication timestamp.');
    }

    if (platformsValue is! Map) {
      throw const FormatException('Invalid update platforms.');
    }

    final DateTime publishedAt = DateTime.parse(publishedValue).toUtc();
    final Map<String, dynamic> platformMap = Map<String, dynamic>.from(
      platformsValue,
    );

    final Map<AppUpdatePlatform, UpdatePlatformRelease> platforms =
        <AppUpdatePlatform, UpdatePlatformRelease>{};

    void readPlatform(String key, AppUpdatePlatform platform) {
      final Object? raw = platformMap[key];

      if (raw == null) {
        return;
      }

      if (raw is! Map) {
        throw FormatException('Invalid platform entry: $key');
      }

      platforms[platform] = UpdatePlatformRelease.fromJson(
        Map<String, dynamic>.from(raw),
      );
    }

    readPlatform('web', AppUpdatePlatform.web);
    readPlatform('windows', AppUpdatePlatform.windows);
    readPlatform('android', AppUpdatePlatform.android);

    final UpdateManifest manifest = UpdateManifest(
      channel: channelValue.trim(),
      version: versionValue.trim(),
      buildNumber: buildValue,
      minimumVersion: minimumValue.trim(),
      publishedAt: publishedAt,
      platforms: Map<AppUpdatePlatform, UpdatePlatformRelease>.unmodifiable(
        platforms,
      ),
    );

    if (_compareStableVersions(manifest.minimumVersion, manifest.version) > 0) {
      throw const FormatException(
        'Minimum version cannot be newer than latest version.',
      );
    }

    return manifest;
  }

  UpdatePlatformRelease? releaseFor(AppUpdatePlatform platform) {
    return platforms[platform];
  }
}

class UpdateCheckResult {
  const UpdateCheckResult({
    required this.state,
    required this.platform,
    required this.currentVersion,
    required this.currentBuildNumber,
    required this.manifest,
    required this.release,
  });

  final AppUpdateState state;
  final AppUpdatePlatform platform;
  final String currentVersion;
  final int currentBuildNumber;
  final UpdateManifest manifest;
  final UpdatePlatformRelease? release;

  String get currentDisplayVersion {
    return '$currentVersion+$currentBuildNumber';
  }

  String get latestDisplayVersion {
    return '${manifest.version}+${manifest.buildNumber}';
  }
}

class UpdateDecisionEngine {
  const UpdateDecisionEngine._();

  static UpdateCheckResult evaluate({
    required String currentVersion,
    required int currentBuildNumber,
    required UpdateManifest manifest,
    required AppUpdatePlatform platform,
  }) {
    if (currentBuildNumber < 0) {
      throw const FormatException('Current build number cannot be negative.');
    }

    final UpdatePlatformRelease? release = manifest.releaseFor(platform);

    if (platform == AppUpdatePlatform.unsupported ||
        release == null ||
        !release.available) {
      return UpdateCheckResult(
        state: AppUpdateState.unsupported,
        platform: platform,
        currentVersion: currentVersion,
        currentBuildNumber: currentBuildNumber,
        manifest: manifest,
        release: release,
      );
    }

    final int minimumComparison = _compareStableVersions(
      currentVersion,
      manifest.minimumVersion,
    );

    if (minimumComparison < 0) {
      return UpdateCheckResult(
        state: AppUpdateState.required,
        platform: platform,
        currentVersion: currentVersion,
        currentBuildNumber: currentBuildNumber,
        manifest: manifest,
        release: release,
      );
    }

    final int latestComparison = _compareStableVersions(
      currentVersion,
      manifest.version,
    );

    if (latestComparison < 0 ||
        (latestComparison == 0 && currentBuildNumber < manifest.buildNumber)) {
      return UpdateCheckResult(
        state: AppUpdateState.available,
        platform: platform,
        currentVersion: currentVersion,
        currentBuildNumber: currentBuildNumber,
        manifest: manifest,
        release: release,
      );
    }

    return UpdateCheckResult(
      state: AppUpdateState.current,
      platform: platform,
      currentVersion: currentVersion,
      currentBuildNumber: currentBuildNumber,
      manifest: manifest,
      release: release,
    );
  }
}

int _compareStableVersions(String left, String right) {
  final List<int> leftParts = _parseStableVersion(left);
  final List<int> rightParts = _parseStableVersion(right);

  for (int index = 0; index < 3; index++) {
    if (leftParts[index] < rightParts[index]) {
      return -1;
    }

    if (leftParts[index] > rightParts[index]) {
      return 1;
    }
  }

  return 0;
}

List<int> _parseStableVersion(String value) {
  final String clean = value.trim().split('+').first.split('-').first;

  final List<String> rawParts = clean.split('.');

  if (rawParts.isEmpty || rawParts.length > 3) {
    throw FormatException('Invalid semantic version: $value');
  }

  final List<int> parts = <int>[];

  for (final String rawPart in rawParts) {
    final int? parsed = int.tryParse(rawPart);

    if (parsed == null || parsed < 0) {
      throw FormatException('Invalid semantic version: $value');
    }

    parts.add(parsed);
  }

  while (parts.length < 3) {
    parts.add(0);
  }

  return parts;
}
