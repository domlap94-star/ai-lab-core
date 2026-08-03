class BackendStatus {
  const BackendStatus({
    required this.isOnline,
    required this.application,
    required this.version,
    required this.environment,
    required this.debug,
    required this.latencyMilliseconds,
    required this.baseUrl,
  });

  final bool isOnline;
  final String application;
  final String version;
  final String environment;
  final bool debug;
  final int latencyMilliseconds;
  final String baseUrl;
}
