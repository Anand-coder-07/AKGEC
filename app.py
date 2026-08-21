import os
import io
import json
import time
import hmac
import mimetypes
import threading
import urllib.request
from flask import Flask, request, jsonify, render_template, send_from_directory, send_file
from werkzeug.utils import secure_filename
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Max upload limit (50 MB)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# --- CONFIGURATION ---
DRIVE_FOLDER_ID = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '')
ADMIN_KEY = os.environ.get('ADMIN_KEY', 'akgec_admin')

FN_SECTIONS_FILE = os.path.join(os.path.dirname(__file__), 'fn_sections.json')
FN_YEARS = ['1st_year', '2nd_year', '3rd_year', '4th_year']
FN_CONFIG_FILENAME = "config_fn_sections.json"

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'webp', 'doc', 'docx', 'ppt', 'pptx'}

# --- THREAD LOCKS & CACHES ---
_drive_lock = threading.Lock()
_cached_creds = None
_cached_service = None

_fn_cache_lock = threading.Lock()
_fn_cache = {'data': None, 'timestamp': 0}
FN_CACHE_TTL = 60  # seconds


# --- HELPER FUNCTIONS ---

def is_allowed_file(filename):
    """Check if file extension is permitted."""
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def sanitize_filename(filename):
    """Return a safe filename while preserving readable alphanumeric & dot chars."""
    clean = secure_filename(filename)
    if not clean:
        clean = f"upload_{int(time.time())}.pdf"
    return clean


def normalize_semester(sem):
    """Normalize semester values (e.g. '1', 'sem1', '1st_sem' -> '1st_sem')."""
    if not sem:
        return ''
    s = str(sem).strip().lower()
    mapping = {
        '1': '1st_sem', 'sem1': '1st_sem', '1st': '1st_sem', '1st_sem': '1st_sem',
        '2': '2nd_sem', 'sem2': '2nd_sem', '2nd': '2nd_sem', '2nd_sem': '2nd_sem',
        '3': '3rd_sem', 'sem3': '3rd_sem', '3rd': '3rd_sem', '3rd_sem': '3rd_sem',
        '4': '4th_sem', 'sem4': '4th_sem', '4th': '4th_sem', '4th_sem': '4th_sem',
        '5': '5th_sem', 'sem5': '5th_sem', '5th': '5th_sem', '5th_sem': '5th_sem',
        '6': '6th_sem', 'sem6': '6th_sem', '6th': '6th_sem', '6th_sem': '6th_sem',
        '7': '7th_sem', 'sem7': '7th_sem', '7th': '7th_sem', '7th_sem': '7th_sem',
        '8': '8th_sem', 'sem8': '8th_sem', '8th': '8th_sem', '8th_sem': '8th_sem',
    }
    return mapping.get(s, s)


def escape_drive_query(s):
    """Safely escape single quotes and backslashes in Google Drive query strings."""
    if not s:
        return ""
    return str(s).replace("\\", "\\\\").replace("'", "\\'")


def is_admin_authorized():
    """Verify admin key using constant-time comparison against header or form data."""
    provided_key = request.headers.get('X-Admin-Key') or request.form.get('admin_key') or ''
    return hmac.compare_digest(provided_key.strip(), ADMIN_KEY.strip())


# --- GOOGLE DRIVE SERVICE ---

def get_drive_service():
    """Get an authenticated Google Drive service with thread-safe caching and auto-refresh."""
    global _cached_creds, _cached_service

    refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

    if not refresh_token:
        return None

    with _drive_lock:
        # Check existing cached credentials
        if _cached_creds and _cached_creds.refresh_token == refresh_token:
            if _cached_creds.valid:
                return _cached_service
            if _cached_creds.expired:
                try:
                    _cached_creds.refresh(Request())
                    return _cached_service
                except Exception as e:
                    error_msg = str(e)
                    print(f"[Token] Refresh failed: {error_msg}")
                    _cached_creds = None
                    _cached_service = None
                    if any(x in error_msg for x in ['invalid_grant', 'expired', 'revoked']):
                        raise Exception(
                            'GOOGLE_TOKEN_EXPIRED: Refresh token expired. '
                            'Re-run setup_oauth.py and update GOOGLE_REFRESH_TOKEN.'
                        )
                    raise

        # Build fresh credentials
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret
        )

        try:
            creds.refresh(Request())
        except Exception as e:
            error_msg = str(e)
            print(f"[Token] Authentication failed: {error_msg}")
            if any(x in error_msg for x in ['invalid_grant', 'expired', 'revoked']):
                raise Exception(
                    'GOOGLE_TOKEN_EXPIRED: Your refresh token has expired. '
                    'Re-run setup_oauth.py locally and update your environment variables.'
                )
            raise

        _cached_creds = creds
        _cached_service = build('drive', 'v3', credentials=creds, cache_discovery=False)
        return _cached_service


