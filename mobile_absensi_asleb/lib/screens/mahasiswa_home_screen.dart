import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/loan_item.dart';
import '../providers/auth_provider.dart';
import '../services/api_exception.dart';
import '../services/api_service.dart';
import '../utils/app_theme.dart';

class MahasiswaHomeScreen extends StatefulWidget {
  const MahasiswaHomeScreen({super.key});

  @override
  State<MahasiswaHomeScreen> createState() => _MahasiswaHomeScreenState();
}

class _MahasiswaHomeScreenState extends State<MahasiswaHomeScreen> {
  List<LoanItem> loans = [];
  bool loading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    Future.microtask(_loadLoans);
  }

  Future<void> _loadLoans() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = await context.read<ApiService>().mahasiswaLoans();
      if (mounted) setState(() => loans = result);
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().user;
    return Scaffold(
      appBar: AppBar(title: const Text('Beranda Mahasiswa')),
      body: RefreshIndicator(
        onRefresh: _loadLoans,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(18, 12, 18, 28),
          children: [
            Container(
              padding: const EdgeInsets.all(22),
              decoration: BoxDecoration(
                color: AppTheme.teal,
                borderRadius: BorderRadius.circular(24),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Halo, ${user?.nama ?? 'Mahasiswa'}',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 22,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    user?.identitas ?? '',
                    style: const TextStyle(color: Colors.white70),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 22),
            const Text(
              'Peminjaman Anda',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 12),
            if (loading)
              const Center(child: CircularProgressIndicator())
            else if (error != null)
              Text('Gagal memuat peminjaman: $error')
            else if (loans.isEmpty)
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(20),
                  child: Text('Belum ada riwayat peminjaman barang.'),
                ),
              )
            else
              ...loans.map(
                (loan) => Card(
                  child: ListTile(
                    leading: const Icon(
                      Icons.inventory_2_outlined,
                      color: AppTheme.teal,
                    ),
                    title: Text(loan.barang),
                    subtitle: Text(
                      '${loan.kode} • ${loan.statusDisplay}\n'
                      'Kembali: ${loan.tanggalKembali == null ? '-' : DateFormat('d MMM yyyy', 'id_ID').format(loan.tanggalKembali!)}',
                    ),
                    isThreeLine: true,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
