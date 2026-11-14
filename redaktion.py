"""Browser editor and persistent announcements for the info panel."""
import base64
import binascii
from contextlib import contextmanager
from datetime import date
from hashlib import sha256
import hmac
import io
import json
import re
import secrets
import sqlite3
from pathlib import Path

import bleach
from bleach.css_sanitizer import CSSSanitizer
from flask import Flask, abort, jsonify, render_template, request, session
from PIL import Image, ImageOps

from schuldaten import CACHE_DIR

ROOT = Path(__file__).resolve().parent
STYLES = CSSSanitizer(allowed_css_properties={
    'font-family', 'font-size', 'font-weight', 'font-style', 'text-decoration',
    'text-align', 'color', 'background-color', 'width',
})


@contextmanager
def database():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(CACHE_DIR / 'meldungen.sqlite3')
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL, starts TEXT NOT NULL,
                ends TEXT NOT NULL, html TEXT NOT NULL, revision TEXT NOT NULL)''')
            columns = {row['name'] for row in connection.execute('PRAGMA table_info(announcements)')}
            for name, default in (('targets', '[]'), ('mode', 'info')):
                if name not in columns:
                    try:
                        connection.execute(f"ALTER TABLE announcements ADD COLUMN {name} TEXT NOT NULL DEFAULT '{default}'")
                    except sqlite3.OperationalError as error:
                        if 'duplicate column name' not in str(error):
                            raise
            yield connection
    finally:
        connection.close()


def active_slides(monitor_id=1):
    if not (CACHE_DIR / 'meldungen.sqlite3').exists():
        return []
    today = date.today().isoformat()
    with database() as db:
        records = list(db.execute('SELECT id,revision,targets,mode FROM announcements WHERE starts<=? AND ends>=? ORDER BY id',
                                  (today, today)))
    slides = []
    for row in records:
        targets = json.loads(row['targets'])
        if not targets or monitor_id in targets:
            slides.append({'kind': 'announcement', 'mode': row['mode'],
                           'url': f"/api/info/announcement/{row['id']}?v={row['revision']}"})
    return slides


def announcement_html(number, monitor_id=1):
    today = date.today().isoformat()
    with database() as db:
        row = db.execute('SELECT html,targets FROM announcements WHERE id=? AND starts<=? AND ends>=?',
                         (number, today, today)).fetchone()
    if row:
        targets = json.loads(row['targets'])
        if not targets or monitor_id in targets:
            return row['html']
    return None


def clean_html(html):
    def attributes(tag, name, value):
        if name == 'style':
            return True
        if tag == 'img':
            return name == 'alt' or (name == 'src' and bool(re.fullmatch(
                r'data:image/webp;base64,[A-Za-z0-9+/=]+', value)))
        return False

    return bleach.clean(html, tags={
        'p', 'div', 'br', 'span', 'strong', 'b', 'em', 'i', 'u', 's',
        'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'blockquote', 'img', 'hr',
    }, attributes=attributes, protocols={'data'}, css_sanitizer=STYLES, strip=True)


def editor_app(password, profiles):
    monitors = [{key: item[key] for key in ('id', 'name', 'board_width', 'board_height', 'info_width')}
                for item in profiles]
    monitor_ids = {item['id'] for item in monitors}
    app = Flask(__name__, template_folder=str(ROOT / 'editor'))
    app.config.update(SECRET_KEY=secrets.token_bytes(32), MAX_CONTENT_LENGTH=12 * 1024 * 1024,
                      SESSION_COOKIE_NAME='schulboard_redaktion', SESSION_COOKIE_SAMESITE='Strict',
                      SESSION_COOKIE_HTTPONLY=True, PERMANENT_SESSION_LIFETIME=28800)

    @app.after_request
    def headers(response):
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                                 'X-Frame-Options': 'DENY',
                                 'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src data:; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"})
        return response

    @app.errorhandler(400)
    @app.errorhandler(401)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error(exc):
        return jsonify(error=exc.description), exc.code

    @app.get('/')
    def home():
        session.setdefault('csrf', secrets.token_urlsafe(32))
        return render_template('redaktion.html', authenticated=session.get('authenticated'),
                               csrf=session['csrf'], monitors=monitors)

    @app.before_request
    def authorize():
        if request.method in {'POST', 'PUT', 'DELETE'}:
            expected = session.get('csrf')
            if not expected or not hmac.compare_digest(expected, request.headers.get('X-CSRF-Token', '')):
                abort(403, 'Bitte die Redaktion neu laden.')
        if request.path.startswith('/api/') and request.path != '/api/login' and not session.get('authenticated'):
            abort(401, 'Bitte anmelden.')

    password_digest = sha256(password.encode()).digest()

    @app.post('/api/login')
    def login():
        body = request.get_json() or {}
        given = str(body.get('password', ''))
        if not hmac.compare_digest(sha256(given.encode()).digest(), password_digest):
            abort(401, 'Das Redaktionspasswort stimmt nicht.')
        session.clear()
        session.update(authenticated=True, csrf=secrets.token_urlsafe(32))
        session.permanent = True
        return jsonify(ok=True)

    @app.post('/api/logout')
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.get('/api/announcements')
    def list_announcements():
        with database() as db:
            return jsonify([dict(row) for row in db.execute(
                'SELECT id,title,starts,ends FROM announcements ORDER BY starts DESC,id DESC')])

    @app.get('/api/announcements/<int:number>')
    def read_announcement(number):
        with database() as db:
            row = db.execute('SELECT * FROM announcements WHERE id=?', (number,)).fetchone()
        if not row:
            abort(404)
        return jsonify({**dict(row), 'targets': json.loads(row['targets'])})

    @app.post('/api/announcements')
    @app.put('/api/announcements/<int:number>')
    def publish(number=None):
        body = request.get_json() or {}
        try:
            title = body['title'].strip()
            start = date.fromisoformat(body['starts'])
            end = date.fromisoformat(body['ends'])
            html = clean_html(body['html'])
            targets = body.get('targets', [])
            mode = body.get('mode', 'info')
            if (not isinstance(targets, list) or any(type(item) is not int or item not in monitor_ids for item in targets)
                    or mode not in ('info', 'fullscreen')):
                raise ValueError
            if not title or len(title) > 150 or end < start or not html.strip():
                raise ValueError
        except (KeyError, ValueError, TypeError, AttributeError):
            abort(400, 'Titel, Inhalt und gültigen Anzeigezeitraum eingeben.')
        values = (title, start.isoformat(), end.isoformat(), html, secrets.token_hex(8), json.dumps(sorted(set(targets))), mode)
        with database() as db:
            if number is None:
                number = db.execute('INSERT INTO announcements (title,starts,ends,html,revision,targets,mode) VALUES (?,?,?,?,?,?,?)',
                                    values).lastrowid
            else:
                operation = db.execute('UPDATE announcements SET title=?,starts=?,ends=?,html=?,revision=?,targets=?,mode=? WHERE id=?',
                                       (*values, number))
                if not operation.rowcount:
                    abort(404)
        return jsonify(id=number)

    @app.delete('/api/announcements/<int:number>')
    def delete_announcement(number):
        with database() as db:
            db.execute('DELETE FROM announcements WHERE id=?', (number,))
        return jsonify(ok=True)

    @app.post('/api/image')
    def upload():
        try:
            with Image.open(request.files['image'].stream) as image:
                if image.format not in {'PNG', 'JPEG', 'WEBP', 'GIF'} or image.width * image.height > 20_000_000:
                    raise ValueError
                resized = ImageOps.exif_transpose(image).convert('RGBA')
                resized.thumbnail((1800, 1800))
                buffer = io.BytesIO()
                resized.save(buffer, format='WEBP', quality=85)
        except (OSError, Image.DecompressionBombError, ValueError, KeyError, binascii.Error):
            abort(400, 'Bitte ein gültiges PNG-, JPEG-, WebP- oder GIF-Bild auswählen.')
        return jsonify(src='data:image/webp;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii'))

    @app.post('/api/preview')
    def preview():
        body = request.get_json() or {}
        return jsonify(html=clean_html(str(body.get('html', ''))))

    @app.get('/editor/<any(redaktion.js,redaktion.css,meldung.css):filename>')
    def assets(filename):
        return app.send_static_file(filename)

    app.static_folder = str(ROOT / 'editor')
    return app
