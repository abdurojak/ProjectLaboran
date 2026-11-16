import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';

class AslabQrScannerScreen extends StatefulWidget {
  const AslabQrScannerScreen({super.key});

  @override
  State<AslabQrScannerScreen> createState() => _AslabQrScannerScreenState();
}

class _AslabQrScannerScreenState extends State<AslabQrScannerScreen> {
  List<Map<String, dynamic>> _modules = [];
  int? _selected;
  String? _error;
  bool _busy = false;
  String? _lastToken;
  final _controller = MobileScannerController(
    formats: [BarcodeFormat.qrCode],
    detectionSpeed: DetectionSpeed.noDuplicates,
  );

  @override
  void initState() {
    super.initState();
    _loadModules();
  }

  Future<void> _loadModules() async {
    try {
      final result = await context.read<ApiService>().aslabQrModules();
      if (mounted) {
        setState(() {
          _modules = (result['results'] as List)
              .map((item) => Map<String, dynamic>.from(item as Map))
              .toList();
          _selected = _modules.isEmpty ? null : 0;
          _error = null;
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() => _error = error.toString());
      }
    }
  }

  Future<void> _onDetect(BarcodeCapture capture) async {
    if (_busy || _selected == null) return;
    final token = capture.barcodes.firstOrNull?.rawValue;
    if (token == null || token == _lastToken) return;
    _busy = true;
    _lastToken = token;
    final module = _modules[_selected!];
    final api = context.read<ApiService>();
    var cameraStopped = false;
    try {
      final preview = await api.aslabQrScan(
        module['matkul_id'] as int,
        module['modul_id'] as int,
        'preview',
        token,
      );
      if (!mounted) return;
      await _controller.stop();
      cameraStopped = true;
      if (!mounted) return;
      final confirm = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Periksa mahasiswa'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                preview['nama'] as String,
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              Text('NIM: ${preview['nim']}'),
              Text(preview['modul'] as String),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Batal'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Konfirmasi hadir'),
            ),
          ],
        ),
      );
      if (confirm == true) {
        await api.aslabQrScan(
          module['matkul_id'] as int,
          module['modul_id'] as int,
          'confirm',
          token,
        );
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Absensi ${preview['nama']} tercatat.')),
          );
        }
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.toString())));
      }
    } finally {
      _busy = false;
      _lastToken = null;
      if (mounted && cameraStopped) await _controller.start();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Pindai QR Mahasiswa')),
    body: Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: DropdownButtonFormField<int>(
            initialValue: _selected,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Kelas dan modul'),
            items: List.generate(
              _modules.length,
              (index) => DropdownMenuItem(
                value: index,
                child: Text(
                  _modules[index]['label'] as String,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ),
            onChanged: (value) => setState(() => _selected = value),
          ),
        ),
        if (_error != null)
          Padding(padding: const EdgeInsets.all(12), child: Text(_error!)),
        if (_modules.isEmpty && _error == null)
          const Padding(
            padding: EdgeInsets.all(12),
            child: Text('Belum ada modul pada kelas yang ditugaskan.'),
          ),
        Expanded(
          child: _selected == null
              ? const SizedBox.shrink()
              : MobileScanner(controller: _controller, onDetect: _onDetect),
        ),
        const Padding(
          padding: EdgeInsets.all(16),
          child: Text(
            'Periksa identitas mahasiswa sebelum mengonfirmasi kehadiran.',
          ),
        ),
      ],
    ),
  );
}