# --- FACULTY NOTES SECTIONS STORAGE & CACHING ---

def get_fn_config_file_id(service):
    """Retrieve the Drive file ID for the faculty notes config file."""
    if not DRIVE_FOLDER_ID:
        return None
    query = f"'{escape_drive_query(DRIVE_FOLDER_ID)}' in parents and name = '{FN_CONFIG_FILENAME}' and trashed = false"
    results = service.files().list(q=query, fields="files(id)", pageSize=1).execute()
    files = results.get('files', [])
    return files[0]['id'] if files else None


def invalidate_fn_cache():
    """Clear memory cache for faculty notes sections."""
    with _fn_cache_lock:
        _fn_cache['data'] = None
        _fn_cache['timestamp'] = 0


def load_fn_sections():
    """Load faculty notes sections with in-memory caching, Drive sync, and local fallback."""
    now = time.time()
    with _fn_cache_lock:
        if _fn_cache['data'] is not None and (now - _fn_cache['timestamp'] < FN_CACHE_TTL):
            return {y: list(_fn_cache['data'].get(y, [])) for y in FN_YEARS}

    default = {y: [] for y in FN_YEARS}

    # 1. Try Google Drive
    try:
        service = get_drive_service()
        if service and DRIVE_FOLDER_ID:
            file_id = get_fn_config_file_id(service)
            if file_id:
                request_file = service.files().get_media(fileId=file_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request_file)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                fh.seek(0)
                data = json.loads(fh.read().decode('utf-8'))
                stored = data.get('sections', {})
                result = {y: [] for y in FN_YEARS}
                if isinstance(stored, dict):
                    for y in FN_YEARS:
                        if y in stored and isinstance(stored[y], list):
                            result[y] = [str(item) for item in stored[y] if item]

                # Update local file sync
                try:
                    with open(FN_SECTIONS_FILE, 'w', encoding='utf-8') as f:
                        json.dump({'sections': result}, f, indent=2)
                except Exception as ex:
                    print(f"[FN Sync] Local file write warning: {ex}")

                with _fn_cache_lock:
                    _fn_cache['data'] = result
                    _fn_cache['timestamp'] = now

                return {y: list(result[y]) for y in FN_YEARS}
    except Exception as e:
        print(f"[FN Sync] Warning loading from Drive: {e}")

    # 2. Fallback to local file
    if os.path.exists(FN_SECTIONS_FILE):
        try:
            with open(FN_SECTIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                stored = data.get('sections', {})
                result = {y: [] for y in FN_YEARS}
                if isinstance(stored, list):
                    result['1st_year'] = [str(item) for item in stored if item]
                elif isinstance(stored, dict):
                    for y in FN_YEARS:
                        if y in stored and isinstance(stored[y], list):
                            result[y] = [str(item) for item in stored[y] if item]

                with _fn_cache_lock:
                    _fn_cache['data'] = result
                    _fn_cache['timestamp'] = now

                return {y: list(result[y]) for y in FN_YEARS}
        except Exception as e:
            print(f"[FN Sync] Warning loading from local file: {e}")

    return default


def save_fn_sections(sections):
    """Save faculty notes sections to local JSON and Google Drive, updating cache."""
    clean_sections = {y: list(sections.get(y, [])) for y in FN_YEARS}

    # Update cache immediately
    with _fn_cache_lock:
        _fn_cache['data'] = clean_sections
        _fn_cache['timestamp'] = time.time()

    # Local save
    try:
        with open(FN_SECTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'sections': clean_sections}, f, indent=2)
    except Exception as e:
        print(f"[FN Sync] Error writing local sections file: {e}")

    # Drive save
    try:
        service = get_drive_service()
        if service and DRIVE_FOLDER_ID:
            file_id = get_fn_config_file_id(service)
            raw_bytes = json.dumps({'sections': clean_sections}).encode('utf-8')
            fh = io.BytesIO(raw_bytes)
            media = MediaIoBaseUpload(fh, mimetype='application/json', resumable=False)

            if file_id:
                service.files().update(fileId=file_id, media_body=media).execute()
            else:
                file_metadata = {
                    'name': FN_CONFIG_FILENAME,
                    'parents': [DRIVE_FOLDER_ID]
                }
                service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    except Exception as e:
        print(f"[FN Sync] Error saving sections to Drive: {e}")


