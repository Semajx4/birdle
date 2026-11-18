from pydantic import BaseModel

class GuessRequest(BaseModel):
    round_id: str
    guess_id: str

class Hints(BaseModel):
    order: bool
    family: bool
    genus: bool

class GuessResponse(BaseModel):
    correct: bool
    hints: Hints
    finished: bool

class BirdPublic(BaseModel):
    id: str
    common_name: str
    scientific_name: str
    genus: str
    order: str
    family: str

class FullBird(BaseModel):
    id: str
    common_name: str
    scientific_name: str
    genus: str
    order: str
    family: str
    audio_path: str | None
    image_path: str | None
    audio_media_id: int | None = None
    image_media_id: int | None = None
    enabled: bool = True

    @classmethod
    def from_bird(cls, b, audio=None, image=None):
        """Build from a models.Bird. ``audio``/``image`` override the bird's
        primary media (e.g. the media pinned for a past day)."""
        audio = audio or b.primary("audio")
        image = image or b.primary("image")
        return cls(
                id=b.id,
                common_name=b.common_name or "Unknown",
                scientific_name=f"{b.genus or ''} {b.species or ''}".strip(),
                genus=b.genus or "unknown",
                order=b.order or "unknown",
                family=b.family or "unknown",
                audio_path=audio.filename if audio else None,
                image_path=image.filename if image else None,
                audio_media_id=audio.id if audio else None,
                image_media_id=image.id if image else None,
                enabled=bool(b.enabled),
                )

    def to_public(self):
        return BirdPublic(
                id=self.id,
                common_name=self.common_name,
                scientific_name=self.scientific_name,
                genus=self.genus,
                order=self.order,
                family=self.family,
                )


class RoundState:
    def __init__(self, bird):
        self.bird = bird
        self.guesses = 0
        self.finished = False
        self.won = False
        self.reveal_ready = False

