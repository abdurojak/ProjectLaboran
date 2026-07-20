import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/loan_item.dart';
import '../providers/laboran_provider.dart';
import '../utils/app_theme.dart';

class LaboranLoansScreen extends StatefulWidget {
  const LaboranLoansScreen({super.key});

  @override
  State<LaboranLoansScreen> createState() => _LaboranLoansScreenState();
}

class _LaboranLoansScreenState extends State<LaboranLoansScreen> {
  String filter = 'aktif';

  @override
  void initState() {
    super.initState();
    Future.microtask(context.read<LaboranProvider>().loadLoans);
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<LaboranProvider>();
    final visible = state.loans.where((loan) {
      if (filter == 'semua') return true;
      if (filter == 'selesai') {
        return {'dikembalikan', 'digantikan'}.contains(loan.status);
      }
      return {'diajukan', 'dipinjam', 'hilang', 'rusak'}.contains(loan.status);
    }).toList();
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Peminjaman',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
      ),
      body: RefreshIndicator(
        onRefresh: state.loadLoans,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(18, 8, 18, 28),
          children: [
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'aktif', label: Text('Aktif')),
                ButtonSegment(value: 'selesai', label: Text('Selesai')),
                ButtonSegment(value: 'semua', label: Text('Semua')),
              ],
              selected: {filter},
              onSelectionChanged: (value) =>
                  setState(() => filter = value.first),
            ),
            const SizedBox(height: 18),
            if (state.loading && state.loans.isEmpty)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(50),
                  child: CircularProgressIndicator(),
                ),
              )
            else if (state.error != null && state.loans.isEmpty)
              Center(child: Text(state.error!))
            else if (visible.isEmpty)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(50),
                  child: Text('Tidak ada peminjaman pada kategori ini.'),
                ),
              )
            else
              ...visible.map(
                (loan) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _LoanCard(loan: loan),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _LoanCard extends StatelessWidget {
  const _LoanCard({required this.loan});
  final LoanItem loan;

  Color get color => switch (loan.status) {
    'diajukan' => AppTheme.amber,
    'dipinjam' => const Color(0xFF2563EB),
    'dikembalikan' || 'digantikan' => AppTheme.teal,
    _ => const Color(0xFFE11D48),
  };

  List<(String, String)> get actions => switch (loan.status) {
    'diajukan' => [('dipinjam', 'Setujui peminjaman')],
    'dipinjam' => [
      ('dikembalikan', 'Barang dikembalikan'),
      ('rusak', 'Tandai rusak'),
      ('hilang', 'Tandai hilang'),
    ],
    'rusak' || 'hilang' => [('digantikan', 'Konfirmasi penggantian')],
    _ => [],
  };

  String date(DateTime? value) =>
      value == null ? '-' : DateFormat('dd MMM yyyy', 'id_ID').format(value);

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(17),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      loan.barang,
                      style: const TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w900,
                        color: AppTheme.navy,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      '${loan.kode} • ${loan.kodeBarang}',
                      style: const TextStyle(
                        color: Color(0xFF64748B),
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: .1),
                  borderRadius: BorderRadius.circular(99),
                ),
                child: Text(
                  loan.statusDisplay,
                  style: TextStyle(
                    color: color,
                    fontSize: 11,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ],
          ),
          const Divider(height: 28),
          Text(
            loan.peminjam,
            style: const TextStyle(fontWeight: FontWeight.w900),
          ),
          Text(loan.nim, style: const TextStyle(color: Color(0xFF64748B))),
          const SizedBox(height: 10),
          Row(
            children: [
              const Icon(
                Icons.date_range_outlined,
                size: 18,
                color: AppTheme.teal,
              ),
              const SizedBox(width: 7),
              Expanded(
                child: Text(
                  '${date(loan.tanggalPinjam)} - ${date(loan.tanggalKembali)}',
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          if (actions.isNotEmpty) ...[
            const SizedBox(height: 15),
            SizedBox(
              width: double.infinity,
              child: FilledButton.tonalIcon(
                onPressed: () => _showActions(context),
                icon: const Icon(Icons.task_alt_outlined),
                label: const Text('Proses Status'),
              ),
            ),
          ],
        ],
      ),
    ),
  );

  void _showActions(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(18, 4, 18, 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Perbarui status barang',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 6),
              Text(
                '${loan.barang} • ${loan.peminjam}',
                style: const TextStyle(color: Color(0xFF64748B)),
              ),
              const SizedBox(height: 16),
              ...actions.map(
                (action) => ListTile(
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                  leading: const Icon(Icons.arrow_forward_rounded),
                  title: Text(
                    action.$2,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  onTap: () async {
                    Navigator.pop(sheetContext);
                    final confirmed = await showDialog<bool>(
                      context: context,
                      builder: (dialogContext) => AlertDialog(
                        title: const Text('Konfirmasi perubahan'),
                        content: Text(
                          'Yakin ingin mengubah status menjadi “${action.$2}”?',
                        ),
                        actions: [
                          TextButton(
                            onPressed: () =>
                                Navigator.pop(dialogContext, false),
                            child: const Text('Batal'),
                          ),
                          FilledButton(
                            onPressed: () => Navigator.pop(dialogContext, true),
                            child: const Text('Ya, lanjutkan'),
                          ),
                        ],
                      ),
                    );
                    if (confirmed != true || !context.mounted) return;
                    final state = context.read<LaboranProvider>();
                    final success = await state.updateLoanStatus(
                      loan,
                      action.$1,
                    );
                    if (!context.mounted) return;
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          success
                              ? 'Status peminjaman berhasil diperbarui.'
                              : state.error ?? 'Status gagal diperbarui.',
                        ),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
