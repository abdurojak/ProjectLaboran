import 'package:flutter/material.dart';

import '../models/schedule.dart';
import '../utils/app_theme.dart';
import 'status_badge.dart';

class ScheduleCard extends StatelessWidget {
  const ScheduleCard({super.key, required this.schedule, this.onTap});
  final PraktikumSchedule schedule;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(24),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 46,
                    height: 46,
                    decoration: BoxDecoration(
                      color: AppTheme.teal.withValues(alpha: .1),
                      borderRadius: BorderRadius.circular(15),
                    ),
                    child: const Icon(
                      Icons.science_outlined,
                      color: AppTheme.teal,
                    ),
                  ),
                  const SizedBox(width: 13),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          schedule.mataKuliah,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w900,
                            color: AppTheme.navy,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Kelas ${schedule.kelas}',
                          style: const TextStyle(color: Color(0xFF64748B)),
                        ),
                      ],
                    ),
                  ),
                  const Icon(Icons.chevron_right, color: Color(0xFF94A3B8)),
                ],
              ),
              const SizedBox(height: 16),
              Wrap(
                spacing: 14,
                runSpacing: 8,
                children: [
                  _Info(
                    icon: Icons.calendar_today_outlined,
                    text: schedule.hariDisplay,
                  ),
                  _Info(
                    icon: Icons.schedule,
                    text:
                        '${schedule.waktuMulai} - ${schedule.waktuSelesai ?? '--:--'}',
                  ),
                  _Info(
                    icon: Icons.meeting_room_outlined,
                    text: schedule.laboratorium,
                  ),
                ],
              ),
              const SizedBox(height: 14),
              StatusBadge(status: schedule.statusAbsensi),
            ],
          ),
        ),
      ),
    );
  }
}

class _Info extends StatelessWidget {
  const _Info({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Icon(icon, size: 16, color: AppTheme.teal),
      const SizedBox(width: 6),
      Text(
        text,
        style: const TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w700,
          color: Color(0xFF475569),
        ),
      ),
    ],
  );
}
