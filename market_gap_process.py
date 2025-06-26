import os
import traceback
import requests
import pandas as pd
from datetime import date

from drive_utils import upload_to_drive
from visualization import generate_visual_charts

# Endpoint for the report engine
REPORTS_URL = os.getenv(
    "MARKET_REPORTS_API_URL",
    "https://market-reports-api.onrender.com"
)


def download_file(drive_url, dest_path):
    """
    Download a file from a Google Drive link or direct URL.
    """
    try:
        resp = requests.get(drive_url, allow_redirects=True, timeout=60)
        resp.raise_for_status()
        with open(dest_path, 'wb') as fp:
            fp.write(resp.content)
    except Exception as e:
        raise RuntimeError(f"Failed to download {drive_url}: {e}")


def extract_insights(local_files):
    """
    Parse GAP Excel files to extract obsolete items, recommendations, and tier counts.
    Returns two dicts: hw_insights, sw_insights.
    """
    hw_insights = {'obsolete': [], 'recommendations': [], 'tier_counts': {}}
    sw_insights = {'obsolete': [], 'recommendations': [], 'tier_counts': {}}

    for f in local_files:
        name = f['file_name'].lower()
        path = f['local_path']
        if not path.lower().endswith('.xlsx'):
            continue
        try:
            df = pd.read_excel(path)
        except Exception:
            continue

        cols = {c.lower(): c for c in df.columns}
        obsolete = []
        if 'lifecycle status' in cols:
            c = cols['lifecycle status']
            obsolete = df[df[c].astype(str).str.lower() == 'obsolete'].iloc[:, 0].astype(str).tolist()

        recommendations = []
        if 'recommendation' in cols:
            c = cols['recommendation']
            recommendations = df[c].dropna().astype(str).tolist()

        tier_counts = {}
        if 'tier' in cols:
            c = cols['tier']
            tier_counts = df[c].value_counts().to_dict()

        insights = {'obsolete': obsolete, 'recommendations': recommendations, 'tier_counts': tier_counts}
        if 'hw' in name:
            hw_insights = insights
        elif 'sw' in name:
            sw_insights = insights

    return hw_insights, sw_insights


def build_narratives(hw_insights, sw_insights):
    """
    Build text narratives for overview, hardware, and software summaries.
    """
    total_hw = sum(hw_insights.get('tier_counts', {}).values())
    total_sw = sum(sw_insights.get('tier_counts', {}).values())

    overview = (
        f"This Market GAP Analysis covers {total_hw} hardware assets and {total_sw} software assets, "
        "highlighting obsolete platforms and modernization paths."
    )

    hw_summary = (
        "Hardware obsolete: " + (', '.join(hw_insights.get('obsolete', [])) or 'None') + ". "
        "Recs: " + (', '.join(hw_insights.get('recommendations', [])) or 'None') + "."
    )

    sw_summary = (
        "Software obsolete: " + (', '.join(sw_insights.get('obsolete', [])) or 'None') + ". "
        "Recs: " + (', '.join(sw_insights.get('recommendations', [])) or 'None') + "."
    )

    return overview, hw_summary, sw_summary


def process_market_gap(session_id, email, files, local_path, folder_id=None):
    """
    Full Market GAP Analysis flow aligned to docx/pptx templates.
    """
    try:
        # 1. Download input files
        local_files = []
        for f in files:
            dest = os.path.join(local_path, f['file_name'])
            download_file(f['drive_url'], dest)
            local_files.append({'file_name': f['file_name'], 'local_path': dest})

        # 2. Extract insights
        hw_insights, sw_insights = extract_insights(local_files)

        # 3. Use recommendations as replacements (stubbed)
        hw_repl = hw_insights.get('recommendations', [])
        sw_repl = sw_insights.get('recommendations', [])
        hw_repl_text = "HW replacements: " + (', '.join(hw_repl) or 'None') + "."
        sw_repl_text = "SW replacements: " + (', '.join(sw_repl) or 'None') + "."

        # 4. Build narratives
        overview, hw_summary, sw_summary = build_narratives(hw_insights, sw_insights)

        # 5. Generate and upload charts
        chart_paths = generate_visual_charts(hw_insights, sw_insights)
        chart_urls = {k: upload_to_drive(p, session_id, folder_id) for k, p in chart_paths.items()}

        # 6. Assemble payload matching latest templates
        payload = {
            'session_id': session_id,
            'date': date.today().isoformat(),
            'organization_name': email,
            'content': {
                'executive_summary': overview + ' ' + hw_summary + ' ' + sw_summary,
                'current_state_overview': overview,
                'hardware_gap_analysis': hw_summary,
                'software_gap_analysis': sw_summary,
                'market_benchmarking': hw_repl_text + ' ' + sw_repl_text,
                'appendices': [lf['file_name'] for lf in local_files]
            },
            'charts': chart_urls
        }

        # 7. Call report engine
        resp = requests.post(f"{REPORTS_URL}/generate_market_reports", json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()
        print(f"✅ Report engine invoked for session {session_id}")

        # 8. Download & upload final reports
        for url in result.get('report_urls', []):
            try:
                r = requests.get(url, timeout=60)
                r.raise_for_status()
                fn = os.path.basename(url)
                dest_f = os.path.join(local_path, fn)
                with open(dest_f, 'wb') as fh:
                    fh.write(r.content)
                upload_to_drive(dest_f, session_id, folder_id)
            except Exception as err:
                print(f"❌ Upload failed for {url}: {err}")

    except Exception as e:
        print(f"🔥 Market GAP processing failed for {session_id}: {e}")
        traceback.print_exc()
