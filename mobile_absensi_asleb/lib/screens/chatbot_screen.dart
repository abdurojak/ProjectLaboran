import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/attendance_provider.dart';
import '../providers/auth_provider.dart';
import '../providers/laboran_provider.dart';
import '../services/api_exception.dart';
import 'admin_chat_screen.dart';

class ChatbotScreen extends StatefulWidget {
  const ChatbotScreen({super.key});

  @override
  State<ChatbotScreen> createState() => _ChatbotScreenState();
}

class _ChatbotScreenState extends State<ChatbotScreen> {
  final controller = TextEditingController();
  final messages = <_ChatMessage>[];
  bool sending = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadRoleContext();
    });
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  Future<void> sendMessage() async {
    final text = controller.text.trim();
    if (text.isEmpty || sending) return;
    setState(() {
      messages.add(_ChatMessage(fromBot: false, text: text));
      sending = true;
      controller.clear();
    });
    try {
      final answer = await context.read<AttendanceProvider>().api.askChatbot(
        text,
      );
      if (!mounted) return;
      setState(() => messages.add(_ChatMessage(fromBot: true, text: answer)));
    } on ApiException catch (error) {
      if (!mounted) return;
      final fallback = await _localFallbackAnswer(text);
      setState(
        () => messages.add(
          _ChatMessage(
            fromBot: true,
            text:
                fallback ??
                'Maaf, bot belum bisa menjawab dari server. ${error.message}',
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  Future<void> _loadRoleContext() async {
    final auth = context.read<AuthProvider>();
    if (auth.user?.role == 'laboran') {
      final provider = context.read<LaboranProvider>();
      if (provider.summary.isEmpty) await provider.loadDashboard();
    } else {
      final provider = context.read<AttendanceProvider>();
      if (provider.profile == null) await provider.loadDashboard();
    }
    if (!mounted) return;
    _ensureGreeting(
      auth.user?.nama ?? 'Pengguna',
      isLaboran: auth.user?.role == 'laboran',
    );
  }

  void _ensureGreeting(String name, {required bool isLaboran}) {
    final greeting = isLaboran
        ? 'Halo $name, saya Bot Bantuan LabHub. Mau tanya inventaris, peminjaman, atau kendala aplikasi?'
        : 'Halo $name, saya Bot Bantuan LabHub. Mau tanya jadwal, absensi, honor, atau kendala aplikasi?';
    if (!mounted) return;
    setState(() {
      if (messages.isEmpty) {
        messages.add(_ChatMessage(fromBot: true, text: greeting));
      } else if (messages.length == 1 &&
          messages.first.fromBot &&
          messages.first.text != greeting) {
        messages[0] = _ChatMessage(fromBot: true, text: greeting);
      }
    });
  }

  Future<String?> _localFallbackAnswer(String question) async {
    final normalized = question.toLowerCase();
    final auth = context.read<AuthProvider>();

    if (auth.user?.role == 'laboran') {
      final provider = context.read<LaboranProvider>();
      if (normalized.contains('barang') ||
          normalized.contains('inventaris') ||
          normalized.contains('pinjam')) {
        if (provider.summary.isEmpty) await provider.loadDashboard();
        final total = provider.summary['total_barang'] ?? 0;
        final units = provider.summary['total_unit'] ?? 0;
        final pending = provider.summary['menunggu_persetujuan'] ?? 0;
        final borrowed = provider.summary['sedang_dipinjam'] ?? 0;
        return 'Ringkasan inventaris: $total jenis barang dengan $units unit. '
            'Peminjaman menunggu persetujuan: $pending, sedang dipinjam: $borrowed.';
      }
      if (normalized.contains('halo') ||
          normalized.contains('hai') ||
          normalized.contains('hi') ||
          normalized.contains('pagi') ||
          normalized.contains('siang') ||
          normalized.contains('sore') ||
          normalized.contains('malam')) {
        return 'Halo ${auth.user?.nama ?? 'Laboran'}. Saya siap membantu informasi inventaris, peminjaman, dan penggunaan aplikasi Laboran.';
      }
      return 'Maaf, koneksi bot server sedang bermasalah. Saya masih bisa membantu ringkasan inventaris dan peminjaman Laboran.';
    }

    final provider = context.read<AttendanceProvider>();

    if (normalized.contains('jadwal')) {
      if (provider.schedules.isEmpty) {
        await provider.loadSchedules();
      }
      if (provider.schedules.isEmpty) {
        return 'Belum ada jadwal praktikum yang terhubung dengan akun Anda.';
      }
      final rows = provider.schedules
          .take(5)
          .map(
            (schedule) =>
                '- ${schedule.hariDisplay}, ${schedule.waktuMulai}-${schedule.waktuSelesai ?? '--:--'}: ${schedule.mataKuliah} (${schedule.kelas}) di ${schedule.laboratorium}',
          )
          .join('\n');
      return 'Jadwal praktikum yang terhubung dengan akun Anda:\n$rows';
    }

    if (normalized.contains('honor') ||
        normalized.contains('gaji') ||
        normalized.contains('bayar')) {
      if (provider.honor == null) {
        await provider.loadDashboard();
      }
      final monthHonor = Map<String, dynamic>.from(
        provider.honor?['bulan_ini'] as Map? ?? {},
      );
      final amount = monthHonor['jumlah'] ?? 0;
      final meetings = monthHonor['total_pertemuan'] ?? 0;
      final status = (monthHonor['status'] as String? ?? 'belum_ada')
          .replaceAll('_', ' ');
      return 'Honor bulan ini: Rp $amount. Total pertemuan: $meetings. Status: $status.';
    }

    if (normalized.contains('halo') ||
        normalized.contains('hai') ||
        normalized.contains('hi') ||
        normalized.contains('pagi') ||
        normalized.contains('siang') ||
        normalized.contains('sore') ||
        normalized.contains('malam')) {
      final name = auth.user?.nama ?? provider.profile?.nama ?? 'Asisten Lab';
      return 'Halo $name. Saya siap bantu. Coba tanyakan jadwal praktikum, status absensi, honor/gaji, atau riwayat absensi Anda.';
    }

    if (normalized.contains('absen') || normalized.contains('absensi')) {
      return 'Untuk absensi, buka menu Jadwal, pilih jadwal praktikum yang sedang berlangsung, lalu tekan Absensi Masuk dan ambil foto bukti dari kamera.';
    }

    return 'Maaf, koneksi bot server sedang bermasalah. Saya masih bisa bantu pertanyaan dasar seperti jadwal praktikum, absensi, honor/gaji, dan riwayat absensi.';
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final isAsleb = auth.user?.role == 'asisten_lab';
    return Scaffold(
      appBar: AppBar(
        title: const Text('Chat Bantuan'),
        actions: [
          if (isAsleb)
            IconButton(
              tooltip: 'Chat Admin',
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const AdminChatScreen()),
              ),
              icon: const Icon(Icons.support_agent_rounded),
            ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 16),
              itemCount: messages.length + (sending ? 1 : 0),
              itemBuilder: (context, index) {
                if (index == messages.length) {
                  return const _MessageBubble(
                    message: _ChatMessage(
                      fromBot: true,
                      text: 'Bot sedang mengetik...',
                    ),
                  );
                }
                return _MessageBubble(message: messages[index]);
              },
            ),
          ),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (isAsleb) ...[
                    OutlinedButton.icon(
                      onPressed: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => const AdminChatScreen(),
                        ),
                      ),
                      icon: const Icon(Icons.support_agent_rounded),
                      label: const Text('Chat Admin'),
                    ),
                    const SizedBox(height: 8),
                  ],
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: controller,
                          minLines: 1,
                          maxLines: 4,
                          textInputAction: TextInputAction.send,
                          onSubmitted: (_) => sendMessage(),
                          decoration: const InputDecoration(
                            hintText: 'Tulis pertanyaan...',
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      FilledButton(
                        onPressed: sending ? null : sendMessage,
                        style: FilledButton.styleFrom(
                          minimumSize: const Size(54, 54),
                          padding: EdgeInsets.zero,
                        ),
                        child: const Icon(Icons.send_rounded),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ChatMessage {
  const _ChatMessage({required this.fromBot, required this.text});
  final bool fromBot;
  final String text;
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message});
  final _ChatMessage message;

  @override
  Widget build(BuildContext context) {
    final alignment = message.fromBot
        ? CrossAxisAlignment.start
        : CrossAxisAlignment.end;
    final colors = Theme.of(context).colorScheme;
    final color = message.fromBot
        ? colors.surfaceContainerHigh
        : colors.primary;
    final textColor = message.fromBot ? colors.onSurface : colors.onPrimary;
    return Column(
      crossAxisAlignment: alignment,
      children: [
        Container(
          constraints: BoxConstraints(
            maxWidth: MediaQuery.sizeOf(context).width * .78,
          ),
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 12),
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(18),
            border: message.fromBot
                ? Border.all(color: colors.outlineVariant)
                : null,
          ),
          child: Text(
            message.text,
            style: TextStyle(
              color: textColor,
              height: 1.4,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    );
  }
}
