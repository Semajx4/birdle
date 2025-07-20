import os
import requests

from bird_recording import BirdRecording

def download_audio(recording, dest_dir="../frontend/public/audio"):
    url = recording["file"]
    file_name = recording["file-name"].replace(" ", "_").replace("/", "_")
    os.makedirs(dest_dir, exist_ok=True)
    file_path = os.path.join("audio/", file_name)

    if not os.path.exists(file_path):
        print(f"Downloading {file_name}...")
        r = requests.get(url)
        if r.status_code == 200:
            with open(file_path, "wb") as f:
                f.write(r.content)
        else:
            raise Exception(f"Download failed for {url}")
    else:
        print(f"Already downloaded: {file_name}")

    return file_path


def is_under_one_minute(length_str):
    try:
        minutes, seconds = map(int, length_str.split(":"))
        return (minutes * 60 + seconds) < 60
    except ValueError:
        return False  # Skip if malformed


def is_mp3(recording: BirdRecording) -> bool:
    return recording["file-name"].lower().endswith(".mp3")