import os
import json
import threading
import time
import urllib.request
from flask import Flask, request, jsonify, render_template, send_from_directory, Response, send_file
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from dotenv import load_dotenv
import io

load_dotenv()

app = Flask(__name__)

# --- GOOGLE DRIVE SETUP ---

DRIVE_FOLDER_ID = os.environ.get('GOOGLE_DRIVE_FOLDER_ID')
ADMIN_KEY = os.environ.get('ADMIN_KEY', 'akgec_admin')

# Faculty Notes sections storage path
FN_SECTIONS_FILE = os.path.join(os.path.dirname(__file__), 'fn_sections.json')

FN_YEARS = ['1st_year', '2nd_year', '3rd_year', '4th_year']

def load_fn_sections():
    """Load faculty notes sections from local JSON file (year-based dict)."""
    default = {y: [] for y in FN_YEARS}
    if not os.path.exists(FN_SECTIONS_FILE):
        return default
    try:
        with open(FN_SECTIONS_FILE, 'r') as f:
            data = json.load(f)
            stored = data.get('sections', {})
            # Migrate from old list format to new dict format
            if isinstance(stored, list):
                default['1st_year'] = stored
                save_fn_sections(default)
                return default
            
            # Deep copy to ensure no shared references
            import copy
            result = copy.deepcopy(default)
            if isinstance(stored, dict):
                for y in FN_YEARS:
                    if y in stored and isinstance(stored[y], list):
                        result[y] = stored[y]
            return result
    except Exception:
        return default

def save_fn_sections(sections):
    """Save faculty notes sections to local JSON file."""
    with open(FN_SECTIONS_FILE, 'w') as f:
        json.dump({'sections': sections}, f)

# Cached credentials (avoids rebuilding on every request)
_cached_creds = None
_cached_service = None

