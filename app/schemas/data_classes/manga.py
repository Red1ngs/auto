from dataclasses import dataclass
from datetime import datetime

@dataclass
class MangaTitle:
    title: str
    genres: str
    rating: str
    status: str
    data_id: str
    translit: str
    poster: str
    last_updated: str = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now().isoformat()


@dataclass
class Volume:
    manga_translit: str
    volume_number: str
    volume_title: str = ""
    last_updated: str = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now().isoformat()


@dataclass
class Chapter:
    manga_translit: str
    volume_number: str
    chapter_number: str
    chapter_title: str
    data_id: str
    chapter_url: str = ""
    last_updated: str = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now().isoformat()