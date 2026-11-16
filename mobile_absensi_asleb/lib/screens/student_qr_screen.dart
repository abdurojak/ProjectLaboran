import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../services/api_service.dart';

class StudentQrScreen extends StatefulWidget {
  const StudentQrScreen({super.key});

  @override
  State<StudentQrScreen> createState() => _StudentQrScreenState();
}

class _StudentQrScreenState extends State<StudentQrScreen>
    with WidgetsBindingObserver {
  Timer? _timer;
  String? _token;
  String? _error;
  DateTime? _expiresAt;
  DateTime _nextAttempt = DateTime.now();
  bool _fetching = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      if (DateTime.now().isAfter(_nextAttempt)) {
        _refresh();
      }
      setState(() {});
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _refresh();
  }

  Future<void> _refresh() async {
    if (_fetching) {
      return;
    }
    _fetching = true;
    _nextAttempt = DateTime.now().add(const Duration(seconds: 5));
    try {
      final data = await context.read<ApiService>().studentQr();
      if (mounted) {
        setState(() {
          _token = data['token'] as String;
          _expiresAt = DateTime.now().add(
            Duration(seconds: data['expires_in'] as int),
          );
          _nextAttempt = DateTime.now().add(
            Duration(seconds: data['refresh_after'] as int),
          );
          _error = null;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      _fetching = false;
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final valid =
        _token != null &&
        _expiresAt != null &&
        DateTime.now().isBefore(_expiresAt!);
    return Scaffold(
      appBar: AppBar(title: const Text('QR Absensi Saya')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (valid)
                QrImageView(
                  key: ValueKey(_token),
                  data: _token!,
                  size: 280,
                  backgroundColor: Colors.white,
                )
              else
                const Icon(Icons.qr_code_2, size: 180),
              const SizedBox(height: 20),
              Text(
                valid
                    ? 'Tunjukkan QR dan identitas Anda kepada Asisten Lab.'
                    : (_error ?? 'QR belum tersedia.'),
                textAlign: TextAlign.center,
              ),
              if (!valid)
                TextButton.icon(
                  onPressed: _refresh,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Coba lagi'),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
