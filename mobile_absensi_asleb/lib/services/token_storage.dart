import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TokenStorage {
  static const _storage = FlutterSecureStorage();
  static const _accessKey = 'labhub_access_token';
  static const _refreshKey = 'labhub_refresh_token';

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
}
