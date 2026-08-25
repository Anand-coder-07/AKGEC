import os
import io
import json
import time
import hmac
import mimetypes
import threading
import urllib.request
from flask import Flask, request, jsonify, render_template, send_from_directory, redirect
from werkzeug.utils import secure_filename
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Max upload limit (50 MB)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# --- CONFIGURATION ---
ADMIN_KEY = os.environ.get('ADMIN_KEY', 'akgec_admin')
R2_ACCOUNT_ID = os.environ.get('R2_ACCOUNT_ID')
R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY')
R2_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME')
R2_PUBLIC_URL = os.environ.get('R2_PUBLIC_URL') # Optional custom domain

FN_SECTIONS_FILE = os.path.join(os.path.dirname(__file__), 'fn_sections.json')
FN_YEARS = ['1st_year', '2nd_year', '3rd_year', '4th_year']
FN_CONFIG_FILENAME = "config_fn_sections.json"

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'webp', 'doc', 'docx', 'ppt', 'pptx'}

# --- THREAD LOCKS & CACHES ---
_r2_lock = threading.Lock()
_cached_r2_client = None

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


# --- CLOUDFLARE R2 SERVICE ---

def get_r2_client():
    """Get an authenticated boto3 client for Cloudflare R2 with thread-safe caching."""
    global _cached_r2_client

    if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME]):
        return None

    with _r2_lock:
        if _cached_r2_client:
            return _cached_r2_client

        endpoint_url = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        
        try:
            _cached_r2_client = boto3.client(
                's3',
                endpoint_url=endpoint_url,
                aws_access_key_id=R2_ACCESS_KEY_ID,
                aws_secret_access_key=R2_SECRET_ACCESS_KEY,
                config=Config(signature_version='s3v4'),
                region_name='auto'
            )
            return _cached_r2_client
        except Exception as e:
            print(f"[R2] Authentication failed: {e}")
            return None

def upload_to_r2(file_stream, object_key, mime_type):
    """Upload a file to R2."""
    client = get_r2_client()
    if not client:
        raise Exception("R2 client not configured")
        
    client.upload_fileobj(
        file_stream,
        R2_BUCKET_NAME,
        object_key,
        ExtraArgs={'ContentType': mime_type}
    )
    return object_key

def generate_presigned_url(object_key, action='download', expiry=3600, filename=None):
    """Generate a presigned URL or public URL for R2 objects."""
    # If a custom domain is configured, use it for direct access
    if R2_PUBLIC_URL:
        base = R2_PUBLIC_URL.rstrip('/')
        return f"{base}/{object_key}"
        
    client = get_r2_client()
    if not client:
        raise Exception("R2 client not configured")
        
    params = {'Bucket': R2_BUCKET_NAME, 'Key': object_key}
    
    if action == 'download' and filename:
        params['ResponseContentDisposition'] = f'attachment; filename="{filename}"'
    elif action == 'view' and filename:
        params['ResponseContentDisposition'] = f'inline; filename="{filename}"'
        
    return client.generate_presigned_url(
        'get_object',
        Params=params,
        ExpiresIn=expiry
    )

def list_r2_objects(prefix):
    """List objects in R2 matching a prefix."""
    client = get_r2_client()
    if not client:
        raise Exception("R2 client not configured")
        
    objects = []
    paginator = client.get_paginator('list_objects_v2')
    
    try:
        for page in paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix=prefix):
            if 'Contents' in page:
                for obj in page['Contents']:
                    objects.append({
                        'Key': obj['Key'],
                        'LastModified': obj['LastModified'],
                        'Size': obj['Size']
                    })
        return objects
    except ClientError as e:
        print(f"[R2] List error: {e}")
        return []

def delete_r2_object(object_key):
    """Delete an object from R2."""
    client = get_r2_client()
    if not client:
        raise Exception("R2 client not configured")
        
    client.delete_object(Bucket=R2_BUCKET_NAME, Key=object_key)
    return True


