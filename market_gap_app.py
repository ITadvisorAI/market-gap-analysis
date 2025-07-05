import os
import json
import logging
import threading
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
        # try to parse JSON first (e.g. from tests)
        if request.is_json:
            data = request.get_json()
        else:
            # fall back to multipart/form-data (file uploads from Postman)
            data = {
                'session_id': request.form['session_id'],
                'email': request.form.get('email', ''),
                'folder_id': request.form['folder_id'],
                'files': []
            }
            # save each uploaded file locally and record its path
            tmp_dir = os.path.join('/tmp', data['session_id'])
            os.makedirs(tmp_dir, exist_ok=True)
            for f in request.files.getlist('files'):
                dest_path = os.path.join(tmp_dir, f.filename)
                f.save(dest_path)
                data['files'].append({
                    'file_name': f.filename,
                    'local_path': dest_path
                })

        # incoming files array and charts
        files      = data.get('files') or []
        charts     = data.get('charts') or {}
        session_id = data.get('session_id')
        email      = data.get('email', '')
        folder_id  = data.get('folder_id')

        logging.info("📦 Incoming payload:\n%s", json.dumps(data, indent=2))

        # Validate required fields
        if not session_id:
            logging.error("❌ Missing session_id")
            return jsonify({"error": "Missing session_id"}), 400
        if not folder_id:
            logging.error("❌ Missing folder_id")
            return jsonify({"error": "Missing folder_id"}), 400
        if not files:
            logging.error("❌ No files provided")
            return jsonify({"error": "No files provided"}), 400

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
        logging.info(
            f"🚀 Started Market GAP processing for {session_id} with {len(files)} files, uploading to Drive folder ID: {folder_id}"
        )

        return jsonify({"message": f"Market GAP analysis started for {session_id}"}), 202

    except Exception:
        logging.exception("🔥 Failed to initiate Market GAP analysis")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logging.info(f"🚦 Starting Market GAP API on port {port}")
    app.run(host="0.0.0.0", port=port)