# --- KEEP-ALIVE BACKGROUND THREAD ---

RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL')

def keep_alive():
    """Background thread that pings /health every 10 minutes to prevent cold boot sleep."""
    while True:
        time.sleep(600)
        if RENDER_URL:
            try:
                url = f"{RENDER_URL.rstrip('/')}/health"
                req = urllib.request.Request(url, headers={'User-Agent': 'AKGEC-Space-KeepAlive/1.0'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        print(f"[Keep-Alive] Pinged {url} successfully")
            except Exception as e:
                print(f"[Keep-Alive] Ping failed: {e}")

if RENDER_URL:
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    print(f"[Keep-Alive] Started background ping for {RENDER_URL}")


# --- ROUTES ---

@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'timestamp': int(time.time())}), 200


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory('static', 'sitemap.xml', mimetype='application/xml')


@app.route('/robots.txt')
def robots():
    return send_from_directory('static', 'robots.txt', mimetype='text/plain')


@app.route('/admin')
def admin():
    return render_template('upload.html')


@app.route('/admin/faculty-notes')
def admin_faculty_notes():
    return render_template('faculty_notes.html')


@app.route('/browse/<year>')
def browse(year):
    if year not in FN_YEARS:
        return render_template('index.html')
    return render_template('browse.html', year=year)


# --- UPLOAD API ---

