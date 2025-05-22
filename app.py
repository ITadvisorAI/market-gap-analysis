
import os
from flask import Flask, request, jsonify, send_from_directory
from process_market_gap import run_market_gap_analysis

app = Flask(__name__)
BASE_DIR = "temp_sessions"

@app.route("/", methods=["GET"])
def health_check():
    return "✅ Market GAP Analysis API is up and running", 200

@app.route("/start_market_gap", methods=["POST"])
def start_market_gap():
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id")
        email = data.get("email")
        files = []

        for i in range(1, 10):
            fname = data.get(f"file_{i}_name")
            furl = data.get(f"file_{i}_url")
            if fname and furl:
                files.append({"file_name": fname, "file_url": furl})

        if not session_id or not email or not files:
            return jsonify({"error": "Missing required fields"}), 400

        session_folder = os.path.join(BASE_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)

        run_market_gap_analysis(session_id, email, files, session_folder)
        return jsonify({"message": "Market GAP analysis started"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/files/<path:filename>", methods=["GET"])
def serve_file(filename):
    try:
        directory = os.path.join(BASE_DIR, os.path.dirname(filename))
        file_only = os.path.basename(filename)
        return send_from_directory(directory, file_only)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    os.makedirs(BASE_DIR, exist_ok=True)
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Starting Market GAP Analysis on port {port}...")
    app.run(host="0.0.0.0", port=port)
