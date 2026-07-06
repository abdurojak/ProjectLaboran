import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:video_player/video_player.dart';

import '../models/attendance.dart';
import '../providers/attendance_provider.dart';
import '../utils/app_theme.dart';
import '../widgets/state_views.dart';
import '../widgets/status_badge.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback(
      (_) => context.read<AttendanceProvider>().loadHistory(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AttendanceProvider>();
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Riwayat Absensi',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
      ),
      body: RefreshIndicator(
        onRefresh: state.loadHistory,
        child: state.loading && state.history.isEmpty
            ? const Center(child: CircularProgressIndicator())
            : state.history.isEmpty
            ? ListView(
                children: const [
                  SizedBox(
                    height: 470,
                    child: EmptyState(
                      title: 'Belum ada riwayat',
                      message:
                          'Absensi masuk yang berhasil akan tersimpan di sini.',
                      icon: Icons.history_toggle_off,
                    ),
                  ),
                ],
              )
            : ListView.separated(
                padding: const EdgeInsets.fromLTRB(18, 8, 18, 28),
                itemCount: state.history.length,
                separatorBuilder: (_, _) => const SizedBox(height: 12),
                itemBuilder: (context, index) {
                  final item = state.history[index];
                  return Card(
                    child: InkWell(
                      onTap: () => showModalBottomSheet(
                        context: context,
                        isScrollControlled: true,
                        showDragHandle: true,
                        builder: (_) => _HistoryDetail(record: item),
                      ),
                      borderRadius: BorderRadius.circular(24),
                      child: Padding(
                        padding: const EdgeInsets.all(18),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    item.mataKuliah,
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w900,
                                      fontSize: 16,
                                      color: AppTheme.navy,
                                    ),
                                  ),
                                ),
                                StatusBadge(status: item.status),
                              ],
                            ),
                            const SizedBox(height: 10),
                            Text(
                              '${DateFormat('d MMM yyyy', 'id_ID').format(item.waktuMasuk.toLocal())} • ${DateFormat('HH:mm').format(item.waktuMasuk.toLocal())}',
                              style: const TextStyle(
                                fontWeight: FontWeight.w700,
                                color: Color(0xFF475569),
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              '${item.kelas} • ${item.laboratorium}',
                              style: const TextStyle(color: Color(0xFF64748B)),
                            ),
                          ],
                        ),
                      ),
                    ),
                  );
                },
              ),
      ),
    );
  }
}

class _HistoryDetail extends StatefulWidget {
  const _HistoryDetail({required this.record});
  final AttendanceRecord record;

  @override
  State<_HistoryDetail> createState() => _HistoryDetailState();
}

class _HistoryDetailState extends State<_HistoryDetail> {
  VideoPlayerController? controller;

  @override
  void initState() {
    super.initState();
    if (widget.record.videoUrl != null) {
      controller =
          VideoPlayerController.networkUrl(Uri.parse(widget.record.videoUrl!))
            ..initialize().then((_) {
              if (mounted) setState(() {});
            });
    }
  }

  @override
  void dispose() {
    controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final record = widget.record;
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              record.mataKuliah,
              style: const TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w900,
                color: AppTheme.navy,
              ),
            ),
            const SizedBox(height: 8),
            StatusBadge(status: record.status),
            const SizedBox(height: 18),
            ClipRRect(
              borderRadius: BorderRadius.circular(20),
              child: AspectRatio(
                aspectRatio: 4 / 3,
                child: Image.network(
                  record.fotoUrl,
                  fit: BoxFit.cover,
                  errorBuilder: (_, _, _) => const ColoredBox(
                    color: Color(0xFFE2E8F0),
                    child: Center(child: Icon(Icons.broken_image_outlined)),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 18),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                  children: [
                    _Data(
                      label: 'Waktu masuk',
                      value: DateFormat(
                        'd MMMM yyyy, HH:mm',
                        'id_ID',
                      ).format(record.waktuMasuk.toLocal()),
                    ),
                    _Data(label: 'Laboratorium', value: record.laboratorium),
                    _Data(
                      label: 'Koordinat',
                      value: '${record.latitude}, ${record.longitude}',
                    ),
                    _Data(label: 'Jarak', value: '${record.jarak} meter'),
                    _Data(
                      label: 'Akurasi GPS',
                      value: '±${record.akurasi} meter',
                    ),
                  ],
                ),
              ),
            ),
            if (record.videoUrl != null) ...[
              const SizedBox(height: 18),
              const Text(
                'Video bukti',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 10),
              if (controller?.value.isInitialized == true)
                ClipRRect(
                  borderRadius: BorderRadius.circular(20),
                  child: AspectRatio(
                    aspectRatio: controller!.value.aspectRatio,
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        VideoPlayer(controller!),
                        IconButton.filled(
                          onPressed: () {
                            controller!.value.isPlaying
                                ? controller!.pause()
                                : controller!.play();
                            setState(() {});
                          },
                          icon: Icon(
                            controller!.value.isPlaying
                                ? Icons.pause
                                : Icons.play_arrow,
                          ),
                        ),
                      ],
                    ),
                  ),
                )
              else
                const Center(child: CircularProgressIndicator()),
            ],
          ],
        ),
      ),
    );
  }
}

class _Data extends StatelessWidget {
  const _Data({required this.label, required this.value});
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 7),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 110,
          child: Text(label, style: const TextStyle(color: Color(0xFF64748B))),
        ),
        Expanded(
          child: Text(
            value,
            textAlign: TextAlign.right,
            style: const TextStyle(fontWeight: FontWeight.w800),
          ),
        ),
      ],
    ),
  );
}
