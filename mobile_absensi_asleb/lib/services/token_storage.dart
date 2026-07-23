import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TokenStorage {
  static const _storage = FlutterSecureStorage();
  static const _accessKey = 'labhub_access_token';
  static const _refreshKey = 'labhub_refresh_token';
  static const _rememberCredentialsKey = 'labhub_remember_credentials';
  static const _identifierKey = 'labhub_login_identifier';
  static const _passwordKey = 'labhub_login_password';

  Future<String?> get accessToken => _storage.read(key: _accessKey);
  Future<String?> get refreshToken => _storage.read(key: _refreshKey);

  Future<void> saveTokens(Map<String, dynamic> tokens) async {
    await _storage.write(key: _accessKey, value: tokens['access'] as String);
    await _storage.write(key: _refreshKey, value: tokens['refresh'] as String);
  }

  Future<void> clear() async {
    await _storage.delete(key: _accessKey);
    await _storage.delete(key: _refreshKey);
  }

  Future<({bool remember, String identifier, String password})>
  getSavedCredentials() async {
    final remember =
        await _storage.read(key: _rememberCredentialsKey) == 'true';
    if (!remember) {
      return (remember: false, identifier: '', password: '');
    }

    return (
      remember: true,
      identifier: await _storage.read(key: _identifierKey) ?? '',
      password: await _storage.read(key: _passwordKey) ?? '',
    );
  }

  Future<void> saveCredentials({
    required String identifier,
    required String password,
  }) async {
    await Future.wait([
      _storage.write(key: _rememberCredentialsKey, value: 'true'),
      _storage.write(key: _identifierKey, value: identifier.trim()),
      _storage.write(key: _passwordKey, value: password),
    ]);
  }

  Future<void> clearCredentials() async {
    await Future.wait([
      _storage.delete(key: _rememberCredentialsKey),
      _storage.delete(key: _identifierKey),
      _storage.delete(key: _passwordKey),
    ]);
  }
}
