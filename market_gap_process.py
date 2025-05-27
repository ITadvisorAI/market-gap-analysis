import os
import json
import traceback
import requests
import matplotlib.pyplot as plt
from docx import Document
from pptx import Presentation
from pptx.util import Inches
from openpyxl import load_workbook
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

def process_market_gap(session_id, email, files, folder_path):
    try:
        os.makedirs(folder_path, exist_ok=True)
        downloaded_files = []

        for f in files:
            path = os.path.join(folder_path, f["file_name"])
            r = requests.get(f["file_url"], timeout=10)
            with open(path, "wb") as fp:
                fp.write(r.content)
            f["local_path"] = path
            downloaded_files.append(f)

        # === Parse Excel files (HW + SW) ===
        hw_insights, sw_insights = {}, {}
        for f in downloaded_files:
            if f["file_type"] in ["hardware_gap", "software_gap"]:
                wb = load_workbook(f["local_path"])
                sheet = wb.active
                obsolete = []
                recommendations = []
                tier_counts = {}
                for row in sheet.iter_rows(min_row=2, values_only=True):
                    name, model, platform, tier, status, recommendation = row[:6]
                    if status and str(status).lower() == "obsolete":
                        obsolete.append(platform)
                    if recommendation:
                        recommendations.append(f"{platform}: {recommendation}")
                    if tier:
                        tier_counts[tier] = tier_counts.get(tier, 0) + 1
                parsed = {
                    "obsolete": list(set(obsolete)),
                    "recommendations": list(set(recommendations)),
                    "tier_counts": tier_counts
                }
                if f["file_type"] == "hardware_gap":
                    hw_insights = parsed
                elif f["file_type"] == "software_gap":
                    sw_insights = parsed

        # === Create DOCX Report ===
        docx_path = os.path.join(folder_path, "market_gap_analysis_report.docx")
        doc = Document()
        doc.add_heading("Market GAP Analysis Report", 0)
        doc.add_paragraph(f"Session ID: {session_id}")
        doc.add_paragraph("\n1. Executive Summary\nThis report summarizes market-based modernization insights.")
        doc.add_paragraph("\n2. Hardware Obsolete Platforms:\n" + ", ".join(hw_insights.get("obsolete", [])) or "None")
        doc.add_paragraph("3. Hardware Recommendations:\n" + "\n".join(hw_insights.get("recommendations", [])) or "None")
        doc.add_paragraph("4. Hardware Tier Distribution:\n" + json.dumps(hw_insights.get("tier_counts", {})))

        doc.add_paragraph("\n5. Software Obsolete Platforms:\n" + ", ".join(sw_insights.get("obsolete", [])) or "None")
        doc.add_paragraph("6. Software Recommendations:\n" + "\n".join(sw_insights.get("recommendations", [])) or "None")
        doc.add_paragraph("7. Software Tier Distribution:\n" + json.dumps(sw_insights.get("tier_counts", {})))
        doc.save(docx_path)

        # === Create PPTX Report ===
        pptx_path = os.path.join(folder_path, "market_gap_analysis_executive_report.pptx")
        ppt = Presentation()
        slide = ppt.slides.add_slide(ppt.slide_layouts[0])
        slide.shapes.title.text = "Market GAP Executive Report"
        slide.placeholders[1].text = f"Session ID: {session_id}"

        def add_bullet_slide(title, items):
            s = ppt.slides.add_slide(ppt.slide_layouts[1])
            s.shapes.title.text = title
            body = s.placeholders[1]
            body.text = ""
            for item in items:
                p = body.text_frame.add_paragraph()
                p.text = item

        add_bullet_slide("Obsolete Hardware", hw_insights.get("obsolete", []))
        add_bullet_slide("Hardware Recommendations", hw_insights.get("recommendations", []))
        add_bullet_slide("Hardware Tier Summary", [f"{k}: {v}" for k, v in hw_insights.get("tier_counts", {}).items()])

        add_bullet_slide("Obsolete Software", sw_insights.get("obsolete", []))
        add_bullet_slide("Software Recommendations", sw_insights.get("recommendations", []))
        add_bullet_slide("Software Tier Summary", [f"{k}: {v}" for k, v in sw_insights.get("tier_counts", {}).items()])

        ppt.save(pptx_path)

        # Upload outputs
        docx_url = upload_to_drive(docx_path, session_id)
        pptx_url = upload_to_drive(pptx_path, session_id)

        for f in downloaded_files:
            f["file_url"] = upload_to_drive(f["local_path"], session_id)

        downloaded_files.extend([
            {
                "file_name": os.path.basename(docx_path),
                "file_url": docx_url,
                "file_type": "docx_market_report"
            },
            {
                "file_name": os.path.basename(pptx_path),
                "file_url": pptx_url,
                "file_type": "pptx_market_summary"
            }
        ])

        # Send to next GPT
        IT_STRATEGY_API = "https://it-strategy-api.onrender.com/start_it_strategy"
        payload = {
            "session_id": session_id,
            "email": email,
            "gpt_module": "gap_market",
            "files": downloaded_files,
            "status": "complete"
        }
        requests.post(IT_STRATEGY_API, json=payload)

    except Exception as e:
        print(f"🔥 GAP analysis failed: {e}")
        traceback.print_exc()
