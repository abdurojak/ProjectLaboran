from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class MataKuliahAsleb(models.Model):
    MATKUL_CHOICES = [
        ('JK_IF01_IR_ADRIAN', 'Jaringan Komputer - Ir. Adrian Syamsul Gamar, MTI - TIF-01'),
        ('JK_TIF02_IR_GATOT', 'Jaringan Komputer - Ir. Gatot Budi Santoso, M.Kom - TIF-02'),
        ('MDI_TIF01_SYANDRA', 'Manajemen Data dan Informasi - Syandra Sari, M.Kom - TIF-01'),
        ('MDI_TIF02_ANUNG', 'Manajemen Data dan Informasi - Anung B. Attibowo, M.Kom - TIF-02'),
        ('MDI_BI01_AGUS', 'Manajemen Data dan Informasi - Agus Salim, S.T., MTI - BI-01'),
        ('MDI_BI02_SYANDRA', 'Manajemen Data dan Informasi - Syandra Sari, M.Kom - BI-02'),
        ('ERP_BI01_DINI', 'Enterprise Resource Planning - Ir. Dini Solihah, S.T., M.Kom - BI-01'),
        ('ERP_BI02_IR_TEDDY', 'Enterprise Resource Planning - Dr. Ir. Teddy Bickwanto, M.MSI - BI-02'),
        ('DW_BI01_IR_TEDDY', 'Data Warehouse - Dr. Ir. Teddy Bickwanto, M.MSI - BI-01'),
        ('DW_BI02_SYANDRA', 'Data Warehouse - Syandra Sari, M.Kom, MTI - BI-02'),
        ('SDA_TIF01_ABDUL', 'Struktur Data dan Algoritma - Abdul Roohman, M.Kom - TIF-01'),
        ('SDA_TIF02_ANUNG', 'Struktur Data dan Algoritma - Anung B. Attibowo, M.Kom - TIF-02'),
        ('SDA_BI01_ANUNG', 'Struktur Data dan Algoritma - Anung B. Attibowo, M.Kom - BI-01'),
        ('SDA_BI02_ABDUL', 'Struktur Data dan Algoritma - Abdul Roohman, M.Kom - BI-02'),
        ('PS_TIF01_DR_DEDY', 'Probabilitas dan Statistika - Dr. Dedy Sugiharto, S.Si., M.M., M.Kom - TIF-01'),
        ('PS_BI01_DRS_AYUDIN', 'Probabilitas dan Statistika - Drs. Ayfuddin, M.Si., Ph.D - BI-01'),
        ('PS_BI02_IR_JOKO', 'Probabilitas dan Statistika - Dr. Joko Putroto, M.MSI - BI-02'),
        ('PW_TIF02_DIAN', 'Pemrograman Web - Dian Pratiwi, S.T., MTI - TIF-02'),
        ('PW_TIF01_YUNIA', 'Pemrograman Web - Yunia Ningish, M.Kom - TIF-01'),
        ('PW_TIF01_DR_BINTI', 'Pemrograman Web - Dr. Binti Solihah, S.T., M.Kom - TIF-01'),
        ('PM_TIF01_RIFDAH', 'Pemrograman Mobile - Rifdah Amelia, M.Kom - TIF-01'),
        ('PM_TIF01_DIAN', 'Pemrograman Mobile - Dian Pratiwi, S.T., MTI - TIF-01'),
        ('PBO_TIF01_ABDUL', 'Pemrograman Berorientasi Objek - Abdul Roohman, M.Kom - TIF-01'),
        ('PBO_TIF02_DR_BINTI', 'Pemrograman Berorientasi Objek - Dr. Binti Solihah, S.T., M.Kom - TIF-02'),
        ('PBO_TIF02_DR_AHMAD', 'Pemrograman Berorientasi Objek - Dr Ahmad Zuhdi, S.Si., M.Kom - TIF-02'),
        ('AD_BI01_SYANDRA', 'Analitik Data - Syandra Sari, M.Kom - BI-01'),
        ('AD_BI02_DR_DEDY', 'Analitik Data - Dr. Dedy Sugiharto, S.Si., M.M., M.Kom - BI-02'),
        ('ML_BI01_ANUNG', 'Machine Learning - Anung B. Attibowo, M.Kom - BI-01'),
        ('KK_BI01_DR_BINTI', 'Keamanan Komputasi - Dr. Binti Solihah, S.T., M.Kom - BI-01'),
        ('KK_BI02_IR_WARDIANTO', 'Keamanan Komputasi - Ir. Wardianto, S.Si., M.Kom - BI-02'),
        ('KK_BI02_IR_ADRIAN', 'Keamanan Komputasi - Ir. Adrian Syamsul Gamar, MTI - BI-02'),
    ]

    kode = models.CharField(max_length=80, unique=True)
    kode_mk = models.CharField('Kode Mata Kuliah', max_length=20, blank=True, db_index=True)
    nama = models.CharField(max_length=200)
    sks = models.PositiveSmallIntegerField('SKS', default=0, blank=True)
    dosen = models.CharField(max_length=200)
    kelas = models.CharField(max_length=50)
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ['nama', 'kelas', 'dosen']
        verbose_name = 'Mata Kuliah Aslab'
        verbose_name_plural = 'Mata Kuliah Aslab'

    def __str__(self):
        return f'{self.nama} - {self.dosen} - {self.kelas}'