# --- FACULTY NOTES SECTIONS STORAGE & CACHING ---

def invalidate_fn_cache():
    """Clear memory cache for faculty notes sections."""
    with _fn_cache_lock:
        _fn_cache['data'] = None
        _fn_cache['timestamp'] = 0


def load_fn_sections():
    """Load faculty notes sections from local file."""
    now = time.time()
    with _fn_cache_lock:
        if _fn_cache['data'] is not None and (now - _fn_cache['timestamp'] < FN_CACHE_TTL):
            return {y: list(_fn_cache['data'].get(y, [])) for y in FN_YEARS}

    default = {y: [] for y in FN_YEARS}

    # Load from local file
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
    """Save faculty notes sections to local JSON."""
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


# --- KEEP-ALIVE BACKGROUND THREAD ---
# Supports Render (RENDER_EXTERNAL_URL) and Hugging Face (APP_URL) deployments.
# Set APP_URL = your full HF Space URL in HF Secrets, e.g. https://username-spacename.hf.space

KEEP_ALIVE_URL = os.environ.get('APP_URL') or os.environ.get('RENDER_EXTERNAL_URL')

def keep_alive():
    """Background thread that pings /health every 8 minutes to prevent cold boot sleep."""
    while True:
        time.sleep(480)  # 8 minutes — well under HF's inactivity window
        if KEEP_ALIVE_URL:
            try:
                url = f"{KEEP_ALIVE_URL.rstrip('/')}/health"
                req = urllib.request.Request(url, headers={'User-Agent': 'AKGEC-Space-KeepAlive/1.0'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        print(f"[Keep-Alive] Pinged {url} successfully")
            except Exception as e:
                print(f"[Keep-Alive] Ping failed: {e}")

if KEEP_ALIVE_URL:
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    print(f"[Keep-Alive] Started background ping for {KEEP_ALIVE_URL}")


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

    client = get_r2_client()
    if not client:
        return jsonify({'error': 'R2 storage not configured. Check server environment variables.'}), 500

    try:
        clean_name = sanitize_filename(file.filename)
        object_key = f"{year}_{branch}_{semester}_{type_}_{session}_{clean_name}"

        mime = file.content_type or mimetypes.guess_type(clean_name)[0] or 'application/octet-stream'
        upload_to_r2(file.stream, object_key, mime)

        return jsonify({
            'success': 'File successfully uploaded to Cloudflare R2!',
            'id': object_key,
            'filename': clean_name
        }), 200
    except Exception as e:
        error_msg = str(e)
        print(f"[Upload Error] {error_msg}")
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

    client = get_r2_client()
    if not client:
        return jsonify({'error': 'R2 storage not configured'}), 500

    try:
        normalized_sem = normalize_semester(raw_semester)
        
        # Candidate prefixes to match (handles normalized '1st_sem' as well as legacy numeric '1')
        candidate_prefixes = [
            f"{year}_{branch}_{normalized_sem}_{type_}_{session}_",
            f"{year}_{branch}_{raw_semester}_{type_}_{session}_"
        ]
        
        # We search with year prefix to reduce list_objects calls
        prefix_to_search = f"{year}_{branch}_"
        all_objects = list_r2_objects(prefix_to_search)

        formatted_files = []
        seen_keys = set()

        for obj in all_objects:
            key = obj['Key']
            if key in seen_keys:
                continue

            matched_prefix = None
            for p in candidate_prefixes:
                if key.startswith(p):
                    matched_prefix = p
                    break

            if matched_prefix:
                original_name = key[len(matched_prefix):]
                seen_keys.add(key)
                formatted_files.append({
                    'name': original_name,
                    'id': key,
                    'path': key
                })

        return jsonify(formatted_files), 200
    except Exception as e:
        print(f"[ERROR] /api/files failed: {e}")
        return jsonify({'error': f'Failed to fetch files: {str(e)}'}), 500


# --- FACULTY NOTES PUBLIC LISTING API ---

@app.route('/api/faculty-notes')
def get_faculty_notes():
    """Fetch all faculty notes for a given year."""
    year = request.args.get('year', '').strip()
    if not year or year not in FN_YEARS:
        return jsonify({'error': 'Missing or invalid year parameter'}), 400

    client = get_r2_client()
    if not client:
        return jsonify({'error': 'R2 storage not configured'}), 500

    try:
        all_objects = list_r2_objects(f"{year}_")

        formatted_files = []
        for obj in all_objects:
            key = obj['Key']
            
            # The object key should have '_notes_' in it
            notes_idx = key.find('_notes_')
            if notes_idx == -1:
                continue

            after_notes = key[notes_idx + len('_notes_'):]
            session_sep = after_notes.find('_')
            if session_sep == -1:
                continue

            original_name = after_notes[session_sep + 1:]
            formatted_files.append({
                'name': original_name,
                'id': key,
                'path': key
            })

        return jsonify(formatted_files), 200
    except Exception as e:
        print(f"[ERROR] /api/faculty-notes failed: {e}")
        return jsonify({'error': f'Failed to fetch faculty notes: {str(e)}'}), 500


# --- FILE STREAMING / DOWNLOAD API ---

def get_file_response(object_key, action='download', passed_name=None):
    """Redirect to a presigned URL or public URL for the R2 object."""
    try:
        original_name = (passed_name or request.args.get('name') or '').strip()
        
        if not original_name:
            if object_key.startswith('fn_'):
                parts = object_key.split('_', 3)
                original_name = parts[-1] if len(parts) >= 4 else object_key
            else:
                parts = object_key.split('_', 5)
                original_name = parts[-1] if len(parts) >= 6 else object_key

        # Fallback check for PDF extension
        mime_type, _ = mimetypes.guess_type(original_name)
        if not mime_type or mime_type == 'application/octet-stream':
            if original_name and original_name.lower().endswith('.pdf'):
                pass
            else:
                original_name = f"{original_name}.pdf"
                
        url = generate_presigned_url(object_key, action=action, filename=original_name)
        return redirect(url, code=302)
    except Exception as e:
        print(f"[File Error] object_key={object_key}, action={action}, error={e}")
        return jsonify({'error': f'Failed to generate URL: {str(e)}'}), 500


@app.route('/download/<path:file_id>')
def download_file(file_id):
    return get_file_response(file_id, action='download')


@app.route('/view/<path:file_id>')
def view_file(file_id):
    return get_file_response(file_id, action='view')


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

        # Delete all R2 files belonging to this section
        try:
            prefix = f"fn_{year}_{section_name}_"
            objects = list_r2_objects(prefix)
            for obj in objects:
                delete_r2_object(obj['Key'])
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

        prefix = f"fn_{year}_{section_name}_"
        objects = list_r2_objects(prefix)
        files = []
        for obj in objects:
            key = obj['Key']
            display_name = key[len(prefix):]
            files.append({'id': key, 'display_name': display_name})

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

        object_key = f"fn_{year}_{section}_{clean_display_name}"

        mime = file.content_type or mimetypes.guess_type(clean_display_name)[0] or 'application/octet-stream'
        upload_to_r2(file.stream, object_key, mime)

        return jsonify({'success': True, 'id': object_key}), 200
    except Exception as e:
        return jsonify({'error': f'Server Error: {str(e)}'}), 500


@app.route('/api/fn/file/<file_id>', methods=['DELETE'])
def fn_delete_file(file_id):
    """Delete a faculty notes file by R2 object key (Admin)."""
    try:
        if not is_admin_authorized():
            return jsonify({'error': 'Unauthorized'}), 401

        delete_r2_object(file_id)
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': f'Server Error: {str(e)}'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', debug=False, port=port)
