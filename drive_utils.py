from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
import os

# Path to your service account JSON key
SERVICE_ACCOUNT_FILE = "/etc/secrets/service_account.json"

# Authenticate and construct Drive client
drive_creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=["https://www.googleapis.com/auth/drive"]
)
drive_service = build('drive', 'v3', credentials=drive_creds)

def upload_to_drive(file_path: str, file_name: str, session_folder_name: str) -> str:
    """
    Uploads a file to a Google Drive folder named session_folder_name,
    makes it publicly readable, and returns its webViewLink.
    """
    # Locate the session folder by exact name
    query = (
        f"name='{session_folder_name}' and "
        "mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    resp = drive_service.files().list(q=query, fields='files(id)').execute()
    folders = resp.get('files', [])
    if not folders:
        raise FileNotFoundError(f"Drive folder '{session_folder_name}' not found")
    folder_id = folders[0]['id']

    # Determine MIME type from file extension
    ext = os.path.splitext(file_name)[1].lower()
    mime = {
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    }.get(ext, 'application/octet-stream')

    # Upload the file\ n    media = MediaFileUpload(file_path, mimetype=mime)
    metadata = {'name': file_name, 'parents': [folder_id]}
    uploaded = drive_service.files().create(
        body=metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    # Make the file publicly readable\ n    drive_service.permissions().create(
        fileId=uploaded['id'],
        body={'type': 'anyone', 'role': 'reader'},
        fields='id'
    ).execute()

    return uploaded.get('webViewLink')

def list_files_in_folder(session_folder_name: str) -> list[dict]:
    """
    Lists files in the Google Drive folder named session_folder_name.
    Returns a list of dicts with id, name, webViewLink, webContentLink.
    """
    # Find the folder by name
    q_folder = (
        f"name='{session_folder_name}' and "
        "mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    resp = drive_service.files().list(q=q_folder, fields='files(id)').execute()
    folders = resp.get('files', [])
    if not folders:
        raise FileNotFoundError(f"Drive folder '{session_folder_name}' not found")
    folder_id = folders[0]['id']

    # List contents of the folder
    query = f"'{folder_id}' in parents and trashed=false"
    resp_files = drive_service.files().list(
        q=query,
        fields='files(id, name, webViewLink, webContentLink)'
    ).execute()
    return resp_files.get('files', [])