@app.route('/upload', methods=['POST'])
def upload_file():
    if not is_admin_authorized():
        return jsonify({'error': 'Unauthorized! Invalid Admin Passcode.'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if not is_allowed_file(file.filename):
        return jsonify({'error': f'Unsupported file type. Allowed: {", ".join(sorted(ALLOWED_EXTENSIONS))}'}), 400

    year = request.form.get('year', '').strip()
    branch = request.form.get('branch', '').strip()
    raw_semester = request.form.get('semester', '').strip()
    type_ = request.form.get('type', '').strip()
    session = request.form.get('session', '').strip()

    if year not in FN_YEARS:
        return jsonify({'error': 'Invalid year selected'}), 400

    semester = normalize_semester(raw_semester)

    if type_ == 'notes':
        semester = semester or 'none'
        session = session or 'none'

    if not all([year, semester, type_, session]):
        return jsonify({'error': 'Missing category information (Year, Semester, Type, or Session)'}), 400

    service = get_drive_service()
    if not service or not DRIVE_FOLDER_ID:
        return jsonify({'error': 'Google Drive service not configured. Check server environment variables.'}), 500

    try:
        clean_name = sanitize_filename(file.filename)
        drive_filename = f"{year}_{branch}_{semester}_{type_}_{session}_{clean_name}"

        file_metadata = {
            'name': drive_filename,
            'parents': [DRIVE_FOLDER_ID]
        }

        mime = file.content_type or mimetypes.guess_type(clean_name)[0] or 'application/octet-stream'
        media = MediaIoBaseUpload(file.stream, mimetype=mime, resumable=True)
        drive_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        return jsonify({
            'success': 'File successfully uploaded to Google Drive!',
            'id': drive_file.get('id'),
            'filename': clean_name
        }), 200
    except Exception as e:
        error_msg = str(e)
        print(f"[Upload Error] {error_msg}")
        if 'GOOGLE_TOKEN_EXPIRED' in error_msg:
            return jsonify({'error': 'Google Drive token expired. Please re-authenticate.'}), 500
        return jsonify({'error': f'Upload failed: {error_msg}'}), 500


# --- PAPERS LISTING API ---

@app.route('/api/files')
def get_files():
    year = request.args.get('year', '').strip()
    branch = request.args.get('branch', '').strip()
    raw_semester = request.args.get('semester', '').strip()
    type_ = request.args.get('type', '').strip()
    session = request.args.get('session', '').strip()

    if not all([year, raw_semester, type_, session]):
        return jsonify({'error': 'Missing required query parameters'}), 400

    service = get_drive_service()
    if not service or not DRIVE_FOLDER_ID:
        return jsonify({'error': 'Google Drive service not configured'}), 500

    try:
        normalized_sem = normalize_semester(raw_semester)
        
        # We search with year prefix and trashed=false to get files in parent folder
        safe_year = escape_drive_query(year)
        safe_folder = escape_drive_query(DRIVE_FOLDER_ID)
        query = f"'{safe_folder}' in parents and name contains '{safe_year}_' and trashed = false"

        results = service.files().list(q=query, fields="files(id, name)", pageSize=1000).execute()
        all_files = results.get('files', [])

        # Candidate prefixes to match (handles normalized '1st_sem' as well as legacy numeric '1')
        candidate_prefixes = [
            f"{year}_{branch}_{normalized_sem}_{type_}_{session}_",
            f"{year}_{branch}_{raw_semester}_{type_}_{session}_"
        ]

        formatted_files = []
        seen_ids = set()

        for f in all_files:
            file_id = f.get('id')
            if not file_id or file_id in seen_ids:
                continue

            name = f.get('name', '')
            matched_prefix = None
            for p in candidate_prefixes:
                if name.startswith(p):
                    matched_prefix = p
                    break

            if matched_prefix:
                original_name = name[len(matched_prefix):]
                seen_ids.add(file_id)
                formatted_files.append({
                    'name': original_name,
                    'id': file_id,
                    'path': file_id
                })

        return jsonify(formatted_files), 200
    except Exception as e:
        print(f"[ERROR] /api/files failed: {e}")
        error_msg = str(e)
        if 'GOOGLE_TOKEN_EXPIRED' in error_msg:
            return jsonify({'error': 'Google Drive token expired. Please re-authenticate.'}), 500
        return jsonify({'error': f'Failed to fetch files: {error_msg}'}), 500


# --- FACULTY NOTES PUBLIC LISTING API ---

@app.route('/api/faculty-notes')
def get_faculty_notes():
    """Fetch all faculty notes for a given year."""
    year = request.args.get('year', '').strip()
    if not year or year not in FN_YEARS:
        return jsonify({'error': 'Missing or invalid year parameter'}), 400

    service = get_drive_service()
    if not service or not DRIVE_FOLDER_ID:
        return jsonify({'error': 'Google Drive service not configured'}), 500

    try:
        safe_year = escape_drive_query(year)
        safe_folder = escape_drive_query(DRIVE_FOLDER_ID)
        query = f"'{safe_folder}' in parents and name contains '{safe_year}_' and name contains '_notes_' and trashed = false"

        results = service.files().list(q=query, fields="files(id, name)", pageSize=1000).execute()
        all_files = results.get('files', [])

        formatted_files = []
        for f in all_files:
            name = f.get('name', '')
            if not name.startswith(f"{year}_"):
                continue

            remainder = name[len(f"{year}_"):]
            notes_idx = remainder.find('_notes_')
            if notes_idx == -1:
                continue

            after_notes = remainder[notes_idx + len('_notes_'):]
            session_sep = after_notes.find('_')
            if session_sep == -1:
                continue

            original_name = after_notes[session_sep + 1:]
            formatted_files.append({
                'name': original_name,
                'id': f['id'],
                'path': f['id']
            })

        return jsonify(formatted_files), 200
    except Exception as e:
        print(f"[ERROR] /api/faculty-notes failed: {e}")
        error_msg = str(e)
        if 'GOOGLE_TOKEN_EXPIRED' in error_msg:
            return jsonify({'error': 'Google Drive token expired. Please re-authenticate.'}), 500
        return jsonify({'error': f'Failed to fetch faculty notes: {error_msg}'}), 500


# --- FILE STREAMING / DOWNLOAD API ---

def get_file_response(file_id, action='download', passed_name=None):
    """Download or view a file from Google Drive efficiently."""
    service = get_drive_service()
    if not service:
        return jsonify({'error': 'Google Drive service not configured'}), 500

    try:
        # Determine filename passed from request
        original_name = (passed_name or request.args.get('name') or '').strip()
        mime_type = None
        file_info = None

        # If original_name is missing OR has no extension, fetch file metadata from Drive
        if not original_name or '.' not in original_name:
            try:
                file_info = service.files().get(fileId=file_id, fields='name, mimeType').execute()
            except Exception as e:
                print(f"[Drive Metadata Warning] file_id={file_id}, error={e}")

        if file_info:
            drive_mime = file_info.get('mimeType')
            raw_drive_name = file_info.get('name', '')

            if not original_name:
                if raw_drive_name.startswith('fn_'):
                    parts = raw_drive_name.split('_', 3)
                    original_name = parts[-1] if len(parts) >= 4 else raw_drive_name
                else:
                    parts = raw_drive_name.split('_', 5)
                    original_name = parts[-1] if len(parts) >= 6 else raw_drive_name
            
            # Use drive MIME type if available and valid
            if drive_mime and drive_mime != 'application/octet-stream':
                mime_type = drive_mime

        # Fallback local lookup if MIME type is still unknown
        if not mime_type or mime_type == 'application/octet-stream':
            mime_type, _ = mimetypes.guess_type(original_name)

        # Fallback check for PDF extension or default to application/pdf for document viewing
        if not mime_type or mime_type == 'application/octet-stream':
            if original_name and original_name.lower().endswith('.pdf'):
                mime_type = 'application/pdf'
            else:
                # Default fallback for notes/papers
                mime_type = 'application/pdf'

        # Ensure original_name has an extension matching mime_type if missing
        if '.' not in original_name:
            if mime_type == 'application/pdf':
                original_name = f"{original_name}.pdf"
            elif mime_type == 'image/png':
                original_name = f"{original_name}.png"
            elif mime_type == 'image/jpeg':
                original_name = f"{original_name}.jpg"

        # Download file content from Google Drive
        request_file = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request_file)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        fh.seek(0)

        response = send_file(
            fh,
            mimetype=mime_type,
            as_attachment=(action == 'download'),
            download_name=original_name
        )
        response.headers['Cache-Control'] = 'public, max-age=86400'
        if action == 'view':
            response.headers['Content-Disposition'] = f'inline; filename="{original_name}"'
        return response
    except Exception as e:
        print(f"[File Error] file_id={file_id}, action={action}, error={e}")
        return jsonify({'error': f'Failed to retrieve file: {str(e)}'}), 500


@app.route('/download/<file_id>/<path:filename>')
@app.route('/download/<file_id>')
def download_file(file_id, filename=None):
    return get_file_response(file_id, action='download', passed_name=filename)


@app.route('/view/<file_id>/<path:filename>')
@app.route('/view/<file_id>')
def view_file(file_id, filename=None):
    return get_file_response(file_id, action='view', passed_name=filename)


# --- FACULTY NOTES MANAGER API ---

@app.route('/api/fn/verify', methods=['POST'])
def fn_verify():
    """Verify admin passcode."""
    if not is_admin_authorized():
        return jsonify({'error': 'Invalid passcode'}), 401
    return jsonify({'success': True}), 200


@app.route('/api/fn/sections', methods=['GET'])
def fn_get_sections():
    """List sections for a given year (Public)."""
    try:
        year = request.args.get('year', '1st_year').strip()
        if year not in FN_YEARS:
            year = '1st_year'
        all_sections = load_fn_sections()
        sections = all_sections.get(year, [])
        return jsonify({'sections': sections, 'year': year}), 200
    except Exception as e:
        return jsonify({'error': f'Server Error: {str(e)}'}), 500


@app.route('/api/fn/sections', methods=['POST'])
def fn_create_section():
    """Create a new section under a specific year (Admin)."""
    try:
        if not is_admin_authorized():
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.get_json(silent=True) or {}
        name = str(data.get('name') or '').strip()
        year = str(data.get('year') or '').strip()

        if not name:
            return jsonify({'error': 'Section name is required'}), 400
        if year not in FN_YEARS:
            return jsonify({'error': 'Invalid year'}), 400

        all_sections = load_fn_sections()
        if name in all_sections[year]:
            return jsonify({'error': f'Section "{name}" already exists in {year}'}), 409

        all_sections[year].append(name)
        save_fn_sections(all_sections)
        return jsonify({'success': True, 'sections': all_sections[year]}), 200
    except Exception as e:
        return jsonify({'error': f'Server Error: {str(e)}'}), 500


@app.route('/api/fn/sections/<year>/<section_name>', methods=['DELETE'])
def fn_delete_section(year, section_name):
    """Delete a section and its associated Drive files (Admin)."""
    try:
        if not is_admin_authorized():
            return jsonify({'error': 'Unauthorized'}), 401
        if year not in FN_YEARS:
            return jsonify({'error': 'Invalid year'}), 400

        all_sections = load_fn_sections()
        if section_name not in all_sections.get(year, []):
            return jsonify({'error': 'Section not found'}), 404

        # Delete all Drive files belonging to this section
        try:
            service = get_drive_service()
            if service and DRIVE_FOLDER_ID:
                prefix = f"fn_{year}_{section_name}_"
                safe_folder = escape_drive_query(DRIVE_FOLDER_ID)
                safe_prefix = escape_drive_query(prefix)
                query = f"'{safe_folder}' in parents and name contains '{safe_prefix}' and trashed = false"
                results = service.files().list(q=query, fields="files(id, name)", pageSize=1000).execute()
                for f in results.get('files', []):
                    if f.get('name', '').startswith(prefix):
                        service.files().delete(fileId=f['id']).execute()
        except Exception as e:
            print(f"[FN] Error deleting files for section {year}/{section_name}: {e}")

        all_sections[year].remove(section_name)
        save_fn_sections(all_sections)
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': f'Server Error: {str(e)}'}), 500


@app.route('/api/fn/files/<year>/<section_name>', methods=['GET'])
def fn_get_files(year, section_name):
    """List files in a faculty notes section (Public)."""
    try:
        if year not in FN_YEARS:
            return jsonify({'error': 'Invalid year'}), 400

        all_sections = load_fn_sections()
        if section_name not in all_sections.get(year, []):
            return jsonify({'error': 'Section not found'}), 404

        service = get_drive_service()
        if not service or not DRIVE_FOLDER_ID:
            return jsonify({'error': 'Google Drive not configured'}), 500

        prefix = f"fn_{year}_{section_name}_"
        safe_folder = escape_drive_query(DRIVE_FOLDER_ID)
        safe_prefix = escape_drive_query(prefix)
        query = f"'{safe_folder}' in parents and name contains '{safe_prefix}' and trashed = false"
        
        results = service.files().list(q=query, fields="files(id, name)", pageSize=1000).execute()
        files = []
        for f in results.get('files', []):
            name = f.get('name', '')
            if name.startswith(prefix):
                display_name = name[len(prefix):]
                files.append({'id': f['id'], 'display_name': display_name})

        return jsonify({'files': files}), 200
    except Exception as e:
        return jsonify({'error': f'Server Error: {str(e)}'}), 500


@app.route('/api/fn/upload', methods=['POST'])
def fn_upload_file():
    """Upload a file to a faculty notes section (Admin)."""
    try:
        if not is_admin_authorized():
            return jsonify({'error': 'Unauthorized'}), 401

        section = request.form.get('section', '').strip()
        year = request.form.get('year', '').strip()
        display_name = request.form.get('display_name', '').strip()

        if 'file' not in request.files or not section or not display_name or not year:
            return jsonify({'error': 'Missing file, year, section, or display name'}), 400

        if year not in FN_YEARS:
            return jsonify({'error': 'Invalid year'}), 400

        all_sections = load_fn_sections()
        if section not in all_sections.get(year, []):
            return jsonify({'error': 'Section not found'}), 404

        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not is_allowed_file(file.filename) and not is_allowed_file(display_name):
            return jsonify({'error': 'Invalid file format. Please upload a PDF or image.'}), 400

        clean_display_name = sanitize_filename(display_name)
        if '.' in file.filename and '.' not in clean_display_name:
            file_ext = file.filename.rsplit('.', 1)[1].lower()
            if file_ext in ALLOWED_EXTENSIONS:
                clean_display_name = f"{clean_display_name}.{file_ext}"

        drive_name = f"fn_{year}_{section}_{clean_display_name}"

        service = get_drive_service()
        if not service or not DRIVE_FOLDER_ID:
            return jsonify({'error': 'Google Drive not configured'}), 500

        file_metadata = {'name': drive_name, 'parents': [DRIVE_FOLDER_ID]}
        mime = file.content_type or mimetypes.guess_type(clean_display_name)[0] or 'application/octet-stream'
        media = MediaIoBaseUpload(file.stream, mimetype=mime, resumable=True)
        drive_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        return jsonify({'success': True, 'id': drive_file.get('id')}), 200
    except Exception as e:
        return jsonify({'error': f'Server Error: {str(e)}'}), 500


@app.route('/api/fn/file/<file_id>', methods=['DELETE'])
def fn_delete_file(file_id):
    """Delete a faculty notes file by Drive file ID (Admin)."""
    try:
        if not is_admin_authorized():
            return jsonify({'error': 'Unauthorized'}), 401

        service = get_drive_service()
        if not service:
            return jsonify({'error': 'Google Drive not configured'}), 500

        service.files().delete(fileId=file_id).execute()
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': f'Server Error: {str(e)}'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', debug=False, port=port)
