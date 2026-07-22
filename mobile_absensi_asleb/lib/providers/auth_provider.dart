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
    final accessToken = await storage.accessToken;
    final cachedUser = await storage.cachedUser;
    if (accessToken == null) {
      user = null;
      initializing = false;
      notifyListeners();
      return;
    }

    // Tampilkan dashboard dari profil terenkripsi tanpa menunggu jaringan.
    user = cachedUser;
    if (cachedUser != null) {
      initializing = false;
      notifyListeners();
    }

    try {
      final data = await api.profile();
      final refreshedUser = UserProfile.fromJson(
        Map<String, dynamic>.from(data['user'] as Map),
      );
      user = refreshedUser;
      await storage.saveUser(refreshedUser);
    } catch (_) {
      // Gangguan jaringan tidak boleh mengeluarkan sesi yang masih tersimpan.
      // ApiService akan memanggil _expireSession jika token benar-benar invalid.
      if (cachedUser == null && user == null) {
        await storage.clear();
      }
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
      await storage.saveUser(user!);
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
