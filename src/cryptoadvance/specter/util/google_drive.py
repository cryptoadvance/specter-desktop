import os, io, json
from functools import wraps

from pathlib import Path
from dotenv import load_dotenv

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google_auth_oauthlib.flow import Flow

from flask import current_app as app, request
from flask_login import current_user

from zipfile import ZipFile

env_path = Path(".") / ".flaskenv"
load_dotenv(env_path)

# If modifying these scopes, delete the file token.json.
CLIENT_CONFIG = {
    "web": {
        "client_id": os.environ.get("GOOGLE_OAUTH_CLIENT_ID"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_secret": os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET"),
    }
}
SCOPES = ["https://www.googleapis.com/auth/drive.appdata"]
REDIRECT_URI = "http://localhost:25441/settings/google_oauth/callback"


def trigger_google_oauth():
    flow = Flow.from_client_config(client_config=CLIENT_CONFIG, scopes=SCOPES)
    flow.redirect_uri = REDIRECT_URI
    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type="offline",
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes="true",
    )
    return authorization_url, state


def backup(file):
    creds = current_user.google_oauth_data["creds"]
    service = build("drive", "v3", credentials=creds)
    file_metadata = {"name": "specter-backup.zip", "parents": ["appDataFolder"]}
    media = MediaIoBaseUpload(file, mimetype="application/zip", resumable=True)
    file = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id")
        .execute()
    )


def download_latest_backup():
    creds = current_user.google_oauth_data["creds"]
    service = build("drive", "v3", credentials=creds)
    response = (
        service.files()
        .list(
            spaces="appDataFolder",
            fields="nextPageToken, files(id, name)",
            pageSize=1,
        )
        .execute()
    )
    files = response.get("files", [])

    if len(files) == 0:
        return None

    # Taking the most recent backup
    file = files[0]
    file_id = file.get("id")

    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()

    return fh


def extract_wallets_and_devices(file):
    wallets = []
    devices = []
    zippedFiles = ZipFile(file)
    for zipinfo in zippedFiles.infolist():
        currFile = zippedFiles.open(zipinfo)
        if "wallets/" in zipinfo.filename:
            wallets.append(json.loads(currFile.read().decode("UTF-8")))
        elif "devices/" in zipinfo.filename:
            devices.append(json.loads(currFile.read().decode("UTF-8")))
    return wallets, devices


def verify_google_oauth(state, auth_response):
    flow = Flow.from_client_config(
        client_config=CLIENT_CONFIG, scopes=SCOPES, state=state
    )
    flow.redirect_uri = REDIRECT_URI
    flow.fetch_token(authorization_response=auth_response)

    return flow.credentials


def require_google_oauth(func):
    """User needs Google OAuth method decorator"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not "creds" in current_user.google_oauth_data:
            authorization_url, state = trigger_google_oauth()
            current_user.set_google_oauth_state(state)
            return (
                {"redirect_url": authorization_url},
                307,
                {"Location": authorization_url},
            )
        else:
            return func(*args, **kwargs)

    return wrapper
