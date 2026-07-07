BOT_GUIDE_INTRO = (
    'Saya Bot Bantuan LabHub. Saya bisa membantu menjelaskan fitur web Project Laboran/LabHub '
    'berdasarkan panduan internal sistem.'
)


BOT_GUIDE_TOPICS = [
    {
        'keywords': {'login', 'masuk', 'akun', 'akses'},
        'answer': (
            'Login dilakukan dari halaman Login dengan NIM/email dan password. Jika akun belum login lalu membuka menu protected, '
            'sistem akan mengarahkan ke halaman login. Hak akses menu mengikuti role akun: Mahasiswa, Asisten Lab, Laboran, atau Admin.'
        ),
    },
    {
        'keywords': {'registrasi', 'register', 'daftar akun', 'buat akun', 'otp', 'verifikasi'},
        'answer': (
            'Registrasi mandiri hanya untuk mahasiswa. NIM harus angka minimal 10 digit, email wajib memakai domain mahasiswa '
            '@std.trisakti.ac.id, lalu akun diaktifkan dengan OTP yang dikirim ke email. Tombol register akan loading saat diproses '
            'agar tidak terkirim berkali-kali.'
        ),
    },
    {
        'keywords': {'lupa password', 'reset password', 'password', 'sandi'},
        'answer': (
            'Gunakan menu Lupa Password di halaman login. Masukkan identitas akun, ikuti verifikasi email, lalu buat password baru. '
            'Jika password baru sama dengan password lama, sistem akan memberi peringatan.'
        ),
    },
    {
        'keywords': {'role', 'hak akses', 'admin', 'laboran', 'mahasiswa', 'asisten lab'},
        'answer': (
            'Ringkasnya: Mahasiswa dapat mendaftar asleb, melihat jadwal/praktikum yang terkait, dan memakai fitur mahasiswa. '
            'Asisten Lab dapat mengakses absensi asleb, jadwal praktikum terkait, nilai/absensi mahasiswa, dan rincian honor miliknya. '
            'Laboran mengelola operasional lab seperti inventaris, peminjaman, peserta praktikum, pendaftaran asleb, honor, surat, dan jadwal. '
            'Admin fokus pada akun pengguna, role, dashboard admin, dan pengaturan dasar.'
        ),
    },
    {
        'keywords': {'pendaftaran aslab', 'pendaftaran asleb', 'daftar aslab', 'daftar asleb', 'qr asleb', 'generate asleb'},
        'answer': (
            'Alur pendaftaran asleb: laboran membuka periode pendaftaran, mahasiswa mengisi form, memilih mata kuliah, upload transkrip PDF, '
            'melengkapi rekening dan tanda tangan. Nama, NIM, dan email dibaca dari akun. Nilai minimal yang diterima adalah B. '
            'Junior hanya boleh memilih 1 mata kuliah, senior maksimal 2. Setelah laboran menerima pendaftar, proses Generate akan memindahkan '
            'pendaftar diterima ke Data Asleb dan membersihkan tabel pendaftaran.'
        ),
    },
    {
        'keywords': {'ditolak', 'penolakan', 'status pendaftaran', 'diterima'},
        'answer': (
            'Status pendaftaran dapat dilihat oleh mahasiswa. Jika diterima, mahasiswa akan diproses menjadi Asisten Lab. '
            'Jika ditolak, notifikasi web akan menampilkan status ditolak dan alasan/catatan bila tersedia; email status juga dikirim.'
        ),
    },
    {
        'keywords': {'profile', 'profil', 'cv', 'resume', 'pengalaman', 'foto'},
        'answer': (
            'Profil berisi identitas, foto profil, foto sampul, ringkasan profesional, keahlian, pendidikan, pengalaman, organisasi, proyek, '
            'dan sertifikasi. Foto profil wajib terdeteksi wajah kecuali Super Admin/Admin yang diberi kelonggaran. CV dapat diunduh otomatis '
            'dari data profil dalam format resume PDF.'
        ),
    },
    {
        'keywords': {'absensi asleb', 'absen asleb', 'modul absensi', 'bukti foto', 'bukti video'},
        'answer': (
            'Absensi Asisten Lab dibuka/ditutup oleh laboran. Asisten Lab memilih modul sesuai mata kuliah, upload modul/bukti foto dan video. '
            'Modul yang sama tidak bisa diabsen dua kali. Dalam satu hari, asisten lab dapat melakukan absensi maksimal 2 modul untuk mengantisipasi '
            'praktikum yang membutuhkan lebih dari satu modul.'
        ),
    },
    {
        'keywords': {'nilai mahasiswa', 'absensi mahasiswa', 'nilai realtime', 'nilai laporan', 'rata rata', 'rata-rata'},
        'answer': (
            'Menu Nilai & Absensi Mahasiswa dipakai untuk mencatat kehadiran dan nilai peserta praktikum. Nilai terdiri dari Nilai Realtime '
            'dan Nilai Laporan; sistem menghitung rata-rata otomatis. Rekap Excel dapat diunduh per mata kuliah, dan jika mengunduh semua mata kuliah '
            'sistem membuat file ZIP berisi satu Excel untuk tiap mata kuliah.'
        ),
    },
    {
        'keywords': {'peserta praktikum', 'csv', 'import peserta', 'hapus peserta', 'daftar peserta'},
        'answer': (
            'Laboran dapat menginput peserta praktikum secara manual atau import CSV. Sistem mencocokkan NIM peserta dengan akun yang sudah ada; '
            'jika akun belum ada, peserta tetap tersimpan dan akan otomatis terhubung saat mahasiswa register dengan NIM yang sama. '
            'Daftar peserta dibuka melalui popup, dan ada tombol Hapus Semua Peserta dengan konfirmasi. Riwayat nilai tetap disimpan.'
        ),
    },
    {
        'keywords': {'inventaris', 'barang', 'peminjaman', 'pinjam alat', 'barang tertinggal'},
        'answer': (
            'Menu Barang & Peminjaman mengelola inventaris, peminjaman alat, dan barang mahasiswa yang tertinggal. Peminjaman memiliki notifikasi '
            'saat request dibuat, disetujui, ditolak, dikembalikan, hilang, rusak, atau diganti. Riwayat peminjaman tetap dapat dilihat walau barang sudah dikembalikan.'
        ),
    },
    {
        'keywords': {'kalender', 'jadwal', 'praktikum', 'ruangan', 'lab'},
        'answer': (
            'Kalender menampilkan kegiatan, hari perayaan, dan jadwal terkait akun. Jadwal praktikum berbeda dari kalender umum. '
            'Pemilihan lab divalidasi berdasarkan jumlah mahasiswa dan kapasitas ruangan. Ruang tambahan hanya boleh untuk Lab Rekayasa Perangkat Lunak '
            'dan Lab Sistem Keamanan Informasi sesuai aturan sistem.'
        ),
    },
    {
        'keywords': {'honor', 'honorarium', 'gaji', 'transfer', 'tf'},
        'answer': (
            'Rekap Honorarium Asleb menghitung honor dari data absensi/pertemuan. Asisten Lab dapat melihat rincian honor miliknya: total sebelum potongan, '
            'biaya admin, total setelah potongan, dan bukti pembayaran. Laboran dapat mengonfirmasi transfer serta mengunggah bukti TF.'
        ),
    },
    {
        'keywords': {'notifikasi', 'email', 'pemberitahuan'},
        'answer': (
            'Notifikasi muncul di web dan beberapa event penting juga dikirim ke email, seperti OTP, pembukaan pendaftaran, status pendaftaran, '
            'peminjaman alat, jadwal, absensi, dan honor. Jika email tidak masuk, periksa konfigurasi SMTP/app password dan folder spam.'
        ),
    },
    {
        'keywords': {'pengaturan', 'tema', 'background', 'tampilan', 'pengguna'},
        'answer': (
            'Menu Pengaturan berisi profil, tampilan/tema, pengguna, dan pengaturan dasar sesuai role. Tema berubah langsung saat dipilih dan disimpan '
            'per akun, sehingga tetap sama setelah logout/login sampai user menggantinya lagi.'
        ),
    },
    {
        'keywords': {'mobile', 'apk', 'flutter', 'api'},
        'answer': (
            'Project juga menyiapkan aplikasi Flutter khusus Absensi Masuk Asisten Lab. Backend tetap Django/API, sedangkan aplikasi mobile dipakai '
            'untuk login asisten lab, melihat jadwal, melakukan absensi masuk, upload foto/video bukti, dan melihat riwayat absensi.'
        ),
    },
]


BOT_FALLBACK = (
    'Maaf, saya belum memahami pertanyaan tersebut. Coba tanyakan dengan kata kunci seperti pendaftaran asleb, absensi, nilai mahasiswa, '
    'peminjaman alat, kalender, honor, profil/CV, OTP, atau pengaturan. Jika masih belum cukup, teruskan percakapan ke admin.'
)
