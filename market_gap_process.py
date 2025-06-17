import os
import traceback
import requests
import pandas as pd

from drive_utils import download_file_from_drive, upload_to_drive
from visualization import generate_visual_charts

# Endpoint for the report engine
REPORTS_URL = os.getenv(
    "MARKET_REPORTS_API_URL",
    "https://market-reports-api.onrender.com"
)

def extract_insights(local_files):
    """
    Analyze GAP spreadsheets to extract core insights:
      - Lists of obsolete items
      - Recommendations from GPT2
      - Distribution of assets by tier
    Returns:
      hw_insights (dict), sw_insights (dict)
    """
    hw_insights = {"obsolete": [], "recommendations": [], "tier_counts": {}}
    sw_insights = {"obsolete": [], "recommendations": [], "tier_counts": {}}

    for file in local_files:
        name = file['file_name'].lower()
        path = file['local_path']
        if not path.lower().endswith('.xlsx'):
            continue
        try:
            df = pd.read_excel(path)
        except Exception:
            continue  # skip invalid or unreadable files

        # Extract obsolete platforms
        obsolete = []
        columns_lower = {c.lower(): c for c in df.columns}
        if 'lifecycle status' in columns_lower:
            col = columns_lower['lifecycle status']
            obsolete = (
                df[df[col].astype(str).str.lower() == 'obsolete']
                .iloc[:, 0].astype(str).tolist()
            )

        # Extract recommendations
        recommendations = []
        if 'recommendation' in columns_lower:
            rec_col = columns_lower['recommendation']
            recommendations = df[rec_col].dropna().astype(str).tolist()

        # Count tiers
        tier_counts = {}
        if 'tier' in columns_lower:
            tier_col = columns_lower['tier']
            tier_counts = df[tier_col].value_counts().to_dict()

        insights = {
            'obsolete': obsolete,
            'recommendations': recommendations,
            'tier_counts': tier_counts
        }

        if 'hw' in name:
            hw_insights = insights
        elif 'sw' in name:
            sw_insights = insights

    return hw_insights, sw_insights

def build_narratives(hw_insights, sw_insights):
    """
    Construct narrative text sections based on insights:
      - overview
      - hardware_summary
      - software_summary
    """
    total_hw = sum(hw_insights.get('tier_counts', {}).values())
    total_sw = sum(sw_insights.get('tier_counts', {}).values())

    overview = (
        f"This analysis reviews {total_hw} hardware assets and {total_sw} software assets, "
        "highlighting obsolete platforms and modernization recommendations."
    )

    hw_summary = (
        "Hardware obsolete platforms: " +
        (', '.join(hw_insights.get('obsolete', [])) or 'None') +
        ". Recommendations: " +
        (', '.join(hw_insights.get('recommendations', [])) or 'None') +
        "."
    )

    sw_summary = (
        "Software obsolete platforms: " +
        (', '.join(sw_insights.get('obsolete', [])) or 'None') +
        ". Recommendations: " +
        (', '.join(sw_insights.get('recommendations', [])) or 'None') +
        "."
    )

    return overview, hw_summary, sw_summary

def process_market_gap(session_id, email, files, local_path, folder_id=None):
    """
    Executes the full Market GAP Analysis flow:
      1. Download files from Drive
      2. Extract insights via Excel parsing
      3. Build narrative sections
      4. Generate visual charts
      5. Upload charts to Drive
      6. Assemble and send payload to report engine
      7. Download and upload final DOCX/PPTX
    """
    try:
        # 1. Download input files
        local_files = []
        for f in files:
            dest_path = os.path.join(local_path, f['file_name'])
            download_file_from_drive(f['drive_url'], dest_path)
            local_files.append({'file_name': f['file_name'], 'local_path': dest_path})

        # 2. Insight extraction
        hw_insights, sw_insights = extract_insights(local_files)

        # 3. Narrative construction
        overview, hw_summary, sw_summary = build_narratives(hw_insights, sw_insights)

        # 4. Chart generation
        chart_paths = generate_visual_charts(
            hw_insights, sw_insights, session_id, local_path
        )

        # 5. Upload charts
        chart_urls = {}
        for label, path in chart_paths.items():
            url = upload_to_drive(path, session_id, folder_id)
            chart_urls[label] = url

        # 6. Payload assembly
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

        # 7. Send to report engine
        resp = requests.post(
            f"{REPORTS_URL}/generate_market_reports",
            json=payload,
            timeout=120
        )
        resp.raise_for_status()
        result = resp.json()
        print(f"✅ Report engine invoked for session {session_id}")

        # 8. Handle generated reports
        for url in result.get('report_urls', []):
            try:
                r = requests.get(url, timeout=60)
                r.raise_for_status()
                filename = os.path.basename(url)
                file_dest = os.path.join(local_path, filename)
                with open(file_dest, 'wb') as file_obj:
                    file_obj.write(r.content)
                upload_to_drive(file_dest, session_id, folder_id)
            except Exception as e:
                print(f"❌ Error uploading report {url}: {e}")

    except Exception as e:
        print(f"🔥 Market GAP processing failed for {session_id}: {e}")
        traceback.print_exc()
