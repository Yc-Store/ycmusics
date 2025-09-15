import os
import json
import time
import logging
import schedule
import threading
from flask import Flask, jsonify, request
from ytmusicapi import YTMusic
import yt_dlp

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Flask app
app = Flask(__name__)

# Dosya adları
LINKS_FILE = "links.json"
COOKIES_FILE = "cookies.txt"  # Buraya kendi cookie dosyanı koyacaksın

# YTMusic başlat
ytmusic = YTMusic()

# --- Yardımcı Fonksiyonlar ---

def get_song_info(video_id):
    """yt-dlp ile ham ses linki ve kapak bilgilerini alır"""
    ydl_opts = {
        "format": "bestaudio/best",
        "cookies": COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
        "quiet": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_id, download=False)
        return {
            "title": info.get("title"),
            "url": info.get("url"),
            "thumbnail": info.get("thumbnail"),
            "artist": ", ".join(a["name"] for a in info.get("artist", [])) if info.get("artist") else None,
            "album": info.get("album"),
            "release_date": info.get("release_date"),
            "duration": info.get("duration"),
            "id": video_id
        }

def fetch_artist_songs(channel_handle):
    """Bir sanatçının tüm şarkılarını alır"""
    logging.info(f"{channel_handle} için şarkılar çekiliyor...")

    try:
        # Sanatçının bilgilerini getir
        artist = ytmusic.get_artist(channel_handle)
        tracks = []

        # Sanatçının şarkılarını al
        for section in artist.get("songs", {}).get("results", []):
            video_id = section.get("videoId")
            if not video_id:
                continue
            try:
                track_info = get_song_info(video_id)
                tracks.append(track_info)
                logging.info(f"'{track_info['title']}' işlendi.")
            except Exception as e:
                logging.error(f"{video_id} alınamadı: {e}")
                continue

        return tracks

    except Exception as e:
        logging.error(f"{channel_handle} sanatçısı alınırken hata: {e}")
        return []

def update_links_json(artists):
    """Tüm sanatçılar için links.json dosyasını günceller"""
    all_tracks = []

    for artist in artists:
        artist_tracks = fetch_artist_songs(artist)
        all_tracks.extend(artist_tracks)

    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_tracks, f, ensure_ascii=False, indent=2)

    logging.info(f"Toplam {len(all_tracks)} şarkı kaydedildi -> {LINKS_FILE}")

# --- Flask Routes ---

@app.route("/update", methods=["POST"])
def update():
    data = request.get_json()
    artists = data.get("artists", [])

    if not artists:
        return jsonify({"error": "Sanatçı listesi boş"}), 400

    update_links_json(artists)
    return jsonify({"status": "ok", "artists": artists})

@app.route("/links", methods=["GET"])
def get_links():
    if not os.path.exists(LINKS_FILE):
        return jsonify([])
    with open(LINKS_FILE, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))

# --- Arka planda otomatik güncelleme ---

def scheduled_task():
    artists_file = "artists.json"
    if not os.path.exists(artists_file):
        logging.warning("artists.json bulunamadı, otomatik güncelleme atlandı.")
        return

    with open(artists_file, "r", encoding="utf-8") as f:
        artists = json.load(f)

    update_links_json(artists)

def run_scheduler():
    schedule.every(3).hours.do(scheduled_task)
    while True:
        schedule.run_pending()
        time.sleep(60)

# Thread başlat
threading.Thread(target=run_scheduler, daemon=True).start()

# Uygulama başlat
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
