import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/attendance_provider.dart';
import '../providers/auth_provider.dart';
import 'chatbot_screen.dart';
import 'dashboard_screen.dart';
import 'history_screen.dart';
import 'laboran_dashboard_screen.dart';
import 'laboran_inventory_screen.dart';
import 'laboran_loans_screen.dart';
import 'mahasiswa_home_screen.dart';
import 'student_qr_screen.dart';
import 'profile_screen.dart';
import 'peer_chat_screen.dart';
import 'schedule_list_screen.dart';

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> with WidgetsBindingObserver {
  int index = 0;
  Timer? chatStatusTimer;
  int? lastUnreadCount;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    Future.microtask(_checkChatStatus);
    chatStatusTimer = Timer.periodic(const Duration(seconds: 20), (_) => _checkChatStatus());
  }

  @override
  void dispose() {
    chatStatusTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _checkChatStatus();
  }

  Future<void> _checkChatStatus() async {
    if (WidgetsBinding.instance.lifecycleState != AppLifecycleState.resumed) return;
    try {
      final result = await context.read<AttendanceProvider>().api.peerChatStatus();
      if (!mounted) return;
      final count = result['unread_count'] as int? ?? 0;
      if (lastUnreadCount != null && count > lastUnreadCount!) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('$count pesan chat belum dibaca'),
          action: SnackBarAction(
            label: 'Buka',
            onPressed: () => Navigator.push(context,
                MaterialPageRoute(builder: (_) => const PeerChatScreen())),
          ),
        ));
      }
      lastUnreadCount = count;
    } catch (_) {
      // Koneksi sementara terputus; pemeriksaan berikutnya akan mencoba lagi.
    }
  }

  Future<void> _confirmLogout() async {
    final shouldLogout = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        icon: const Icon(Icons.logout_rounded),
        title: const Text('Keluar dari akun?'),
        content: const Text(
          'Jika Anda keluar, aplikasi akan kembali ke halaman login.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Tidak'),
          ),
          FilledButton.icon(
            onPressed: () => Navigator.pop(dialogContext, true),
            icon: const Icon(Icons.logout_rounded),
            label: const Text('Ya, logout'),
          ),
        ],
      ),
    );

    if (shouldLogout == true && mounted) {
      await context.read<AuthProvider>().logout();
    }
  }

  @override
  Widget build(BuildContext context) {
    final role = context.watch<AuthProvider>().user?.role;
    final isLaboran = role == 'laboran';
    final isMahasiswa = role == 'mahasiswa';
    final screens = isLaboran
        ? const [
            LaboranDashboardScreen(),
            LaboranInventoryScreen(),
            LaboranLoansScreen(),
            ChatbotScreen(),
            ProfileScreen(),
          ]
        : isMahasiswa
        ? const [
            MahasiswaHomeScreen(),
            StudentQrScreen(),
            ChatbotScreen(),
            ProfileScreen(),
          ]
        : const [
            DashboardScreen(),
            ScheduleListScreen(),
            HistoryScreen(),
            ChatbotScreen(),
            ProfileScreen(),
          ];
    final destinations = isLaboran
        ? const [
            NavigationDestination(
              icon: Icon(Icons.home_outlined),
              selectedIcon: Icon(Icons.home),
              label: 'Beranda',
            ),
            NavigationDestination(
              icon: Icon(Icons.inventory_2_outlined),
              selectedIcon: Icon(Icons.inventory_2),
              label: 'Inventaris',
            ),
            NavigationDestination(
              icon: Icon(Icons.swap_horiz_outlined),
              selectedIcon: Icon(Icons.swap_horiz),
              label: 'Pinjam',
            ),
            NavigationDestination(
              icon: Icon(Icons.chat_bubble_outline),
              selectedIcon: Icon(Icons.chat_bubble),
              label: 'Bantuan',
            ),
            NavigationDestination(
              icon: Icon(Icons.person_outline),
              selectedIcon: Icon(Icons.person),
              label: 'Profil',
            ),
          ]
        : isMahasiswa
        ? const [
            NavigationDestination(
              icon: Icon(Icons.home_outlined),
              selectedIcon: Icon(Icons.home),
              label: 'Beranda',
            ),
            NavigationDestination(
              icon: Icon(Icons.qr_code_2),
              label: 'QR Absen',
            ),
            NavigationDestination(
              icon: Icon(Icons.chat_bubble_outline),
              selectedIcon: Icon(Icons.chat_bubble),
              label: 'Bantuan',
            ),
            NavigationDestination(
              icon: Icon(Icons.person_outline),
              selectedIcon: Icon(Icons.person),
              label: 'Profil',
            ),
          ]
        : const [
            NavigationDestination(
              icon: Icon(Icons.home_outlined),
              selectedIcon: Icon(Icons.home),
              label: 'Beranda',
            ),
            NavigationDestination(
              icon: Icon(Icons.event_note_outlined),
              selectedIcon: Icon(Icons.event_note),
              label: 'Jadwal',
            ),
            NavigationDestination(
              icon: Icon(Icons.history_outlined),
              selectedIcon: Icon(Icons.history),
              label: 'Riwayat',
            ),
            NavigationDestination(
              icon: Icon(Icons.chat_bubble_outline),
              selectedIcon: Icon(Icons.chat_bubble),
              label: 'Bantuan',
            ),
            NavigationDestination(
              icon: Icon(Icons.person_outline),
              selectedIcon: Icon(Icons.person),
              label: 'Profil',
            ),
          ];
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) {
          _confirmLogout();
        }
      },
      child: Scaffold(
        body: IndexedStack(index: index, children: screens),
        bottomNavigationBar: NavigationBar(
          selectedIndex: index,
          onDestinationSelected: (value) => setState(() => index = value),
          destinations: destinations,
        ),
      ),
    );
  }
}
