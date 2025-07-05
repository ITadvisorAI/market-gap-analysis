import re
import requests
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Constants: update SERVICE_ACCOUNT_FILE path
# Adjust SCOPES for read-only ('https://www.googleapis.com/auth/drive.readonly')
# or full drive access ('https://www.googleapis.com/auth/drive') depending on module requirements
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'service_account.json'

# Initialize Drive client with specified permissions
creds = Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=SCOPES
)
drive_service = build('drive', 'v3', credentials=creds)

# Setup HTTP session with retry logic for downloads
session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["GET", "POST"]
)
adapter = HTTPAdapter(max_retries=retries)
session.mount('https://', adapter)
session.mount('http://', adapter)

def download_sheet_as_xlsx(drive_url: str, download_dir: str) -> str:
    """
    Download a Google Sheets file (given its webView URL) as a .xlsx file.
    Uses streaming, retry logic, and timeout to handle large files and transient errors.
    """
    m = re.search(r'/d/([a-zA-Z0-9_-]+)', drive_url)
    if not m:
        raise ValueError(f"Cannot parse file ID from URL: {drive_url}")
    file_id = m.group(1)

    export_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
    resp = session.get(export_url, timeout=30, stream=True)
    resp.raise_for_status()

    Path(download_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(download_dir) / f"{file_id}.xlsx"
    # Stream response to file in chunks
    with open(out_path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return str(out_path)


def list_files_by_id(folder_id: str) -> list:
    """
    List all non-trashed files in the given Drive folder ID.
    Handles pagination to return all files.
    """
    files = []
    page_token = None
    while True:
        resp = drive_service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields='nextPageToken, files(id,name,webViewLink,webContentLink)',
            pageToken=page_token
        ).execute()
        files.extend(resp.get('files', []))
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return files


def upload_to_drive(file_path: str, drive_folder_id: str) -> str:
    """
    Upload a local file to the specified Drive folder.
    Automatically sets MIME type for .docx/.pptx and returns new file ID.
    """
    file_name = Path(file_path).name
    if file_name.endswith('.docx'):
        mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    elif file_name.endswith('.pptx'):
        mime_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    else:
        mime_type = None

    media = MediaFileUpload(file_path, mimetype=mime_type) if mime_type else MediaFileUpload(file_path)
    metadata = {'name': file_name, 'parents': [drive_folder_id]}
    created = drive_service.files().create(
        body=metadata,
        media_body=media,
        fields='id'
    ).execute()
    return created.get('id')