class PengaturanPendaftaranAsleb(models.Model):
    dibuka = models.BooleanField(default=False)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pengaturan Pendaftaran Aslab'
        verbose_name_plural = 'Pengaturan Pendaftaran Aslab'

    @classmethod
    def get_solo(cls):
        pengaturan, _ = cls.objects.get_or_create(pk=1)
        return pengaturan

    def __str__(self):
        return 'Pendaftaran Aslab Dibuka' if self.dibuka else 'Pendaftaran Aslab Ditutup'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        today = timezone.localdate()
        period = PeriodeAsleb.get_for_date(today)
        if self.dibuka and not period.pendaftaran_dibuka:
            period.pendaftaran_mulai = today
            period.pendaftaran_selesai = min(period.selesai, today + timedelta(days=29))
            period.save(update_fields=['pendaftaran_mulai', 'pendaftaran_selesai', 'diperbarui_pada'])
        elif not self.dibuka and period.pendaftaran_dibuka:
            period.pendaftaran_selesai = today - timedelta(days=1)
            if period.pendaftaran_mulai > period.pendaftaran_selesai:
                period.pendaftaran_mulai = period.pendaftaran_selesai
            period.save(update_fields=['pendaftaran_mulai', 'pendaftaran_selesai', 'diperbarui_pada'])


class PeriodeAsleb(models.Model):
    SEMESTER_CHOICES = [(1, 'Januari - Juni'), (2, 'Juli - Desember')]

    tahun = models.PositiveSmallIntegerField()
    semester = models.PositiveSmallIntegerField(choices=SEMESTER_CHOICES)
    mulai = models.DateField()
    selesai = models.DateField()
    pendaftaran_mulai = models.DateField()
    pendaftaran_selesai = models.DateField()
    diakhiri_pada = models.DateTimeField(blank=True, null=True)
    diakhiri_oleh = models.ForeignKey(
        'pengguna.Pengguna',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='periode_asleb_diakhiri',
    )
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-tahun', '-semester']
        constraints = [
            models.UniqueConstraint(fields=['tahun', 'semester'], name='unique_periode_asleb_per_semester'),
        ]
        verbose_name = 'Periode Aslab'
        verbose_name_plural = 'Periode Aslab'

    @property
    def nama(self):
        bulan = 'Januari - Juni' if self.semester == 1 else 'Juli - Desember'
        return f'{bulan} {self.tahun}'

    @property
    def pendaftaran_dibuka(self):
        today = timezone.localdate()
        return self.pendaftaran_mulai <= today <= self.pendaftaran_selesai

    @property
    def sedang_berjalan(self):
        today = timezone.localdate()
        return self.mulai <= today <= self.selesai

    @classmethod
    def get_for_date(cls, value=None):
        value = value or timezone.localdate()
        semester = 1 if value.month <= 6 else 2
        start_month = 1 if semester == 1 else 7
        end_month = 6 if semester == 1 else 12
        defaults = {
            'mulai': date(value.year, start_month, 1),
            'selesai': date(value.year, end_month, 30 if end_month == 6 else 31),
            'pendaftaran_mulai': date(value.year, start_month, 1),
            'pendaftaran_selesai': date(value.year, start_month, 1) + timedelta(days=29),
        }
        period, _ = cls.objects.get_or_create(tahun=value.year, semester=semester, defaults=defaults)
        return period

    def __str__(self):
        return self.nama


