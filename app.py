import os
import json
import threading
import time
import urllib.request
from flask import Flask, request, jsonify, render_template, send_from_directory, Response, send_file
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from dotenv import load_dotenv
import io

load_dotenv()

app = Flask(__name__)

# --- GOOGLE DRIVE SETUP ---

# We use OAuth2 refresh token since service accounts have 0MB storage quota
DRIVE_FOLDER_ID = os.environ.get('GOOGLE_DRIVE_FOLDER_ID')

def get_drive_service():
    refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

    if not refresh_token:
        return None

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    return build('drive', 'v3', credentials=creds)

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

@app.route('/admin')
def admin():
    return render_template('upload.html')

@app.route('/browse/<year>')
def browse(year):
    return render_template('browse.html', year=year)

@app.route('/upload', methods=['POST'])
def upload_file():
    admin_key = request.form.get('admin_key')
    if admin_key != 'akgec_admin':
        return jsonify({'error': 'Unauthorized! Invalid Admin Passcode.'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    year = request.form.get('year')
    branch = request.form.get('branch', '')
    semester = request.form.get('semester')
    type_ = request.form.get('type')
    session = request.form.get('session')

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if not all([year, semester, type_, session]):
        return jsonify({'error': 'Missing category information'}), 400
    if year != '1st_year' and not branch:
        return jsonify({'error': 'Branch is required for this year'}), 400

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
        if 'invalid_grant' in error_msg or 'Token has been expired' in error_msg or 'revoked' in error_msg:
            return jsonify({'error': 'Google Drive token expired. Re-run setup_oauth.py and update GOOGLE_REFRESH_TOKEN on Render.'}), 500
        return jsonify({'error': f'Failed to fetch files from Google Drive: {error_msg}'}), 500

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)
