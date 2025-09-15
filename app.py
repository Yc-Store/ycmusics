import json
import os
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from ytmusicapi import YTMusic
from yt_dlp import YoutubeDL
import threading
from apscheduler.schedulers.background import BackgroundScheduler
import logging

# Logging ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
ytmusic = YTMusic()

ARTISTS_FILE = "artists.txt"
JSON_FILE = "links.json"

# Başlangıçta dosyaların var olduğundan emin ol
if not os.path.exists(ARTISTS_FILE):
    with open(ARTISTS_FILE, "w") as f:
        pass
if not os.path.exists(JSON_FILE):
    with open(JSON_FILE, "w") as f:
        json.dump([], f)

def get_artist_id(artist_name):
    """Verilen sanatçı adından tarayıcı ID'sini alır."""
    try:
        search_results = ytmusic.search(artist_name, filter="artists")
        if search_results:
            return search_results[0]['browseId']
    except Exception as e:
        logging.error(f"Sanatçı ID'si alınırken hata: {artist_name} - {e}")
    return None

def get_direct_stream_url(video_id):
    """Video ID'sinden doğrudan ses linkini ve metadata'yı alır."""
    if not video_id:
        return None, None
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'force_generic_extractor': True,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            # 'formats' yerine 'url' anahtarını kontrol et
            if 'url' in info:
                # Meta verileri de alalım
                metadata = {
                    'title': info.get('title'),
                    'artist': info.get('artist') or info.get('uploader'),
                    'thumbnail': info.get('thumbnail')
                }
                return info['url'], metadata
    except Exception as e:
        logging.error(f"Stream URL alınırken hata (Video ID: {video_id}): {e}")
    return None, None


def fetch_all_songs_for_artist(artist_id):
    """Bir sanatçının tüm şarkılarını (albümler, single'lar) toplar."""
    songs = []
    try:
        artist_details = ytmusic.get_artist(artist_id)
        
        # Albümleri ve single'ları al
        if 'albums' in artist_details and artist_details['albums']['results']:
            for album in artist_details['albums']['results']:
                logging.info(f"'{artist_details['name']}' sanatçısının '{album['title']}' albümü işleniyor...")
                album_details = ytmusic.get_album(album['browseId'])
                for track in album_details['tracks']:
                    if track.get('videoId'):
                        songs.append(track)
        
        # Single'ları al
        if 'singles' in artist_details and artist_details['singles']['results']:
            for single in artist_details['singles']['results']:
                 logging.info(f"'{artist_details['name']}' sanatçısının '{single['title']}' single'ı işleniyor...")
                 # Single'lar bazen albüm gibi gelir
                 if single.get('browseId'):
                    single_details = ytmusic.get_album(single['browseId'])
                    for track in single_details['tracks']:
                        if track.get('videoId'):
                            songs.append(track)

    except Exception as e:
        logging.error(f"Sanatçı şarkıları alınırken hata (Artist ID: {artist_id}): {e}")
    
    # Mükerrer kayıtları videoId'ye göre temizle
    unique_songs = {song['videoId']: song for song in songs if song.get('videoId')}.values()
    return list(unique_songs)

