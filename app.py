import os
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-me')

# Environment variable that Vercel will set
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    if 'db' not in g:
        if DATABASE_URL:
            # Neon PostgreSQL
            import psycopg2
            import psycopg2.extras
            g.db = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            # Local SQLite fallback
            db_path = os.path.join(os.path.dirname(__file__), 'absensi.db')
            g.db = sqlite3.connect(db_path)
            g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    if DATABASE_URL:
        # PostgreSQL tables
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS admin (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            );
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS absensi (
                id SERIAL PRIMARY KEY,
                nama TEXT NOT NULL,
                bagian TEXT NOT NULL,
                outsourcing TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Masuk',
                lat REAL,
                lng REAL,
                foto TEXT,
                created_at TEXT NOT NULL
            );
        ''')
        cur.execute(
            "INSERT INTO admin (id, username, password) VALUES (1, 'admin', 'admin123') "
            "ON CONFLICT (id) DO NOTHING;"
        )
        conn.commit()
        cur.close()
        conn.close()
    else:
        # SQLite tables (local dev)
        db_path = os.path.join(os.path.dirname(__file__), 'absensi.db')
        db = sqlite3.connect(db_path)
        db.executescript('''
            CREATE TABLE IF NOT EXISTS admin (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS absensi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nama TEXT NOT NULL,
                bagian TEXT NOT NULL,
                outsourcing TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Masuk',
                lat REAL,
                lng REAL,
                foto TEXT,
                created_at TEXT NOT NULL
            );
            INSERT OR IGNORE INTO admin (id, username, password) VALUES (1, 'admin', 'admin123');
        ''')
        # pastikan kolom status ada bila sebelumnya belum dibuat
        cols = [r[1] for r in db.execute('PRAGMA table_info(absensi)').fetchall()]
        if 'status' not in cols:
            db.execute("ALTER TABLE absensi ADD COLUMN status TEXT NOT NULL DEFAULT 'Masuk'")
        db.commit()
        db.close()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/absen', methods=['POST'])
def absen():
    nama = (request.form.get('nama') or '').strip()
    bagian = (request.form.get('bagian') or '').strip()
    outsourcing = (request.form.get('outsourcing') or '').strip()
    status = (request.form.get('status') or '').strip()
    lat = request.form.get('lat')
    lng = request.form.get('lng')
    foto = request.form.get('foto') or ''
    allowed_os = {
        'PT. Amanah Amarta',
        'PT. Krisna Sejati',
        'PT. Artakemas Indonesia',
    }
if not nama or not bagian or outsourcing not in allowed_os \
       or status not in ('Masuk', 'Pulang') or not foto or not lat or not lng:
        return jsonify({'ok': False,
                        'msg': 'Semua field wajib diisi: nama, bagian, outsourcing, status, foto, GPS'}), 400
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except ValueError:
        lat_f = lng_f = None
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db = get_db()
    cur = db.cursor()
    if DATABASE_URL:
        cur.execute(
            'INSERT INTO absensi (nama, bagian, outsourcing, status, lat, lng, foto, created_at) '
            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
            (nama, bagian, outsourcing, status, lat_f, lng_f, foto[:500000], now)
        )
    else:
        cur.execute(
            'INSERT INTO absensi (nama, bagian, outsourcing, status, lat, lng, foto, created_at) '
            'VALUES (?,?,?,?,?,?,?,?)',
            (nama, bagian, outsourcing, status, lat_f, lng_f, foto[:500000], now)
        )
    db.commit()
    cur.close()
    return jsonify({'ok': True, 'msg': 'Absensi tercatat.', 'waktu': now})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = (request.form.get('username') or '').strip()
        pw = request.form.get('password') or ''
        db = get_db()
        cur = db.cursor()
        if DATABASE_URL:
            cur.execute('SELECT id FROM admin WHERE username=%s AND password=***', (user, pw))
        else:
            cur.execute('SELECT id FROM admin WHERE username=? AND password=***', (user, pw))
        row = cur.fetchone()
        cur.close()
        if row:
            session['admin'] = user
            return redirect(url_for('kelola'))
        flash('Username atau password salah.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('login'))

@app.route('/kelola')
@login_required
def kelola():
    db = get_db()
    cur = db.cursor()
    q = (request.args.get('q') or '').strip()
    tgl = (request.args.get('tgl') or '').strip()
    if DATABASE_URL:
        sql = 'SELECT * FROM absensi WHERE 1=1'
        params = []
        if q:
            sql += ' AND (nama ILIKE %s OR bagian ILIKE %s OR outsourcing ILIKE %s)'
            params += [f'%{q}%', f'%{q}%', f'%{q}%']
        if tgl:
            sql += ' AND created_at LIKE %s'
            params.append(f'{tgl}%')
        sql += ' ORDER BY id DESC'
        cur.execute(sql, params)
    else:
        sql = 'SELECT * FROM absensi WHERE 1=1'
        params = []
        if q:
            sql += ' AND (nama LIKE ? OR bagian LIKE ? OR outsourcing LIKE ?)'
            params += [f'%{q}%', f'%{q}%', f'%{q}%']
        if tgl:
            sql += ' AND created_at LIKE ?'
            params.append(f'{tgl}%')
        sql += ' ORDER BY id DESC'
        cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return render_template('kelola.html', rows=rows, q=q, tgl=tgl)

@app.route('/hapus/<int:aid>', methods=['POST'])
@login_required
def hapus(aid):
    db = get_db()
    cur = db.cursor()
    if DATABASE_URL:
        cur.execute('DELETE FROM absensi WHERE id=%s', (aid,))
    else:
        cur.execute('DELETE FROM absensi WHERE id=?', (aid,))
    db.commit()
    cur.close()
    return redirect(url_for('kelola'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5055, debug=True)
