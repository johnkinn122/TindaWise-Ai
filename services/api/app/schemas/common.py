from pydantic import BaseModel, ConfigDict


class Page[T](BaseModel):
    """A page of results. `total` is the count across all pages for the same filters."""

    items: list[T]
    total: int
    limit: int
    offset: int


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
