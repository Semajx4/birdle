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
    audio_path: str
    image_path: str | None

    @classmethod
    def from_orm_record(cls, r):
        return cls(
                id=r.id,
                common_name=r.common_name or "Unknown",
                scientific_name=f"{r.genus or ''} {r.species or ''}".strip(),
                genus=r.genus or "unknown",
                order=r.order or "unknown",
                family=r.family or "unknown",
                audio_path=r.audio_path,
                image_path=r.image_path,
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

