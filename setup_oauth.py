"""
One-time setup: Run this script to authorize your personal Google account.
It will open a browser, you log in, and it saves a refresh token.
You only need to do this ONCE.
"""
import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow

# Permissions: read/write files created or opened by this app
SCOPES = ['https://www.googleapis.com/auth/drive.file']

CLIENT_SECRET_FILE = os.path.join(os.path.dirname(__file__), 'client_secret.json')

if not os.path.exists(CLIENT_SECRET_FILE):
    print("=" * 60)
    print("STEP 1: Create OAuth Client ID in Google Cloud Console")
    print("=" * 60)
    print()
    print("1. Go to: https://console.cloud.google.com/apis/credentials")
    print("2. Click '+ CREATE CREDENTIALS' -> 'OAuth client ID'")
    print("3. If asked for consent screen:")
    print("   - Choose 'External' -> Create")
    print("   - App name: AKGEC Space")
    print("   - Support email: your email")
    print("   - Developer email: your email")
    print("   - Click 'Save and Continue' through all steps")
    print("   - On 'Test users' page, add YOUR Gmail address")
    print("4. Back to Credentials -> Create OAuth client ID")
    print("   - Application type: 'Desktop app'")
    print("   - Name: AKGEC Desktop")
    print("   - Click 'Create'")
    print("5. Click 'DOWNLOAD JSON' button")
    print(f"6. Save the downloaded file as: {CLIENT_SECRET_FILE}")
    print()
    print("Then run this script again!")
    exit(1)

print("Starting OAuth authentication flow...")
print("A browser tab will open — log in with your Google account and grant permissions.")
print()

try:
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    # prompt='consent' and access_type='offline' ensures Google always returns a refresh token
    creds = flow.run_local_server(port=0, prompt='consent', access_type='offline')

    refresh_token = creds.refresh_token
    client_id = creds.client_id
    client_secret = creds.client_secret

    if not refresh_token:
        print("[WARNING] Google did not return a refresh token.")
        print("Please delete client_secret.json, create a new OAuth Desktop Client ID, and try again.")
    else:
        print()
        print("=" * 60)
        print("SUCCESS! Here are your credentials:")
        print("=" * 60)
        print()
        print(f"GOOGLE_REFRESH_TOKEN={refresh_token}")
        print(f"GOOGLE_CLIENT_ID={client_id}")
        print(f"GOOGLE_CLIENT_SECRET={client_secret}")
        print()
        print("Add these variables to your .env file and your Render/cloud environment.")
        print("=" * 60)

        token_data = {
            'GOOGLE_REFRESH_TOKEN': refresh_token,
            'GOOGLE_CLIENT_ID': client_id,
            'GOOGLE_CLIENT_SECRET': client_secret
        }
        with open('oauth_tokens.json', 'w', encoding='utf-8') as f:
            json.dump(token_data, f, indent=2)
        print(f"\nTokens also saved safely to: oauth_tokens.json\n")
except Exception as e:
    print(f"\n[Error during OAuth setup]: {e}")