class PendaftaranAsleb(models.Model):
    JENIS_REGULER = 'reguler'
    JENIS_REPLACEMENT = 'replacement'
    JENIS_CHOICES = [
        (JENIS_REGULER, 'Reguler'),
        (JENIS_REPLACEMENT, 'Pengganti'),
    ]
    STATUS_CHOICES = [
        ('diajukan', 'Diajukan'),
        ('diterima', 'Diterima'),
        ('ditolak', 'Ditolak'),
        ('digenerate', 'Masuk Data Aslab'),
    ]
    LIVE_REPLACEMENT_STATUSES = {'diajukan', 'diterima'}
    METODE_REKENING_CHOICES = [
        ('bni', 'BNI (gratis biaya admin)'),
        ('bank_lain', 'Bank lain (biaya admin Rp2.500)'),
        ('dana', 'DANA (gratis biaya admin)'),
        ('shopeepay', 'ShopeePay (biaya admin Rp1.500)'),
        ('gopay', 'GoPay (biaya admin Rp1.500)'),
        ('ovo', 'OVO (biaya admin Rp1.500)'),
    ]
    NILAI_CHOICES = [
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('E', 'E'),
        ('tidak_terbaca', 'Tidak terbaca'),
    ]

    nama = models.CharField(max_length=150)
    nim = models.CharField('NIM', max_length=30)
    no_hp = models.CharField('No HP', max_length=30)
    email = models.EmailField(blank=True)
    program_studi = models.CharField(max_length=120)
    semester = models.PositiveSmallIntegerField()
    matkul = models.ForeignKey(MataKuliahAsleb, on_delete=models.PROTECT, related_name='pendaftaran')
    periode = models.ForeignKey(
        PeriodeAsleb,
        on_delete=models.PROTECT,
        related_name='pendaftaran',
        blank=True,
        null=True,
    )
    cv = models.FileField('CV', upload_to='pendaftaran_asleb/cv/', blank=True)
    transkrip = models.FileField('Transkrip', upload_to='pendaftaran_asleb/transkrip/', blank=True)
    tanda_tangan = models.ImageField('Tanda Tangan', upload_to='pendaftaran_asleb/tanda_tangan/', blank=True)
    metode_rekening = models.CharField(
        max_length=30,
        choices=METODE_REKENING_CHOICES,
        default='bni',
    )
    rekening = models.CharField(max_length=150, blank=True)
    nama_pemilik_rekening = models.CharField('Atas Nama', max_length=150, blank=True)
    nilai_transkrip = models.CharField(
        max_length=20,
        choices=NILAI_CHOICES,
        default='tidak_terbaca',
    )
    skor_nilai = models.PositiveSmallIntegerField(default=0)
    alasan = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='diajukan')
    jenis = models.CharField(max_length=16, choices=JENIS_CHOICES, default=JENIS_REGULER)
    replacement_process = models.ForeignKey(
        'AslabReplacement',
        on_delete=models.PROTECT,
        related_name='registrations',
        null=True,
        blank=True,
    )
    candidate_user = models.ForeignKey(
        'pengguna.Pengguna',
        on_delete=models.PROTECT,
        related_name='aslab_registrations',
        null=True,
        blank=True,
    )
    live_candidate_user = models.ForeignKey(
        'pengguna.Pengguna',
        on_delete=models.PROTECT,
        related_name='live_aslab_registrations',
        null=True,
        blank=True,
        editable=False,
    )
    tanggal_daftar = models.DateField(auto_now_add=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['matkul__nama', 'matkul__kelas', '-skor_nilai', 'dibuat_pada', 'nama']
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(
                        jenis='reguler',
                        replacement_process__isnull=True,
                        candidate_user__isnull=True,
                    )
                    | models.Q(
                        jenis='replacement',
                        replacement_process__isnull=False,
                        candidate_user__isnull=False,
                    )
                ),
                name='registration_replacement_linkage_guard',
            ),
            models.UniqueConstraint(
                fields=['replacement_process', 'live_candidate_user'],
                name='unique_live_replacement_registration_candidate',
            ),
            models.CheckConstraint(
                check=(
                    models.Q(
                        jenis='replacement',
                        status__in=['diajukan', 'diterima'],
                        candidate_user__isnull=False,
                        live_candidate_user__isnull=False,
                        live_candidate_user=models.F('candidate_user'),
                    )
                    | (
                        ~models.Q(
                            jenis='replacement',
                            status__in=['diajukan', 'diterima'],
                        )
                        & models.Q(live_candidate_user__isnull=True)
                    )
                ),
                name='live_replacement_registration_guard',
            ),
        ]
        verbose_name = 'Pendaftaran Aslab'
        verbose_name_plural = 'Pendaftaran Aslab'

    def __str__(self):
        return f'{self.nama} - {self.matkul}'

    def clean(self):
        super().clean()
        expected_id = (
            self.candidate_user_id
            if self.jenis == self.JENIS_REPLACEMENT
            and self.status in self.LIVE_REPLACEMENT_STATUSES
            else None
        )
        if self.live_candidate_user_id != expected_id:
            raise ValidationError({
                'live_candidate_user': 'Guard pendaftaran pengganti aktif tidak sesuai.',
            })

    def save(self, *args, **kwargs):
        self.live_candidate_user_id = (
            self.candidate_user_id
            if self.jenis == self.JENIS_REPLACEMENT
            and self.status in self.LIVE_REPLACEMENT_STATUSES
            else None
        )
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            persisted_fields = set(update_fields)
            guard_dependencies = {
                'jenis', 'status',
                'replacement_process', 'replacement_process_id',
                'candidate_user', 'candidate_user_id',
                'live_candidate_user', 'live_candidate_user_id',
            }
            if persisted_fields.intersection(guard_dependencies):
                persisted_fields.add('live_candidate_user')
            kwargs['update_fields'] = persisted_fields
        super().save(*args, **kwargs)

    @staticmethod
    def grade_to_score(grade):
        return {
            'A': 3,
            'B': 2,
            'C': 1,
        }.get(grade, 0)

    @property
    def biaya_admin_transfer(self):
        return PengaturanBiayaTransfer.get_solo().get_fee(self.metode_rekening)


