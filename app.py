from flask import Flask, request, jsonify
import os
import threading
import logging
from process_market_gap import handle_market_gap

app = Flask(__name__)
BASE_DIR = "temp_sessions"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

@app.route("/", methods=["GET"])
def health_check():
    return "✅ Market GAP Analysis API is up", 200

@app.route("/start_market_gap", methods=["POST"])
def start_market_gap():
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id")
        email = data.get("email")
        files = [  # capture all files
            {"name": data.get(f"file_{i}_name"), "url": data.get(f"file_{i}_url")}
            for i in range(1, 10)
            if data.get(f"file_{i}_name") and data.get(f"file_{i}_url")
        ]

        if not session_id or not email or not files:
            logging.error("❌ Missing required fields")
            return jsonify({"message": "Missing required fields"}), 400

        folder = os.path.join(BASE_DIR, session_id)
        os.makedirs(folder, exist_ok=True)

        logging.info(f"📦 Starting market GAP analysis for: {session_id} with {len(files)} file(s)")

        thread = threading.Thread(
            target=handle_market_gap,
            args=(session_id, email, files, folder)
        )
        thread.daemon = True
        thread.start()

        return jsonify({"message": "Market GAP Analysis started"}), 200

    except Exception as e:
        logging.exception("🔥 Exception in /start_market_gap")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    os.makedirs(BASE_DIR, exist_ok=True)
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
