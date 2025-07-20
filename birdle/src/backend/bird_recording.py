class BirdRecording:
    def __init__(self, data: dict):
        self.id: str = data.get("id")
        self.genus: str = data.get("gen")
        self.species: str = data.get("sp")
        self.subspecies: str = data.get("ssp")
        self.group: str = data.get("grp")
        self.common_name: str = data.get("en")
        self.country: str = data.get("cnt")
        self.location: str = data.get("loc")
        self.latitude: Optional[float] = float(data["lat"]) if data.get("lat") else None
        self.longitude: Optional[float] = float(data["lon"]) if data.get("lon") else None
        self.type: str = data.get("type")
        self.sex: str = data.get("sex")
       
        self.method: str = data.get("method")
        self.url: str = "https:" + data.get("url", "")
        self.audio_file: str = "https:" + data.get("file", "")
        self.file_name: str = data.get("file-name")
        self.sono: Dict[str, str] = {
            k: "https:" + v for k, v in data.get("sono", {}).items()
        }
        self.osci: Dict[str, str] = {
            k: "https:" + v for k, v in data.get("osci", {}).items()
        }
        self.quality: str = data.get("q")
        self.length: str = data.get("length")
        self.time: str = data.get("time")
        self.date: str = data.get("date")
        self.also: List[str] = data.get("also", [])
        self.remark: str = data.get("rmk")
        self.animal_seen: bool = data.get("animal-seen") == "yes"
        self.playback_used: bool = data.get("playback-used") == "yes"
        self.sample_rate: Optional[int] = int(data["smp"]) if data.get("smp") else None
        self.device: str = data.get("dvc")
        self.microphone: str = data.get("mic")
        self.auto: str = data.get("auto")

    def __str__(self):
        return f"{self.common_name} ({self.genus} {self.species}) recorded in {self.location}"

    def preview(self):
        return {
            "name": self.common_name,
            "location": self.location,
            "audio": self.audio_file,
            "spectrogram": self.sono.get("med", "")
        }