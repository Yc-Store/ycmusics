from flask import Flask, jsonify, send_from_directory, request, redirect
from ytmusicapi import YTMusic
import json
import os
import threading
from apscheduler.schedulers.background import BackgroundScheduler
import logging

app = Flask(__name__)

# Loglama
logging.basicConfig(level=logging.INFO)

# JSON dosyaları
LINKS_FILE = "links.json"
ARTISTS_FILE = "artists.json"

# Scheduler başlat
scheduler = BackgroundScheduler()
scheduler.start()

# Basit görev örneği (isteğe bağlı)
def scheduled_task():
    logging.info("Scheduled task çalıştı.")

scheduler.add_job(scheduled_task, 'interval', minutes=10, id='scheduled_task')

# Ana sayfa route'u
@app.route("/")
def index():
    # index.html dosyasını sun
    return send_from_directory(".", "index.html")

# Links JSON'u sun
@app.route("/links.json")
def links():
    if os.path.exists(LINKS_FILE):
        with open(LINKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    else:
        return jsonify([])

# Admin panelden link güncelleme (opsiyonel)
@app.route("/update", methods=["POST"])
def update_links():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Boş veri"}), 400
    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return jsonify({"status": "success"})

# Eğer YTMusic API kullanacaksan buraya ekle
def update_from_ytmusic():
    if not os.path.exists(ARTISTS_FILE):
        return
    with open(ARTISTS_FILE, "r", encoding="utf-8") as f:
        artists = json.load(f)
    # YTMusic login ve veri çekme işlemleri
    # cookies.txt dosyasıyla giriş yapabilirsin
    ytmusic = YTMusic("cookies.txt")
    # Örnek: sanatçıdan şarkı listesi al
    # data = ytmusic.get_artist_songs(artist_id)
    # Links.json güncelle

# YTMusic scheduler
scheduler.add_job(update_from_ytmusic, 'interval', minutes=60, id='ytmusic_update')

# Statik dosya (ör. css, js) sunmak için
@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(".", filename)

# Render port ayarı
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
