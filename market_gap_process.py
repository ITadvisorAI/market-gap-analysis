import os
import json
import traceback
import requests
import matplotlib.pyplot as plt
import pandas as pd
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


def upload_to_drive(file_path, session_id, folder_id=None):
    """
    Uploads a file (including charts) to an existing Drive folder; creates folder if needed.
    """
    try:
        if folder_id:
            target_folder = folder_id
        else:
            # find or create folder by session_id name
            q = f"name='{session_id}' and mimeType='application/vnd.google-apps.folder'"
            res = drive_service.files().list(q=q, fields="files(id)").execute()
            files = res.get("files", [])
            if files:
                target_folder = files[0]["id"]
            else:
                fld = drive_service.files().create(body={
                    "name": session_id,
                    "mimeType": "application/vnd.google-apps.folder"
                }, fields="id").execute()
                target_folder = fld["id"]

        file_meta = {"name": os.path.basename(file_path), "parents": [target_folder]}
        media = MediaFileUpload(file_path, resumable=True)
        uploaded = drive_service.files().create(body=file_meta, media_body=media, fields="id").execute()
        return f"https://drive.google.com/file/d/{uploaded['id']}/view"
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        traceback.print_exc()
        return None


def download_files(files, local_path):
    """
    Downloads each file URL into local_path and returns list of local file info.
    """
    os.makedirs(local_path, exist_ok=True)
    downloaded = []
    for f in files:
        url = f.get("file_url")
        name = f.get("file_name")
        if not url or not name:
            continue
        dest = os.path.join(local_path, name)
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            with open(dest, "wb") as fp:
                fp.write(r.content)
            downloaded.append({"file_name": name, "local_path": dest})
        except Exception as e:
            print(f"❌ Download failed for {name}: {e}")
    return downloaded


def extract_insights(downloaded_files):
    """
    Parses GAP Excel files to extract insights: obsolete, recommendations, tier_counts.
    """
    hw, sw = {"obsolete": [], "recommendations": [], "tier_counts": {}}, {"obsolete": [], "recommendations": [], "tier_counts": {}}
    for f in downloaded_files:
        name = f["file_name"].lower()
        path = f["local_path"]
        if not name.endswith(".xlsx"): continue
        df = pd.read_excel(path)
        obsolete = df[df['Lifecycle Status'].str.lower()=='obsolete']['Device Type'].tolist() if 'Lifecycle Status' in df else []
        recs = df['Recommendation'].dropna().astype(str).tolist() if 'Recommendation' in df else []
        tiers = df['Tier'].value_counts().to_dict() if 'Tier' in df else {}
        insights = {"obsolete": obsolete, "recommendations": recs, "tier_counts": tiers}
        if 'hw' in name:
            hw = insights
        elif 'sw' in name:
            sw = insights
    return hw, sw


def build_narratives(hw_insights, sw_insights):
    """
    Constructs narrative sections based on insights.
    """
    overview = (
        f"This analysis covers {sum(hw_insights['tier_counts'].values())} hardware assets"
        f" and {sum(sw_insights['tier_counts'].values())} software assets."
    )
    hw_summary = (
        f"Hardware obsolete platforms: {', '.join(hw_insights['obsolete']) or 'None'}."
        f" Recommendations: {'; '.join(hw_insights['recommendations']) or 'None'}."
    )
    sw_summary = (
        f"Software obsolete platforms: {', '.join(sw_insights['obsolete']) or 'None'}."
        f" Recommendations: {'; '.join(sw_insights['recommendations']) or 'None'}."
    )
    return overview, hw_summary, sw_summary


def generate_charts(hw_insights, sw_insights, session_id, local_path):
    """
    Creates bar charts for tier distributions and returns local paths.
    """
    charts = {}
    for label, insights in [('hardware', hw_insights), ('software', sw_insights)]:
        data = insights.get('tier_counts', {})
        if not data: continue
        plt.figure()
        plt.bar(list(data.keys()), list(data.values()))
        plt.title(f"{label.title()} Tier Distribution")
        plt.tight_layout()
        filename = os.path.join(local_path, f"{session_id}_{label}_tier_dist.png")
        plt.savefig(filename)
        plt.close()
        charts[label + '_tier_chart'] = filename
    return charts


def process_market_gap(session_id, email, files, local_path, folder_id=None):
    """
    Main entry: download files, extract insights, build narratives and charts,
    and send payload to Market Reports API.
    """
    try:
        # 1. Download
        downloaded = download_files(files, local_path)

        # 2. Extract insights
        hw_insights, sw_insights = extract_insights(downloaded)

        # 3. Narratives
        overview, hw_summary, sw_summary = build_narratives(hw_insights, sw_insights)

        # 4. Charts
        chart_paths = generate_charts(hw_insights, sw_insights, session_id, local_path)
        chart_urls = {
            key: upload_to_drive(path, session_id, folder_id)
            for key, path in chart_paths.items()
        }

        # 5. Assemble payload
        payload = {
            "session_id": session_id,
            "email": email,
            "folder_id": folder_id,
            "content": {
                "overview": overview,
                "hardware_summary": hw_summary,
                "software_summary": sw_summary
            },
            "charts": chart_urls,
            "input_files": [{"file_name": f["file_name"]} for f in downloaded]
        }

        # 6. Call Reports API
        REPORTS_URL = os.getenv("MARKET_REPORTS_API_URL", "https://market-reports-api.onrender.com")
        resp = requests.post(f"{REPORTS_URL}/generate_market_reports", json=payload, timeout=120)
        resp.raise_for_status()
        print(f"✅ Market reports triggered for {session_id}")

    except Exception as e:
        print(f"🔥 Market GAP processing failed: {e}")
        traceback.print_exc()