def update_links_json():
    """artists.txt dosyasını okur ve links.json dosyasını günceller."""
    with app.app_context():
        logging.info("links.json güncelleme işlemi başladı.")
        
        with open(ARTISTS_FILE, "r") as f:
            artist_names = [line.strip() for line in f if line.strip()]

        all_tracks_data = []
        for artist_name in artist_names:
            logging.info(f"Sanatçı işleniyor: {artist_name}")
            artist_id = get_artist_id(artist_name)
            if not artist_id:
                logging.warning(f"Sanatçı bulunamadı veya ID alınamadı: {artist_name}")
                continue
            
            songs = fetch_all_songs_for_artist(artist_id)
            logging.info(f"{artist_name} için toplam {len(songs)} adet özgün şarkı bulundu.")

            for i, song in enumerate(songs):
                video_id = song.get('videoId')
                if not video_id:
                    continue

                logging.info(f"[{i+1}/{len(songs)}] Şarkı işleniyor: {song.get('title')}")
                audio_url, metadata = get_direct_stream_url(video_id)
                
                if audio_url and metadata:
                    track_data = {
                        "title": metadata.get('title', song.get('title')),
                        "artist": ", ".join([artist['name'] for artist in song['artists']]) if song.get('artists') else metadata.get('artist'),
                        "album": song['album']['name'] if song.get('album') else "Single",
                        "year": song.get('year'),
                        "coverArtUrl": metadata.get('thumbnail', f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"),
                        "audioUrl": audio_url
                    }
                    all_tracks_data.append(track_data)
                else:
                    logging.warning(f"Doğrudan link alınamadı: {song.get('title')}")

        # JSON dosyasına yaz
        with open(JSON_FILE, "w", encoding='utf8') as f:
            json.dump(all_tracks_data, f, indent=4, ensure_ascii=False)
        
        logging.info(f"links.json başarıyla güncellendi. Toplam {len(all_tracks_data)} şarkı eklendi.")

# Admin Paneli Arayüzü
ADMIN_PANEL_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Müzik Çalar Admin Paneli</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #121212; color: #fff; margin: 0; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .container { background-color: #1e1e1e; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); width: 90%; max-width: 600px; }
        h1 { text-align: center; color: #1DB954; }
        form { display: flex; flex-direction: column; gap: 1rem; }
        input[type="text"] { padding: 0.8rem; border-radius: 8px; border: 1px solid #333; background-color: #282828; color: #fff; font-size: 1rem; }
        button { padding: 0.8rem 1.5rem; border: none; border-radius: 50px; background-color: #1DB954; color: #fff; font-weight: bold; cursor: pointer; transition: background-color 0.2s; font-size: 1rem; }
        button:hover { background-color: #1ED760; }
        #message { margin-top: 1rem; text-align: center; font-weight: bold; }
        .artist-list { margin-top: 2rem; }
        h2 { border-bottom: 1px solid #333; padding-bottom: 0.5rem; }
        ul { list-style: none; padding: 0; }
        li { background-color: #282828; padding: 0.7rem; border-radius: 8px; margin-bottom: 0.5rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Müzik Çalar Admin Paneli</h1>
        <form id="artistForm">
            <input type="text" id="artistName" name="artist_name" placeholder="Sanatçı Kullanıcı Adı (ör: @blok3real)" required>
            <button type="submit">Sanatçıyı Ekle</button>
        </form>
        <div id="message"></div>
        <div class="artist-list">
            <h2>Takip Edilen Sanatçılar</h2>
            <ul id="artists">
                <!-- Sanatçılar buraya eklenecek -->
            </ul>
        </div>
        <form id="updateForm" style="margin-top: 1.5rem;">
             <button type="submit">links.json Dosyasını Şimdi Güncelle</button>
        </form>
         <div id="updateMessage"></div>
    </div>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            loadArtists();

            document.getElementById('artistForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const artistName = document.getElementById('artistName').value;
                const messageDiv = document.getElementById('message');
                messageDiv.textContent = 'Ekleniyor...';

                const response = await fetch('/add_artist', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ artist_name: artistName })
                });
                const result = await response.json();
                messageDiv.textContent = result.message;
                document.getElementById('artistName').value = '';
                loadArtists();
            });

             document.getElementById('updateForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const updateMessageDiv = document.getElementById('updateMessage');
                updateMessageDiv.textContent = 'Güncelleme işlemi başlatıldı. Bu işlem uzun sürebilir, lütfen bekleyin...';
                
                const response = await fetch('/trigger_update', { method: 'POST' });
                const result = await response.json();
                updateMessageDiv.textContent = result.message;
             });
        });

        async function loadArtists() {
            const response = await fetch('/get_artists');
            const artists = await response.json();
            const ul = document.getElementById('artists');
            ul.innerHTML = '';
            artists.forEach(artist => {
                const li = document.createElement('li');
                li.textContent = artist;
                ul.appendChild(li);
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def admin_panel():
    return render_template_string(ADMIN_PANEL_HTML)

@app.route('/add_artist', methods=['POST'])
def add_artist():
    data = request.json
    artist_name = data.get('artist_name')
    if not artist_name:
        return jsonify({"message": "Sanatçı adı boş olamaz!"}), 400
    
    with open(ARTISTS_FILE, "a+") as f:
        f.seek(0)
        if artist_name in [line.strip() for line in f]:
            return jsonify({"message": f"'{artist_name}' zaten listede."})
        f.write(f"{artist_name}\n")
    
    return jsonify({"message": f"'{artist_name}' başarıyla eklendi."})

@app.route('/get_artists')
def get_artists():
    if os.path.exists(ARTISTS_FILE):
        with open(ARTISTS_FILE, "r") as f:
            artists = [line.strip() for line in f if line.strip()]
        return jsonify(artists)
    return jsonify([])

@app.route('/trigger_update', methods=['POST'])
def trigger_update():
    # Güncellemeyi arka planda başlat
    thread = threading.Thread(target=update_links_json)
    thread.start()
    return jsonify({"message": "Güncelleme başlatıldı. İşlem tamamlandığında links.json dosyası yenilenecektir."})

@app.route('/links.json')
def serve_json():
    # CORS başlığını ekleyerek GitHub Pages'dan erişime izin ver
    response = send_from_directory('.', JSON_FILE)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

# Zamanlanmış görevi ayarla
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(update_links_json, 'interval', hours=3)
scheduler.start()

if __name__ == '__main__':
    # İlk çalıştırmada bir güncelleme yap
    logging.info("Sunucu başlatılıyor, ilk veri güncellemesi yapılıyor...")
    initial_thread = threading.Thread(target=update_links_json)
    initial_thread.start()
    # Uygulamayı Render'ın beklediği port üzerinden çalıştır
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
