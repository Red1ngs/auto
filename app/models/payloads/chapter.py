from typing import TypedDict

class ReadChapterPayload (TypedDict):
    manga_id: int
    chapter_id: int

class TakeCandyPayload(TypedDict):
    token: str
    
class LoadChaptersPayload(TypedDict):
    manga_id: int
