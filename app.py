from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import bcrypt, os, json
from database import get_db, init_db
from datetime import datetime, timedelta

app = Flask(__name__, static_folder="public", static_url_path="")
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET", "simak-nna-secret-2026")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=12)
CORS(app)
jwt = JWTManager(app)

# ──────────────────────────────────────────────────────────────────────────────
# STATIC
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("public", "index.html")

# ──────────────────────────────────────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username=? AND aktif=1", (data["username"],)).fetchone()
    if not user or not bcrypt.checkpw(data["password"].encode(), user["password_hash"].encode()):
        return jsonify({"error": "Username atau password salah"}), 401
    token = create_access_token(identity=json.dumps({"id": user["id"], "role": user["role"], "nama": user["nama"]}))
    guru = db.execute("SELECT * FROM guru WHERE user_id=?", (user["id"],)).fetchone()
    db.close()
    return jsonify({
        "token": token,
        "role": user["role"],
        "nama": user["nama"],
        "guru_id": guru["id"] if guru else None
    })

@app.route("/api/me", methods=["GET"])
@jwt_required()
def me():
    identity = json.loads(get_jwt_identity())
    db = get_db()
    user = db.execute("SELECT id,username,role,nama,email,no_hp FROM users WHERE id=?", (identity["id"],)).fetchone()
    guru = db.execute("SELECT * FROM guru WHERE user_id=?", (identity["id"],)).fetchone()
    notif = db.execute("SELECT COUNT(*) as n FROM notifikasi WHERE user_id=? AND dibaca=0", (identity["id"],)).fetchone()
    db.close()
    return jsonify({**dict(user), "guru": dict(guru) if guru else None, "unread_notif": notif["n"]})

# ──────────────────────────────────────────────────────────────────────────────
# DASHBOARD STATS
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/dashboard", methods=["GET"])
@jwt_required()
def dashboard():
    db = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    stats = {
        "total_siswa":  db.execute("SELECT COUNT(*) FROM siswa WHERE status='Aktif'").fetchone()[0],
        "total_guru":   db.execute("SELECT COUNT(*) FROM guru WHERE aktif=1").fetchone()[0],
        "total_kelas":  db.execute("SELECT COUNT(*) FROM kelas WHERE aktif=1").fetchone()[0],
        "hadir_hari_ini": db.execute("SELECT COUNT(*) FROM absensi_siswa WHERE tanggal=? AND status='Hadir'", (today,)).fetchone()[0],
        "izin_hari_ini":  db.execute("SELECT COUNT(*) FROM absensi_siswa WHERE tanggal=? AND status='Izin'", (today,)).fetchone()[0],
        "alpha_hari_ini": db.execute("SELECT COUNT(*) FROM absensi_siswa WHERE tanggal=? AND status='Alpha'", (today,)).fetchone()[0],
        "ppdb_pending":   db.execute("SELECT COUNT(*) FROM ppdb WHERE status='Mendaftar'").fetchone()[0],
        "spp_belum_bayar":db.execute("SELECT COUNT(*) FROM spp WHERE status='Belum Bayar'").fetchone()[0],
    }
    # Keuangan bulan ini
    bulan = datetime.now().month
    tahun = datetime.now().year
    masuk = db.execute("SELECT COALESCE(SUM(jumlah),0) FROM keuangan WHERE jenis='Pemasukan' AND strftime('%m',tanggal)=? AND strftime('%Y',tanggal)=?", (f"{bulan:02d}", str(tahun))).fetchone()[0]
    keluar = db.execute("SELECT COALESCE(SUM(jumlah),0) FROM keuangan WHERE jenis='Pengeluaran' AND strftime('%m',tanggal)=? AND strftime('%Y',tanggal)=?", (f"{bulan:02d}", str(tahun))).fetchone()[0]
    stats["pemasukan_bulan"] = masuk
    stats["pengeluaran_bulan"] = keluar
    stats["saldo_bulan"] = masuk - keluar

    # Pengumuman terbaru
    pengumuman = db.execute("SELECT * FROM pengumuman ORDER BY created_at DESC LIMIT 5").fetchall()
    stats["pengumuman"] = [dict(p) for p in pengumuman]

    # Absensi 7 hari terakhir
    absensi_7 = db.execute("""
        SELECT tanggal,
               SUM(CASE WHEN status='Hadir' THEN 1 ELSE 0 END) as hadir,
               SUM(CASE WHEN status='Alpha' THEN 1 ELSE 0 END) as alpha
        FROM absensi_siswa
        WHERE tanggal >= date('now','-7 days')
        GROUP BY tanggal ORDER BY tanggal
    """).fetchall()
    stats["absensi_chart"] = [dict(r) for r in absensi_7]

    db.close()
    return jsonify(stats)