class RiwayatAsleb(models.Model):
    nim = models.CharField('NIM', max_length=30, db_index=True)
    nama = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    periode = models.ForeignKey(PeriodeAsleb, on_delete=models.PROTECT, related_name='riwayat_asleb')
    matkul = models.ForeignKey(MataKuliahAsleb, on_delete=models.PROTECT, related_name='riwayat_asleb')
    metode_rekening = models.CharField(max_length=30, choices=PendaftaranAsleb.METODE_REKENING_CHOICES)
    rekening = models.CharField(max_length=150, blank=True)
    nama_pemilik_rekening = models.CharField(max_length=150, blank=True)
    source_pendaftaran_id = models.PositiveBigIntegerField()
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-periode__tahun', '-periode__semester', 'nama']
        constraints = [
            models.UniqueConstraint(
                fields=['nim', 'periode', 'matkul'],
                name='unique_riwayat_asleb_periode_matkul',
            ),
            models.UniqueConstraint(
                fields=['source_pendaftaran_id'],
                name='unique_source_pendaftaran_riwayat_asleb',
            ),
        ]
        verbose_name = 'Riwayat Aslab'
        verbose_name_plural = 'Riwayat Aslab'

    def __str__(self):
        return f'{self.nama} - {self.matkul} - {self.periode}'


