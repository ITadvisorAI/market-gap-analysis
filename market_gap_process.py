import os
import json
import pandas as pd
import requests
import openai
import traceback
from datetime import date
from visualization import generate_visual_charts
from drive_utils import download_sheet_as_xlsx, upload_to_drive

# Configuration
REPORTS_URL = os.getenv(
    "MARKET_REPORTS_API_URL",
    "https://market-reports-api.onrender.com"
)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Insight extraction

def extract_insights(local_files):
    hw_insights = {"obsolete": [], "recommendations": [], "tier_counts": {}}
    sw_insights = {"obsolete": [], "recommendations": [], "tier_counts": {}}

    for f in local_files:
        name = f['file_name'].lower()
        path = f['local_path']
        if not path.lower().endswith('.xlsx'):
            continue
        try:
            df = pd.read_excel(path, engine='openpyxl')
        except Exception:
            continue

        cols = {c.lower(): c for c in df.columns}
        obsolete = []
        if 'lifecycle status' in cols:
            obsolete = df[
                df[cols['lifecycle status']].astype(str).str.lower() == 'obsolete'
            ].iloc[:, 0].astype(str).tolist()
        recommendations = []
        if 'recommendation' in cols:
            recommendations = (
                df[cols['recommendation']]
                .dropna()
                .astype(str)
                .tolist()
            )
        tier_counts = {}
        if 'tier' in cols:
            tier_counts = df[cols['tier']].value_counts().to_dict()

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

# Section builders

def build_executive_summary(hw_df, sw_df):
    return {"text": f"Analyzed {len(hw_df)} hardware items and {len(sw_df)} software items."}


def build_section_2_current_state_overview(hw_df, sw_df):
    total_devices = len(hw_df)
    total_applications = len(sw_df)
    scores = pd.to_numeric(
        hw_df.get("Tier Total Score", pd.Series()),
        errors="coerce"
    )
    healthy_devices = int((scores >= 75).sum())
    compliant_licenses = int(
        (sw_df.get("License Status", pd.Series()) != "Expired").sum()
    )
    return {
        "total_devices": total_devices,
        "total_applications": total_applications,
        "healthy_devices": healthy_devices,
        "compliant_licenses": compliant_licenses
    }


def build_section_3_hardware_gap_analysis(hw_df):
    return {"hardware_items": hw_df.to_dict(orient="records")}


def build_section_4_software_gap_analysis(sw_df):
    counts = sw_df.get("Category", pd.Series()).value_counts().to_dict()
    return {"software_gap_analysis": counts}


def build_section_5_market_benchmarking(hw_df, sw_df):
    dist = hw_df.get("Category", pd.Series()).value_counts().to_dict()
    return {"market_benchmarking": dist}

# AI narrative generator

def ai_narrative(section_name: str, summary: dict) -> str:
    print(f"[DEBUG] ai_narrative for {section_name}", flush=True)
    raw = json.dumps(summary)
    if len(raw) > 10000:
        raw = raw[:10000] + '... (truncated)'
    user_content = f"Section: {section_name}\nData: {raw}"

    messages = [
        {"role": "system", "content": (
            "You are an expert IT transformation analyst. "
            "Using the data provided, write a concise, insightful narrative for the given section."
        )},
        {"role": "user", "content": user_content}
    ]

    try:
        resp = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=500
        )
    except openai.RateLimitError:
        resp = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.3,
            max_tokens=300
        )
    return resp.choices[0].message.content.strip()

# Main processing function

def process_market_gap(session_id, email, files, local_path, folder_id=None):
    """
    Full Market GAP Analysis: downloads files, extracts insights, generates charts,
    uses OpenAI to create narratives for each section, then calls report generator.
    """
    try:
        os.makedirs(local_path, exist_ok=True)
        local_files = []
        hw_df = pd.DataFrame()
        sw_df = pd.DataFrame()

        # 1. Download input files and build DataFrames
        for f in files:
            dest = download_sheet_as_xlsx(f['drive_url'], local_path)
            local_files.append({'file_name': f['file_name'], 'local_path': dest})
            name_lower = f['file_name'].lower()
            if 'hw' in name_lower:
                hw_df = pd.read_excel(dest, engine='openpyxl')
            elif 'sw' in name_lower:
                sw_df = pd.read_excel(dest, engine='openpyxl')

        # 2. Extract insights
        hw_insights, sw_insights = extract_insights(local_files)

        # 3. Generate and upload charts
        data_frames = {
            'hardware_insights': pd.DataFrame(
                list(hw_insights['tier_counts'].items()),
                columns=['Tier', 'Count']
            ),
            'software_insights': pd.DataFrame(
                list(sw_insights['tier_counts'].items()),
                columns=['Tier', 'Count']
            )
        }
        chart_dir = os.path.join(local_path, 'market_gap_charts')
        os.makedirs(chart_dir, exist_ok=True)
        chart_paths = generate_visual_charts(data_frames, chart_dir)
        chart_ids = {k: upload_to_drive(path, folder_id) for k, path in chart_paths.items()}

        chart_urls = {k: f"https://drive.google.com/file/d/{fid}/view?usp=drivesdk" for k, fid in chart_ids.items()}

        # 4. Build section summaries
        summaries = {
            'executive_summary': build_executive_summary(hw_df, sw_df),
            'current_state_overview': build_section_2_current_state_overview(hw_df, sw_df),
            'hardware_gap_analysis': build_section_3_hardware_gap_analysis(hw_df),
            'software_gap_analysis': build_section_4_software_gap_analysis(sw_df),
            'market_benchmarking': build_section_5_market_benchmarking(hw_df, sw_df)
        }

        # 5. Generate narratives via OpenAI\        sections = {k: ai_narrative(k, summaries[k]) for k in summaries}

        # 6. Assemble payload
        payload = {
            'session_id': session_id,
            'date': date.today().isoformat(),
            'organization_name': email,
            'content': sections,
            'charts': chart_urls,
            'appendices': [lf['file_name'] for lf in local_files]
        }
        print(f"[DEBUG] Calling report generator with payload keys: {list(payload.keys())}", flush=True)

        # 7. Call report generator service
        resp = requests.post(
            f"{REPORTS_URL}/generate_market_reports",
            json=payload,
            timeout=120
        )
        resp.raise_for_status()
        result = resp.json()

        # 8. Download & upload final reports
        for url in result.get('report_urls', []):
            try:
                r = requests.get(url, timeout=60)
                r.raise_for_status()
                fn = os.path.basename(url)
                dest = os.path.join(local_path, fn)
                with open(dest, 'wb') as fh:
                    fh.write(r.content)
                upload_to_drive(dest, folder_id)
            except Exception as err:
                print(f"❌ Failed to download/upload {url}: {err}")

        return result

    except Exception as e:
        print(f"🔥 process_market_gap failed for {session_id}: {e}")
        traceback.print_exc()
        return {'error': str(e)}
