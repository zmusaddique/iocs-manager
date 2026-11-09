from pydantic import BaseModel, Field


class IOCCreate(BaseModel):
    value: str = Field(min_length=1, max_length=4096)
    tags: list[str] = Field(default_factory=list)


class IOCTag(BaseModel):
    id: int
    name: str


class IOCCreated(BaseModel):
    """POST /api/iocs response: echoes the raw value as submitted."""

    id: int
    value: str  # raw input, exactly as the user sent it
    type: str
    tags: list[IOCTag]
    created_at: str


class IOCRead(BaseModel):
    """GET responses: `value` is re-defanged from the canonical value."""

    id: int
    value: str  # re-defanged display value
    type: str
    tags: list[IOCTag]
    created_at: str


class IOCList(BaseModel):
    items: list[IOCRead]
    total: int


class TagList(BaseModel):
    tags: list[str]
