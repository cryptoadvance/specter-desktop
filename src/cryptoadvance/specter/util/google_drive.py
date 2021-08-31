import os, io, json

from pathlib import Path
from dotenv import load_dotenv

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google_auth_oauthlib.flow import Flow

from flask import current_app as app, session, request, redirect, url_for

from zipfile import ZipFile

env_path = Path(".") / ".flaskenv"
load_dotenv(env_path)

# If modifying these scopes, delete the file token.json.
CLIENT_CONIG = {
    "web": {
        "client_id": os.environ.get("GOOGLE_OAUTH_CLIENT_ID"),
        "project_id": os.environ.get("GOOGLE_OAUTH_PROJECT_ID"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET"),
        "redirect_uris": ["http://localhost:25441/"],
        "javascript_origins": ["http://localhost:25441"],
    }
}
SCOPES = ["https://www.googleapis.com/auth/drive.appdata"]
REDIRECT_URI = "http://localhost:25441/settings/backup_to_google_drive/callback"


def trigger_oauth(current_user):
    flow = Flow.from_client_config(client_config=CLIENT_CONIG, scopes=SCOPES)
    flow.redirect_uri = REDIRECT_URI
    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type="offline",
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes="true",
    )
    current_user.set_google_oauth_state(state)
    return {"redirect_url": authorization_url}


def backup(file, current_user):
    if not "creds" in current_user.google_oauth_data:
        return trigger_oauth(current_user)
    try:
        creds = current_user.google_oauth_data["creds"]
        service = build("drive", "v3", credentials=creds)
        file_metadata = {"name": "specter-backup.zip", "parents": ["appDataFolder"]}
        media = MediaIoBaseUpload(file, mimetype="application/zip", resumable=True)
        file = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )
        app.logger.info("Backed up to Google Drive successfully!")
        response = (
            service.files()
            .list(
                spaces="appDataFolder",
                fields="nextPageToken, files(id, name)",
                pageSize=10,
            )
            .execute()
        )
        return {"success": True}
    except Exception as e:
        current_user.clear_google_oauth_data()
        app.logger.warning("Failed to backup to Google Drive. Exception: {}".format(e))
    return {"success": False}


def restore(current_user):
    if not "creds" in current_user.google_oauth_data:
        return trigger_oauth(current_user)
    try:
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
            return {"success": False, message: "No backups found."}
        file = files[0]
        file_id = file.get("id")
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        app.logger.info("Downloaded the latest backup from Google Drive!")
        wallets = []
        devices = []
        zippedFiles = ZipFile(fh)
        for zipinfo in zippedFiles.infolist():
            currFile = zippedFiles.open(zipinfo)
            if "wallets/" in zipinfo.filename:
                wallets.append(json.loads(currFile.read().decode("UTF-8")))
            elif "devices/" in zipinfo.filename:
                devices.append(json.loads(currFile.read().decode("UTF-8")))
        return {"success": True, "wallets": wallets, "devices": devices}
    except Exception as e:
        current_user.clear_google_oauth_data()
        app.logger.warning("Failed to backup to Google Drive. Exception: {}".format(e))
    return {"success": False}


def callback(current_user):
    try:
        state = current_user.google_oauth_data["state"]
        flow = Flow.from_client_config(
            client_config=CLIENT_CONIG, scopes=SCOPES, state=state
        )
        flow.redirect_uri = REDIRECT_URI

        authorization_response = request.url
        flow.fetch_token(authorization_response=authorization_response)

        credentials = flow.credentials
        current_user.set_google_oauth_creds(credentials)
    except Exception as e:
        current_user.clear_google_oauth_data()
        app.logger.warning("Failed to login to Google Drive. Exception: {}".format(e))
    return redirect(url_for("settings_endpoint.general"))
