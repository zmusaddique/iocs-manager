from pydantic import BaseModel, Field


class IOCCreate(BaseModel):
    value: str = Field(min_length=1, max_length=4096)
    tags: list[str] = Field(default_factory=list)


class IOCTag(BaseModel):
    id: int
    name: str


class IOCRead(BaseModel):
    id: int
    value: str
    type: str
    tags: list[IOCTag]
    created_at: str


class IOCList(BaseModel):
    items: list[IOCRead]
    total: int