# ──────────────────────────────────────────────────────────────────────────────
# GURU
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/guru", methods=["GET"])
@jwt_required()
def get_guru():
    db = get_db()
    rows = db.execute("""SELECT g.*, u.email, u.username FROM guru g
                         LEFT JOIN users u ON g.user_id=u.id WHERE g.aktif=1 ORDER BY g.nama""").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/guru/<int:gid>", methods=["GET"])
@jwt_required()
def get_guru_detail(gid):
    db = get_db()
    g = db.execute("SELECT g.*,u.email,u.username FROM guru g LEFT JOIN users u ON g.user_id=u.id WHERE g.id=?", (gid,)).fetchone()
    kpi_list = db.execute("SELECT * FROM kpi WHERE guru_id=? ORDER BY periode DESC LIMIT 5", (gid,)).fetchall()
    tugas = db.execute("SELECT * FROM tugas_struktural WHERE guru_id=? ORDER BY created_at DESC LIMIT 10", (gid,)).fetchall()
    gaji = db.execute("SELECT * FROM penggajian WHERE guru_id=? ORDER BY tahun DESC, bulan DESC LIMIT 6", (gid,)).fetchall()
    # Rekap absensi bulan ini
    bln = datetime.now().month; thn = datetime.now().year
    absensi = db.execute("""SELECT status, COUNT(*) as total FROM absensi_guru
                            WHERE guru_id=? AND strftime('%m',tanggal)=? AND strftime('%Y',tanggal)=?
                            GROUP BY status""", (gid, f"{bln:02d}", str(thn))).fetchall()
    db.close()
    if not g: return jsonify({"error":"Tidak ditemukan"}), 404
    return jsonify({**dict(g), "kpi": [dict(k) for k in kpi_list],
                    "tugas": [dict(t) for t in tugas], "gaji": [dict(g) for g in gaji],
                    "absensi_bulan": [dict(a) for a in absensi]})

@app.route("/api/guru/<int:gid>", methods=["PUT"])
@jwt_required()
def update_guru(gid):
    data = request.json
    db = get_db()
    fields = ["jabatan_struktural","wali_kelas","gaji_pokok","tj_jabatan","no_hp","alamat","kualifikasi","unit"]
    sets = ", ".join(f"{f}=?" for f in fields if f in data)
    vals = [data[f] for f in fields if f in data] + [gid]
    db.execute(f"UPDATE guru SET {sets} WHERE id=?", vals)
    db.commit(); db.close()
    return jsonify({"ok": True})

# ──────────────────────────────────────────────────────────────────────────────
# SISWA
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/siswa", methods=["GET"])
@jwt_required()
def get_siswa():
    db = get_db()
    kelas_id = request.args.get("kelas_id")
    q = request.args.get("q","")
    if kelas_id:
        rows = db.execute("""SELECT s.*,k.nama as nama_kelas FROM siswa s
                             LEFT JOIN kelas k ON s.kelas_id=k.id
                             WHERE s.kelas_id=? AND s.status='Aktif' AND s.nama LIKE ?
                             ORDER BY s.nama""", (kelas_id, f"%{q}%")).fetchall()
    else:
        rows = db.execute("""SELECT s.*,k.nama as nama_kelas FROM siswa s
                             LEFT JOIN kelas k ON s.kelas_id=k.id
                             WHERE s.status='Aktif' AND s.nama LIKE ?
                             ORDER BY k.tingkat, s.nama""", (f"%{q}%",)).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/siswa/<int:sid>", methods=["GET"])
@jwt_required()
def get_siswa_detail(sid):
    db = get_db()
    s = db.execute("SELECT s.*,k.nama as nama_kelas FROM siswa s LEFT JOIN kelas k ON s.kelas_id=k.id WHERE s.id=?", (sid,)).fetchone()
    nilai = db.execute("""SELECT n.*,m.nama as nama_mapel FROM nilai n
                          LEFT JOIN mata_pelajaran m ON n.mata_pelajaran_id=m.id
                          WHERE n.siswa_id=? ORDER BY n.tahun_ajaran DESC, n.semester""", (sid,)).fetchall()
    absensi = db.execute("""SELECT status, COUNT(*) as total FROM absensi_siswa WHERE siswa_id=?
                            AND strftime('%Y',tanggal)=? GROUP BY status""", (sid, str(datetime.now().year))).fetchall()
    spp = db.execute("SELECT * FROM spp WHERE siswa_id=? ORDER BY tahun DESC, bulan DESC", (sid,)).fetchall()
    db.close()
    if not s: return jsonify({"error":"Tidak ditemukan"}), 404
    return jsonify({**dict(s), "nilai": [dict(n) for n in nilai],
                    "absensi_rekap": [dict(a) for a in absensi],
                    "spp": [dict(p) for p in spp]})

