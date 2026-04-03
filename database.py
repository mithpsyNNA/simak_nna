import sqlite3
import bcrypt
import os

DB_PATH = os.environ.get("DB_PATH", "simak_nna.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    # ─────────────────────────────────────────────
    # USERS & AUTH
    # ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','yayasan','kepsek','guru','siswa','ortu')),
        nama TEXT NOT NULL,
        email TEXT,
        no_hp TEXT,
        aktif INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # ─────────────────────────────────────────────
    # GURU / PEGAWAI
    # ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS guru (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        nip TEXT,
        nama TEXT NOT NULL,
        jabatan_fungsional TEXT DEFAULT 'Guru Kelas',
        jabatan_struktural TEXT,
        unit TEXT,
        status_kepegawaian TEXT DEFAULT 'Pegawai Tetap',
        kualifikasi TEXT,
        tahun_masuk INTEGER,
        wali_kelas TEXT,
        gaji_pokok INTEGER DEFAULT 0,
        tj_jabatan INTEGER DEFAULT 0,
        no_hp TEXT,
        alamat TEXT,
        foto TEXT,
        aktif INTEGER DEFAULT 1
    )""")

    # ─────────────────────────────────────────────
    # KELAS
    # ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS kelas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT NOT NULL,
        tingkat INTEGER NOT NULL,
        tahun_ajaran TEXT NOT NULL,
        wali_kelas_id INTEGER REFERENCES guru(id),
        kapasitas INTEGER DEFAULT 28,
        aktif INTEGER DEFAULT 1
    )""")

    # ─────────────────────────────────────────────
    # SISWA
    # ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS siswa (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        nis TEXT UNIQUE,
        nisn TEXT,
        nama TEXT NOT NULL,
        kelas_id INTEGER REFERENCES kelas(id),
        jenis_kelamin TEXT,
        tanggal_lahir TEXT,
        tempat_lahir TEXT,
        nama_ayah TEXT,
        nama_ibu TEXT,
        nama_wali TEXT,
        no_hp_ortu TEXT,
        alamat TEXT,
        tahun_masuk INTEGER,
        status TEXT DEFAULT 'Aktif' CHECK(status IN ('Aktif','Lulus','Keluar','Pindah')),
        foto TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # ─────────────────────────────────────────────
    # MATA PELAJARAN
    # ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS mata_pelajaran (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kode TEXT,
        nama TEXT NOT NULL,
        tingkat INTEGER,
        jp_per_minggu INTEGER DEFAULT 2,
        aktif INTEGER DEFAULT 1
    )""")

    # ─────────────────────────────────────────────
    # JADWAL
    # ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS jadwal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kelas_id INTEGER REFERENCES kelas(id),
        mata_pelajaran_id INTEGER REFERENCES mata_pelajaran(id),
        guru_id INTEGER REFERENCES guru(id),
        hari TEXT NOT NULL,
        jam_mulai TEXT NOT NULL,
        jam_selesai TEXT NOT NULL,
        tahun_ajaran TEXT,
        semester INTEGER DEFAULT 1
    )""")

    # ─────────────────────────────────────────────
    # ABSENSI SISWA
    # ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS absensi_siswa (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        siswa_id INTEGER REFERENCES siswa(id),
        kelas_id INTEGER REFERENCES kelas(id),
        tanggal TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Hadir','Izin','Sakit','Alpha')),
        keterangan TEXT,
        dicatat_oleh INTEGER REFERENCES users(id),
        created_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(siswa_id, tanggal)
    )""")

    # ─────────────────────────────────────────────
    # ABSENSI GURU
    # ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS absensi_guru (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guru_id INTEGER REFERENCES guru(id),
        tanggal TEXT NOT NULL,
        jam_masuk TEXT,
        jam_keluar TEXT,
        status TEXT DEFAULT 'Hadir' CHECK(status IN ('Hadir','Izin','Sakit','Alpha','Dinas Luar')),
        keterangan TEXT,
        dicatat_oleh INTEGER REFERENCES users(id),
        UNIQUE(guru_id, tanggal)
    )""")

    # ─────────────────────────────────────────────
    # NILAI
    # ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS nilai (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        siswa_id INTEGER REFERENCES siswa(id),
        mata_pelajaran_id INTEGER REFERENCES mata_pelajaran(id),
        kelas_id INTEGER REFERENCES kelas(id),
        semester INTEGER NOT NULL,
        tahun_ajaran TEXT NOT NULL,
        nilai_harian REAL,
        nilai_uts REAL,
        nilai_uas REAL,
        nilai_akhir REAL,
        predikat TEXT,
        catatan_guru TEXT,
        diinput_oleh INTEGER REFERENCES users(id),
        updated_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(siswa_id, mata_pelajaran_id, semester, tahun_ajaran)
    )""")

    # ─────────────────────────────────────────────
    # PPDB
    # ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS ppdb (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tahun_ajaran TEXT NOT NULL,
        nama_calon TEXT NOT NULL,
        tanggal_lahir TEXT,
        jenis_kelamin TEXT,
        nama_ayah TEXT,
        nama_ibu TEXT,
        no_hp TEXT NOT NULL,
        asal_sekolah TEXT,
        status TEXT DEFAULT 'Mendaftar' CHECK(status IN ('Mendaftar','Lulus Seleksi','Diterima','Tidak Diterima','Mengundurkan Diri')),
        catatan TEXT,
        tanggal_daftar TEXT DEFAULT (datetime('now','localtime')),
        diproses_oleh INTEGER REFERENCES users(id)
    )""")

    # ─────────────────────────────────────────────
    # PENGGAJIAN
    # ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS penggajian (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guru_id INTEGER REFERENCES guru(id),
        bulan INTEGER NOT NULL,
        tahun INTEGER NOT NULL,
        gaji_pokok INTEGER DEFAULT 0,
        tj_jabatan INTEGER DEFAULT 0,
        tj_lain INTEGER DEFAULT 0,
        lembur INTEGER DEFAULT 0,
        thr INTEGER DEFAULT 0,
        bruto INTEGER DEFAULT 0,
        potongan_bpjs_kes INTEGER DEFAULT 0,
        potongan_bpjs_tk INTEGER DEFAULT 0,
        potongan_lain INTEGER DEFAULT 0,
        thp INTEGER DEFAULT 0,
        status TEXT DEFAULT 'Belum Dibayar' CHECK(status IN ('Belum Dibayar','Sudah Dibayar')),
        tgl_bayar TEXT,
        catatan TEXT,
        dibuat_oleh INTEGER REFERENCES users(id),
        UNIQUE(guru_id, bulan, tahun)
    )""")

    # ─────────────────────────────────────────────
    # KEUANGAN
    # ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS keuangan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tanggal TEXT NOT NULL,
        jenis TEXT NOT NULL CHECK(jenis IN ('Pemasukan','Pengeluaran')),
        kategori TEXT NOT NULL,
        keterangan TEXT NOT NULL,
        jumlah INTEGER NOT NULL,
        sumber TEXT,
        bukti TEXT,
        dicatat_oleh INTEGER REFERENCES users(id),
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # ─────────────────────────────────────────────
    # SPP SISWA
    # ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS spp (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        siswa_id INTEGER REFERENCES siswa(id),
        bulan INTEGER NOT NULL,
        tahun INTEGER NOT NULL,
        jumlah INTEGER NOT NULL,
        status TEXT DEFAULT 'Belum Bayar' CHECK(status IN ('Belum Bayar','Lunas','Cicilan')),
        tgl_bayar TEXT,
        dicatat_oleh INTEGER REFERENCES users(id),
        UNIQUE(siswa_id, bulan, tahun)
    )""")

    # ─────────────────────────────────────────────
    # KPI KINERJA GURU
    # ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS kpi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guru_id INTEGER REFERENCES guru(id),
        periode TEXT NOT NULL,
        aspek_pembelajaran REAL,
        aspek_administrasi REAL,
        aspek_kedisiplinan REAL,
        aspek_struktural REAL,
        aspek_inovasi REAL,
        nilai_total REAL,
        predikat TEXT,
        catatan_penilai TEXT,
        penilai_id INTEGER REFERENCES users(id),
        tgl_penilaian TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(guru_id, periode)
    )""")

    # ─────────────────────────────────────────────
    # TUGAS STRUKTURAL
    # ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS tugas_struktural (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guru_id INTEGER REFERENCES guru(id),
        judul TEXT NOT NULL,
        deskripsi TEXT,
        kategori TEXT DEFAULT 'Umum',
        prioritas TEXT DEFAULT 'Normal' CHECK(prioritas IN ('Rendah','Normal','Tinggi','Urgent')),
        deadline TEXT,
        status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending','Proses','Selesai','Dibatalkan')),
        progress INTEGER DEFAULT 0,
        catatan_progres TEXT,
        dibuat_oleh INTEGER REFERENCES users(id),
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # ─────────────────────────────────────────────
    # NOTIFIKASI
    # ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS notifikasi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        judul TEXT NOT NULL,
        pesan TEXT NOT NULL,
        tipe TEXT DEFAULT 'info',
        dibaca INTEGER DEFAULT 0,
        link TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # ─────────────────────────────────────────────
    # PENGUMUMAN
    # ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS pengumuman (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        judul TEXT NOT NULL,
        isi TEXT NOT NULL,
        target TEXT DEFAULT 'semua',
        penting INTEGER DEFAULT 0,
        dibuat_oleh INTEGER REFERENCES users(id),
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    conn.commit()
    seed_data(conn)
    conn.close()
    print("✅ Database initialized.")

def seed_data(conn):
    c = conn.cursor()

    # Check if already seeded
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] > 0:
        return

    def hash_pw(pw):
        return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

    # ── USERS ──────────────────────────────────────
    users = [
        ("admin",       hash_pw("admin123"),    "admin",    "Administrator",              "admin@nna.sch.id",    "08100000000"),
        ("yayasan",     hash_pw("yayasan123"),  "yayasan",  "Pramitha Aulia, M.Psi",      "ketua@nna.sch.id",    "081234567890"),
        ("kepsek",      hash_pw("kepsek123"),   "kepsek",   "Desiana, S.Pd",              "kepsek@nna.sch.id",   "082345678901"),
        ("desiana",     hash_pw("guru123"),     "kepsek",   "Desiana, S.Pd",              "desiana@nna.sch.id",  "082345678901"),
        ("neni",        hash_pw("guru123"),     "guru",     "Neni Elika, S.Pd",           "neni@nna.sch.id",     "083456789012"),
        ("citra",       hash_pw("guru123"),     "guru",     "Citra Noveni, S.Pd",         "citra@nna.sch.id",    "084567890123"),
        ("agus",        hash_pw("guru123"),     "guru",     "Agus Salim Tanjung, S.Pd.I", "agus@nna.sch.id",     "085678901234"),
        ("ariyanti",    hash_pw("guru123"),     "guru",     "Ariyanti R. Lubis, S.Pd",    "ariyanti@nna.sch.id", "086789012345"),
        ("hairunisah",  hash_pw("guru123"),     "guru",     "Hairunisah, S.Pd",           "hair@nna.sch.id",     "087890123456"),
        ("rekani",      hash_pw("guru123"),     "guru",     "Rekani Sanja Siregar, S.Pd", "rekani@nna.sch.id",   "088901234567"),
        ("anin",        hash_pw("guru123"),     "guru",     "Anin Dita Safitri, S.Si",    "anin@nna.sch.id",     "089012345678"),
        ("nurlely",     hash_pw("guru123"),     "guru",     "Nurlely",                    "nurlely@nna.sch.id",  "081123456789"),
        ("annisa",      hash_pw("guru123"),     "guru",     "Annisa Rusdha, S.Pd",        "annisa@nna.sch.id",   "082234567890"),
        ("halimah",     hash_pw("guru123"),     "guru",     "Halimah Tussadia, S.Pd",     "halimah@nna.sch.id",  "083345678901"),
        ("winda",       hash_pw("guru123"),     "guru",     "Winda Widya Puspa, S.Pd",    "winda@nna.sch.id",    "084456789012"),
        ("rini",        hash_pw("guru123"),     "guru",     "Rini Febriani Sari, S.Pd",   "rini@nna.sch.id",     "085567890123"),
    ]
    c.executemany("INSERT INTO users (username,password_hash,role,nama,email,no_hp) VALUES (?,?,?,?,?,?)", users)

    # ── GURU DATA ──────────────────────────────────
    guru_data = [
        # user_id, nip, nama, jabatan_fungsional, jabatan_struktural, unit, status, kualifikasi, tahun_masuk, wali_kelas, gaji_pokok, tj_jabatan, no_hp
        (4,  "001", "Desiana, S.Pd",              "Guru Kelas",  "Kepala Sekolah",            "Manajemen",    "Pegawai Tetap", "S1 Biologi, 16 thn",      2008, None,      1500000, 800000, "082345678901"),
        (5,  "002", "Neni Elika, S.Pd",           "Guru Kelas",  "Wakasek Kurikulum",         "Manajemen",    "Pegawai Tetap", "S1 Biologi, 13 thn",      2011, "Kelas 5", 1200000, 400000, "083456789012"),
        (6,  "003", "Citra Noveni, S.Pd",         "Guru Kelas",  "Koord. Humas & Marketing",  "Unit Humas",   "Pegawai Tetap", "S1 B.Inggris, 11 thn",    2013, "Kelas 6", 1200000, 400000, "084567890123"),
        (7,  "004", "Agus Salim Tanjung, S.Pd.I", "Guru Agama",  "Koord. Karakter Islami",    "Unit Akademik","Pegawai Tetap", "S1 PAI, 10 thn",          2014, "Kelas 4B",1000000, 300000, "085678901234"),
        (8,  "005", "Ariyanti R. Lubis, S.Pd",   "Guru Kelas",  "Wakasek Kesiswaan",         "Manajemen",    "Pegawai Tetap", "S1 Matematika, 9 thn",    2015, "Kelas 4A",1200000, 500000, "086789012345"),
        (9,  "006", "Hairunisah, S.Pd",           "Guru Kelas",  "Tim Media Sosial",          "Unit Humas",   "Pegawai Tetap", "S1 Biologi, 8 thn",       2016, "Kelas 3A",1000000, 150000, "087890123456"),
        (10, "007", "Rekani Sanja Siregar, S.Pd", "Guru Kelas",  "Koord. Konten & Publikasi", "Unit Humas",   "Pegawai Tetap", "S1 B.Indonesia, 8 thn",   2016, "Kelas 3B",1000000, 200000, "088901234567"),
        (11, "008", "Anin Dita Safitri, S.Si",    "Guru Kelas",  "Koord. Akademik & Litbang", "Unit Akademik","Pegawai Tetap", "S1 Matematika, 8 thn",    2016, "Kelas 2A",1100000, 300000, "089012345678"),
        (12, "009", "Nurlely",                    "Guru Kelas",  "Bendahara Sekolah",         "Administrasi", "Pegawai Tetap", "SMK Ekonomi, 7 thn",      2017, None,      1050000, 200000, "081123456789"),
        (13, "010", "Annisa Rusdha, S.Pd",        "Guru Kelas",  "Admin Kesiswaan",           "Administrasi", "Pegawai Tetap", "S1 B.Indonesia, 6 thn",   2018, "Kelas 2B",1000000, 150000, "082234567890"),
        (14, "011", "Halimah Tussadia, S.Pd",     "Guru Kelas",  "Tim Media Sosial",          "Unit Humas",   "Pegawai Tetap", "S1 B.Inggris, 5 thn",     2019, "Kelas 1A",1000000, 150000, "083345678901"),
        (15, "012", "Winda Widya Puspa, S.Pd",    "Guru Kelas",  "Admin PPDB",                "Administrasi", "Pegawai Tetap", "S1 PGSD, 5 thn",          2019, "Kelas 1B",1000000, 150000, "084456789012"),
        (16, "013", "Rini Febriani Sari, S.Pd",   "Guru Kelas",  None,                        "Unit Akademik","Pegawai Tetap", "S1 PGMI, 3 thn",          2021, None,       950000,       0, "085567890123"),
    ]
    c.executemany("""INSERT INTO guru
        (user_id,nip,nama,jabatan_fungsional,jabatan_struktural,unit,status_kepegawaian,kualifikasi,tahun_masuk,wali_kelas,gaji_pokok,tj_jabatan,no_hp)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", guru_data)

    # ── KELAS ───────────────────────────────────────
    kelas_data = [
        ("Kelas 1A", 1, "2025/2026", 11, 28),
        ("Kelas 1B", 1, "2025/2026", 12, 28),
        ("Kelas 2A", 2, "2025/2026", 8, 28),
        ("Kelas 2B", 2, "2025/2026", 10, 28),
        ("Kelas 3A", 3, "2025/2026", 6, 28),
        ("Kelas 3B", 3, "2025/2026", 7, 28),
        ("Kelas 4A", 4, "2025/2026", 5, 28),
        ("Kelas 4B", 4, "2025/2026", 4, 28),
        ("Kelas 5",  5, "2025/2026", 2, 28),
        ("Kelas 6",  6, "2025/2026", 3, 28),
    ]
    c.executemany("INSERT INTO kelas (nama,tingkat,tahun_ajaran,wali_kelas_id,kapasitas) VALUES (?,?,?,?,?)", kelas_data)

    # ── MATA PELAJARAN ──────────────────────────────
    mapel = [
        ("MTK",  "Matematika",           None, 6),
        ("BIN",  "Bahasa Indonesia",     None, 6),
        ("IPA",  "Ilmu Pengetahuan Alam",None, 4),
        ("IPS",  "Ilmu Pengetahuan Sosial",None,4),
        ("PAI",  "Pendidikan Agama Islam",None,4),
        ("PKN",  "PPKn",                 None, 2),
        ("BING", "Bahasa Inggris",       None, 4),
        ("PJOK", "PJOK",                 None, 4),
        ("SBK",  "Seni Budaya & Keterampilan",None,2),
        ("TAH",  "Tahfiz Al-Qur'an",     None, 6),
    ]
    c.executemany("INSERT INTO mata_pelajaran (kode,nama,tingkat,jp_per_minggu) VALUES (?,?,?,?)", mapel)

    # ── SAMPLE SISWA (30 siswa) ─────────────────────
    import random
    names_m = ["Ahmad Fauzi","Muhammad Rizki","Farhan Maulana","Daffa Pratama","Zaki Abdullah",
               "Ilham Syahputra","Rafi Hidayat","Nabil Akbar","Fathan Ardiansyah","Bagas Kurniawan"]
    names_f = ["Aisyah Putri","Fatimah Azzahra","Zahra Nurul","Siti Rofiah","Nabila Rahmah",
               "Aulia Fitri","Salma Khoirunisa","Nayla Syifa","Adinda Rahma","Putri Maharani"]
    all_names = [(n,"L") for n in names_m] + [(n,"P") for n in names_f]

    siswa_rows = []
    for i, (nama, jk) in enumerate(all_names * 2):
        kelas_id = (i % 10) + 1
        nis = f"2020{i+1:04d}"
        siswa_rows.append((nis, f"{nama} {i+1}", kelas_id, jk, f"2016-0{(i%9)+1}-15",
                           "Pematangsiantar", f"Ayah {nama}", f"Ibu {nama}", "08"+str(random.randint(1000000000,9999999999)),
                           "Pematangsiantar", 2020+int(kelas_id/2)))

    c.executemany("""INSERT INTO siswa (nis,nama,kelas_id,jenis_kelamin,tanggal_lahir,tempat_lahir,
        nama_ayah,nama_ibu,no_hp_ortu,alamat,tahun_masuk)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""", siswa_rows)

    conn.commit()
    print("✅ Seed data inserted.")

if __name__ == "__main__":
    init_db()
