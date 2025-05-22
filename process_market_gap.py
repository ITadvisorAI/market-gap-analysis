
import os
import traceback
import requests
from docx import Document
from pptx import Presentation
from pptx.util import Inches
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# === Google Drive Setup ===
try:
    SERVICE_ACCOUNT_FILE = "/etc/secrets/service_account.json"
    SCOPES = ["https://www.googleapis.com/auth/drive"]
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    drive_service = build("drive", "v3", credentials=creds)
    print("✅ Google Drive client initialized.")
except Exception as e:
    drive_service = None
    print(f"❌ Failed to initialize Google Drive: {e}")

def download_file(url, dest_path):
    try:
        print(f"⬇️ Downloading: {url}")
        response = requests.get(url)
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            f.write(response.content)
        print(f"✅ Downloaded: {dest_path}")
    except Exception as e:
        print(f"❌ Failed to download file: {e}")
        traceback.print_exc()

def get_or_create_drive_folder(folder_name):
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder'"
    response = drive_service.files().list(q=query, spaces='drive', fields='files(id)').execute()
    if response['files']:
        return response['files'][0]['id']
    file_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
    folder = drive_service.files().create(body=file_metadata, fields='id').execute()
    return folder['id']

def upload_to_drive(local_path, session_id):
    if not drive_service:
        print("❌ Google Drive not configured.")
        return None
    folder_id = get_or_create_drive_folder(session_id)
    file_metadata = {'name': os.path.basename(local_path), 'parents': [folder_id]}
    media = MediaFileUpload(local_path, resumable=True)
    uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = uploaded.get("id")
    return f"https://drive.google.com/file/d/{file_id}/view"

def fill_word_template(path, session_id):
    doc = Document()
    doc.add_heading("Market GAP Analysis Report", level=1)
    doc.add_paragraph(f"Session ID: {session_id}")
    doc.add_paragraph("Summary: Modernization opportunities identified for infrastructure.")
    doc.add_paragraph("Recommendations: Replace obsolete hardware with cloud-native alternatives.")
    doc.save(path)
    print(f"📝 Word report saved: {path}")

def fill_ppt_template(path, session_id):
    ppt = Presentation()
    slide = ppt.slides.add_slide(ppt.slide_layouts[0])
    title, subtitle = slide.shapes.title, slide.placeholders[1]
    title.text = "Market GAP Summary"
    subtitle.text = f"Session ID: {session_id}"

    slide2 = ppt.slides.add_slide(ppt.slide_layouts[1])
    slide2.shapes.title.text = "Recommendations"
    slide2.placeholders[1].text = "- Migrate Tier 1 workloads to cloud\n- Refresh unsupported hardware\n- Optimize licensing"

    ppt.save(path)
    print(f"📊 PowerPoint report saved: {path}")

def run_market_gap_analysis(session_id, email, files, session_folder):
    try:
        print(f"🚀 Running Market GAP analysis for session: {session_id}")
        os.makedirs(session_folder, exist_ok=True)

        for f in files:
            dest_path = os.path.join(session_folder, f["file_name"])
            download_file(f["file_url"], dest_path)

        docx_path = os.path.join(session_folder, "GAP_Market_Report.docx")
        pptx_path = os.path.join(session_folder, "GAP_Market_Summary.pptx")

        fill_word_template(docx_path, session_id)
        fill_ppt_template(pptx_path, session_id)

        # Upload to Drive
        docx_url = upload_to_drive(docx_path, session_id)
        pptx_url = upload_to_drive(pptx_path, session_id)

        print(f"📤 Uploaded Word: {docx_url}")
        print(f"📤 Uploaded PPT: {pptx_url}")
    except Exception as e:
        print(f"💥 Market GAP analysis failed: {e}")
        traceback.print_exc()
