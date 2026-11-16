class InventoryItem {
  const InventoryItem({
    required this.id,
    required this.kode,
    required this.nama,
    required this.category,
    required this.categoryLabel,
    required this.jumlah,
    required this.dipinjam,
    required this.tersedia,
    required this.keterangan,
    required this.photoUrls,
    required this.locations,
  });

  final int id;
  final String kode;
  final String nama;
  final String category;
  final String categoryLabel;
  static const categoryOptions = <String, String>{
    'sensor': 'Sensor',
    'mikrokontroler': 'Board Mikro & SBC',
    'modul': 'Modul & Antarmuka',
    'tampilan': 'Tampilan & Indikator',
    'daya': 'Daya & Baterai',
    'motor': 'Motor & Aktuator',
    'kabel': 'Kabel & Konektor',
    'komputer': 'Komputer & Periferal',
    'jaringan': 'Jaringan',
    'elektronika': 'Komponen Elektronika',
    'audio_visual': 'Audio, Video & XR',
    'perkakas': 'Perkakas & Alat Ukur',
    'lainnya': 'Lainnya',
  };
  final int jumlah;
  final int dipinjam;
  final int tersedia;
  final String keterangan;
  final List<String> photoUrls;
  final List<Map<String, dynamic>> locations;

  String? get photoUrl => photoUrls.isEmpty ? null : photoUrls.first;

  factory InventoryItem.fromJson(Map<String, dynamic> json) => InventoryItem(
    id: json['id'] as int,
    kode: json['kode'] as String? ?? '-',
    nama: json['nama'] as String? ?? '-',
    category: json['kategori'] as String? ?? 'lainnya',
    categoryLabel: json['kategori_label'] as String? ?? 'Lainnya',
    jumlah: json['jumlah'] as int? ?? 0,
    dipinjam: json['dipinjam'] as int? ?? 0,
    tersedia: json['tersedia'] as int? ?? 0,
    keterangan: json['keterangan'] as String? ?? '',
    photoUrls: (json['foto_urls'] as List? ?? const [])
        .map((item) => item.toString())
        .toList(),
    locations: (json['lokasi'] as List? ?? const [])
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList(),
  );
}
