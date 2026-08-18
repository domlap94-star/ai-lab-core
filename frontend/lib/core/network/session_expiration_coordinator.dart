import 'dart:async';

typedef SessionExpiredHandler = Future<void> Function(String accessToken);

class SessionExpirationCoordinator {
  SessionExpiredHandler? _handler;
  final Set<String> _handledTokens = <String>{};
  final Map<String, Future<void>> _inFlight = <String, Future<void>>{};
  String? _activeAccessToken;
  int _sessionGeneration = 0;

  void registerHandler(SessionExpiredHandler handler) {
    _handler = handler;
  }

  void unregisterHandler(SessionExpiredHandler handler) {
    if (identical(_handler, handler)) {
      _handler = null;
    }
  }

  void markSessionActive(String accessToken) {
    final String normalized = accessToken.trim();
    if (normalized.isNotEmpty) {
      _sessionGeneration++;
      _activeAccessToken = normalized;
      _handledTokens.remove(normalized);
    }
  }

  void markSessionInactive() {
    _sessionGeneration++;
    _activeAccessToken = null;
  }

  int? captureGeneration(String accessToken) {
    final String normalized = accessToken.trim();
    return normalized.isNotEmpty && normalized == _activeAccessToken
        ? _sessionGeneration
        : null;
  }

  Future<void> handleUnauthorized(
    String accessToken, {
    int? requestGeneration,
  }) {
    final String normalized = accessToken.trim();
    final SessionExpiredHandler? handler = _handler;

    if (normalized.isEmpty ||
        handler == null ||
        requestGeneration == null ||
        requestGeneration != _sessionGeneration ||
        normalized != _activeAccessToken) {
      return Future<void>.value();
    }

    final Future<void>? existing = _inFlight[normalized];
    if (existing != null) {
      return existing;
    }
    if (_handledTokens.contains(normalized)) {
      return Future<void>.value();
    }

    _handledTokens.add(normalized);
    final Future<void> operation = Future<void>.sync(() => handler(normalized));
    _inFlight[normalized] = operation;
    return operation.whenComplete(() {
      _inFlight.remove(normalized);
    });
  }
}
