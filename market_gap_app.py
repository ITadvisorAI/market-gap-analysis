import os
import json
import logging
import threading
import requests
from flask import Flask, request, jsonify
from market_gap_process import generate_market_reports
from drive_utils import upload_to_drive, list_files_in_folder

app = Flask(__name__)

@app.route("/healthz", methods=["GET"])
def health_check():
    """Simple keep-alive endpoint."""
    return "OK", 200



logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_DIR = "temp_sessions"
os.makedirs(BASE_DIR, exist_ok=True)

@app.route("/", methods=["GET"])
def health():
    return "✅ Market Gap Analysis API is live", 200

@app.route("/start_market_gap", methods=["POST"])
def start_market_gap():
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id")
        email = data.get("email", "")
        folder_id = data.get("folder_id")
        next_webhook = data.get("next_action_webhook")

        logging.info("📦 Incoming payload for market gap analysis:\n%s", json.dumps(data, indent=2))

        # Initial ingestion trigger if no content/charts
        if not data.get("content") and not data.get("charts"):
            files = list_files_in_folder(folder_id)
            file_entries = []
            for f in files:
                file_entries.append({
                    "file_name": f.get("name"),
                    "file_url": f.get("webViewLink") or f.get("webContentLink") or f.get("id")
                })
            payload = {
                "session_id": session_id,
                "folder_id": folder_id,
                "files": file_entries,
                "next_action_webhook": next_webhook
            }
            try:
                resp = requests.post(next_webhook, json=payload)
                resp.raise_for_status()
                logging.info("➡️ Triggered ingestion, status %s", resp.status_code)
            except Exception:
                logging.exception("🔥 Error triggering ingestion")
            return jsonify({"message": "Ingestion triggered"}), 200

        # Report generation from GPT3 output
        missing = []
        if not session_id:
            missing.append("session_id")
        if not data.get("content"):
            missing.append("content")
        if not data.get("charts"):
            missing.append("charts")
        if missing:
            return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

        folder_name = session_id if session_id.startswith("Temp_") else f"Temp_{session_id}"
        local_path = os.path.join(BASE_DIR, folder_name)
        os.makedirs(local_path, exist_ok=True)

        def runner():
            try:
                generate_market_reports(session_id, email, folder_id, data, local_path)
            except Exception:
                logging.exception("🔥 Error generating market reports")

        threading.Thread(target=runner, daemon=True).start()
        return jsonify({"message": "Market gap report generation started"}), 200

    except Exception:
        logging.exception("🔥 Failed to initiate generation")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logging.info(f"🚦 Starting Market Gap Analysis API on port {port}")
    app.run(host="0.0.0.0", port=port)
