import os
import json
import logging
import threading
import re
from flask import Flask, request, jsonify
from market_gap_process import process_market_gap

app = Flask(__name__)

@app.route("/healthz", methods=["GET"])
def health_check():
    return "OK", 200

@app.route("/", methods=["GET"])
def health():
    return "✅ Market GAP Analysis API is live", 200

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Directory for staging
BASE_DIR = "temp_sessions"
os.makedirs(BASE_DIR, exist_ok=True)

@app.route("/start_market_gap", methods=["POST"])
def start_market_gap():
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id")
        email = data.get("email", "")
        folder_id = data.get("folder_id")  # Required Drive folder ID where GPT1/GPT2 uploaded files

        logging.info("📦 Incoming payload:\n%s", json.dumps(data, indent=2))

        # Validate required fields
        if not session_id:
            logging.error("❌ Missing session_id")
            return jsonify({"error": "Missing session_id"}), 400
        if not folder_id:
            logging.error("❌ Missing folder_id")
            return jsonify({"error": "Missing folder_id"}), 400

        # Collect file drive URLs
        files = []
        pattern = re.compile(r"^file_(\d+)_drive_url$")
        for key, url in data.items():
            match = pattern.match(key)
            if match and url:
                idx = match.group(1)
                file_name = f"file_{idx}"
                files.append({
                    "file_name": file_name,
                    "drive_url": url
                })

        if not files:
            logging.error("❌ No file URLs provided")
            return jsonify({"error": "No files provided"}), 400

        # Sort files by index
        files.sort(key=lambda f: int(f["file_name"].split("_")[1]))

        # Prepare local session folder for staging
        folder_name = session_id if session_id.startswith("Temp_") else f"Temp_{session_id}"
        folder_path = os.path.join(BASE_DIR, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        # Launch background processing thread
        def runner():
            try:
                process_market_gap(session_id, email, files, folder_path, folder_id)
            except Exception:
                logging.exception("🔥 Error in Market GAP processing thread")

        threading.Thread(target=runner, daemon=True).start()
        logging.info(f"🚀 Started Market GAP processing for {session_id} with {len(files)} files, uploading to Drive folder ID: {folder_id}")

        return jsonify({"message": f"Market GAP analysis started for {session_id}"}), 202

    except Exception:
        logging.exception("🔥 Failed to initiate Market GAP analysis")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logging.info(f"🚦 Starting Market GAP API on port {port}")
    app.run(host="0.0.0.0", port=port)
