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
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w900,
                            color: Theme.of(context).colorScheme.onSurface,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Kelas ${schedule.kelas}',
                          style: TextStyle(
                            color: Theme.of(
                              context,
                            ).colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const Padding(
                    padding: EdgeInsets.only(top: 2),
                    child: Icon(Icons.chevron_right, color: Color(0xFF94A3B8)),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Column(
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: _Info(
                          icon: Icons.calendar_today_outlined,
                          text: schedule.hariDisplay,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _Info(
                          icon: Icons.schedule,
                          text:
                              '${schedule.waktuMulai} - ${schedule.waktuSelesai ?? '--:--'}',
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 9),
                  _Info(
                    icon: Icons.meeting_room_outlined,
                    text: schedule.laboratorium,
                    maxLines: 2,
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
  const _Info({required this.icon, required this.text, this.maxLines = 1});
  final IconData icon;
  final String text;
  final int maxLines;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.max,
    children: [
      Icon(icon, size: 16, color: AppTheme.teal),
      const SizedBox(width: 6),
      Expanded(
        child: Text(
          text,
          maxLines: maxLines,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w700,
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
      ),
    ],
  );
}
