import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/schedule.dart';
import '../providers/attendance_provider.dart';
import '../utils/app_theme.dart';
import '../widgets/status_badge.dart';
import 'check_in_screen.dart';

class ScheduleDetailScreen extends StatelessWidget {
  const ScheduleDetailScreen({super.key, required this.schedule});
  final PraktikumSchedule schedule;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Detail Jadwal',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
      ),
      body: FutureBuilder<Map<String, dynamic>>(
        future: context.read<AttendanceProvider>().loadScheduleDetail(
          schedule.id,
        ),
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text(
                  snapshot.error.toString(),
                  textAlign: TextAlign.center,
                ),
              ),
            );
          }
          final data = snapshot.data!;
          final canCheckIn = data['can_check_in'] as bool? ?? false;
          return ListView(
            padding: const EdgeInsets.all(18),
            children: [
              Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF073B40), AppTheme.teal],
                  ),
                  borderRadius: BorderRadius.circular(28),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(
                      Icons.science_outlined,
                      color: Colors.white,
                      size: 34,
                    ),
                    const SizedBox(height: 18),
                    Text(
                      schedule.mataKuliah,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 24,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Kelas ${schedule.kelas}',
                      style: const TextStyle(
                        color: Color(0xFFD4EFED),
                        fontSize: 16,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    children: [
                      _DetailRow(
                        icon: Icons.calendar_today_outlined,
                        label: 'Hari',
                        value: schedule.hariDisplay,
                      ),
                      _DetailRow(
                        icon: Icons.schedule,
                        label: 'Waktu',
                        value:
                            '${schedule.waktuMulai} - ${schedule.waktuSelesai ?? '--:--'}',
                      ),
                      _DetailRow(
                        icon: Icons.meeting_room_outlined,
                        label: 'Laboratorium',
                        value: schedule.laboratorium,
                      ),
                      _DetailRow(
                        icon: Icons.fact_check_outlined,
                        label: 'Status',
                        trailing: StatusBadge(status: schedule.statusAbsensi),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: canCheckIn
                      ? const Color(0xFFECFDF5)
                      : const Color(0xFFFFF7ED),
                  borderRadius: BorderRadius.circular(18),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      canCheckIn
                          ? Icons.check_circle_outline
                          : Icons.info_outline,
                      color: canCheckIn
                          ? const Color(0xFF047857)
                          : const Color(0xFFB45309),
                    ),
                    const SizedBox(width: 11),
                    Expanded(
                      child: Text(
                        data['check_in_message'] as String? ?? '-',
                        style: const TextStyle(
                          fontWeight: FontWeight.w700,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 22),
              FilledButton.icon(
                onPressed: canCheckIn
                    ? () async {
                        final success = await Navigator.push<bool>(
                          context,
                          MaterialPageRoute(
                            builder: (_) => CheckInScreen(schedule: schedule),
                          ),
                        );
                        if (success == true && context.mounted) {
                          Navigator.pop(context);
                        }
                      }
                    : null,
                icon: const Icon(Icons.login),
                label: const Text('Absensi Masuk'),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({
    required this.icon,
    required this.label,
    this.value,
    this.trailing,
  });
  final IconData icon;
  final String label;
  final String? value;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 11),
    child: Row(
      children: [
        Icon(icon, color: AppTheme.teal, size: 20),
        const SizedBox(width: 12),
        SizedBox(
          width: 90,
          child: Text(
            label,
            style: const TextStyle(
              color: Color(0xFF64748B),
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        Expanded(
          child:
              trailing ??
              Text(
                value ?? '-',
                textAlign: TextAlign.right,
                style: const TextStyle(
                  fontWeight: FontWeight.w900,
                  color: AppTheme.navy,
                ),
              ),
        ),
      ],
    ),
  );
}