class AslabSlot(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_VACANT = 'vacant'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Aktif'),
        (STATUS_VACANT, 'Kosong'),
        (STATUS_CLOSED, 'Ditutup'),
    ]

    periode = models.ForeignKey(
        PeriodeAsleb,
        on_delete=models.PROTECT,
        related_name='aslab_slots',
    )
    matkul = models.ForeignKey(
        MataKuliahAsleb,
        on_delete=models.PROTECT,
        related_name='aslab_slots',
    )
    nomor = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['periode', 'matkul', 'nomor']
        constraints = [
            models.CheckConstraint(
                check=models.Q(nomor__in=[1, 2]),
                name='aslab_slot_number_1_or_2',
            ),
            models.UniqueConstraint(
                fields=['periode', 'matkul', 'nomor'],
                name='unique_aslab_slot',
            ),
        ]
        verbose_name = 'Slot Aslab'
        verbose_name_plural = 'Slot Aslab'

    def __str__(self):
        return f'{self.periode} - {self.matkul} - Slot {self.nomor}'


class AslabAssignment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_ACTIVE = 'active'
    STATUS_RESIGNED = 'resigned'
    STATUS_TERMINATED = 'terminated'
    STATUS_REPLACED = 'replaced'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Menunggu'),
        (STATUS_ACTIVE, 'Aktif'),
        (STATUS_RESIGNED, 'Mengundurkan Diri'),
        (STATUS_TERMINATED, 'Diberhentikan'),
        (STATUS_REPLACED, 'Digantikan'),
        (STATUS_COMPLETED, 'Selesai'),
        (STATUS_CANCELLED, 'Dibatalkan'),
    ]

    slot = models.ForeignKey(
        AslabSlot,
        on_delete=models.PROTECT,
        related_name='assignments',
    )
    active_slot = models.OneToOneField(
        AslabSlot,
        on_delete=models.PROTECT,
        related_name='active_assignment',
        null=True,
        blank=True,
        editable=False,
    )
    asleb = models.ForeignKey(
        'asleb.Asleb',
        on_delete=models.PROTECT,
        related_name='assignments',
    )
    source_pendaftaran = models.ForeignKey(
        PendaftaranAsleb,
        on_delete=models.SET_NULL,
        related_name='aslab_assignments',
        null=True,
        blank=True,
    )
    mulai_pada = models.DateField()
    berakhir_pada = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    alasan_berakhir = models.TextField(blank=True)
    diakhiri_oleh = models.ForeignKey(
        'pengguna.Pengguna',
        on_delete=models.SET_NULL,
        related_name='aslab_assignments_ended',
        null=True,
        blank=True,
    )
    menggantikan = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        related_name='digantikan_oleh',
        null=True,
        blank=True,
    )
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-mulai_pada', '-dibuat_pada']
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(
                        status='active',
                        active_slot__isnull=False,
                        active_slot=models.F('slot'),
                    )
                    | (~models.Q(status='active') & models.Q(active_slot__isnull=True))
                ),
                name='active_assignment_slot_guard',
            ),
        ]
        verbose_name = 'Penugasan Aslab'
        verbose_name_plural = 'Penugasan Aslab'

    def clean(self):
        super().clean()
        expected_active_slot_id = self.slot_id if self.status == self.STATUS_ACTIVE else None
        if self.active_slot_id != expected_active_slot_id:
            raise ValidationError({
                'active_slot': 'Guard slot aktif harus sesuai dengan slot dan status penugasan.',
            })

    def save(self, *args, **kwargs):
        self.active_slot_id = self.slot_id if self.status == self.STATUS_ACTIVE else None
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            persisted_fields = set(update_fields)
            if persisted_fields.intersection({'status', 'slot', 'slot_id'}):
                persisted_fields.add('active_slot')
            kwargs['update_fields'] = persisted_fields
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.asleb} - {self.slot} - {self.get_status_display()}'


