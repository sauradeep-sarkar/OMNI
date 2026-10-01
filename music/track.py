from dataclasses import dataclass

@dataclass
class Track:
    title: str
    url: str
    source_url: str
    duration: int
    requester: int
    thumbnail: str
    artist: str = "Unknown"
    video_id: str = ""
