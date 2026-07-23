import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/attendance_provider.dart';
import '../widgets/schedule_card.dart';
import '../widgets/state_views.dart';
import 'schedule_detail_screen.dart';

class ScheduleListScreen extends StatefulWidget {
  const ScheduleListScreen({super.key});

  @override
  State<ScheduleListScreen> createState() => _ScheduleListScreenState();
}

class _ScheduleListScreenState extends State<ScheduleListScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback(
      (_) => context.read<AttendanceProvider>().loadSchedules(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AttendanceProvider>();
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Jadwal Praktikum',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
      ),
      body: RefreshIndicator(
        onRefresh: state.loadSchedules,
        child: state.loading && state.schedules.isEmpty
            ? const Center(child: CircularProgressIndicator())
            : state.schedules.isEmpty
            ? ListView(
                children: const [
                  SizedBox(
                    height: 470,
                    child: EmptyState(
                      title: 'Belum ada jadwal',
                      message:
                          'Jadwal yang sudah disetujui laboran akan tampil di sini.',
                      icon: Icons.event_busy_outlined,
                    ),
                  ),
                ],
              )
            : ListView.separated(
                padding: const EdgeInsets.fromLTRB(18, 8, 18, 28),
                itemCount: state.schedules.length + 1,
                separatorBuilder: (_, _) => const SizedBox(height: 12),
                itemBuilder: (context, index) {
                  if (index == 0) {
                    return Container(
                      padding: const EdgeInsets.all(18),
                      decoration: BoxDecoration(
                        color: scheme.primary.withValues(alpha: .14),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                          color: scheme.primary.withValues(alpha: .28),
                        ),
                      ),
                      child: Row(
                        children: [
                          Icon(Icons.info_outline, color: scheme.primary),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              'Absensi hanya aktif pada hari dan rentang waktu jadwal.',
                              style: TextStyle(
                                fontWeight: FontWeight.w700,
                                color: scheme.onSurface,
                              ),
                            ),
                          ),
                        ],
                      ),
                    );
                  }
                  final schedule = state.schedules[index - 1];
                  return ScheduleCard(
                    schedule: schedule,
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) =>
                            ScheduleDetailScreen(schedule: schedule),
                      ),
                    ),
                  );
                },
              ),
      ),
    );
  }
}
