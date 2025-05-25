import os
import json
import logging
import threading
import traceback
from flask import Flask, request, jsonify
from market_gap_process import process_market_gap

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_DIR = "temp_sessions"
os.makedirs(BASE_DIR, exist_ok=True)

@app.route("/", methods=["GET"])
def health():
    return "✅ Market GAP Analysis API is live", 200

@app.route("/start_market_gap", methods=["POST"])
def start_market_gap():
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id")
        email = data.get("email")
        files = data.get("files", [])
        webhook = data.get("next_action_webhook")

        logging.warning("📦 Incoming payload:\n%s", json.dumps(data, indent=2))
        if not all([session_id, email, webhook, files]):
            logging.error("❌ Missing required fields")
            return jsonify({"error": "Missing required fields"}), 400

        folder = session_id if session_id.startswith("Temp_") else f"Temp_{session_id}"
        folder_path = os.path.join(BASE_DIR, folder)
        os.makedirs(folder_path, exist_ok=True)

        def runner():
            try:
                process_market_gap(session_id, email, files, webhook, folder_path)
            except Exception as e:
                logging.exception("🔥 Error inside market GAP processing thread")

        threading.Thread(target=runner, daemon=True).start()
        logging.info(f"🚀 Started Market GAP processing for {session_id}")

        return jsonify({"message": "Market GAP analysis started"}), 200
    except Exception as e:
        logging.exception("🔥 Failed to initiate market GAP analysis")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logging.info(f"🚦 Starting Market GAP API on port {port}")
    app.run(host="0.0.0.0", port=port)
