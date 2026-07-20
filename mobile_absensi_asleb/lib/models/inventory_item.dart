class InventoryItem {
  const InventoryItem({
    required this.id,
    required this.kode,
    required this.nama,
    required this.jumlah,
    required this.dipinjam,
    required this.tersedia,
    required this.keterangan,
    required this.photoUrls,
  });

  final int id;
  final String kode;
  final String nama;
  final int jumlah;
  final int dipinjam;
  final int tersedia;
  final String keterangan;
  final List<String> photoUrls;

  String? get photoUrl => photoUrls.isEmpty ? null : photoUrls.first;

  factory InventoryItem.fromJson(Map<String, dynamic> json) => InventoryItem(
    id: json['id'] as int,
    kode: json['kode'] as String? ?? '-',
    nama: json['nama'] as String? ?? '-',
    jumlah: json['jumlah'] as int? ?? 0,
    dipinjam: json['dipinjam'] as int? ?? 0,
    tersedia: json['tersedia'] as int? ?? 0,
    keterangan: json['keterangan'] as String? ?? '',
    photoUrls: (json['foto_urls'] as List? ?? const [])
        .map((item) => item.toString())
        .toList(),
  );
}
