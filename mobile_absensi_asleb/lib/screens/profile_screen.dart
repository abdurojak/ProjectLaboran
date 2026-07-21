import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/attendance_provider.dart';
import '../providers/auth_provider.dart';
import '../providers/theme_provider.dart';
import '../utils/app_theme.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final attendance = context.watch<AttendanceProvider>();
    final user = auth.user;
    final isLaboran = user?.role == 'laboran';
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Profil',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(18, 8, 18, 28),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(22),
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 48,
                    backgroundColor: AppTheme.teal.withValues(alpha: .12),
                    backgroundImage: user?.fotoUrl == null
                        ? null
                        : NetworkImage(user!.fotoUrl!),
                    child: user?.fotoUrl == null
                        ? const Icon(
                            Icons.person_outline,
                            color: AppTheme.teal,
                            size: 44,
                          )
                        : null,
                  ),
                  const SizedBox(height: 15),
                  Text(
                    user?.nama ?? '-',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 21,
                      fontWeight: FontWeight.w900,
                      color: Theme.of(context).colorScheme.onSurface,
                    ),
                  ),
                  const SizedBox(height: 5),
                  Text(
                    user?.identitas ?? '-',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 7,
                    ),
                    decoration: BoxDecoration(
                      color: AppTheme.teal.withValues(alpha: .1),
                      borderRadius: BorderRadius.circular(99),
                    ),
                    child: Text(
                      isLaboran ? 'Laboran' : 'Asisten Laboratorium',
                      style: const TextStyle(
                        color: AppTheme.teal,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: SwitchListTile.adaptive(
              value: context.watch<ThemeProvider>().isDark,
              onChanged: (value) =>
                  context.read<ThemeProvider>().setDark(value),
              secondary: const Icon(
                Icons.dark_mode_outlined,
                color: AppTheme.teal,
              ),
              title: const Text(
                'Mode Gelap',
                style: TextStyle(fontWeight: FontWeight.w900),
              ),
              subtitle: const Text(
                'Warna aplikasi tersimpan otomatis di perangkat ini.',
              ),
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                children: [
                  _ProfileRow(
                    icon: Icons.email_outlined,
                    label: 'Email',
                    value: user?.email ?? '-',
                  ),
                  _ProfileRow(
                    icon: Icons.school_outlined,
                    label: 'Program Studi',
                    value: user?.programStudi ?? '-',
                  ),
                  if (!isLaboran)
                    _ProfileRow(
                      icon: Icons.menu_book_outlined,
                      label: 'Mata Kuliah',
                      value: attendance.courses.isEmpty
                          ? '-'
                          : attendance.courses.join('\n'),
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 22),
          OutlinedButton.icon(
            onPressed: auth.loading ? null : () => auth.logout(),
            style: OutlinedButton.styleFrom(
              foregroundColor: const Color(0xFFBE123C),
              minimumSize: const Size.fromHeight(52),
              side: const BorderSide(color: Color(0xFFFDA4AF)),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
            ),
            icon: const Icon(Icons.logout),
            label: const Text(
              'Keluar',
              style: TextStyle(fontWeight: FontWeight.w900),
            ),
          ),
        ],
      ),
    );
  }
}

class _ProfileRow extends StatelessWidget {
  const _ProfileRow({
    required this.icon,
    required this.label,
    required this.value,
  });
  final IconData icon;
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 10),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: AppTheme.teal, size: 21),
        const SizedBox(width: 12),
        SizedBox(
          width: 100,
          child: Text(
            label,
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        Expanded(
          child: Text(
            value,
            textAlign: TextAlign.right,
            style: const TextStyle(fontWeight: FontWeight.w800, height: 1.4),
          ),
        ),
      ],
    ),
  );
}
