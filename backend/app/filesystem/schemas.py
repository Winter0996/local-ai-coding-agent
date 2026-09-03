from pydantic import BaseModel


class DirEntryResponse(BaseModel):
    name: str
    path: str


class BrowseResponse(BaseModel):
    path: str | None
    parent: str | None
    entries: list[DirEntryResponse]
    roots: list[DirEntryResponse] = []