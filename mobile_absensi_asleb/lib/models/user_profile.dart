class UserProfile {
  const UserProfile({
    required this.id,
    required this.nama,
    required this.identitas,
    required this.email,
    required this.role,
    required this.programStudi,
    this.fotoUrl,
  });

  final int id;
  final String nama;
  final String identitas;
  final String email;
  final String role;
  final String programStudi;
  final String? fotoUrl;

  factory UserProfile.fromJson(Map<String, dynamic> json) => UserProfile(
    id: json['id'] as int,
    nama: json['nama'] as String? ?? '-',
    identitas: json['identitas'] as String? ?? '-',
    email: json['email'] as String? ?? '-',
    role: json['role'] as String? ?? '-',
    programStudi: json['program_studi'] as String? ?? '-',
    fotoUrl: json['foto_url'] as String?,
  );

  Map<String, dynamic> toJson() => {
    'id': id,
    'nama': nama,
    'identitas': identitas,
    'email': email,
    'role': role,
    'program_studi': programStudi,
    'foto_url': fotoUrl,
  };
}