def get_drive_service():
    """Get an authenticated Google Drive service with caching and auto-refresh."""
    global _cached_creds, _cached_service

    refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

    if not refresh_token:
        return None

    # If we have cached creds, check if they're still valid
    if _cached_creds and _cached_creds.refresh_token == refresh_token:
        if _cached_creds.valid:
            return _cached_service
        # Access token expired — try to refresh it
        if _cached_creds.expired:
            try:
                _cached_creds.refresh(Request())
                print("[Token] Access token refreshed successfully")
                return _cached_service
            except Exception as e:
                error_msg = str(e)
                print(f"[Token] Refresh failed: {error_msg}")
                # If refresh token itself is invalid, clear cache and fall through
                _cached_creds = None
                _cached_service = None
                if 'invalid_grant' in error_msg or 'Token has been expired' in error_msg or 'revoked' in error_msg:
                    raise Exception(
                        'GOOGLE_TOKEN_EXPIRED: Refresh token expired. '
                        'Re-run setup_oauth.py and update GOOGLE_REFRESH_TOKEN on Render.'
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

    # Eagerly refresh to catch token issues immediately
    try:
        creds.refresh(Request())
        print("[Token] New credentials obtained successfully")
    except Exception as e:
        error_msg = str(e)
        print(f"[Token] Authentication failed: {error_msg}")
        if 'invalid_grant' in error_msg or 'Token has been expired' in error_msg or 'revoked' in error_msg:
            raise Exception(
                'GOOGLE_TOKEN_EXPIRED: Your refresh token has expired. '
                'Go to /admin/token to update it, or re-run setup_oauth.py locally. '
                'To prevent this permanently, publish your OAuth app in Google Cloud Console.'
            )
        raise

    # Cache for future requests
    _cached_creds = creds
    _cached_service = build('drive', 'v3', credentials=creds)
    return _cached_service

# --- SELF-PING TO KEEP RENDER ALIVE ---

RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL')  # Render sets this automatically

def keep_alive():
    """Background thread that pings the app every 10 minutes to prevent Render sleep."""
    while True:
        time.sleep(600)  # 10 minutes
        if RENDER_URL:
            try:
                urllib.request.urlopen(f"{RENDER_URL}/health")
                print(f"[Keep-Alive] Pinged {RENDER_URL}/health successfully")
            except Exception as e:
                print(f"[Keep-Alive] Ping failed: {e}")

# Start keep-alive thread only in production (on Render)
if RENDER_URL:
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    print(f"[Keep-Alive] Started background ping for {RENDER_URL}")

# --- ROUTES ---

@app.route('/health')
def health():
    return jsonify({'status': 'ok'}), 200

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory('static', 'sitemap.xml')

@app.route('/robots.txt')
def robots():
    return send_from_directory('static', 'robots.txt')

@app.route('/admin')
def admin():
    return render_template('upload.html')

@app.route('/admin/faculty-notes')
def admin_faculty_notes():
    return render_template('faculty_notes.html')

@app.route('/browse/<year>')
def browse(year):
    return render_template('browse.html', year=year)


@app.route('/upload', methods=['POST'])
def upload_file():
    admin_key = request.form.get('admin_key')
    if admin_key != ADMIN_KEY:
        return jsonify({'error': 'Unauthorized! Invalid Admin Passcode.'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    year = request.form.get('year')
    branch = request.form.get('branch', '')
    semester = request.form.get('semester')
    type_ = request.form.get('type')
    session = request.form.get('session')

    if type_ == 'notes':
        semester = semester or 'none'
        session = session or 'none'

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if not all([year, semester, type_, session]):
        return jsonify({'error': 'Missing category information'}), 400

    service = get_drive_service()
    if not service:
        return jsonify({'error': 'Google Drive service not configured'}), 500

    # Path: [Year]_[Branch]_[Semester]_[Type]_[Session]_[Filename]
    # Google Drive doesn't really have folders in the same way, so we'll use a naming convention 
    # OR we can create actual subfolders (more complex). 
    # For now, let's keep it simple: prefix the filename with the metadata.
    filename = f"{year}_{branch}_{semester}_{type_}_{session}_{file.filename}"
    
    file_metadata = {
        'name': filename,
        'parents': [DRIVE_FOLDER_ID]
    }
    
    media = MediaIoBaseUpload(file.stream, mimetype=file.content_type, resumable=True)
    drive_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    
    return jsonify({'success': 'File successfully uploaded to Google Drive!', 'id': drive_file.get('id')}), 200

@app.route('/api/files')
def get_files():
    year = request.args.get('year')
    branch = request.args.get('branch', '')
    semester = request.args.get('semester')
    type_ = request.args.get('type')
    session = request.args.get('session')

    if not all([year, semester, type_, session]):
        return jsonify({'error': 'Missing parameters'}), 400

    service = get_drive_service()
    if not service:
        return jsonify({'error': 'Google Drive service not configured. Check environment variables.'}), 500

    try:
        # Search for files matching the year/branch/semester to narrow down results
        # We use a broad 'contains' and then filter strictly in Python for prefix match
        query_prefix = f"{year}_{branch}_{semester}_"
        query = f"'{DRIVE_FOLDER_ID}' in parents and name contains '{query_prefix}' and trashed = false"
        
        results = service.files().list(q=query, fields="files(id, name)", pageSize=1000).execute()
        all_files = results.get('files', [])
        
        # Strictly define the prefix we are looking for
        strict_prefix = f"{year}_{branch}_{semester}_{type_}_{session}_"
        
        formatted_files = []
        for f in all_files:
            name = f['name']
            if name.startswith(strict_prefix):
                # Only remove the prefix from the START of the name
                original_name = name[len(strict_prefix):]
                formatted_files.append({
                    'name': original_name,
                    'id': f['id'],
                    'path': f['id']
                })
        return jsonify(formatted_files)
    except Exception as e:
        print(f"[ERROR] /api/files failed: {e}")
        error_msg = str(e)
        if 'GOOGLE_TOKEN_EXPIRED' in error_msg or 'invalid_grant' in error_msg or 'Token has been expired' in error_msg or 'revoked' in error_msg:
            return jsonify({'error': 'Google Drive token expired. Re-run setup_oauth.py and update GOOGLE_REFRESH_TOKEN on Render.'}), 500
        return jsonify({'error': f'Failed to fetch files from Google Drive: {error_msg}'}), 500

@app.route('/api/faculty-notes')
def get_faculty_notes():
    """Fetch all faculty notes for a given year (no semester/session filter)."""
    year = request.args.get('year')

    if not year:
        return jsonify({'error': 'Missing year parameter'}), 400

    service = get_drive_service()
    if not service:
        return jsonify({'error': 'Google Drive service not configured. Check environment variables.'}), 500

    try:
        # Search for all files in the Drive folder that start with the year and contain '_notes_'
        query = f"'{DRIVE_FOLDER_ID}' in parents and name contains '{year}_' and name contains '_notes_' and trashed = false"

        results = service.files().list(q=query, fields="files(id, name)", pageSize=1000).execute()
        all_files = results.get('files', [])

        formatted_files = []
        for f in all_files:
            name = f['name']
            # File naming: {year}_{branch}_{semester}_notes_{session}_{filename}
            # We need to verify the type part is exactly 'notes'
            parts = name.split('_')
            # Find 'notes' in the parts — it should be the type field
            # Format: year_branch_semester_type_session_filename
            # e.g.: 1st_year__1st_sem_notes_2024-25_file.pdf
            # year = "1st_year", branch = "", semester = "1st_sem", type = "notes"
            if not name.startswith(f"{year}_"):
                continue

            # Remove the year prefix to get: {branch}_{semester}_notes_{session}_{filename}
            remainder = name[len(f"{year}_"):]
            # Find '_notes_' in the remainder to confirm type
            notes_idx = remainder.find('_notes_')
            if notes_idx == -1:
                continue

            # Extract original filename: everything after {branch}_{semester}_notes_{session}_
            after_notes = remainder[notes_idx + len('_notes_'):]
            # after_notes = "{session}_{filename}"
            # Session is like "2024-25", so find the first underscore after that
            session_sep = after_notes.find('_')
            if session_sep == -1:
                continue
            original_name = after_notes[session_sep + 1:]

            formatted_files.append({
                'name': original_name,
                'id': f['id'],
                'path': f['id']
            })

        return jsonify(formatted_files)
    except Exception as e:
        print(f"[ERROR] /api/faculty-notes failed: {e}")
        error_msg = str(e)
        if 'GOOGLE_TOKEN_EXPIRED' in error_msg or 'invalid_grant' in error_msg or 'Token has been expired' in error_msg or 'revoked' in error_msg:
            return jsonify({'error': 'Google Drive token expired. Re-run setup_oauth.py and update GOOGLE_REFRESH_TOKEN on Render.'}), 500
        return jsonify({'error': f'Failed to fetch faculty notes: {error_msg}'}), 500

def get_file_response(file_id, action='download', passed_name=None):
    service = get_drive_service()
    if not service:
        return jsonify({'error': 'Service not configured'}), 500

    request_file = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request_file)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    
    fh.seek(0)
    
    # The frontend knows the exact proper display name, so we can extract it safely
    original_name = passed_name or request.args.get('name')
    if not original_name:
        file_info = service.files().get(fileId=file_id, fields='name, mimeType').execute()
        original_name = file_info['name'].split('_')[-1] # Fallback
    else:
        file_info = service.files().get(fileId=file_id, fields='mimeType').execute()
        
    mime_type = file_info.get('mimeType', 'application/octet-stream')
    if original_name.lower().endswith('.pdf'):
        mime_type = 'application/pdf'
        
    # Flask's send_file securely handles Content-Disposition & Content-Type for us
    return send_file(
        fh,
        mimetype=mime_type,
        as_attachment=(action == 'download'),
        download_name=original_name
    )

@app.route('/download/<file_id>/<path:filename>')
@app.route('/download/<file_id>')
def download_file(file_id, filename=None):
    return get_file_response(file_id, action='download', passed_name=filename)

@app.route('/view/<file_id>/<path:filename>')
@app.route('/view/<file_id>')
def view_file(file_id, filename=None):
    return get_file_response(file_id, action='view', passed_name=filename)


# ============================================================
# FACULTY NOTES MANAGER API
# ============================================================

def fn_auth():
    """Check admin key from header or form."""
    key = request.headers.get('X-Admin-Key') or request.form.get('admin_key')
    return key == ADMIN_KEY


@app.route('/api/fn/verify', methods=['POST'])
def fn_verify():
    """Dedicated endpoint to verify admin passcode."""
    if not fn_auth():
        return jsonify({'error': 'Invalid passcode'}), 401
    return jsonify({'success': True}), 200


@app.route('/api/fn/sections', methods=['GET'])
def fn_get_sections():
    """List sections for a given year. Public for browsing."""
    try:
        year = request.args.get('year', '1st_year')
        all_sections = load_fn_sections()
        sections = all_sections.get(year, [])
        return jsonify({'sections': sections, 'year': year}), 200
    except Exception as e:
        return jsonify({'error': f'Server Error: {str(e)}'}), 500


@app.route('/api/fn/sections', methods=['POST'])
def fn_create_section():
    try:
        if not fn_auth():
            return jsonify({'error': 'Unauthorized'}), 401
        data = request.get_json()
        name = (data.get('name') or '').strip() if data else ''
        year = (data.get('year') or '').strip() if data else ''
        if not name:
            return jsonify({'error': 'Section name is required'}), 400
        if year not in FN_YEARS:
            return jsonify({'error': 'Invalid year'}), 400
        all_sections = load_fn_sections()
        if name in all_sections[year]:
            return jsonify({'error': f'Section "{name}" already exists in this year'}), 409
        all_sections[year].append(name)
        save_fn_sections(all_sections)
        return jsonify({'success': True, 'sections': all_sections[year]}), 200
    except Exception as e:
        return jsonify({'error': f'Server Error: {str(e)}'}), 500


@app.route('/api/fn/sections/<year>/<section_name>', methods=['DELETE'])
def fn_delete_section(year, section_name):
    try:
        if not fn_auth():
            return jsonify({'error': 'Unauthorized'}), 401
        if year not in FN_YEARS:
            return jsonify({'error': 'Invalid year'}), 400
        all_sections = load_fn_sections()
        if section_name not in all_sections[year]:
            return jsonify({'error': 'Section not found'}), 404

        # Delete all Drive files belonging to this section
        try:
            service = get_drive_service()
            if service:
                prefix = f"fn_{year}_{section_name}_"
                query = f"'{DRIVE_FOLDER_ID}' in parents and name contains 'fn_{year}_{section_name}_' and trashed = false"
                results = service.files().list(q=query, fields="files(id, name)", pageSize=1000).execute()
                for f in results.get('files', []):
                    if f['name'].startswith(prefix):
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
    """List files in a section. Public endpoint."""
    try:
        if year not in FN_YEARS:
            return jsonify({'error': 'Invalid year'}), 400
        all_sections = load_fn_sections()
        if section_name not in all_sections.get(year, []):
            return jsonify({'error': 'Section not found'}), 404
        service = get_drive_service()
        if not service:
            return jsonify({'error': 'Google Drive not configured'}), 500
        
        prefix = f"fn_{year}_{section_name}_"
        query = f"'{DRIVE_FOLDER_ID}' in parents and name contains '{prefix}' and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)", pageSize=1000).execute()
        files = []
        for f in results.get('files', []):
            if f['name'].startswith(prefix):
                display_name = f['name'][len(prefix):]
                files.append({'id': f['id'], 'display_name': display_name})
        return jsonify({'files': files}), 200
    except Exception as e:
        return jsonify({'error': f'Server Error: {str(e)}'}), 500


@app.route('/api/fn/upload', methods=['POST'])
def fn_upload_file():
    try:
        if not fn_auth():
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
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Store on Drive as: fn_{year}_{section}_{display_name}
        drive_name = f"fn_{year}_{section}_{display_name}"
        service = get_drive_service()
        if not service:
            return jsonify({'error': 'Google Drive not configured'}), 500
        
        file_metadata = {'name': drive_name, 'parents': [DRIVE_FOLDER_ID]}
        media = MediaIoBaseUpload(file.stream, mimetype=file.content_type, resumable=True)
        drive_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return jsonify({'success': True, 'id': drive_file.get('id')}), 200
    except Exception as e:
        return jsonify({'error': f'Server Error: {str(e)}'}), 500


@app.route('/api/fn/file/<file_id>', methods=['DELETE'])
def fn_delete_file(file_id):
    try:
        if not fn_auth():
            return jsonify({'error': 'Unauthorized'}), 401
        service = get_drive_service()
        if not service:
            return jsonify({'error': 'Google Drive not configured'}), 500
        service.files().delete(fileId=file_id).execute()
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': f'Server Error: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)
