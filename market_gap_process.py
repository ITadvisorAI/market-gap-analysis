import os
import json
import traceback
import requests
from docx import Document
from pptx import Presentation
from pptx.util import Inches
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# === Google Drive Setup ===
drive_service = None
try:
    creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if creds_json:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(creds_json),
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        drive_service = build("drive", "v3", credentials=creds)
except Exception as e:
    print(f"❌ Failed to initialize Google Drive: {e}")
    traceback.print_exc()

# === Upload utility ===
def upload_to_drive(file_path, session_id):
    try:
        folder_id = None
        query = f"name='{session_id}' and mimeType='application/vnd.google-apps.folder'"
        results = drive_service.files().list(q=query, fields="files(id)").execute()
        folders = results.get("files", [])
        if folders:
            folder_id = folders[0]["id"]
        else:
            folder = drive_service.files().create(body={
                "name": session_id,
                "mimeType": "application/vnd.google-apps.folder"
            }, fields="id").execute()
            folder_id = folder["id"]

        file_meta = {"name": os.path.basename(file_path), "parents": [folder_id]}
        media = MediaFileUpload(file_path, resumable=True)
        uploaded = drive_service.files().create(body=file_meta, media_body=media, fields="id").execute()
        return f"https://drive.google.com/file/d/{uploaded['id']}/view"
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        traceback.print_exc()
        return None

# === Main processing ===
def process_market_gap(session_id, email, files, webhook, folder_path):
    try:
        os.makedirs(folder_path, exist_ok=True)

        downloaded = {}
        for f in files:
            path = os.path.join(folder_path, f["file_name"])
            r = requests.get(f["file_url"], timeout=10)
            with open(path, "wb") as fp:
                fp.write(r.content)
            downloaded[f["file_type"]] = path

        # === DOCX Report ===
        docx_path = os.path.join(folder_path, "market_gap_analysis_report.docx")
        doc = Document()
        doc.add_heading("Market GAP Analysis Report", 0)
        doc.add_paragraph(f"Session ID: {session_id}")
        doc.add_paragraph("\n1. Executive Summary\n<Insert summary>")
        doc.add_paragraph("2. Scope of Analysis\n<Scope>")
        doc.add_paragraph("3. Current Infrastructure Overview\n<Overview>")
        doc.add_paragraph("4. Market Landscape Overview\n<Market options>")
        doc.add_paragraph("5. Comparative Analysis\n<Tables>")
        doc.add_paragraph("6. Recommendations\n<Upgrades>")
        doc.add_paragraph("7. ROI\n<Cost-benefit>")
        doc.add_paragraph("8. Risks\n<Risks>")
        doc.save(docx_path)

        # === PPTX Report ===
        pptx_path = os.path.join(folder_path, "market_gap_analysis_executive_report.pptx")
        ppt = Presentation()
        slide1 = ppt.slides.add_slide(ppt.slide_layouts[0])
        slide1.shapes.title.text = "Market GAP Executive Report"
        slide1.placeholders[1].text = f"Session ID: {session_id}"
        titles = ["Executive Summary", "Scope", "Overview", "Market Trends", "Comparative Gaps", "Recommendations"]
        for t in titles:
            slide = ppt.slides.add_slide(ppt.slide_layouts[1])
            slide.shapes.title.text = t
            slide.placeholders[1].text = f"<{t} content>"
        ppt.save(pptx_path)

        docx_url = upload_to_drive(docx_path, session_id)
        pptx_url = upload_to_drive(pptx_path, session_id)

        payload = {
            "session_id": session_id,
            "gpt_module": "gap_market",
            "file_1_name": "market_gap_analysis_report.docx",
            "file_1_url": docx_url,
            "file_2_name": "market_gap_analysis_executive_report.pptx",
            "file_2_url": pptx_url,
            "status": "complete"
        }
        requests.post(webhook, json=payload)

    except Exception as e:
        print(f"🔥 GAP analysis failed: {e}")
        traceback.print_exc()
