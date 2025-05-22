from flask import Flask, request, jsonify, send_from_directory
import os
import threading
import logging
from process_market_gap import run_market_gap_analysis

# === Flask App Setup ===
app = Flask(__name__)
BASE_DIR = "temp_sessions"

# === Logging ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# === Health Check ===
@app.route("/", methods=["GET"])
def health_check():
    return "✅ Market GAP Analysis API is live", 200

# === POST /start_market_gap ===
@app.route("/start_market_gap", methods=["POST"])
def start_market_gap():
    try:
        data = request.get_json(force=True)
        logging.info("📥 Received POST /start_market_gap")
        logging.debug(f"Payload: {data}")

        session_id = data.get("session_id")
        email = data.get("email")
        files = []

        # Extract uploaded files
        for i in range(1, 10):
            name_key = f"file_{i}_name"
            url_key = f"file_{i}_url"
            if name_key in data and url_key in data:
                files.append({
                    "file_name": data[name_key],
                    "file_url": data[url_key]
                })

        if not session_id or not email or not files:
            logging.error("❌ Missing required fields: session_id, email, or files")
            return jsonify({"error": "Missing required fields"}), 400

        # Create session folder
        folder_name = session_id if session_id.startswith("Temp_") else f"Temp_{session_id}"
        session_folder = os.path.join(BASE_DIR, folder_name)
        os.makedirs(session_folder, exist_ok=True)
        logging.info(f"📁 Session folder ready: {session_folder}")

        # Start GAP analysis in background
        thread = threading.Thread(
            target=run_market_gap_analysis,
            args=(session_id, email, files, session_folder)
        )
        thread.daemon = True
        thread.start()
        logging.info("🚀 Market GAP analysis thread started")

        return jsonify({"message": "Market GAP analysis started"}), 200

    except Exception as e:
        logging.exception("🔥 Exception in /start_market_gap")
        return jsonify({"error": str(e)}), 500

# === Serve Output Files ===
@app.route("/files/<path:filename>", methods=["GET"])
def serve_file(filename):
    try:
        directory = os.path.join(BASE_DIR, os.path.dirname(filename))
        file_only = os.path.basename(filename)
        logging.info(f"📤 Serving file: {filename}")
        return send_from_directory(directory, file_only)
    except Exception as e:
        logging.exception("❌ File serving error")
        return jsonify({"error": str(e)}), 500

# === Main Entry Point ===
if __name__ == "__main__":
    os.makedirs(BASE_DIR, exist_ok=True)
    port = int(os.environ.get("PORT", 5000))
    logging.info(f"🚦 Starting Market GAP API server on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
