import 'package:flutter/foundation.dart';

import '../models/user_profile.dart';
import '../services/api_exception.dart';
import '../services/api_service.dart';
import '../services/token_storage.dart';

class AuthProvider extends ChangeNotifier {
  AuthProvider(this.api, this.storage) {
    api.onSessionExpired = _expireSession;
  }

  final ApiService api;
  final TokenStorage storage;
  UserProfile? user;
  bool initializing = true;
  bool loading = false;
  String? error;

  bool get isAuthenticated => user != null;

  void _expireSession() {
    user = null;
    error = 'Sesi Anda telah berakhir. Silakan login kembali.';
    notifyListeners();
  }

  Future<void> restoreSession() async {
    initializing = true;
    notifyListeners();
    try {
      if (await storage.accessToken != null) {
        final data = await api.profile();
        user = UserProfile.fromJson(
          Map<String, dynamic>.from(data['user'] as Map),
        );
      }
    } catch (_) {
      await storage.clear();
      user = null;
    } finally {
      initializing = false;
      notifyListeners();
    }
  }

  Future<bool> login(String identifier, String password) async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      user = await api.login(identifier.trim(), password);
      return true;
    } on ApiException catch (exception) {
      error = exception.message;
      return false;
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> logout() async {
    loading = true;
    notifyListeners();
    await api.logout();
    user = null;
    loading = false;
    notifyListeners();
  }
}