class AslabReplacement(models.Model):
    METHOD_UNDECIDED = 'undecided'
    METHOD_DIRECT_OFFER = 'direct_offer'
    METHOD_LIMITED_REGISTRATION = 'limited_registration'
    METHOD_CHOICES = [
        (METHOD_UNDECIDED, 'Belum Ditentukan'),
        (METHOD_DIRECT_OFFER, 'Penawaran Langsung'),
        (METHOD_LIMITED_REGISTRATION, 'Pendaftaran Terbatas'),
    ]
    STATUS_WAITING_ACTION = 'waiting_action'
    STATUS_SEARCHING = 'searching'
    STATUS_WAITING_CONSENT = 'waiting_consent'
    STATUS_COMPLETING_DATA = 'completing_data'
    STATUS_WAITING_VERIFICATION = 'waiting_verification'
    STATUS_ACTIVE = 'active'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_WAITING_ACTION, 'Menunggu Tindakan'),
        (STATUS_SEARCHING, 'Mencari Pengganti'),
        (STATUS_WAITING_CONSENT, 'Menunggu Persetujuan'),
        (STATUS_COMPLETING_DATA, 'Melengkapi Data'),
        (STATUS_WAITING_VERIFICATION, 'Menunggu Verifikasi'),
        (STATUS_ACTIVE, 'Aktif'),
        (STATUS_CANCELLED, 'Dibatalkan'),
    ]

    slot = models.ForeignKey(AslabSlot, on_delete=models.PROTECT, related_name='replacements')
    outgoing_assignment = models.OneToOneField(
        AslabAssignment, on_delete=models.PROTECT, related_name='replacement_process'
    )
    incoming_assignment = models.OneToOneField(
        AslabAssignment, on_delete=models.PROTECT, related_name='incoming_replacement_process',
        null=True, blank=True,
    )
    effective_date = models.DateField()
    transfer_month = models.DateField()
    method = models.CharField(max_length=24, choices=METHOD_CHOICES, default=METHOD_UNDECIDED)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_WAITING_ACTION)
    created_by = models.ForeignKey(
        'pengguna.Pengguna', on_delete=models.PROTECT, related_name='aslab_replacements_created'
    )
    activated_by = models.ForeignKey(
        'pengguna.Pengguna', on_delete=models.SET_NULL,
        related_name='aslab_replacements_activated', null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        errors = {}
        if (
            self.slot_id and self.outgoing_assignment_id
            and self.slot_id != self.outgoing_assignment.slot_id
        ):
            errors['slot'] = 'Slot harus sama dengan penugasan aslab yang keluar.'
        if self.incoming_assignment_id:
            if self.slot_id != self.incoming_assignment.slot_id:
                errors['incoming_assignment'] = 'Penugasan masuk harus menggunakan slot yang sama.'
            elif self.incoming_assignment.menggantikan_id != self.outgoing_assignment_id:
                errors['incoming_assignment'] = 'Penugasan masuk harus menggantikan penugasan yang keluar.'
        if self.transfer_month and self.transfer_month.day != 1:
            errors['transfer_month'] = 'Bulan transfer harus menggunakan tanggal pertama.'
        if (
            self.effective_date and self.transfer_month
            and (self.effective_date.year, self.effective_date.month)
            != (self.transfer_month.year, self.transfer_month.month)
        ):
            errors['transfer_month'] = 'Bulan transfer harus sesuai dengan tanggal efektif.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'Penggantian {self.outgoing_assignment} ({self.get_status_display()})'


class AslabOffer(models.Model):
    STATUS_WAITING = 'waiting'
    STATUS_ACCEPTED_INCOMPLETE = 'accepted_incomplete'
    STATUS_SUBMITTED = 'submitted'
    STATUS_VERIFIED = 'verified'
    STATUS_DECLINED = 'declined'
    STATUS_EXPIRED = 'expired'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_WAITING, 'Menunggu'),
        (STATUS_ACCEPTED_INCOMPLETE, 'Diterima, Data Belum Lengkap'),
        (STATUS_SUBMITTED, 'Diajukan'),
        (STATUS_VERIFIED, 'Terverifikasi'),
        (STATUS_DECLINED, 'Ditolak'),
        (STATUS_EXPIRED, 'Kedaluwarsa'),
        (STATUS_CANCELLED, 'Dibatalkan'),
    ]
    LIVE_STATUSES = {STATUS_WAITING, STATUS_ACCEPTED_INCOMPLETE, STATUS_SUBMITTED}

    replacement = models.ForeignKey(
        AslabReplacement, on_delete=models.PROTECT, related_name='offers'
    )
    live_replacement = models.OneToOneField(
        AslabReplacement, on_delete=models.PROTECT, related_name='live_offer',
        null=True, blank=True, editable=False,
    )
    candidate = models.ForeignKey(
        'pengguna.Pengguna', on_delete=models.PROTECT, related_name='aslab_offers'
    )
    registration = models.OneToOneField(
        PendaftaranAsleb, on_delete=models.SET_NULL, related_name='replacement_offer',
        null=True, blank=True,
    )
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_WAITING)
    deadline = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        'pengguna.Pengguna', on_delete=models.SET_NULL, related_name='aslab_offers_verified',
        null=True, blank=True,
    )
    verification_notes = models.TextField(blank=True)
    decline_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-id']
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(status__in=['waiting', 'accepted_incomplete', 'submitted'],
                             live_replacement__isnull=False,
                             live_replacement=models.F('replacement'))
                    | (~models.Q(status__in=['waiting', 'accepted_incomplete', 'submitted'])
                       & models.Q(live_replacement__isnull=True))
                ),
                name='aslab_offer_live_replacement_guard',
            ),
        ]

    def clean(self):
        super().clean()
        expected_id = self.replacement_id if self.status in self.LIVE_STATUSES else None
        if self.live_replacement_id != expected_id:
            raise ValidationError({'live_replacement': 'Guard penawaran aktif tidak sesuai.'})

    def save(self, *args, **kwargs):
        self.live_replacement_id = (
            self.replacement_id if self.status in self.LIVE_STATUSES else None
        )
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            persisted_fields = set(update_fields)
            if persisted_fields.intersection({'status', 'replacement', 'replacement_id'}):
                persisted_fields.add('live_replacement')
            kwargs['update_fields'] = persisted_fields
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.candidate} - {self.replacement} ({self.get_status_display()})'


