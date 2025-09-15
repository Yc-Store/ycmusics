import json
import os
from flask import Flask, jsonify, request, send_from_directory, redirect
from apscheduler.schedulers.background import BackgroundScheduler
import logging

# Log ayarları
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# JSON dosya yolları
LINKS_FILE = "links.json"

# Scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Arka plan işi örneği (isteğe bağlı)
def scheduled_task():
    logging.info("Scheduled task running...")

scheduler.add_job(scheduled_task, 'interval', minutes=30)  # Her 30 dakikada bir çalışır

# Ana sayfa route'u (index.html sunar)
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

# JSON verilerini sunan route
@app.route("/links.json")
def get_links():
    if os.path.exists(LINKS_FILE):
        with open(LINKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    else:
        return jsonify([])

# Admin veya güncelleme route (isteğe bağlı)
@app.route("/update", methods=["POST"])
def update_links():
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Boş veri"}), 400

    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    return jsonify({"status": "success", "message": "Links güncellendi"}), 200

# Favicon isteğini engelleme (opsiyonel)
@app.route("/favicon.ico")
def favicon():
    return "", 204

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
