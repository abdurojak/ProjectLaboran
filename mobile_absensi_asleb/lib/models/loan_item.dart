class LoanItem {
  const LoanItem({
    required this.id,
    required this.kode,
    required this.barang,
    required this.kodeBarang,
    required this.peminjam,
    required this.nim,
    required this.tanggalPinjam,
    required this.tanggalKembali,
    required this.status,
    required this.statusDisplay,
    required this.catatan,
  });

  final int id;
  final String kode;
  final String barang;
  final String kodeBarang;
  final String peminjam;
  final String nim;
  final DateTime? tanggalPinjam;
  final DateTime? tanggalKembali;
  final String status;
  final String statusDisplay;
  final String catatan;

  factory LoanItem.fromJson(Map<String, dynamic> json) => LoanItem(
    id: json['id'] as int,
    kode: json['kode'] as String? ?? '-',
    barang: json['barang'] as String? ?? '-',
    kodeBarang: json['kode_barang'] as String? ?? '-',
    peminjam: json['peminjam'] as String? ?? '-',
    nim: json['nim'] as String? ?? '-',
    tanggalPinjam: DateTime.tryParse('${json['tanggal_pinjam'] ?? ''}'),
    tanggalKembali: DateTime.tryParse('${json['tanggal_kembali'] ?? ''}'),
    status: json['status'] as String? ?? '-',
    statusDisplay: json['status_display'] as String? ?? '-',
    catatan: json['catatan'] as String? ?? '',
  );
}
