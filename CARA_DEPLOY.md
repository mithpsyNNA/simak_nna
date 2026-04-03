# 🚀 CARA DEPLOY SIMAK NNA

## Opsi 1: Railway.app (GRATIS, Paling Mudah)

1. Buat akun di https://railway.app (pakai Google/GitHub)
2. Klik **"New Project" → "Deploy from GitHub"**
3. Upload folder `simak_nna` ke GitHub terlebih dahulu
4. Pilih repo, Railway otomatis detect Python
5. Di tab **Variables**, tambahkan:
   - `JWT_SECRET` = buat string acak panjang (mis: `nna2026secretkey!@#`)
   - `PORT` = 5000
6. Klik **Deploy** → tunggu 2-3 menit
7. Railway beri URL seperti `https://simak-nna.up.railway.app`
8. **Selesai!** Bisa diakses dari HP/laptop siapapun

---

## Opsi 2: Render.com (GRATIS)

1. Buat akun di https://render.com
2. New → **Web Service** → Connect GitHub repo
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn app:app`
5. Tambah Environment Variable: `JWT_SECRET`
6. Deploy → dapat URL gratis

---

## Opsi 3: Jalankan Lokal (WiFi Sekolah)

```bash
# Di laptop/PC sekolah, buka terminal:
cd simak_nna
pip install -r requirements.txt
python app.py

# Cari IP laptop (Windows: ipconfig, Mac/Linux: ifconfig)
# Semua perangkat di WiFi sekolah bisa akses via:
# http://192.168.x.x:5000
```

---

## Akun Default

| Username | Password    | Role              |
|----------|-------------|-------------------|
| admin    | admin123    | Administrator     |
| kepsek   | kepsek123   | Kepala Sekolah    |
| neni     | guru123     | Guru (Wakasek)    |
| yayasan  | yayasan123  | Pengurus Yayasan  |

**⚠️ WAJIB GANTI PASSWORD setelah pertama login!**

---

## Fitur Sistem

- ✅ **Absensi Siswa** — Input harian per kelas, rekap bulanan
- ✅ **Absensi Guru** — Dengan jam masuk/keluar dan status
- ✅ **Nilai & Rapor** — Input nilai, hitung otomatis, cetak rapor
- ✅ **Jadwal Pelajaran** — Tampilan tabel per hari per kelas
- ✅ **Data Siswa** — CRUD lengkap, filter per kelas
- ✅ **Data Guru & SDM** — Profil, jabatan, wali kelas
- ✅ **Penggajian** — Generate slip gaji otomatis, cetak
- ✅ **Keuangan Sekolah** — Catat transaksi, grafik
- ✅ **SPP Siswa** — Tracking pembayaran per bulan
- ✅ **KPI Kinerja Guru** — Input & hitung nilai KPI
- ✅ **Tugas Struktural** — Kanban board (Pending/Proses/Selesai)
- ✅ **PPDB** — Pendaftaran siswa baru, alur status
- ✅ **Pengumuman** — Buat & tampilkan ke semua pengguna
- ✅ **Multi-role** — Admin, Yayasan, Kepsek, Guru, Siswa

---

## Cara Tambah User Baru

Sementara tambah via database langsung:
```python
import sqlite3, bcrypt
conn = sqlite3.connect("simak_nna.db")
pw = bcrypt.hashpw("password123".encode(), bcrypt.gensalt()).decode()
conn.execute("INSERT INTO users (username,password_hash,role,nama) VALUES (?,?,?,?)",
             ("username_baru", pw, "guru", "Nama Guru"))
conn.commit()
```

(Fitur manajemen user dari UI akan ditambahkan di versi berikutnya)
