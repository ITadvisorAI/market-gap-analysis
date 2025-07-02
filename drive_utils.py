from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
import os
import requests

# Path to your service account JSON key
SERVICE_ACCOUNT_FILE = "/etc/secrets/service_account.json"

# Authenticate and construct Drive client
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=["https://www.googleapis.com/auth/drive"]
)
drive_service = build('drive', 'v3', credentials=creds)

def upload_to_drive(file_path: str, drive_folder_id: str) -> str:
    """
    Uploads a local file into the Google Drive folder with the given ID,
    makes it publicly readable, and returns its webViewLink.
    """
    file_name = os.path.basename(file_path)
    media = MediaFileUpload(file_path)
    metadata = {
        "name": file_name,
        "parents": [drive_folder_id]
    }
    uploaded = drive_service.files().create(
        body=metadata,
        media_body=media,
        fields="id, webViewLink"
    ).execute()
    # Grant read access to anyone
    drive_service.permissions().create(
        fileId=uploaded["id"],
        body={"type": "anyone", "role": "reader"},
        fields="id"
    ).execute()
    return uploaded["webViewLink"]

def list_files_in_folder(session_folder_name: str) -> list[dict]:
    """
    Lists files in the Google Drive folder named session_folder_name.
    Returns a list of dicts with id, name, webViewLink, webContentLink.
    """
    # Find the session folder
    folder_query = (
        f"name='{session_folder_name}' and "
        "mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    response = drive_service.files().list(
        q=folder_query,
        fields="files(id)"
    ).execute()
    folders = response.get("files", [])
    if not folders:
        raise FileNotFoundError(f"Drive folder '{session_folder_name}' not found")
    folder_id = folders[0]["id"]

    # List files in folder
    file_query = f"'{folder_id}' in parents and trashed=false"
    response = drive_service.files().list(
        q=file_query,
        fields="files(id, name, webViewLink, webContentLink)"
    ).execute()
    return response.get("files", [])
    
def download_file(url: str, dest_path: str):
    """
    Download a file from a public URL and save it locally.
    """
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
