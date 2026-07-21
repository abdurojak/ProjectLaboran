import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import 'package:video_player/video_player.dart';

import '../models/schedule.dart';
import '../providers/attendance_provider.dart';
import '../services/api_exception.dart';
import '../utils/app_theme.dart';

class CheckInScreen extends StatefulWidget {
  const CheckInScreen({super.key, required this.schedule});
  final PraktikumSchedule schedule;

  @override
  State<CheckInScreen> createState() => _CheckInScreenState();
}

class _CheckInScreenState extends State<CheckInScreen> {
  final picker = ImagePicker();
  XFile? photo;
  XFile? video;
  VideoPlayerController? videoController;
  bool submitting = false;
  String? error;

  @override
  void dispose() {
    videoController?.dispose();
    super.dispose();
  }

  Future<void> capturePhoto() async {
    final result = await picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 78,
      maxWidth: 1600,
    );
    if (result != null) setState(() => photo = result);
  }

  Future<void> captureVideo() async {
    final result = await picker.pickVideo(
      source: ImageSource.camera,
      maxDuration: const Duration(seconds: 15),
    );
    if (result == null) return;
    await videoController?.dispose();
    final controller = VideoPlayerController.file(File(result.path));
    await controller.initialize();
    setState(() {
      video = result;
      videoController = controller;
    });
  }

  Future<void> submit() async {
    final provider = context.read<AttendanceProvider>();
    if (photo == null) {
      setState(() => error = 'Ambil foto selfie terlebih dahulu.');
      return;
    }
    setState(() {
      submitting = true;
      error = null;
    });
    try {
      await provider.checkIn(
        schedule: widget.schedule,
        photo: photo!,
        video: video,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Absensi masuk berhasil disimpan.'),
          behavior: SnackBarBehavior.floating,
        ),
      );
      Navigator.pop(context, true);
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Absensi Masuk',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(18, 6, 18, 32),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    widget.schedule.mataKuliah,
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w900,
                      color: Theme.of(context).colorScheme.onSurface,
                    ),
                  ),
                  const SizedBox(height: 7),
                  Text(
                    '${widget.schedule.hariDisplay}, ${widget.schedule.waktuMulai} • ${widget.schedule.laboratorium}',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 18),
          const _SectionTitle(
            number: '1',
            title: 'Ambil selfie',
            subtitle: 'Foto wajib diambil langsung dari kamera.',
          ),
          const SizedBox(height: 10),
          InkWell(
            onTap: capturePhoto,
            borderRadius: BorderRadius.circular(22),
            child: Container(
              height: 230,
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surface,
                borderRadius: BorderRadius.circular(22),
                border: Border.all(
                  color: Theme.of(context).colorScheme.outlineVariant,
                ),
              ),
              clipBehavior: Clip.antiAlias,
              child: photo == null
                  ? const Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.add_a_photo_outlined,
                          size: 46,
                          color: AppTheme.teal,
                        ),
                        SizedBox(height: 10),
                        Text(
                          'Buka kamera',
                          style: TextStyle(fontWeight: FontWeight.w900),
                        ),
                      ],
                    )
                  : Stack(
                      fit: StackFit.expand,
                      children: [
                        Image.file(File(photo!.path), fit: BoxFit.cover),
                        Positioned(
                          right: 10,
                          bottom: 10,
                          child: FilledButton.tonalIcon(
                            onPressed: capturePhoto,
                            icon: const Icon(Icons.refresh),
                            label: const Text('Ulangi'),
                          ),
                        ),
                      ],
                    ),
            ),
          ),
          const SizedBox(height: 22),
          const _SectionTitle(
            number: '2',
            title: 'Rekam video',
            subtitle: 'Opsional, maksimal 15 detik dan direkam dari kamera.',
          ),
          const SizedBox(height: 10),
          if (videoController?.value.isInitialized == true)
            ClipRRect(
              borderRadius: BorderRadius.circular(22),
              child: AspectRatio(
                aspectRatio: videoController!.value.aspectRatio,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    VideoPlayer(videoController!),
                    IconButton.filled(
                      onPressed: () {
                        videoController!.value.isPlaying
                            ? videoController!.pause()
                            : videoController!.play();
                        setState(() {});
                      },
                      icon: Icon(
                        videoController!.value.isPlaying
                            ? Icons.pause
                            : Icons.play_arrow,
                      ),
                    ),
                  ],
                ),
              ),
            )
          else
            OutlinedButton.icon(
              onPressed: captureVideo,
              icon: const Icon(Icons.videocam_outlined),
              label: const Text('Rekam video bukti'),
            ),
          if (video != null)
            TextButton.icon(
              onPressed: captureVideo,
              icon: const Icon(Icons.refresh),
              label: const Text('Rekam ulang video'),
            ),
          /* Lokasi dihapus dari alur absensi.
          const SizedBox(height: 22),
          const _SectionTitle(
            number: '3',
            title: 'Verifikasi lokasi',
            subtitle: 'GPS dan akurasi akan diperiksa kembali oleh server.',
          ),
          const SizedBox(height: 10),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(17),
              child: Row(
                children: [
                  Container(
                    width: 46,
                    height: 46,
                    decoration: BoxDecoration(
                      color: AppTheme.teal.withValues(alpha: .1),
                      borderRadius: BorderRadius.circular(15),
                    ),
                    child: const Icon(Icons.my_location, color: AppTheme.teal),
                  ),
                  const SizedBox(width: 13),
                  Expanded(
                    child: position == null
                        ? const Text(
                            'Lokasi belum diambil',
                            style: TextStyle(fontWeight: FontWeight.w800),
                          )
                        : Text(
                            'Akurasi ±${position!.accuracy.toStringAsFixed(1)} meter',
                            style: const TextStyle(fontWeight: FontWeight.w900),
                          ),
                  ),
                  TextButton(
                    onPressed: loadingLocation ? null : acquireLocation,
                    child: Text(loadingLocation ? 'Mengambil...' : 'Ambil GPS'),
                  ),
                ],
              ),
            ),
          ),
          */
          if (error != null) ...[
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: const Color(0xFFFFE4E6),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Text(
                error!,
                style: const TextStyle(
                  color: Color(0xFFBE123C),
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: submitting ? null : submit,
            icon: submitting
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.fact_check_outlined),
            label: Text(submitting ? 'Menyimpan...' : 'Kirim Absensi Masuk'),
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({
    required this.number,
    required this.title,
    required this.subtitle,
  });
  final String number;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      CircleAvatar(
        radius: 15,
        backgroundColor: AppTheme.teal,
        child: Text(
          number,
          style: const TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w900,
          ),
        ),
      ),
      const SizedBox(width: 11),
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w900,
                color: Theme.of(context).colorScheme.onSurface,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              subtitle,
              style: TextStyle(
                fontSize: 12,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
                height: 1.4,
              ),
            ),
          ],
        ),
      ),
    ],
  );
}
