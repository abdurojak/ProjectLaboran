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
    return _buildTheme(scheme, mist);
  }

  static ThemeData get dark {
    final scheme =
        ColorScheme.fromSeed(
          seedColor: const Color(0xFF2DD4BF),
          brightness: Brightness.dark,
          surface: const Color(0xFF101D2C),
        ).copyWith(
          primary: const Color(0xFF5EEAD4),
          onPrimary: const Color(0xFF003736),
          secondary: const Color(0xFF7DD3FC),
          outline: const Color(0xFF405268),
          outlineVariant: const Color(0xFF26384C),
          surfaceContainerLow: const Color(0xFF132235),
          surfaceContainer: const Color(0xFF17283C),
          surfaceContainerHigh: const Color(0xFF1D3046),
          onSurface: const Color(0xFFF1F5F9),
          onSurfaceVariant: const Color(0xFFB7C5D6),
        );
    return _buildTheme(scheme, const Color(0xFF081421));
  }

  static ThemeData _buildTheme(ColorScheme scheme, Color background) {
    final isDark = scheme.brightness == Brightness.dark;
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: background,
      fontFamily: 'sans-serif',
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent,
        foregroundColor: scheme.onSurface,
        elevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        color: scheme.surface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(24),
          side: BorderSide(color: scheme.outlineVariant),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerLow,
        labelStyle: TextStyle(color: scheme.onSurfaceVariant),
        hintStyle: TextStyle(color: scheme.onSurfaceVariant),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 18,
          vertical: 16,
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: isDark ? scheme.primary : teal,
          foregroundColor: isDark ? scheme.onPrimary : Colors.white,
          minimumSize: const Size.fromHeight(52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w800),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: scheme.surface,
        indicatorColor: scheme.primaryContainer,
        iconTheme: WidgetStateProperty.resolveWith(
          (states) => IconThemeData(
            color: states.contains(WidgetState.selected)
                ? scheme.onPrimaryContainer
                : scheme.onSurfaceVariant,
          ),
        ),
        labelTextStyle: WidgetStateProperty.all(
          TextStyle(color: scheme.onSurface, fontWeight: FontWeight.w700),
        ),
      ),
      dividerColor: scheme.outlineVariant,
      dialogTheme: DialogThemeData(backgroundColor: scheme.surface),
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: scheme.surface,
        modalBackgroundColor: scheme.surface,
      ),
    );
  }
}
