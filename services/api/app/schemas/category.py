import uuid
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.schemas.common import ORMModel

CategoryName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class CategoryCreate(BaseModel):
    name: CategoryName


class CategoryRead(ORMModel):
    id: uuid.UUID
    name: str