class LimitedReplacementOpening(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_OPEN = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_FILLED = 'filled'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draf'), (STATUS_OPEN, 'Dibuka'),
        (STATUS_CLOSED, 'Ditutup'), (STATUS_FILLED, 'Terisi'),
    ]

    replacement = models.OneToOneField(
        AslabReplacement, on_delete=models.PROTECT, related_name='limited_opening'
    )
    opens_at = models.DateTimeField()
    closes_at = models.DateTimeField()
    program_studi = models.CharField(max_length=120, blank=True)
    cohort = models.PositiveSmallIntegerField(null=True, blank=True)
    allowed_candidates = models.ManyToManyField(
        'pengguna.Pengguna', related_name='limited_replacement_openings', blank=True
    )
    additional_requirements = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.opens_at and self.closes_at and self.closes_at <= self.opens_at:
            raise ValidationError({'closes_at': 'Waktu penutupan harus setelah pembukaan.'})


class AslabReplacementAudit(models.Model):
    replacement = models.ForeignKey(
        AslabReplacement, on_delete=models.PROTECT, related_name='audit_entries'
    )
    actor = models.ForeignKey(
        'pengguna.Pengguna', on_delete=models.SET_NULL,
        related_name='aslab_replacement_audits', null=True, blank=True,
    )
    action = models.CharField(max_length=80)
    previous_state = models.CharField(max_length=24, blank=True)
    new_state = models.CharField(max_length=24, blank=True)
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']


class PengaturanBiayaTransfer(models.Model):
    biaya_bni = models.PositiveIntegerField('Biaya BNI', default=0)
    biaya_bank_lain = models.PositiveIntegerField('Biaya Bank Lain', default=2500)
    biaya_dana = models.PositiveIntegerField('Biaya DANA', default=0)
    biaya_shopeepay = models.PositiveIntegerField('Biaya ShopeePay', default=1500)
    biaya_gopay = models.PositiveIntegerField('Biaya GoPay', default=1500)
    biaya_ovo = models.PositiveIntegerField('Biaya OVO', default=1500)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pengaturan Biaya Transfer'
        verbose_name_plural = 'Pengaturan Biaya Transfer'

    @classmethod
    def get_solo(cls):
        setting, _ = cls.objects.get_or_create(pk=1)
        return setting

    def get_fee(self, method):
        return {
            'bni': self.biaya_bni,
            'bank_lain': self.biaya_bank_lain,
            'rekening_bank': self.biaya_bank_lain,
            'dana': self.biaya_dana,
            'shopeepay': self.biaya_shopeepay,
            'gopay': self.biaya_gopay,
            'ovo': self.biaya_ovo,
        }.get(method, 0)

    def __str__(self):
        return 'Pengaturan Biaya Transfer Honor'
