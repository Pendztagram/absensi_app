# Absensi Karyawan

App lokal Flask + SQLite. Siap di-zip lalu di-upload ke hosting yang mendukung Python (Passenger, gunicorn, dll).

## Fitur
- Halaman absen: nama, bagian, outsourcing, kamera wajah, GPS
- Login admin + halaman kelola (filter, hapus)
- Responsive mobile

## Jalankan lokal
```
cd absensi_app
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Buka http://127.0.0.1:5055

Login demo: `admin` / `admin123` — ganti sebelum produksi.

Kamera dan GPS butuh HTTPS atau localhost. Di HP, buka lewat tunnel/HTTPS hosting.

## Hosting
- Set `SECRET_KEY` di environment.
- Jalankan dengan gunicorn: `gunicorn -b 0.0.0.0:8000 app:app`
- File DB `absensi.db` harus writable.
