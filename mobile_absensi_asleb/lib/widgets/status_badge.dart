import 'package:flutter/material.dart';

class StatusBadge extends StatelessWidget {
  const StatusBadge({super.key, required this.status});
  final String status;

  @override
  Widget build(BuildContext context) {
    final (label, color, icon) = switch (status) {
      'sudah_absen' => (
        'Sudah Absen',
        const Color(0xFF047857),
        Icons.check_circle_outline,
      ),
      'tidak_hadir' => (
        'Tidak Hadir',
        const Color(0xFFBE123C),
        Icons.cancel_outlined,
      ),
      'ditolak_di_luar_radius' => (
        'Di luar radius',
        const Color(0xFFBE123C),
        Icons.location_off_outlined,
      ),
      _ => (
        'Belum Absen',
        const Color(0xFF475569),
        Icons.radio_button_unchecked,
      ),
    };
    return DecoratedBox(
      decoration: BoxDecoration(
        color: color.withValues(alpha: .1),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 15, color: color),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                color: color,
                fontSize: 12,
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
