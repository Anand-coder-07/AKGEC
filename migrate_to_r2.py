import os
import io
import time
import argparse
import mimetypes
from dotenv import load_dotenv

# Google APIs
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# AWS/Cloudflare R2
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

load_dotenv()

# --- CONFIGURATION ---
DRIVE_FOLDER_ID = os.environ.get('GOOGLE_DRIVE_FOLDER_ID')

R2_ACCOUNT_ID = os.environ.get('R2_ACCOUNT_ID')
R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY')
R2_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME')

def get_drive_service():
    """Authenticate and return Google Drive service."""
    refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

    if not all([refresh_token, client_id, client_secret]):
        print("Missing Google Drive credentials in .env")
        return None

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    
    try:
        creds.refresh(Request())
        return build('drive', 'v3', credentials=creds, cache_discovery=False)
    except Exception as e:
        print(f"Failed to authenticate with Google Drive: {e}")
        return None

def get_r2_client():
    """Authenticate and return Cloudflare R2 client via boto3."""
    if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME]):
        print("Missing R2 credentials in .env")
        return None
        
    endpoint_url = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    
    return boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )

def escape_drive_query(s):
    if not s:
        return ""
    return str(s).replace("\\", "\\\\").replace("'", "\\'")

def get_all_drive_files(service):
    """Retrieve all files in the configured Drive folder."""
    print(f"Fetching file list from Google Drive folder: {DRIVE_FOLDER_ID}...")
    safe_folder = escape_drive_query(DRIVE_FOLDER_ID)
    query = f"'{safe_folder}' in parents and trashed = false"
    
    files = []
    page_token = None
    
    while True:
        results = service.files().list(
            q=query, 
            fields="nextPageToken, files(id, name, mimeType, size)", 
            pageSize=1000,
            pageToken=page_token
        ).execute()
        
        items = results.get('files', [])
        files.extend(items)
        
        page_token = results.get('nextPageToken')
        if not page_token:
            break
            
    print(f"Found {len(files)} files in Google Drive.")
    return files

def get_existing_r2_objects(s3_client):
    """Retrieve all object keys currently in the R2 bucket to avoid re-uploading."""
    print(f"Checking existing files in R2 bucket: {R2_BUCKET_NAME}...")
    existing_keys = set()
    
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=R2_BUCKET_NAME):
            if 'Contents' in page:
                for obj in page['Contents']:
                    existing_keys.add(obj['Key'])
        print(f"Found {len(existing_keys)} existing objects in R2.")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchBucket':
            print(f"Bucket {R2_BUCKET_NAME} does not exist. Please create it first.")
            return None
        print(f"Error checking R2: {e}")
        return None
        
    return existing_keys

def migrate_file(drive_service, s3_client, drive_file, dry_run=False):
    """Download from Drive and stream directly to R2."""
    file_id = drive_file['id']
    file_name = drive_file['name']
    mime_type = drive_file.get('mimeType', 'application/octet-stream')
    
    # Skip the faculty notes config file - we don't migrate this
    if file_name == 'config_fn_sections.json':
        print(f"Skipping config file: {file_name}")
        return True
        
    if dry_run:
        print(f"[DRY RUN] Would migrate: {file_name} ({drive_file.get('size', 'unknown')} bytes)")
        return True
        
    print(f"Migrating: {file_name}...", end='', flush=True)
    
    try:
        # Download from Drive
        request_file = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request_file)
        
        done = False
        while not done:
            _, done = downloader.next_chunk()
            
        fh.seek(0)
        
        # Determine content type for R2
        if mime_type == 'application/octet-stream':
            guessed_type, _ = mimetypes.guess_type(file_name)
            if guessed_type:
                mime_type = guessed_type
            elif file_name.lower().endswith('.pdf'):
                mime_type = 'application/pdf'
                
        # Upload to R2
        s3_client.upload_fileobj(
            fh, 
            R2_BUCKET_NAME, 
            file_name,
            ExtraArgs={'ContentType': mime_type}
        )
        print(" DONE")
        return True
    except Exception as e:
        print(f" ERROR: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Migrate files from Google Drive to Cloudflare R2")
    parser.add_argument("--dry-run", action="store_true", help="List files to migrate without actually copying them")
    parser.add_argument("--force", action="store_true", help="Force re-upload of all files, even if they exist in R2")
    args = parser.parse_args()
    
    print("=" * 60)
    print("AKGEC File Storage Migration: Google Drive -> Cloudflare R2")
    print("=" * 60)
    
    if args.dry_run:
        print(">>> RUNNING IN DRY-RUN MODE (No files will be transferred) <<<")
    
    drive_service = get_drive_service()
    if not drive_service:
        return
        
    s3_client = get_r2_client()
    if not s3_client:
        return
        
    existing_keys = get_existing_r2_objects(s3_client)
    if existing_keys is None:
        return
        
    drive_files = get_all_drive_files(drive_service)
    
    to_migrate = []
    for f in drive_files:
        if f['name'] == 'config_fn_sections.json':
            continue
            
        if not args.force and f['name'] in existing_keys:
            continue
            
        to_migrate.append(f)
        
    if not to_migrate:
        print("\nAll files are already migrated! Nothing to do.")
        return
        
    print(f"\nFiles to migrate: {len(to_migrate)}")
    
    success_count = 0
    fail_count = 0
    
    start_time = time.time()
    
    for i, f in enumerate(to_migrate):
        print(f"[{i+1}/{len(to_migrate)}] ", end='')
        if migrate_file(drive_service, s3_client, f, args.dry_run):
            success_count += 1
        else:
            fail_count += 1
            
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"Total time : {elapsed:.2f} seconds")
    print(f"Successful : {success_count}")
    print(f"Failed     : {fail_count}")

if __name__ == "__main__":
    main()
