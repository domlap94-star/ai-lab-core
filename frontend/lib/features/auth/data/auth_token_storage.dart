import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../domain/auth_session.dart';

class AuthTokenStorage {
  const AuthTokenStorage(this._storage);

  static const String _accessTokenKey = 'auth_access_token';
  static const String _tokenTypeKey = 'auth_token_type';

  final FlutterSecureStorage _storage;

  Future<void> saveSession(AuthSession session) async {
    await _storage.write(key: _accessTokenKey, value: session.accessToken);

    await _storage.write(key: _tokenTypeKey, value: session.tokenType);
  }

  Future<AuthSession?> readSession() async {
    final String? accessToken = await _storage.read(key: _accessTokenKey);

    if (accessToken == null || accessToken.isEmpty) {
      return null;
    }

    final String tokenType =
        await _storage.read(key: _tokenTypeKey) ?? 'bearer';

    return AuthSession(accessToken: accessToken, tokenType: tokenType);
  }

  Future<void> clearSession() async {
    await _storage.delete(key: _accessTokenKey);
    await _storage.delete(key: _tokenTypeKey);
  }
}
