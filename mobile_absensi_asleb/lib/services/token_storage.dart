import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../models/user_profile.dart';

class TokenStorage {
  static const _storage = FlutterSecureStorage();
  static const _accessKey = 'labhub_access_token';
  static const _refreshKey = 'labhub_refresh_token';
  static const _userKey = 'labhub_user_profile';

  Future<String?> get accessToken => _storage.read(key: _accessKey);
  Future<String?> get refreshToken => _storage.read(key: _refreshKey);

  Future<UserProfile?> get cachedUser async {
    final raw = await _storage.read(key: _userKey);
    if (raw == null || raw.isEmpty) return null;
    try {
      return UserProfile.fromJson(
        Map<String, dynamic>.from(jsonDecode(raw) as Map),
      );
    } catch (_) {
      await _storage.delete(key: _userKey);
      return null;
    }
  }

  Future<void> saveTokens(Map<String, dynamic> tokens) async {
    await _storage.write(key: _accessKey, value: tokens['access'] as String);
    await _storage.write(key: _refreshKey, value: tokens['refresh'] as String);
  }

  Future<void> saveUser(UserProfile user) =>
      _storage.write(key: _userKey, value: jsonEncode(user.toJson()));

  Future<void> clear() async {
    await _storage.delete(key: _accessKey);
    await _storage.delete(key: _refreshKey);
    await _storage.delete(key: _userKey);
  }
}
