from flask import Flask, request, render_template, jsonify
import subprocess
import json
import os
import sys
from ytmusicapi import YTMusic

app = Flask(__name__)
ytmusic = YTMusic()

# The links.json file will be created by the app if it doesn't exist
LINKS_FILE = "links.json"

# Helper function to get direct audio URL using yt-dlp
def get_audio_url(video_id):
    """
    Fetches the direct audio URL for a given YouTube video ID using yt-dlp.
    """
    try:
        # Command to get the best audio-only stream's URL
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--print-json",
            "--skip-download",
            "--extract-audio",
            "--audio-format", "m4a",
            "--format", "bestaudio/best",
            "--no-playlist",
            f"https://www.youtube.com/watch?v={video_id}"
        ]
        
        # Run the command and capture the JSON output
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        
        # Find the URL of the best audio stream. yt-dlp might provide multiple formats.
        # We prefer a direct URL from the 'url' field.
        if 'url' in info:
            return info['url']
        
        return None
        
    except subprocess.CalledProcessError as e:
        print(f"Error fetching audio URL for {video_id}: {e.stderr}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print(f"Failed to parse yt-dlp JSON for {video_id}", file=sys.stderr)
        return None

@app.route('/')
def home():
    """
    Serves the admin panel HTML page.
    """
    return render_template('index.html')

@app.route('/process_artists', methods=['POST'])
def process_artists():
    """
    Handles the artist list submission from the admin panel.
    Fetches songs and their metadata, then saves them to links.json.
    """
    artists_input = request.form.get('artists', '')
    if not artists_input:
        return jsonify({"success": False, "message": "Lütfen en az bir sanatçı adı girin."})

    artists = [name.strip() for name in artists_input.split('\n') if name.strip()]
    
    data = {}
    try:
        # Load existing data if the file already exists
        if os.path.exists(LINKS_FILE):
            with open(LINKS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        for artist_name in artists:
            print(f"Processing artist: {artist_name}")
            
            # Search for the artist
            search_results = ytmusic.search(artist_name, "artists")
            if not search_results:
                print(f"No results found for artist: {artist_name}")
                continue
            
            artist_id = search_results[0]['browseId']
            
            # Get the full artist page, which includes all songs
            artist_data = ytmusic.get_artist(artist_id)
            
            # Find the songs section
            songs = []
            if 'songs' in artist_data and 'results' in artist_data['songs']:
                songs = artist_data['songs']['results']
            
            if not songs:
                print(f"No songs found for artist: {artist_name}")
                continue
            
            # Loop through songs and gather data
            artist_songs = []
            for song in songs:
                song_data = {
                    "title": song.get('title'),
                    "artist": artist_name,
                    "album": song.get('album', {}).get('name') if song.get('album') else None,
                    "cover_art_url": song.get('thumbnails', [{}])[-1].get('url'),
                    "video_id": song.get('videoId'),
                    "audio_url": None, # This will be filled by the helper function
                }
                
                if song_data["video_id"]:
                    print(f"  Fetching audio link for: {song_data['title']}")
                    audio_url = get_audio_url(song_data["video_id"])
                    song_data["audio_url"] = audio_url

                artist_songs.append(song_data)
                
            data[artist_name] = artist_songs
            print(f"Finished processing {artist_name}. {len(artist_songs)} songs found.")
            
        # Write the updated data to the JSON file
        with open(LINKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        return jsonify({"success": True, "message": "İşlem tamamlandı! Şarkılar links.json dosyasına kaydedildi."})

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        return jsonify({"success": False, "message": f"Bir hata oluştu: {str(e)}"})

if __name__ == '__main__':
    # Using '0.0.0.0' makes the app accessible from outside the container,
    # which is necessary for services like Render.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
