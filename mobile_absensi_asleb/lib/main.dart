import 'package:flutter/material.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import 'providers/attendance_provider.dart';
import 'providers/auth_provider.dart';
import 'providers/laboran_provider.dart';
import 'providers/theme_provider.dart';
import 'screens/login_screen.dart';
import 'screens/main_shell.dart';
import 'services/api_service.dart';
import 'services/token_storage.dart';
import 'utils/app_theme.dart';
import 'utils/constants.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('id_ID');
  final storage = TokenStorage();
  final api = ApiService(storage);
  runApp(LabHubApp(api: api, storage: storage));
}

class LabHubApp extends StatelessWidget {
  const LabHubApp({super.key, required this.api, required this.storage});
  final ApiService api;
  final TokenStorage storage;

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<ApiService>.value(value: api),
        ChangeNotifierProvider(
          create: (_) => AuthProvider(api, storage)..restoreSession(),
        ),
        ChangeNotifierProvider(create: (_) => AttendanceProvider(api)),
        ChangeNotifierProvider(create: (_) => LaboranProvider(api)),
        ChangeNotifierProvider(create: (_) => ThemeProvider()..load()),
      ],
      child: Consumer<ThemeProvider>(
        builder: (context, theme, _) => MaterialApp(
          title: 'LabHub',
          debugShowCheckedModeBanner: false,
          theme: AppTheme.light,
          darkTheme: AppTheme.dark,
          themeMode: theme.mode,
          home: AppVersionGate(api: api),
        ),
      ),
    );
  }
}

class AppVersionGate extends StatefulWidget {
  const AppVersionGate({super.key, required this.api});
  final ApiService api;

  @override
  State<AppVersionGate> createState() => _AppVersionGateState();
}

class _AppVersionGateState extends State<AppVersionGate> {
  late Future<Map<String, dynamic>> _check;

  @override
  void initState() {
    super.initState();
    _check = widget.api.appVersion();
  }

  void _retry() => setState(() => _check = widget.api.appVersion());

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: _check,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        if (snapshot.hasError) {
          return _VersionMessage(
            icon: Icons.cloud_off_outlined,
            title: 'Pemeriksaan versi gagal',
            message: 'Hubungkan perangkat ke internet lalu coba kembali.',
            buttonLabel: 'Coba Lagi',
            onPressed: _retry,
          );
        }
        final config = snapshot.data!;
        final minimumBuild = (config['minimum_build'] as num?)?.toInt() ?? 0;
        if (AppConstants.appBuild < minimumBuild) {
          final url = Uri.tryParse(config['download_url'] as String? ?? '');
          return _VersionMessage(
            icon: Icons.system_update_alt,
            title: 'Update wajib tersedia',
            message: config['message'] as String? ??
                'Perbarui LabHub agar aplikasi dapat digunakan kembali.',
            detail: 'Versi terbaru ${config['latest_version'] ?? '-'}',
            buttonLabel: 'Unduh Versi Terbaru',
            onPressed: url == null
                ? null
                : () => launchUrl(url, mode: LaunchMode.externalApplication),
          );
        }
        return const AuthGate();
      },
    );
  }
}

class _VersionMessage extends StatelessWidget {
  const _VersionMessage({
    required this.icon,
    required this.title,
    required this.message,
    required this.buttonLabel,
    required this.onPressed,
    this.detail,
  });
  final IconData icon;
  final String title;
  final String message;
  final String? detail;
  final String buttonLabel;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF064E3B), Color(0xFF0F766E), Color(0xFFD1FAE5)],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 440),
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(28),
                    child: Column(
                      children: [
                        CircleAvatar(
                          radius: 36,
                          backgroundColor: const Color(0xFFD1FAE5),
                          child: Icon(icon, size: 38, color: const Color(0xFF047857)),
                        ),
                        const SizedBox(height: 22),
                        Text(title, textAlign: TextAlign.center, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900)),
                        const SizedBox(height: 12),
                        Text(message, textAlign: TextAlign.center, style: const TextStyle(height: 1.5, color: Color(0xFF64748B))),
                        if (detail != null) ...[
                          const SizedBox(height: 10),
                          Text(detail!, style: const TextStyle(fontWeight: FontWeight.w800, color: Color(0xFF047857))),
                        ],
                        const SizedBox(height: 24),
                        FilledButton.icon(
                          onPressed: onPressed,
                          icon: const Icon(Icons.download),
                          label: Text(buttonLabel),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<AuthProvider>(
      builder: (context, auth, _) {
        if (auth.initializing) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        return auth.isAuthenticated ? const MainShell() : const LoginScreen();
      },
    );
  }
}
