from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
import os

# Path to your service account JSON key (Render: mount under /etc/secrets)
SERVICE_ACCOUNT_FILE = "/etc/secrets/service_account.json"

# Authenticate and construct Drive client
drive_creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=["https://www.googleapis.com/auth/drive"]
)
drive_service = build('drive', 'v3', credentials=drive_creds)


def upload_to_drive(file_path: str, file_name: str, session_folder_name: str) -> str:
    """
    Uploads a file to a Drive folder named exactly session_folder_name,
    makes it publicly readable, and returns its webViewLink.

    Args:
      file_path: Local path to the file to upload.
      file_name: Desired name in Drive (e.g. 'report.docx').
      session_folder_name: Name of the Drive folder (session-specific).

    Returns:
      URL (webViewLink) of the uploaded file.
    """
    # 1. Find the session folder by name
    query = (
        f"name='{session_folder_name}'"
        " and mimeType='application/vnd.google-apps.folder'"
        " and trashed=false"
    )
    resp = drive_service.files().list(q=query, fields="files(id)").execute()
    files = resp.get('files', [])
    if not files:
        raise FileNotFoundError(f"Drive folder '{session_folder_name}' not found")
    folder_id = files[0]['id']

    # 2. Determine MIME type based on extension
    ext = os.path.splitext(file_name)[1].lower()
    mime = {
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    }.get(ext, 'application/octet-stream')

    # 3. Upload the file
    media = MediaFileUpload(file_path, mimetype=mime)
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    uploaded = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    # 4. Make the file publicly readable
    drive_service.permissions().create(
        fileId=uploaded['id'],
        body={'type': 'anyone', 'role': 'reader'},
        fields='id'
    ).execute()

    return uploaded.get('webViewLink')
