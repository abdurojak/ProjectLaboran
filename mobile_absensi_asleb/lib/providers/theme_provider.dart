import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ThemeProvider extends ChangeNotifier {
  static const _storage = FlutterSecureStorage();
  static const _key = 'labhub_theme_mode';

  ThemeMode mode = ThemeMode.system;

  bool get isDark => mode == ThemeMode.dark;

  Future<void> load() async {
    final saved = await _storage.read(key: _key);
    mode = saved == 'dark'
        ? ThemeMode.dark
        : saved == 'light'
        ? ThemeMode.light
        : ThemeMode.system;
    notifyListeners();
  }

  Future<void> setDark(bool enabled) async {
    mode = enabled ? ThemeMode.dark : ThemeMode.light;
    await _storage.write(key: _key, value: enabled ? 'dark' : 'light');
    notifyListeners();
  }
}
