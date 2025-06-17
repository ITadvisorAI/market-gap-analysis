# market_gap_process.py

```python
import os
import traceback
import requests
import pandas as pd

from drive_utils import upload_to_drive, download_file_from_drive
from visualization import generate_visual_charts

# Endpoint for the report engine
REPORTS_URL = os.getenv(
    "MARKET_REPORTS_API_URL",
    "https://market-reports-api.onrender.com"
)


def extract_insights(local_files):
    """
    Parses GAP Excel files to extract:
    - obsolete items
    - recommendations
    - tier distribution counts
    Returns two dicts: (hw_insights, sw_insights).
    """
    hw_insights = {"obsolete": [], "recommendations": [], "tier_counts": {}}
    sw_insights = {"obsolete": [], "recommendations": [], "tier_counts": {}}

    for f in local_files:
        name = f["file_name"].lower()
        path = f["local_path"]
        if not name.endswith(".xlsx"):
            continue
        df = pd.read_excel(path)
        obsolete = (
            df[df.get('Lifecycle Status', '').astype(str).str.lower() == 'obsolete']['Device Type']
            .tolist()
            if 'Lifecycle Status' in df.columns else []
        )
        recs = (
            df['Recommendation'].dropna().astype(str).tolist()
            if 'Recommendation' in df.columns else []
        )
        tiers = (
            df['Tier'].value_counts().to_dict()
            if 'Tier' in df.columns else {}
        )
        insights = {"obsolete": obsolete, "recommendations": recs, "tier_counts": tiers}

        if 'hw' in name:
            hw_insights = insights
        elif 'sw' in name:
            sw_insights = insights

    return hw_insights, sw_insights


def build_narratives(hw_insights, sw_insights):
    """
    Builds narrative sections:
    - overview
    - hardware summary
    - software summary
    """
    total_hw = sum(hw_insights['tier_counts'].values())
    total_sw = sum(sw_insights['tier_counts'].values())

    overview = (
        f"This analysis covers {total_hw} hardware assets"
        f" and {total_sw} software assets."
    )

    hw_summary = (
        "Hardware obsolete platforms: " +
        (', '.join(hw_insights['obsolete']) or 'None') +
        ". Recommendations: " +
        (', '.join(hw_insights['recommendations']) or 'None') +
        "."
    )

    sw_summary = (
        "Software obsolete platforms: " +
        (', '.join(sw_insights['obsolete']) or 'None') +
        ". Recommendations: " +
        (', '.join(sw_insights['recommendations']) or 'None') +
        "."
    )

    return overview, hw_summary, sw_summary


def process_market_gap(session_id, email, files, local_path, folder_id=None):
    """
    Main pipeline for Market GAP Analysis:
      1. Download files from Google Drive
      2. Extract insights from GAP spreadsheets
      3. Build narrative text
      4. Generate charts
      5. Upload charts to Drive
      6. Assemble payload and call report engine
      7. Download and upload final reports
    """
    try:
        # 1. Download files
        local_files = []
        for f in files:
            dest = os.path.join(local_path, f['file_name'])
            download_file_from_drive(f['drive_url'], dest)
            local_files.append({'file_name': f['file_name'], 'local_path': dest})

        # 2. Extract insights
        hw_insights, sw_insights = extract_insights(local_files)

        # 3. Build narratives
        overview, hw_summary, sw_summary = build_narratives(hw_insights, sw_insights)

        # 4. Generate charts
        chart_paths = generate_visual_charts(hw_insights, sw_insights, session_id, local_path)

        # 5. Upload charts
        chart_urls = {}
        for key, path in chart_paths.items():
            url = upload_to_drive(path, session_id, folder_id)
            chart_urls[key] = url

        # 6. Assemble payload
        payload = {
            'session_id': session_id,
            'email': email,
            'folder_id': folder_id,
            'content': {
                'overview': overview,
                'hardware_summary': hw_summary,
                'software_summary': sw_summary
            },
            'charts': chart_urls,
            'input_files': [{'file_name': lf['file_name']} for lf in local_files]
        }

        # 7. Call report engine
        response = requests.post(
            f"{REPORTS_URL}/generate_market_reports",
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        result = response.json()
        print(f"✅ Report engine triggered for session {session_id}")

        # 8. Download and upload generated reports
        for report_url in result.get('report_urls', []):
            try:
                r = requests.get(report_url, timeout=60)
                r.raise_for_status()
                filename = os.path.basename(report_url)
                dest = os.path.join(local_path, filename)
                with open(dest, 'wb') as fp:
                    fp.write(r.content)
                upload_to_drive(dest, session_id, folder_id)
            except Exception as upload_err:
                print(f"❌ Failed to upload report {report_url}: {upload_err}")

    except Exception as err:
        print(f"🔥 Market GAP processing failed for session {session_id}: {err}")
        traceback.print_exc()
```
