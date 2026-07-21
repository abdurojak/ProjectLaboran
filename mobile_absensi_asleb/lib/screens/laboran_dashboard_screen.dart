import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/auth_provider.dart';
import '../providers/laboran_provider.dart';
import '../utils/app_theme.dart';

class LaboranDashboardScreen extends StatefulWidget {
  const LaboranDashboardScreen({super.key});

  @override
  State<LaboranDashboardScreen> createState() => _LaboranDashboardScreenState();
}

class _LaboranDashboardScreenState extends State<LaboranDashboardScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(context.read<LaboranProvider>().loadDashboard);
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<LaboranProvider>();
    final user = context.watch<AuthProvider>().user;
    return Scaffold(
      body: RefreshIndicator(
        onRefresh: state.loadDashboard,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(18, 56, 18, 28),
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF064E52), AppTheme.teal],
                ),
                borderRadius: BorderRadius.circular(28),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'PUSAT OPERASIONAL',
                          style: TextStyle(
                            color: Color(0xFFA7F3D0),
                            fontWeight: FontWeight.w900,
                            letterSpacing: 1.5,
                          ),
                        ),
                        const SizedBox(height: 10),
                        Text(
                          'Halo, ${user?.nama ?? 'Laboran'}',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 25,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                        const SizedBox(height: 6),
                        const Text(
                          'Pantau inventaris dan peminjaman langsung dari HP.',
                          style: TextStyle(
                            color: Color(0xFFD5F1EF),
                            height: 1.4,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const Icon(
                    Icons.science_outlined,
                    color: Colors.white,
                    size: 54,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 22),
            if (state.loading && state.summary.isEmpty)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(50),
                  child: CircularProgressIndicator(),
                ),
              )
            else if (state.error != null)
              _Error(message: state.error!, retry: state.loadDashboard)
            else
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 1.22,
                children: [
                  _Metric(
                    icon: Icons.inventory_2_outlined,
                    label: 'Total Barang',
                    value: state.summary['total_barang'] ?? 0,
                    color: AppTheme.teal,
                  ),
                  _Metric(
                    icon: Icons.hourglass_top_rounded,
                    label: 'Menunggu',
                    value: state.summary['menunggu_persetujuan'] ?? 0,
                    color: AppTheme.amber,
                  ),
                  _Metric(
                    icon: Icons.swap_horiz_rounded,
                    label: 'Dipinjam',
                    value: state.summary['sedang_dipinjam'] ?? 0,
                    color: const Color(0xFF2563EB),
                  ),
                  _Metric(
                    icon: Icons.location_on_outlined,
                    label: 'Lokasi',
                    value: state.summary['lokasi'] ?? 0,
                    color: const Color(0xFF7C3AED),
                  ),
                ],
              ),
            const SizedBox(height: 22),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Akses mobile Laboran',
                      style: TextStyle(
                        fontSize: 19,
                        fontWeight: FontWeight.w900,
                        color: Theme.of(context).colorScheme.onSurface,
                      ),
                    ),
                    const SizedBox(height: 9),
                    Text(
                      'Gunakan tab Inventaris untuk menambah barang dan foto. Gunakan tab Peminjaman untuk menyetujui, mengonfirmasi pengembalian, atau mencatat masalah barang.',
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                        height: 1.5,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });
  final IconData icon;
  final String label;
  final dynamic value;
  final Color color;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(17),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 26),
          const Spacer(),
          Text(
            '$value',
            style: TextStyle(
              color: color,
              fontSize: 27,
              fontWeight: FontWeight.w900,
            ),
          ),
          Text(
            label,
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurface,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    ),
  );
}

class _Error extends StatelessWidget {
  const _Error({required this.message, required this.retry});
  final String message;
  final Future<void> Function() retry;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          Text(message),
          const SizedBox(height: 10),
          OutlinedButton.icon(
            onPressed: retry,
            icon: const Icon(Icons.refresh),
            label: const Text('Coba lagi'),
          ),
        ],
      ),
    ),
  );
}
