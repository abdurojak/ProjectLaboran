import 'package:flutter/material.dart';

class AppTheme {
  static const teal = Color(0xFF006D6F);
  static const navy = Color(0xFF102238);
  static const mist = Color(0xFFF2F7F7);
  static const amber = Color(0xFFF59E0B);

  static ThemeData get light {
    final scheme = ColorScheme.fromSeed(
      seedColor: teal,
      brightness: Brightness.light,
      surface: const Color(0xFFFAFCFC),
    );
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: mist,
      fontFamily: 'sans-serif',
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        foregroundColor: navy,
        elevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(24),
          side: const BorderSide(color: Color(0xFFDDE8E8)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: Color(0xFFD7E2E2)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: Color(0xFFD7E2E2)),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 18,
          vertical: 16,
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: teal,
          foregroundColor: Colors.white,
          minimumSize: const Size.fromHeight(52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w800),
        ),
      ),
    );
  }
}
