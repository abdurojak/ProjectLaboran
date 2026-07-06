import 'package:flutter/material.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:provider/provider.dart';

import 'providers/attendance_provider.dart';
import 'providers/auth_provider.dart';
import 'screens/login_screen.dart';
import 'screens/main_shell.dart';
import 'services/api_service.dart';
import 'services/token_storage.dart';
import 'utils/app_theme.dart';

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
        ChangeNotifierProvider(
          create: (_) => AuthProvider(api, storage)..restoreSession(),
        ),
        ChangeNotifierProvider(create: (_) => AttendanceProvider(api)),
      ],
      child: MaterialApp(
        title: 'LabHub Absensi',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light,
        home: const AuthGate(),
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
