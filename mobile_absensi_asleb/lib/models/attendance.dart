class AttendanceRecord {
  const AttendanceRecord({
    required this.id,
    required this.tanggal,
    required this.waktuMasuk,
    required this.mataKuliah,
    required this.kelas,
    required this.laboratorium,
    required this.status,
    required this.statusDisplay,
    required this.latitude,
    required this.longitude,
    required this.jarak,
    required this.akurasi,
    required this.fotoUrl,
    this.videoUrl,
  });

  final int id;
  final String tanggal;
  final DateTime waktuMasuk;
  final String mataKuliah;
  final String kelas;
  final String laboratorium;
  final String status;
  final String statusDisplay;
  final String latitude;
  final String longitude;
  final String jarak;
  final String akurasi;
  final String fotoUrl;
  final String? videoUrl;

  factory AttendanceRecord.fromJson(Map<String, dynamic> json) =>
      AttendanceRecord(
        id: json['id'] as int,
        tanggal: json['tanggal_absensi'] as String? ?? '-',
        waktuMasuk: DateTime.parse(json['waktu_masuk'] as String),
        mataKuliah: json['mata_kuliah'] as String? ?? '-',
        kelas: json['kelas'] as String? ?? '-',
        laboratorium: json['laboratorium'] as String? ?? '-',
        status: json['status'] as String? ?? '-',
        statusDisplay: json['status_display'] as String? ?? '-',
        latitude: json['latitude'].toString(),
        longitude: json['longitude'].toString(),
        jarak: json['jarak_lokasi_meter'].toString(),
        akurasi: json['akurasi_gps_meter'].toString(),
        fotoUrl: json['foto_url'] as String? ?? '',
        videoUrl: json['video_url'] as String?,
      );
}
