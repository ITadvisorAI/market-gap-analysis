import os
import json
import logging
import threading
import requests
from flask import Flask, request, jsonify
from market_reports_process import generate_market_reports
from drive_utils import upload_to_drive, list_files_in_folder

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_DIR = "temp_sessions"
os.makedirs(BASE_DIR, exist_ok=True)

@app.route("/", methods=["GET"])
def health():
    return "✅ Market Reports API is live", 200

@app.route("/generate_market_reports", methods=["POST"])
def generate_reports():
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id")
        email = data.get("email", "")
        folder_id = data.get("folder_id")
        next_webhook = data.get("next_action_webhook")

        logging.info("📦 Incoming payload for market reports:\n%s", json.dumps(data, indent=2))

        # Initial call: trigger GPT3 ingestion when no content/charts present
        if not data.get("content") and not data.get("charts"):
            # List files in Drive folder
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
            # Post to GPT3 ingestion endpoint (placeholder)
            try:
                resp = requests.post(next_webhook, json=payload)
                resp.raise_for_status()
                logging.info("➡️ Triggered GPT3 ingestion, status %s", resp.status_code)
            except Exception:
                logging.exception("🔥 Error triggering GPT3 ingestion")
            return jsonify({"message": "GPT3 ingestion triggered"}), 200

        # Final call: generate reports from GPT3 output
        missing = []
        if not session_id:
            missing.append("session_id")
        if not data.get("content"):
            missing.append("content")
        if not data.get("charts"):
            missing.append("charts")
        if missing:
            return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

        # Prepare local session folder
        folder_name = session_id if session_id.startswith("Temp_") else f"Temp_{session_id}"
        local_path = os.path.join(BASE_DIR, folder_name)
        os.makedirs(local_path, exist_ok=True)

        # Background processing
        def runner():
            try:
                generate_market_reports(session_id, email, folder_id, data, local_path)
            except Exception:
                logging.exception("🔥 Error generating market reports")

        threading.Thread(target=runner, daemon=True).start()
        return jsonify({"message": "Market reports generation started"}), 200

    except Exception:
        logging.exception("🔥 Failed to initiate market reports generation")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logging.info(f"🚦 Starting Market Reports API on port {port}")
    app.run(host="0.0.0.0", port=port)