@app.route("/api/siswa", methods=["POST"])
@jwt_required()
def add_siswa():
    data = request.json
    db = get_db()
    db.execute("""INSERT INTO siswa (nis,nisn,nama,kelas_id,jenis_kelamin,tanggal_lahir,tempat_lahir,
                  nama_ayah,nama_ibu,nama_wali,no_hp_ortu,alamat,tahun_masuk)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               (data.get("nis"), data.get("nisn"), data["nama"], data["kelas_id"],
                data.get("jenis_kelamin"), data.get("tanggal_lahir"), data.get("tempat_lahir"),
                data.get("nama_ayah"), data.get("nama_ibu"), data.get("nama_wali"),
                data.get("no_hp_ortu"), data.get("alamat"), data.get("tahun_masuk", datetime.now().year)))
    db.commit(); db.close()
    return jsonify({"ok": True}), 201

@app.route("/api/siswa/<int:sid>", methods=["PUT"])
@jwt_required()
def update_siswa(sid):
    data = request.json
    db = get_db()
    fields = ["nama","kelas_id","jenis_kelamin","tanggal_lahir","tempat_lahir","nama_ayah","nama_ibu","nama_wali","no_hp_ortu","alamat","status"]
    sets = ", ".join(f"{f}=?" for f in fields if f in data)
    vals = [data[f] for f in fields if f in data] + [sid]
    db.execute(f"UPDATE siswa SET {sets} WHERE id=?", vals)
    db.commit(); db.close()
    return jsonify({"ok": True})

# ──────────────────────────────────────────────────────────────────────────────
# KELAS
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/kelas", methods=["GET"])
@jwt_required()
def get_kelas():
    db = get_db()
    rows = db.execute("""SELECT k.*, g.nama as nama_wali,
                         (SELECT COUNT(*) FROM siswa s WHERE s.kelas_id=k.id AND s.status='Aktif') as jumlah_siswa
                         FROM kelas k LEFT JOIN guru g ON k.wali_kelas_id=g.id WHERE k.aktif=1 ORDER BY k.tingkat""").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

# ──────────────────────────────────────────────────────────────────────────────
# ABSENSI SISWA
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/absensi/siswa", methods=["GET"])
@jwt_required()
def get_absensi_siswa():
    kelas_id = request.args.get("kelas_id")
    tanggal  = request.args.get("tanggal", datetime.now().strftime("%Y-%m-%d"))
    db = get_db()
    rows = db.execute("""SELECT s.id, s.nama, s.nis, a.status, a.keterangan
                         FROM siswa s LEFT JOIN absensi_siswa a ON s.id=a.siswa_id AND a.tanggal=?
                         WHERE s.kelas_id=? AND s.status='Aktif' ORDER BY s.nama""", (tanggal, kelas_id)).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/absensi/siswa", methods=["POST"])
@jwt_required()
def post_absensi_siswa():
    identity = json.loads(get_jwt_identity())
    data = request.json  # [{siswa_id, status, keterangan}]
    tanggal = data.get("tanggal", datetime.now().strftime("%Y-%m-%d"))
    absensi = data.get("absensi", [])
    db = get_db()
    for a in absensi:
        db.execute("""INSERT INTO absensi_siswa (siswa_id,kelas_id,tanggal,status,keterangan,dicatat_oleh)
                      VALUES (?,?,?,?,?,?)
                      ON CONFLICT(siswa_id,tanggal) DO UPDATE SET status=excluded.status, keterangan=excluded.keterangan""",
                   (a["siswa_id"], a.get("kelas_id"), tanggal, a["status"], a.get("keterangan",""), identity["id"]))
    db.commit(); db.close()
    return jsonify({"ok": True, "saved": len(absensi)})

@app.route("/api/absensi/siswa/rekap", methods=["GET"])
@jwt_required()
def rekap_absensi_siswa():
    bulan = int(request.args.get("bulan", datetime.now().month))
    tahun = int(request.args.get("tahun", datetime.now().year))
    kelas_id = request.args.get("kelas_id")
    db = get_db()
    rows = db.execute("""SELECT s.nama, s.nis, k.nama as kelas,
                         SUM(CASE WHEN a.status='Hadir' THEN 1 ELSE 0 END) as hadir,
                         SUM(CASE WHEN a.status='Izin'  THEN 1 ELSE 0 END) as izin,
                         SUM(CASE WHEN a.status='Sakit' THEN 1 ELSE 0 END) as sakit,
                         SUM(CASE WHEN a.status='Alpha' THEN 1 ELSE 0 END) as alpha
                         FROM siswa s LEFT JOIN kelas k ON s.kelas_id=k.id
                         LEFT JOIN absensi_siswa a ON s.id=a.siswa_id
                             AND strftime('%m',a.tanggal)=? AND strftime('%Y',a.tanggal)=?
                         WHERE s.status='Aktif' AND (? IS NULL OR s.kelas_id=?)
                         GROUP BY s.id ORDER BY k.tingkat, s.nama""",
                      (f"{bulan:02d}", str(tahun), kelas_id, kelas_id)).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

# ──────────────────────────────────────────────────────────────────────────────
# ABSENSI GURU
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/absensi/guru", methods=["GET"])
@jwt_required()
def get_absensi_guru():
    tanggal = request.args.get("tanggal", datetime.now().strftime("%Y-%m-%d"))
    db = get_db()
    rows = db.execute("""SELECT g.id, g.nama, g.jabatan_fungsional, g.jabatan_struktural,
                         a.status, a.jam_masuk, a.jam_keluar, a.keterangan
                         FROM guru g LEFT JOIN absensi_guru a ON g.id=a.guru_id AND a.tanggal=?
                         WHERE g.aktif=1 ORDER BY g.nama""", (tanggal,)).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/absensi/guru", methods=["POST"])
@jwt_required()
def post_absensi_guru():
    identity = json.loads(get_jwt_identity())
    data = request.json
    tanggal = data.get("tanggal", datetime.now().strftime("%Y-%m-%d"))
    absensi = data.get("absensi", [])
    db = get_db()
    for a in absensi:
        db.execute("""INSERT INTO absensi_guru (guru_id,tanggal,jam_masuk,jam_keluar,status,keterangan,dicatat_oleh)
                      VALUES (?,?,?,?,?,?,?)
                      ON CONFLICT(guru_id,tanggal) DO UPDATE SET status=excluded.status,
                      jam_masuk=excluded.jam_masuk, jam_keluar=excluded.jam_keluar""",
                   (a["guru_id"], tanggal, a.get("jam_masuk"), a.get("jam_keluar"),
                    a.get("status","Hadir"), a.get("keterangan",""), identity["id"]))
    db.commit(); db.close()
    return jsonify({"ok": True})

# ──────────────────────────────────────────────────────────────────────────────
# NILAI
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/nilai", methods=["GET"])
@jwt_required()
def get_nilai():
    kelas_id = request.args.get("kelas_id")
    mapel_id = request.args.get("mapel_id")
    semester = request.args.get("semester", 1)
    ta = request.args.get("tahun_ajaran", "2025/2026")
    db = get_db()
    rows = db.execute("""SELECT s.nama, s.nis, n.*
                         FROM siswa s LEFT JOIN nilai n ON s.id=n.siswa_id
                             AND n.mata_pelajaran_id=? AND n.semester=? AND n.tahun_ajaran=?
                         WHERE s.kelas_id=? AND s.status='Aktif' ORDER BY s.nama""",
                      (mapel_id, semester, ta, kelas_id)).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/nilai", methods=["POST"])
@jwt_required()
def post_nilai():
    identity = json.loads(get_jwt_identity())
    data = request.json
    db = get_db()
    for n in data.get("nilai", []):
        nh = n.get("nilai_harian", 0) or 0
        uts = n.get("nilai_uts", 0) or 0
        uas = n.get("nilai_uas", 0) or 0
        akhir = round(nh * 0.4 + uts * 0.3 + uas * 0.3, 1)
        predikat = "A" if akhir >= 90 else "B" if akhir >= 75 else "C" if akhir >= 60 else "D"
        db.execute("""INSERT INTO nilai (siswa_id,mata_pelajaran_id,kelas_id,semester,tahun_ajaran,
                      nilai_harian,nilai_uts,nilai_uas,nilai_akhir,predikat,catatan_guru,diinput_oleh)
                      VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                      ON CONFLICT(siswa_id,mata_pelajaran_id,semester,tahun_ajaran)
                      DO UPDATE SET nilai_harian=excluded.nilai_harian, nilai_uts=excluded.nilai_uts,
                      nilai_uas=excluded.nilai_uas, nilai_akhir=excluded.nilai_akhir,
                      predikat=excluded.predikat, updated_at=datetime('now','localtime')""",
                   (n["siswa_id"], n["mata_pelajaran_id"], n.get("kelas_id"), n["semester"],
                    n["tahun_ajaran"], nh, uts, uas, akhir, predikat, n.get("catatan",""), identity["id"]))
    db.commit(); db.close()
    return jsonify({"ok": True})

@app.route("/api/rapor/<int:sid>", methods=["GET"])
@jwt_required()
def get_rapor(sid):
    semester = request.args.get("semester", 1)
    ta = request.args.get("tahun_ajaran", "2025/2026")
    db = get_db()
    s = db.execute("SELECT s.*,k.nama as nama_kelas FROM siswa s LEFT JOIN kelas k ON s.kelas_id=k.id WHERE s.id=?", (sid,)).fetchone()
    nilai = db.execute("""SELECT m.nama as mapel, m.kode, n.nilai_harian, n.nilai_uts, n.nilai_uas,
                          n.nilai_akhir, n.predikat, n.catatan_guru
                          FROM nilai n JOIN mata_pelajaran m ON n.mata_pelajaran_id=m.id
                          WHERE n.siswa_id=? AND n.semester=? AND n.tahun_ajaran=?""", (sid, semester, ta)).fetchall()
    absensi = db.execute("""SELECT SUM(CASE WHEN status='Hadir' THEN 1 ELSE 0 END) as hadir,
                             SUM(CASE WHEN status='Izin' THEN 1 ELSE 0 END) as izin,
                             SUM(CASE WHEN status='Sakit' THEN 1 ELSE 0 END) as sakit,
                             SUM(CASE WHEN status='Alpha' THEN 1 ELSE 0 END) as alpha
                             FROM absensi_siswa WHERE siswa_id=?
                             AND strftime('%Y',tanggal)=?""", (sid, ta[:4])).fetchone()
    db.close()
    return jsonify({"siswa": dict(s), "nilai": [dict(n) for n in nilai], "absensi": dict(absensi) if absensi else {}})

# ──────────────────────────────────────────────────────────────────────────────
# JADWAL
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/jadwal", methods=["GET"])
@jwt_required()
def get_jadwal():
    kelas_id = request.args.get("kelas_id")
    guru_id  = request.args.get("guru_id")
    db = get_db()
    if kelas_id:
        rows = db.execute("""SELECT j.*,m.nama as mapel,g.nama as nama_guru,k.nama as nama_kelas
                             FROM jadwal j JOIN mata_pelajaran m ON j.mata_pelajaran_id=m.id
                             JOIN guru g ON j.guru_id=g.id JOIN kelas k ON j.kelas_id=k.id
                             WHERE j.kelas_id=? ORDER BY j.hari, j.jam_mulai""", (kelas_id,)).fetchall()
    elif guru_id:
        rows = db.execute("""SELECT j.*,m.nama as mapel,g.nama as nama_guru,k.nama as nama_kelas
                             FROM jadwal j JOIN mata_pelajaran m ON j.mata_pelajaran_id=m.id
                             JOIN guru g ON j.guru_id=g.id JOIN kelas k ON j.kelas_id=k.id
                             WHERE j.guru_id=? ORDER BY j.hari, j.jam_mulai""", (guru_id,)).fetchall()
    else:
        rows = db.execute("""SELECT j.*,m.nama as mapel,g.nama as nama_guru,k.nama as nama_kelas
                             FROM jadwal j JOIN mata_pelajaran m ON j.mata_pelajaran_id=m.id
                             JOIN guru g ON j.guru_id=g.id JOIN kelas k ON j.kelas_id=k.id
                             ORDER BY k.tingkat, j.hari, j.jam_mulai""").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/jadwal", methods=["POST"])
@jwt_required()
def add_jadwal():
    data = request.json
    db = get_db()
    db.execute("""INSERT INTO jadwal (kelas_id,mata_pelajaran_id,guru_id,hari,jam_mulai,jam_selesai,tahun_ajaran,semester)
                  VALUES (?,?,?,?,?,?,?,?)""",
               (data["kelas_id"], data["mata_pelajaran_id"], data["guru_id"],
                data["hari"], data["jam_mulai"], data["jam_selesai"],
                data.get("tahun_ajaran","2025/2026"), data.get("semester",1)))
    db.commit(); db.close()
    return jsonify({"ok": True}), 201

@app.route("/api/jadwal/<int:jid>", methods=["DELETE"])
@jwt_required()
def del_jadwal(jid):
    db = get_db()
    db.execute("DELETE FROM jadwal WHERE id=?", (jid,))
    db.commit(); db.close()
    return jsonify({"ok": True})

@app.route("/api/mapel", methods=["GET"])
@jwt_required()
def get_mapel():
    db = get_db()
    rows = db.execute("SELECT * FROM mata_pelajaran WHERE aktif=1 ORDER BY nama").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

# ──────────────────────────────────────────────────────────────────────────────
# PENGGAJIAN
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/penggajian", methods=["GET"])
@jwt_required()
def get_penggajian():
    bulan = int(request.args.get("bulan", datetime.now().month))
    tahun = int(request.args.get("tahun", datetime.now().year))
    db = get_db()
    rows = db.execute("""SELECT p.*,g.nama,g.jabatan_fungsional,g.jabatan_struktural,g.unit
                         FROM penggajian p JOIN guru g ON p.guru_id=g.id
                         WHERE p.bulan=? AND p.tahun=? ORDER BY g.nama""", (bulan, tahun)).fetchall()
    if not rows:
        # Auto-generate dari data guru
        guru_all = db.execute("SELECT * FROM guru WHERE aktif=1").fetchall()
        identity = json.loads(get_jwt_identity())
        for g in guru_all:
            bruto = g["gaji_pokok"] + g["tj_jabatan"]
            bpjs_kes = round(g["gaji_pokok"] * 0.01)
            bpjs_tk  = round(g["gaji_pokok"] * 0.03)
            thp = bruto - bpjs_kes - bpjs_tk
            db.execute("""INSERT OR IGNORE INTO penggajian
                          (guru_id,bulan,tahun,gaji_pokok,tj_jabatan,bruto,potongan_bpjs_kes,potongan_bpjs_tk,thp,dibuat_oleh)
                          VALUES (?,?,?,?,?,?,?,?,?,?)""",
                       (g["id"], bulan, tahun, g["gaji_pokok"], g["tj_jabatan"],
                        bruto, bpjs_kes, bpjs_tk, thp, identity["id"]))
        db.commit()
        rows = db.execute("""SELECT p.*,g.nama,g.jabatan_fungsional,g.jabatan_struktural,g.unit
                             FROM penggajian p JOIN guru g ON p.guru_id=g.id
                             WHERE p.bulan=? AND p.tahun=? ORDER BY g.nama""", (bulan, tahun)).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/penggajian/<int:pid>", methods=["PUT"])
@jwt_required()
def update_penggajian(pid):
    data = request.json
    db = get_db()
    bruto = data.get("gaji_pokok",0) + data.get("tj_jabatan",0) + data.get("tj_lain",0) + data.get("lembur",0) + data.get("thr",0)
    thp   = bruto - data.get("potongan_bpjs_kes",0) - data.get("potongan_bpjs_tk",0) - data.get("potongan_lain",0)
    db.execute("""UPDATE penggajian SET gaji_pokok=?,tj_jabatan=?,tj_lain=?,lembur=?,thr=?,
                  bruto=?,potongan_bpjs_kes=?,potongan_bpjs_tk=?,potongan_lain=?,thp=?,status=?,tgl_bayar=?,catatan=?
                  WHERE id=?""",
               (data.get("gaji_pokok"), data.get("tj_jabatan"), data.get("tj_lain",0),
                data.get("lembur",0), data.get("thr",0), bruto,
                data.get("potongan_bpjs_kes",0), data.get("potongan_bpjs_tk",0),
                data.get("potongan_lain",0), thp, data.get("status","Belum Dibayar"),
                data.get("tgl_bayar"), data.get("catatan"), pid))
    db.commit(); db.close()
    return jsonify({"ok": True, "thp": thp})

@app.route("/api/penggajian/slip/<int:guru_id>", methods=["GET"])
@jwt_required()
def slip_gaji(guru_id):
    bulan = int(request.args.get("bulan", datetime.now().month))
    tahun = int(request.args.get("tahun", datetime.now().year))
    db = get_db()
    p = db.execute("""SELECT p.*,g.nama,g.jabatan_fungsional,g.jabatan_struktural,g.nip,g.unit
                      FROM penggajian p JOIN guru g ON p.guru_id=g.id
                      WHERE p.guru_id=? AND p.bulan=? AND p.tahun=?""", (guru_id, bulan, tahun)).fetchone()
    db.close()
    if not p: return jsonify({"error":"Data tidak ditemukan"}), 404
    return jsonify(dict(p))

# ──────────────────────────────────────────────────────────────────────────────
# KEUANGAN
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/keuangan", methods=["GET"])
@jwt_required()
def get_keuangan():
    bulan = request.args.get("bulan")
    tahun = request.args.get("tahun", str(datetime.now().year))
    db = get_db()
    if bulan:
        rows = db.execute("""SELECT * FROM keuangan WHERE strftime('%m',tanggal)=? AND strftime('%Y',tanggal)=?
                             ORDER BY tanggal DESC""", (f"{int(bulan):02d}", tahun)).fetchall()
    else:
        rows = db.execute("SELECT * FROM keuangan WHERE strftime('%Y',tanggal)=? ORDER BY tanggal DESC", (tahun,)).fetchall()
    total_masuk  = sum(r["jumlah"] for r in rows if r["jenis"]=="Pemasukan")
    total_keluar = sum(r["jumlah"] for r in rows if r["jenis"]=="Pengeluaran")
    db.close()
    return jsonify({"transaksi": [dict(r) for r in rows], "total_masuk": total_masuk, "total_keluar": total_keluar, "saldo": total_masuk - total_keluar})

@app.route("/api/keuangan", methods=["POST"])
@jwt_required()
def post_keuangan():
    identity = json.loads(get_jwt_identity())
    data = request.json
    db = get_db()
    db.execute("""INSERT INTO keuangan (tanggal,jenis,kategori,keterangan,jumlah,sumber,dicatat_oleh)
                  VALUES (?,?,?,?,?,?,?)""",
               (data["tanggal"], data["jenis"], data["kategori"], data["keterangan"],
                data["jumlah"], data.get("sumber"), identity["id"]))
    db.commit(); db.close()
    return jsonify({"ok": True}), 201

@app.route("/api/spp", methods=["GET"])
@jwt_required()
def get_spp():
    bulan = int(request.args.get("bulan", datetime.now().month))
    tahun = int(request.args.get("tahun", datetime.now().year))
    kelas_id = request.args.get("kelas_id")
    db = get_db()
    rows = db.execute("""SELECT s.nama, s.nis, k.nama as kelas, sp.status, sp.jumlah, sp.tgl_bayar
                         FROM siswa s LEFT JOIN kelas k ON s.kelas_id=k.id
                         LEFT JOIN spp sp ON s.id=sp.siswa_id AND sp.bulan=? AND sp.tahun=?
                         WHERE s.status='Aktif' AND (? IS NULL OR s.kelas_id=?)
                         ORDER BY k.tingkat, s.nama""",
                      (bulan, tahun, kelas_id, kelas_id)).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/spp", methods=["POST"])
@jwt_required()
def post_spp():
    identity = json.loads(get_jwt_identity())
    data = request.json
    db = get_db()
    db.execute("""INSERT INTO spp (siswa_id,bulan,tahun,jumlah,status,tgl_bayar,dicatat_oleh)
                  VALUES (?,?,?,?,?,?,?)
                  ON CONFLICT(siswa_id,bulan,tahun) DO UPDATE SET status=excluded.status, tgl_bayar=excluded.tgl_bayar""",
               (data["siswa_id"], data["bulan"], data["tahun"], data.get("jumlah",73130),
                "Lunas", datetime.now().strftime("%Y-%m-%d"), identity["id"]))
    db.commit(); db.close()
    return jsonify({"ok": True})

# ──────────────────────────────────────────────────────────────────────────────
# KPI
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/kpi", methods=["GET"])
@jwt_required()
def get_kpi():
    guru_id = request.args.get("guru_id")
    db = get_db()
    if guru_id:
        rows = db.execute("SELECT * FROM kpi WHERE guru_id=? ORDER BY periode DESC", (guru_id,)).fetchall()
    else:
        rows = db.execute("""SELECT k.*,g.nama FROM kpi k JOIN guru g ON k.guru_id=g.id
                             ORDER BY k.periode DESC, g.nama""").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/kpi", methods=["POST"])
@jwt_required()
def post_kpi():
    identity = json.loads(get_jwt_identity())
    data = request.json
    db = get_db()
    a1 = float(data.get("aspek_pembelajaran",0))
    a2 = float(data.get("aspek_administrasi",0))
    a3 = float(data.get("aspek_kedisiplinan",0))
    a4 = float(data.get("aspek_struktural",0)) if data.get("aspek_struktural") else 0
    a5 = float(data.get("aspek_inovasi",0))
    total = round((a1*0.35 + a2*0.2 + a3*0.2 + a4*0.15 + a5*0.1), 2)
    predikat = "Sangat Baik" if total>=90 else "Baik" if total>=75 else "Cukup" if total>=60 else "Kurang"
    db.execute("""INSERT INTO kpi (guru_id,periode,aspek_pembelajaran,aspek_administrasi,aspek_kedisiplinan,
                  aspek_struktural,aspek_inovasi,nilai_total,predikat,catatan_penilai,penilai_id)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?)
                  ON CONFLICT(guru_id,periode) DO UPDATE SET aspek_pembelajaran=excluded.aspek_pembelajaran,
                  aspek_administrasi=excluded.aspek_administrasi,aspek_kedisiplinan=excluded.aspek_kedisiplinan,
                  aspek_struktural=excluded.aspek_struktural,aspek_inovasi=excluded.aspek_inovasi,
                  nilai_total=excluded.nilai_total,predikat=excluded.predikat""",
               (data["guru_id"], data["periode"], a1, a2, a3,
                a4 if a4 else None, a5, total, predikat, data.get("catatan"), identity["id"]))
    db.commit(); db.close()
    return jsonify({"ok": True, "nilai_total": total, "predikat": predikat})

# ──────────────────────────────────────────────────────────────────────────────
# TUGAS STRUKTURAL
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/tugas", methods=["GET"])
@jwt_required()
def get_tugas():
    identity = json.loads(get_jwt_identity())
    guru_id = request.args.get("guru_id")
    db = get_db()
    if guru_id:
        rows = db.execute("""SELECT t.*,g.nama as nama_guru FROM tugas_struktural t JOIN guru g ON t.guru_id=g.id
                             WHERE t.guru_id=? ORDER BY t.created_at DESC""", (guru_id,)).fetchall()
    else:
        rows = db.execute("""SELECT t.*,g.nama as nama_guru FROM tugas_struktural t JOIN guru g ON t.guru_id=g.id
                             ORDER BY t.created_at DESC""").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/tugas", methods=["POST"])
@jwt_required()
def post_tugas():
    identity = json.loads(get_jwt_identity())
    data = request.json
    db = get_db()
    db.execute("""INSERT INTO tugas_struktural (guru_id,judul,deskripsi,kategori,prioritas,deadline,dibuat_oleh)
                  VALUES (?,?,?,?,?,?,?)""",
               (data["guru_id"], data["judul"], data.get("deskripsi"), data.get("kategori","Umum"),
                data.get("prioritas","Normal"), data.get("deadline"), identity["id"]))
    db.commit(); db.close()
    return jsonify({"ok": True}), 201

@app.route("/api/tugas/<int:tid>", methods=["PUT"])
@jwt_required()
def update_tugas(tid):
    data = request.json
    db = get_db()
    db.execute("""UPDATE tugas_struktural SET status=?,progress=?,catatan_progres=?,
                  updated_at=datetime('now','localtime') WHERE id=?""",
               (data.get("status"), data.get("progress"), data.get("catatan_progres"), tid))
    db.commit(); db.close()
    return jsonify({"ok": True})

# ──────────────────────────────────────────────────────────────────────────────
# PPDB
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/ppdb", methods=["GET"])
@jwt_required()
def get_ppdb():
    ta = request.args.get("tahun_ajaran", "2026/2027")
    db = get_db()
    rows = db.execute("SELECT * FROM ppdb WHERE tahun_ajaran=? ORDER BY tanggal_daftar DESC", (ta,)).fetchall()
    stats = {s: db.execute("SELECT COUNT(*) FROM ppdb WHERE tahun_ajaran=? AND status=?", (ta,s)).fetchone()[0]
             for s in ["Mendaftar","Lulus Seleksi","Diterima","Tidak Diterima"]}
    db.close()
    return jsonify({"data": [dict(r) for r in rows], "stats": stats})

@app.route("/api/ppdb", methods=["POST"])
@jwt_required()
def post_ppdb():
    identity = json.loads(get_jwt_identity())
    data = request.json
    db = get_db()
    db.execute("""INSERT INTO ppdb (tahun_ajaran,nama_calon,tanggal_lahir,jenis_kelamin,
                  nama_ayah,nama_ibu,no_hp,asal_sekolah,catatan,diproses_oleh)
                  VALUES (?,?,?,?,?,?,?,?,?,?)""",
               (data.get("tahun_ajaran","2026/2027"), data["nama_calon"], data.get("tanggal_lahir"),
                data.get("jenis_kelamin"), data.get("nama_ayah"), data.get("nama_ibu"),
                data["no_hp"], data.get("asal_sekolah"), data.get("catatan"), identity["id"]))
    db.commit(); db.close()
    return jsonify({"ok": True}), 201

@app.route("/api/ppdb/<int:pid>", methods=["PUT"])
@jwt_required()
def update_ppdb(pid):
    data = request.json
    db = get_db()
    db.execute("UPDATE ppdb SET status=?,catatan=? WHERE id=?",
               (data["status"], data.get("catatan"), pid))
    db.commit(); db.close()
    return jsonify({"ok": True})

# ──────────────────────────────────────────────────────────────────────────────
# NOTIFIKASI & PENGUMUMAN
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/notifikasi", methods=["GET"])
@jwt_required()
def get_notifikasi():
    identity = json.loads(get_jwt_identity())
    db = get_db()
    rows = db.execute("SELECT * FROM notifikasi WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (identity["id"],)).fetchall()
    db.execute("UPDATE notifikasi SET dibaca=1 WHERE user_id=?", (identity["id"],))
    db.commit(); db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/pengumuman", methods=["GET"])
@jwt_required()
def get_pengumuman():
    db = get_db()
    rows = db.execute("SELECT p.*,u.nama as pembuat FROM pengumuman p JOIN users u ON p.dibuat_oleh=u.id ORDER BY p.created_at DESC LIMIT 10").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/pengumuman", methods=["POST"])
@jwt_required()
def post_pengumuman():
    identity = json.loads(get_jwt_identity())
    data = request.json
    db = get_db()
    db.execute("INSERT INTO pengumuman (judul,isi,target,penting,dibuat_oleh) VALUES (?,?,?,?,?)",
               (data["judul"], data["isi"], data.get("target","semua"), data.get("penting",0), identity["id"]))
    db.commit(); db.close()
    return jsonify({"ok": True}), 201

# ──────────────────────────────────────────────────────────────────────────────
# RUN
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
