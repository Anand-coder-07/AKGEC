---
title: AKGEC Notes
emoji: 📚
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# AKGEC Study Website

This Flask application serves study materials and faculty notes for AKGEC students. It stores files in **Cloudflare R2** (S3-compatible object storage) and serves them directly to users via presigned URLs to minimize server bandwidth usage.

## Architecture

- **Web Server**: Flask (Python)
- **Storage**: Cloudflare R2 (zero egress bandwidth)
- **Database**: Local JSON files (for faculty notes sections)
- **File Serving**: Presigned URL redirects (files stream directly from R2 to the user, bypassing the server)

## Local Development Setup

1. **Clone the repository**
2. **Create a virtual environment**: `python -m venv venv`
3. **Activate the virtual environment**:
   - Windows: `venv\Scripts\activate`
   - Mac/Linux: `source venv/bin/activate`
4. **Install dependencies**: `pip install -r requirements.txt`
5. **Set up Environment Variables**: Create a `.env` file in the root directory (see below).
6. **Run the server**: `flask run`

## Cloudflare R2 Setup

You need a Cloudflare account to set up R2 storage.

1. **Create an R2 Bucket**:
   - Go to Cloudflare Dashboard > R2.
   - Click "Create bucket", name it (e.g., `akgec-files`).
2. **Generate API Tokens**:
   - In the R2 dashboard, click "Manage R2 API Tokens" on the right side.
   - Click "Create API token".
   - Permissions: **Object Read & Write**.
   - Copy the **Access Key ID**, **Secret Access Key**, and **Account ID** (available on the R2 overview page).
3. **(Optional) Custom Domain**:
   - In your bucket settings, connect a custom domain (e.g., `files.akgec.in`).
   - If configured, set `R2_PUBLIC_URL` in your `.env` to bypass presigned URLs and serve publicly cacheable links.

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ADMIN_KEY` | Password for uploading/deleting files | `akgec_admin` |
| `R2_ACCOUNT_ID` | Cloudflare Account ID | `abc123def456` |
| `R2_ACCESS_KEY_ID` | R2 API Token Access Key | `a1b2c3...` |
| `R2_SECRET_ACCESS_KEY` | R2 API Token Secret | `xyz...` |
| `R2_BUCKET_NAME` | Name of your R2 bucket | `akgec-files` |
| `R2_PUBLIC_URL` | *(Optional)* Custom domain | `https://files.akgec.in` |
| `APP_URL` or `RENDER_EXTERNAL_URL` | Used for keep-alive ping on free tiers | `https://my-app.onrender.com` |

## Migration from Google Drive

If you have an existing Google Drive setup, you can migrate your files to Cloudflare R2 using the included script.

1. Keep your old Google Drive credentials in your `.env` file (`GOOGLE_DRIVE_FOLDER_ID`, `GOOGLE_REFRESH_TOKEN`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`).
2. Add the new R2 credentials to your `.env` file.
3. Run the migration script locally:
   ```bash
   python migrate_to_r2.py
   ```
4. Once completed successfully, you can remove the Google Drive credentials from your `.env` and production environment variables.

## Deployment (Render)

1. Connect your GitHub repository to a Render Web Service.
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `gunicorn app:app`
4. Add all the required Environment Variables from the table above in the Render dashboard.
