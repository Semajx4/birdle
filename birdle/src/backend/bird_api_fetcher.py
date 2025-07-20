import requests
from bird_recording import BirdRecording
import os

from models import save_to_db
from utils import download_audio, is_mp3, is_under_one_minute

# Load environment variables from .env file

# Get the API key from the environment
API_KEY = os.getenv("XENO_API_KEY")
def get_recordings(queries, page=1):
    base_url = "https://xeno-canto.org/api/3/recordings"
    params = {"key": API_KEY, "query": "", "per_page" : "500", "page": page}
    for query in queries:
        params["query"] += query
    url = base_url
    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        return data.get("recordings", [])
    else:
        raise Exception(f"API call failed: {response.status_code} - {response.text}")

# Example queries
queries = [
    "cnt: \"new zealand\"",
    # "grp: birds",
    "q:A",
]




birds = []
seen = set()  # Track unique birds using genus + species

try:
    for i in range(1, 10):
        print(i)
        recordings = get_recordings(queries, i)
        for recording in recordings:
            if is_under_one_minute(recording["length"]) and is_mp3(recording):
                try:
                    identifier = (recording["gen"], recording["sp"])

                    if identifier not in seen:
                        seen.add(identifier)
                        audio_path = download_audio(recording)
                        save_to_db(recording, audio_path)
                except Exception as e:
                    print(f"Error processing {recording['id']}: {e}")
except Exception as e:
    print(f"Error: {e}")
