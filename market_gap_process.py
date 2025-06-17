import os
import json
import logging
import traceback
import threading
import requests
import pandas as pd
import openai
from flask import Flask, request, jsonify
from docxtpl import DocxTemplate
from drive_utils import upload_to_drive, list_files_in_folder
from visualization import generate_visual_charts

# ---------------------- Configuration ----------------------
# Local sessions directory\ nBASE_DIR = "temp_sessions"
os.makedirs(BASE_DIR, exist_ok=True)

# Market Reports API endpoint (to generate DOCX/PPTX)
REPORT_API_URL = os.getenv("REPORT_API_URL", "http://localhost:10000/generate_market_reports")

# OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Templates directory and DOCX placeholder introspection
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
DOCX_TEMPLATE = os.path.join(TEMPLATES_DIR, "market_gap_analysis_report_template.docx")

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# ---------------------- Helper Functions ----------------------
def download_file(url: str, local_dir: str) -> str:
    """
    Download a file from a URL into local_dir and return its local path.
    """
    filename = os.path.basename(url.split("?")[0])
    dest = os.path.join(local_dir, filename)
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)
    return dest

# ---------------------- Core Processing ----------------------
def ingest_and_analyze(session_id: str, folder_id: str, next_webhook: str, email: str):
    """
    Downloads input files, extracts data, calls OpenAI for narratives,
    generates charts, uploads assets, and triggers report API.
    """
    try:
        logger.info(f"🔍 Starting Market Gap analysis for session {session_id}")
        local_path = os.path.join(BASE_DIR, session_id)
        os.makedirs(local_path, exist_ok=True)

        # 1. Download all files from Drive
        files = list_files_in_folder(folder_id)
        data_frames = {}
        for f in files:
            name = f.get("name")
            url = f.get("webContentLink") or f.get("webViewLink") or f.get("id")
            try:
                local_file = download_file(url, local_path)
                if name.lower().endswith(".xlsx"):
                    df = pd.read_excel(local_file)
                    data_frames[name] = df
                    logger.info(f"📊 Parsed Excel: {name} ({len(df)} rows)")
            except Exception as e:
                logger.warning(f"⚠️ Failed to download/parse {name}: {e}")

        # 2. Summarize data for OpenAI
        summary = {name: df.head(100).to_dict(orient="records") for name, df in data_frames.items()}

        # 3. Extract docx placeholders
        doc = DocxTemplate(DOCX_TEMPLATE)
        placeholders = list(doc.get_undeclared_template_variables())
        logger.info(f"🏷️ Found placeholders in template: {placeholders}")

        # 4. Call OpenAI to generate narratives
        system_prompt = (
            "You are an expert IT analyst. "
            "Generate narrative sections for a market gap analysis report. "
            "Structure the output as a JSON mapping each placeholder key to a paragraph of text."
        )
        user_prompt = (
            f"Data summary (sample records): {json.dumps(summary)}\n"
            f"Placeholders: {placeholders}"
        )
        logger.info("🤖 Calling OpenAI for narrative generation...")
        completion = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=1500
        )
        content = json.loads(completion.choices[0].message.content)
        logger.info("✅ Received narratives from OpenAI")

        # 5. Generate charts using visualization module
        charts_local = generate_visual_charts(data_frames, local_path)
        charts = {}
        for key, img_path in charts_local.items():
            try:
                url = upload_to_drive(img_path, session_id, folder_id)
                charts[key] = url
                logger.info(f"📈 Uploaded chart {key} -> {url}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to upload chart {key}: {e}")

        # 6. Build payload and trigger report generation
        report_payload = {
            "session_id": session_id,
            "folder_id": folder_id,
            "email": email,
            "content": content,
            "charts": charts,
            "next_action_webhook": next_webhook
        }
        logger.info(f"🚀 Sending payload to Market Reports API at {REPORT_API_URL}")
        resp = requests.post(REPORT_API_URL, json=report_payload, timeout=60)
        resp.raise_for_status()
        logger.info("✅ Report API triggered successfully")

    except Exception as e:
        logger.error(f"🔥 Market Gap analysis failed: {e}")
        traceback.print_exc()

# ---------------------- Flask Routes ----------------------
@app.route("/start_market_gap", methods=["POST"])
def start_market_gap():
    data = request.get_json(force=True)
    logger.info(f"📦 Incoming payload to /start_market_gap: {data}")
    session_id = data.get("session_id")
    folder_id = data.get("folder_id")
    next_webhook = data.get("next_action_webhook")
    email = data.get("email", "")

    missing = [k for k in ("session_id", "folder_id") if not data.get(k)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    # Run processing asynchronously
    threading.Thread(
        target=ingest_and_analyze,
        args=(session_id, folder_id, next_webhook, email),
        daemon=True
    ).start()
    return jsonify({"message": "Market Gap analysis started"}), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    logger.info(f"🚦 Starting Market Gap Analysis service on port {port}")
    app.run(host="0.0.0.0", port=port)
