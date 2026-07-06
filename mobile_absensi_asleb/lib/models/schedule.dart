class PraktikumSchedule {
  const PraktikumSchedule({
    required this.id,
    required this.mataKuliah,
    required this.kelas,
    required this.hari,
    required this.hariDisplay,
    required this.waktuMulai,
    required this.waktuSelesai,
    required this.laboratorium,
    required this.statusAbsensi,
    this.waktuAbsensi,
  });

  final int id;
  final String mataKuliah;
  final String kelas;
  final String hari;
  final String hariDisplay;
  final String waktuMulai;
  final String? waktuSelesai;
  final String laboratorium;
  final String statusAbsensi;
  final DateTime? waktuAbsensi;

  factory PraktikumSchedule.fromJson(Map<String, dynamic> json) =>
      PraktikumSchedule(
        id: json['id'] as int,
        mataKuliah: json['mata_kuliah'] as String? ?? '-',
        kelas: json['kelas'] as String? ?? '-',
        hari: json['hari'] as String? ?? '-',
        hariDisplay: json['hari_display'] as String? ?? '-',
        waktuMulai: (json['waktu_mulai'] as String? ?? '--:--').substring(0, 5),
        waktuSelesai: json['waktu_selesai'] == null
            ? null
            : (json['waktu_selesai'] as String).substring(0, 5),
        laboratorium: json['laboratorium'] as String? ?? '-',
        statusAbsensi: json['status_absensi'] as String? ?? 'belum_absen',
        waktuAbsensi: json['waktu_absensi'] == null
            ? null
            : DateTime.tryParse(json['waktu_absensi'] as String),
      );
}
