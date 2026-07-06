import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../providers/attendance_provider.dart';
import '../utils/app_theme.dart';
import '../widgets/schedule_card.dart';
import '../widgets/state_views.dart';
import 'schedule_detail_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback(
      (_) => context.read<AttendanceProvider>().loadDashboard(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AttendanceProvider>();
    final profile = state.profile;
    return Scaffold(
      body: RefreshIndicator(
        onRefresh: state.loadDashboard,
        child: CustomScrollView(
          slivers: [
            SliverAppBar.large(
              title: const Text('LabHub'),
              actions: [
                Padding(
                  padding: const EdgeInsets.only(right: 18),
                  child: CircleAvatar(
                    backgroundColor: Colors.white,
                    backgroundImage: profile?.fotoUrl == null
                        ? null
                        : NetworkImage(profile!.fotoUrl!),
                    child: profile?.fotoUrl == null
                        ? const Icon(Icons.person_outline)
                        : null,
                  ),
                ),
              ],
            ),
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(18, 0, 18, 28),
              sliver: SliverList.list(
                children: [
                  Container(
                    padding: const EdgeInsets.all(22),
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFF073B40), AppTheme.teal],
                      ),
                      borderRadius: BorderRadius.circular(28),
                      boxShadow: [
                        BoxShadow(
                          color: AppTheme.teal.withValues(alpha: .2),
                          blurRadius: 24,
                          offset: const Offset(0, 10),
                        ),
                      ],
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          DateFormat(
                            'EEEE, d MMMM yyyy',
                            'id_ID',
                          ).format(DateTime.now()),
                          style: const TextStyle(
                            color: Color(0xFFBFE7E4),
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(height: 13),
                        Text(
                          'Halo, ${profile?.nama ?? 'Asisten Lab'}',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 25,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                        const SizedBox(height: 7),
                        Text(
                          profile?.identitas ?? '',
                          style: const TextStyle(color: Color(0xFFD4EFED)),
                        ),
                        const SizedBox(height: 20),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 8,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: .12),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            '${state.todaySchedules.length} jadwal praktikum hari ini',
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),
                  const Text(
                    'Jadwal hari ini',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w900,
                      color: AppTheme.navy,
                    ),
                  ),
                  const SizedBox(height: 12),
                  if (state.loading && state.todaySchedules.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(40),
                      child: Center(child: CircularProgressIndicator()),
                    )
                  else if (state.error != null)
                    _ErrorCard(
                      message: state.error!,
                      onRetry: state.loadDashboard,
                    )
                  else if (state.todaySchedules.isEmpty)
                    const SizedBox(
                      height: 230,
                      child: EmptyState(
                        title: 'Tidak ada jadwal hari ini',
                        message:
                            'Jadwal praktikum berikutnya dapat dilihat pada menu Jadwal.',
                      ),
                    )
                  else
                    ...state.todaySchedules.map(
                      (schedule) => Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: ScheduleCard(
                          schedule: schedule,
                          onTap: () => Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) =>
                                  ScheduleDetailScreen(schedule: schedule),
                            ),
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.message, required this.onRetry});
  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          Text(message, textAlign: TextAlign.center),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('Coba lagi'),
          ),
        ],
      ),
    ),
  );
}
